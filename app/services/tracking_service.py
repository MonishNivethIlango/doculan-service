import json
from typing import Dict, List, Any, Tuple, Optional
from fastapi import HTTPException

from auth_app.app.model.UserModel import FolderAssignment
from config import config
from database.db_config import s3_client
from repositories.s3_repo import DOCUMENT_BASE_PATH, load_tracking_metadata, TRACKING_BASE_PATH, get_role_document_ids
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.logger import logger


class TrackingService:
    def __init__(self, email: str):
        self.email = email

    def get_tracking_by_id(self, document_id: str, tracking_id: str) -> Dict[str, Any]:
        try:
            return load_tracking_metadata(self.email, document_id, tracking_id)
        except HTTPException as e:
            raise e

    def get_tracking_fields(self, document_id: str, tracking_id: str) -> Tuple[
        List[Dict[str, Any]], List[Dict[str, Any]], int, Dict[str, Any], str]:

        tracking = self.get_tracking_by_id(document_id, tracking_id)
        return (
            tracking.get("email_response", []),
            tracking.get("parties", []),
            tracking.get("remainder", 1),
            tracking,
            tracking.get("validityDate", ""),

        )

    def get_all_tracking_ids_status(
            self, role: str
    ) -> Dict[str, Any]:
        """
        Collect all tracking JSONs, group by document, and summarize by status.
        """
        import json
        from concurrent.futures import ThreadPoolExecutor, as_completed

        result: Dict[str, Dict[str, Dict[str, Any]]] = {}
        status_totals: Dict[str, int] = {
            "in_progress": 0,
            "completed": 0,
            "cancelled": 0,
            "expired": 0,
            "declined": 0,
            "unknown": 0,
        }

        logger.info(f"[TRACKING] Collecting tracking status for role={role}, email={self.email}")

        # 🔑 Step 1: Decide prefixes
        if role == "admin":
            # Admin: scan all documents
            prefixes = [f"{self.email}/{TRACKING_BASE_PATH}/"]
            allowed_document_ids = None  # no restriction
            logger.debug(f"[TRACKING] Admin role → scanning all trackings under {prefixes}")
        else:
            # Non-admin: get allowed document IDs
            ids_data = get_role_document_ids(role=role, email=self.email)
            allowed_document_ids = ids_data.get("documentIds", [])
            if not allowed_document_ids:
                logger.warning(f"[TRACKING] No assigned documents for role={role}, returning empty result")
                return {
                    "total_trackings": 0,
                    "status_counts": status_totals,
                    "documents": {},
                }
            prefixes = [
                f"{self.email}/{TRACKING_BASE_PATH}/{doc_id}/"
                for doc_id in allowed_document_ids
            ]
            logger.debug(f"[TRACKING] Non-admin role → scanning {len(prefixes)} document tracking paths")

        # 🔑 Step 2: Collect all keys under allowed prefixes
        all_keys = []
        for prefix in prefixes:
            logger.debug(f"[TRACKING] Listing objects under prefix={prefix}")
            response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
            for obj in response.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".json"):
                    all_keys.append(key)

        if not all_keys:
            logger.info("[TRACKING] No tracking files found, returning empty result")
            return {
                "total_trackings": 0,
                "status_counts": status_totals,
                "documents": {},
            }

        logger.info(f"[TRACKING] Found {len(all_keys)} tracking JSON files")

        # 🔑 Step 3: Process function
        def process_tracking_file(key: str):
            try:
                obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
                content = obj["Body"].read().decode("utf-8")
                tracking_data = json.loads(content)

                document_id = tracking_data.get("document_id") or key.split("/")[-2]
                tracking_id = tracking_data.get("tracking_id") or key.split("/")[-1].replace(".json", "")
                status = tracking_data.get("tracking_status", {}).get("status", "unknown")
                parties = tracking_data.get("parties", [])
                last_updated = tracking_data.get("tracking_status", {}).get("dateTime")

                if status not in status_totals:
                    logger.warning(f"[TRACKING] Unknown status '{status}' in {key}, forcing to 'unknown'")
                    status = "unknown"

                # Non-admin filter safeguard
                if allowed_document_ids is not None and document_id not in allowed_document_ids:
                    return None

                return (document_id, tracking_id, status, parties, last_updated)
            except Exception as e:
                logger.error(f"❌ Failed processing {key}: {e}")
                return None

        # 🔑 Step 4: Process in parallel
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_tracking_file, key) for key in all_keys]
            for future in as_completed(futures):
                result_data = future.result()
                if not result_data:
                    continue

                document_id, tracking_id, status, parties, last_updated = result_data

                if document_id not in result:
                    result[document_id] = {s: {} for s in status_totals.keys()}

                result[document_id][status][tracking_id] = {
                    "parties": parties,
                    "last_updated": last_updated,
                }
                status_totals[status] += 1

        # 🔑 Step 5: Filter out empty statuses
        filtered_result = {
            doc_id: {s: t for s, t in statuses.items() if t}
            for doc_id, statuses in result.items()
        }

        logger.info(
            f"[TRACKING] Completed aggregation → total={sum(status_totals.values())}, "
            f"status_counts={status_totals}, documents={len(filtered_result)}"
        )

        return {
            "total_trackings": sum(status_totals.values()),
            "status_counts": status_totals,
            "documents": filtered_result,
        }
