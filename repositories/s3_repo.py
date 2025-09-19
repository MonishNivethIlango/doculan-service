from typing import Dict, List, Any, Optional
from pathlib import PurePosixPath
from dateutil.parser import parse as parse_datetime
from app.schemas.tracking_schemas import DocumentRequest, PartyUpdateItem
from app.services.security_service import AESCipher, EncryptionService
from auth_app.app.model.UserModel import FolderAssignment
from config import config
from database.db_config import s3_client, S3_user
import pymupdf as fitz
import requests
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import HTTPException
import base64
from utils.logger import logger
from typing import Dict, Any
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from collections import defaultdict
import logging


TRACKING_BASE_PATH = "metadata/tracking"
DOCUMENT_BASE_PATH = "metadata/document"



def generate_summary_from_trackings(trackings: dict) -> dict:
    status_counts = {}
    for tracking in trackings.values():
        status = tracking.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "total_documents": 1,
        "total_trackings": len(trackings),
        "status_counts": status_counts
    }


def load_tracking_metadata(email: str, document_id: str, tracking_id: str) -> dict:
    key = f"{email}/{TRACKING_BASE_PATH}/{document_id}/{tracking_id}.json"
    try:
        obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
        data = json.loads(obj["Body"].read().decode("utf-8"))
        return data
    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"Tracking metadata not found for key: {key}")
        raise HTTPException(status_code=404, detail="Tracking metadata not found")
    except Exception as e:
        logger.error(f"Error loading tracking metadata: {e}")
        raise HTTPException(status_code=500, detail="Error loading tracking metadata")


def save_tracking_metadata(email: str, document_id: str, tracking_id: str, tracking_data: dict):
    tracking_key = f"{email}/{TRACKING_BASE_PATH}/{document_id}/{tracking_id}.json"
    document_key = f"{email}/{DOCUMENT_BASE_PATH}/{document_id}.json"
    now = datetime.now(timezone.utc).isoformat()
    current_status = tracking_data.get("tracking_status", {}).get("status", "unknown")

    try:
        # Save tracking metadata
        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=tracking_key,
            Body=json.dumps(tracking_data),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID
        )
        logger.info(f"[save_tracking_metadata] Saved tracking file: {tracking_key}")

        # Load or initialize document-level metadata
        try:
            doc_obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=document_key)
            doc_data = json.loads(doc_obj["Body"].read().decode("utf-8"))
        except s3_client.exceptions.NoSuchKey:
            logger.warning(f"[save_tracking_metadata] No existing metadata found, initializing")
            doc_data = {
                "total_trackings": 0,
                "status_counts": {},
                "documents": {}
            }
        except Exception as e:
            logger.error(f"Failed to load document metadata: {e}")
            raise HTTPException(status_code=500, detail="Failed to read document metadata")

        # Ensure proper structure
        doc_data.setdefault("documents", {})
        doc_data["documents"].setdefault(document_id, {})

        # Remove tracking_id from old statuses
        for status in list(doc_data["documents"][document_id].keys()):
            tracking_ids = doc_data["documents"][document_id][status]
            if tracking_id in tracking_ids:
                tracking_ids.remove(tracking_id)
            if not tracking_ids:
                del doc_data["documents"][document_id][status]

        # Add tracking_id to current status
        doc_data["documents"][document_id].setdefault(current_status, []).append(tracking_id)

        # Update counts
        all_statuses = ["in_progress", "completed", "cancelled", "expired", "unknown"]
        status_counts = {s: len(doc_data["documents"][document_id].get(s, [])) for s in all_statuses}
        doc_data["status_counts"] = status_counts
        doc_data["total_trackings"] = sum(status_counts.values())

        # Save summary
        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=document_key,
            Body=json.dumps(doc_data),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID
        )
        logger.info(f"[save_tracking_metadata] Updated summary saved: {document_key}")

    except Exception as e:
        logger.exception(f"Failed to save tracking metadata: {e}")
        raise HTTPException(status_code=500, detail="Failed to save tracking metadata")


    except Exception as e:
        logger.exception(f"[save_tracking_metadata] Failed to save tracking metadata for {document_id}/{tracking_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save tracking metadata")


def update_tracking_status_counts_in_place(email: str):
    global_counts = {
        "in_progress": 0,
        "completed": 0,
        "cancelled": 0,
        "unknown": 0
    }

    prefix = f"{email}/{DOCUMENT_BASE_PATH}/"
    document_summaries = []

    try:
        response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
        if "Contents" not in response:
            return

        for obj in response["Contents"]:
            key = obj["Key"]
            try:
                content = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)["Body"].read().decode("utf-8")
                doc_data = json.loads(content)
                trackings = doc_data.get("trackings", {})

                doc_counts = {
                    "in_progress": 0,
                    "completed": 0,
                    "cancelled": 0,
                    "unknown": 0
                }

                for t_id, t_info in trackings.items():
                    status = t_info.get("status", "unknown")
                    if status not in doc_counts:
                        status = "unknown"
                    doc_counts[status] += 1
                    global_counts[status] += 1

                doc_data["doc_status"] = doc_counts

                document_summaries.append({
                    "document_id": key.split("/")[-1].replace(".json", ""),
                    "last_modified": obj.get("LastModified").isoformat() if obj.get("LastModified") else None,
                    **doc_counts
                })

                s3_client.put_object(
                    Bucket=config.S3_BUCKET,
                    Key=key,
                    Body=json.dumps(doc_data),
                    ContentType="application/json",
                    ServerSideEncryption="aws:kms",
                    SSEKMSKeyId=config.KMS_KEY_ID
                )

            except Exception as e:
                logger.warning(f"Failed to update tracking status summary for {key}: {e}")

        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=f"{email}/metadata/document/status_summary.json",
            Body=json.dumps({
                "summary": {
                    "total_documents": len(document_summaries),
                    "total_trackings": sum(global_counts.values()),
                    "status_counts": global_counts
                },
                "indexed_summary": document_summaries
            }),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID
        )

    except Exception as e:
        logger.error(f"Failed to update tracking status counts in place: {e}")



def load_meta_s3(email: str, document_id: str, tracking_id: str):
    return load_tracking_metadata(email, document_id=document_id, tracking_id=tracking_id)


def save_meta_s3(email: str, document_id: str, tracking_id: str, tracking_data: dict):
    return save_tracking_metadata(email, document_id, tracking_id, tracking_data)



def upload_meta_s3(email: str, doc_data: DocumentRequest, tracking_data: dict, defaults: bool):
    document_id = doc_data.document_id
    tracking_id = tracking_data.get("tracking_id")
    tracking_key = f"{email}/{TRACKING_BASE_PATH}/{document_id}/{tracking_id}.json"
    document_key = f"{email}/{DOCUMENT_BASE_PATH}/{document_id}.json"
    now = datetime.now(timezone.utc).isoformat()

    try:
        # Load existing document metadata (document-level)
        try:
            existing_data = s3_client.get_object(Bucket=config.S3_BUCKET, Key=document_key)
            doc_metadata = json.loads(existing_data['Body'].read().decode('utf-8'))
            is_first_upload = False
        except s3_client.exceptions.NoSuchKey:
            doc_metadata = {
                "document_id": document_id,
                "trackings": {}
            }
            is_first_upload = True

        # Load existing tracking metadata if available
        try:
            tracking_obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=tracking_key)
            existing_tracking_data = json.loads(tracking_obj['Body'].read().decode('utf-8'))
            is_first_tracking = False
        except s3_client.exceptions.NoSuchKey:
            existing_tracking_data = {}
            is_first_tracking = True

        # Ensure tracking_status exists; only set "in_progress" on first upload
        if is_first_tracking or "tracking_status" not in existing_tracking_data:
            tracking_data.setdefault("tracking_status", {})["status"] = "in_progress"
            tracking_data["tracking_status"]["dateTime"] = now

        # Merge new tracking_data into existing_tracking_data
        merged_tracking_data = {**existing_tracking_data, **tracking_data}

        # Add defaults if it's first document upload or explicitly requested
        if is_first_upload or defaults:
            merged_tracking_data["defaults"] = {
                "default_fields": tracking_data.get("fields", []),
                "parties": tracking_data.get("parties", [])
            }

        # Save tracking metadata
        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=tracking_key,
            Body=json.dumps(merged_tracking_data),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID
        )

        # Update document-level tracking summary
        doc_metadata.setdefault("trackings", {})
        doc_metadata["trackings"][tracking_id] = {
            "status": merged_tracking_data.get("tracking_status", {}).get("status", "in_progress"),
            "updated_at": now
        }

        # Add defaults to document-level metadata only if needed
        if is_first_upload or defaults:
            doc_metadata["defaults"] = {
                "default_fields": tracking_data.get("fields", []),
                "parties": tracking_data.get("parties", [])
            }

        # Recompute and update document-level summary
        doc_metadata["summary"] = generate_summary_from_trackings(doc_metadata["trackings"])

        # Save updated document-level metadata
        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=document_key,
            Body=json.dumps(doc_metadata),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID
        )

    except Exception as e:
        logger.exception(
            f"[upload_meta_s3] Failed to upload metadata for document_id={document_id}, tracking_id={tracking_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Failed to upload metadata")

def update_parties_tracking(email: str, document_id: str, tracking_id: str, parties: List[PartyUpdateItem]):
    tracking_key = f"{email}/{TRACKING_BASE_PATH}/{document_id}/{tracking_id}.json"

    try:
        # Load existing tracking metadata
        tracking_obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=tracking_key)
        tracking_data = json.loads(tracking_obj['Body'].read().decode('utf-8'))

        updated_parties = []

        # Update parties
        for update_item in parties:
            updated = False
            for party in tracking_data.get("parties", []):
                if party.get("id") == update_item.party_id:
                    if update_item.new_name and update_item.new_name != "string":
                        party["name"] = update_item.new_name
                    if update_item.new_email and update_item.new_email != "user@example.com":
                        party["email"] = update_item.new_email
                    updated = True
                    updated_parties.append({
                        "party_id": update_item.party_id,
                        "new_name": update_item.new_name if update_item.new_name and update_item.new_name != "string" else "Null",
                        "new_email": update_item.new_email if update_item.new_email and update_item.new_email != "user@example.com" else "Null"
                    })
            if not updated:
                raise HTTPException(status_code=404, detail=f"Party {update_item.party_id} not found in tracking")

        # Save updated tracking
        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=tracking_key,
            Body=json.dumps(tracking_data),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID
        )

        return {
            "document_id": document_id,
            "tracking_id": tracking_id,
            "updated_parties": updated_parties
        }

    except Exception as e:
        logger.exception(f"[update_parties_tracking] Failed for doc={document_id}, tracking={tracking_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update parties in tracking")




def upload_sign_meta_s3(email: str, document_id: str, tracking_id: str, tracking_data: dict):
    return save_tracking_metadata(email, document_id, tracking_id, tracking_data)


def get_meta_s3(email: str, document_id: str, tracking_id: str):
    return load_tracking_metadata(email, document_id=document_id, tracking_id=tracking_id)


def get_doc_meta(email: str):
    prefix = f"{email}/{DOCUMENT_BASE_PATH}/"
    try:
        response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
        all_docs = {}
        for obj in response.get("Contents", []):
            key = obj["Key"]
            content = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)["Body"].read().decode("utf-8")
            doc_data = json.loads(content)
            document_id = doc_data.get("document_id")
            if document_id:
                all_docs[document_id] = doc_data
        return all_docs
    except Exception as e:
        logger.error(f"Failed to list document metadata: {e}")
        raise HTTPException(status_code=500, detail="Failed to list document metadata")

def store_tracking_metadata(email: str, document_id: str, tracking_id: str, tracking_data: dict) -> None:
    """
    Stores the tracking metadata as a single JSON file under:
    {email}/metadata/tracking/{document_id}/{tracking_id}.json
    """
    key = str(PurePosixPath(email, TRACKING_BASE_PATH, document_id, f"{tracking_id}.json"))
    try:
        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=key,
            Body=json.dumps(tracking_data),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID
        )
        logger.info(f"Tracking metadata saved successfully for key: {key}")
    except ClientError as e:
        logger.error(f"Failed to store tracking metadata: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error saving tracking metadata: {str(e)}")
        raise

def get_all_document_statuses_flat(email) -> Dict[str, List[Dict[str, Any]]]:

    all_statuses = []
    prefix = f"{email}/{TRACKING_BASE_PATH}/"
    response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)

    for obj in response.get("Contents", []):
        key = obj["Key"]
        try:
            content = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)["Body"].read().decode("utf-8")
            tracking_data = json.loads(content)

            document_id = tracking_data.get("document_id")
            validityDate = tracking_data.get("validityDate")
            tracking_id = tracking_data.get("tracking_id", key.split("/")[-1].replace(".json", ""))
            status = tracking_data.get("tracking_status", {}).get("status", "unknown")
            parties = tracking_data.get("parties", [])
            datetime = tracking_data.get("tracking_status", {}).get("dateTime", "unknown")

            all_statuses.append({
                "document_id": document_id,
                "tracking_id": tracking_id,
                "validity_date": validityDate,
                "status": status,
                "parties": parties,
                "datetime": datetime
            })
        except Exception as e:
            logger.warning(f"Error reading tracking status for key {key}: {e}")
            continue

    return {"documents": all_statuses}


def format_datetime_utc(dt_str: str) -> str:
    try:
        dt = parse_datetime(dt_str)
        return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec='microseconds')
    except Exception:
        return dt_str  # fallback if already formatted or invalid

def get_document_details(email: str, document_id: str) -> Dict[str, Any]:
    document_key = f"{email}/{DOCUMENT_BASE_PATH}/{document_id}.json"
    tracking_base = f"{email}/{TRACKING_BASE_PATH}/{document_id}/"

    try:
        # Load only defaults from document metadata
        doc_obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=document_key)
        doc_data = json.loads(doc_obj["Body"].read().decode("utf-8"))
        defaults = doc_data.get("defaults", {})

        # List all tracking files
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=config.S3_BUCKET, Prefix=tracking_base)

        tracking_keys = []
        for page in pages:
            tracking_keys.extend([
                obj["Key"] for obj in page.get("Contents", [])
                if obj["Key"].endswith(".json")
            ])

        trackings_with_parties: Dict[str, Dict[str, Any]] = {}
        status_counts = defaultdict(int)
        doc_status_counts = defaultdict(int)

        def fetch_tracking(key: str):
            try:
                obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
                tracking_data = json.loads(obj["Body"].read().decode("utf-8"))

                tracking_id = key.split("/")[-1].replace(".json", "")
                status_block = tracking_data.get("tracking_status", {})
                status = status_block.get("status", "unknown")
                updated_at = status_block.get("dateTime")

                parties = tracking_data.get("parties", [])
                formatted_parties = [
                    {
                        "party_id": p.get("id"),
                        "name": p.get("name"),
                        "email": p.get("email")
                    }
                    for p in parties if p.get("email")
                ]

                return tracking_id, status, updated_at, formatted_parties

            except Exception as e:
                logger.warning(f"Failed to process tracking file {key}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_tracking, key) for key in tracking_keys]
            for future in as_completed(futures):
                result = future.result()
                if not result:
                    continue

                tracking_id, status, updated_at, parties = result

                # Populate tracking structure
                trackings_with_parties[tracking_id] = {
                    "status": status,
                    "updated_at": updated_at,
                    "parties": parties
                }

                # Count statuses
                status_counts[status] += 1
                doc_status_counts[status or "unknown"] += 1

        total_trackings = len(trackings_with_parties)

        summary = {
            "total_documents": 1,
            "total_trackings": total_trackings,
            "status_counts": dict(status_counts)
        }

        doc_status = {
            "in_progress": doc_status_counts.get("in_progress", 0),
            "completed": doc_status_counts.get("completed", 0),
            "cancelled": doc_status_counts.get("cancelled", 0),
            "unknown": doc_status_counts.get("unknown", 0),
        }

        return {
            "document_id": document_id,
            "trackings": trackings_with_parties,
            "summary": summary,
            "doc_status": doc_status,
            "defaults": defaults
        }

    except ClientError as ce:
        if ce.response['Error']['Code'] == 'NoSuchKey':
            logger.error(f"Document not found: {document_key}")
            raise HTTPException(status_code=404, detail="Document not found")
        logger.error(f"Failed to load document: {ce}")
        raise HTTPException(status_code=500, detail="S3 document metadata error")

    except Exception as e:
        logger.exception("Unhandled exception in get_document_details")
        raise HTTPException(status_code=500, detail="Internal server error")








def load_document_metadata(email: str, document_id: str) -> dict:
    key = f"{email}/{DOCUMENT_BASE_PATH}/{document_id}.json"
    try:
        obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="Document ID not found")
    except Exception as e:
        logger.error(f"Failed to load document metadata from S3 for email={email}, document_id={document_id}, error: {e}")
        raise HTTPException(status_code=500, detail="Error loading document metadata")

def load_all_json_from_prefix(email: str) -> List[Dict[str, Any]]:
    """
    Load and parse all JSON files under the given S3 prefix for the specified email.
    Returns a list of dictionaries representing each JSON file.
    """
    prefix = f"{email}/{DOCUMENT_BASE_PATH}".rstrip("/") + "/"
    result = []

    try:
        response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
        contents = response.get("Contents", [])
        logger.info(f"[load_all_json_from_prefix] Found {len(contents)} items under {prefix}")

        for obj in contents:
            key = obj["Key"]
            if not key.endswith(".json"):
                continue

            try:
                raw = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)["Body"].read().decode("utf-8")
                parsed = json.loads(raw)
                result.append(parsed)
            except json.JSONDecodeError as e:
                logger.warning(f"[load_all_json_from_prefix] Skipping invalid JSON: {key} — {e}")
            except ClientError as e:
                logger.warning(f"[load_all_json_from_prefix] Could not read key {key}: {e}")
            except Exception as e:
                logger.error(f"[load_all_json_from_prefix] Unexpected error reading {key}: {e}")

    except ClientError as e:
        logger.error(f"[load_all_json_from_prefix] Failed to list objects under {prefix}: {e}")
        raise

    return result


def store_tracking_status(doc_entry, document_id, email):
    s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=f"{email}/{DOCUMENT_BASE_PATH}/{document_id}.json",
            Body=json.dumps(doc_entry),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID
        )
def s3_file_responses(email: str, key_suffix: str):
    key = f"{email}/{key_suffix}"
    try:
        response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
        return response["Body"].read().decode("utf-8")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.warning(f"S3 key not found: {key}")
            return "{}"
        else:
            logger.error(f"S3 ClientError in s3_file_responses for {key}: {e}")
            raise
    except Exception as e:
        logger.error(f"Unexpected error in s3_file_responses for {key}: {e}")
        raise

def store_status(document_id: str, document_summary: dict, email: str):
    key = f"{email}/{DOCUMENT_BASE_PATH}/{document_id}.json"

    try:
        # Step 1: Load existing document (if exists)
        try:
            existing_obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
            existing_data = json.loads(existing_obj["Body"].read().decode("utf-8"))
        except s3_client.exceptions.NoSuchKey:
            existing_data = {}

        # Step 2: Preserve and merge existing status per tracking ID
        existing_trackings = existing_data.get("trackings", {})
        new_trackings = document_summary.get("trackings", {})

        for tracking_id, new_entry in new_trackings.items():
            existing_entry = existing_trackings.get(tracking_id, {})
            # Merge existing and new (new overrides flat keys, preserves nested history)
            merged_entry = {
                **existing_entry,
                **new_entry,
                "status": new_entry.get("tracking_status", existing_entry.get("tracking_status")),
                "updated_at": new_entry.get("updated_at", datetime.now(timezone.utc).isoformat())
            }
            existing_trackings[tracking_id] = merged_entry

        # Step 3: Update main structure
        existing_data["document_id"] = document_id
        existing_data["trackings"] = existing_trackings
        existing_data["summary"] = document_summary.get("summary", existing_data.get("summary", {}))

        # Step 4: Save back to S3
        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=key,
            Body=json.dumps(existing_data),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID
        )
    except Exception as e:
        logger.exception(f"Failed to store status for document_id={document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error storing tracking status")




async def mark_expired_trackings(email: str):
    prefix = f"{email}/{DOCUMENT_BASE_PATH}/"
    now = datetime.now(timezone.utc)

    try:
        response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
        contents = response.get("Contents", [])

        if not contents:
            logger.info(f"No documents found for user: {email}")
            return

        for obj in contents:
            doc_key = obj.get("Key")
            if not doc_key or not doc_key.endswith(".json"):
                continue

            try:
                doc_obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=doc_key)
                doc_data = json.loads(doc_obj["Body"].read().decode("utf-8"))
            except (ClientError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to read or parse document {doc_key}: {e}")
                continue

            document_id = doc_data.get("document_id")
            if not document_id:
                continue

            updated = False
            trackings = doc_data.get("trackings", {})
            for tracking_id in list(trackings.keys()):
                try:
                    tracking_data = load_tracking_metadata(email, document_id, tracking_id)
                except Exception as e:
                    logger.warning(f"Unable to load tracking metadata for {tracking_id}: {e}")
                    continue

                status = tracking_data.get("tracking_status", {}).get("status")
                if status in {"completed", "cancelled", "expired"}:
                    continue

                validity = tracking_data.get("validity_date")
                if not validity:
                    continue

                try:
                    validity_dt = datetime.fromisoformat(validity.replace("Z", "+00:00"))
                except Exception as e:
                    logger.warning(f"Invalid validity_date format for {tracking_id}: {e}")
                    continue

                if now > validity_dt:
                    tracking_data["tracking_status"] = {
                        "status": "expired",
                        "dateTime": now.isoformat(),
                        "device": "System",
                        "browser": "System"
                    }

                    for party in tracking_data.get("parties", []):
                        party.setdefault("status", {})
                        party["status"]["expired"] = {
                            "isExpired": True,
                            "dateTime": now.isoformat(),
                            "device": "System",
                            "browser": "System"
                        }

                    try:
                        save_tracking_metadata(email, document_id, tracking_id, tracking_data)
                        logger.info(f"[mark_expired_trackings] Tracking {tracking_id} marked as expired.")
                        updated = True
                    except Exception as e:
                        logger.error(f"Failed to save expired tracking {tracking_id}: {e}")

            if updated:
                logger.info(f"[mark_expired_trackings] Updated expired trackings for document_id={document_id}")

    except Exception as e:
        logger.error(f"[mark_expired_trackings] Fatal error for user {email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark expired trackings")


def expire_old_trackings(email: str):
    prefix = f"{email}/forms/submissions/"
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=config.S3_BUCKET, Prefix=prefix, Delimiter="/")

        for page in pages:
            for folder in page.get("CommonPrefixes", []):
                form_id = folder["Prefix"].split("/")[-2]  # extract form_id

                tracking_key = f"{email}/forms/submissions/{form_id}/trackings.json"

                try:
                    resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=tracking_key)
                    trackings = json.loads(resp["Body"].read().decode("utf-8"))
                except ClientError as e:
                    if e.response['Error']['Code'] == "NoSuchKey":
                        continue
                    raise

                updated = False
                now = datetime.now(timezone.utc)

                for tracking in trackings.get("trackings", []):
                    validity = tracking.get("validity_date")
                    status = tracking.get("status")

                    if validity and status in ["sent", "opened"]:
                        validity_dt = datetime.fromisoformat(validity.replace("Z", "+00:00"))
                        if now > validity_dt:
                            tracking["status"] = "expired"
                            updated = True

                if updated:
                    s3_client.put_object(
                        Bucket=config.S3_BUCKET,
                        Key=tracking_key,
                        Body=json.dumps(trackings, indent=2),
                        ServerSideEncryption="aws:kms",
                        SSEKMSKeyId=config.KMS_KEY_ID,
                    )

    except Exception as e:
        print(f"Error in expire_old_trackings: {e}")



def save_defaults(email: str, document_id: str, default_fields: list):
    key = f"{email}/{DOCUMENT_BASE_PATH}/{document_id}.json"
    try:
        try:
            obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
            data = json.loads(obj["Body"].read().decode("utf-8"))
        except s3_client.exceptions.NoSuchKey:
            data = {"document_id": document_id, "trackings": {}, "defaults": {}}

        data["defaults"]["default_fields"] = default_fields

        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=key,
            Body=json.dumps(data),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID
        )
        logger.info(f"Saved default fields for document_id={document_id}")
    except Exception as e:
        logger.exception(f"Failed to save default fields: {e}")
        raise HTTPException(status_code=500, detail="Failed to save default fields")


def save_defaults_fields(email: str, payload):
    document_id = payload.document_id
    default_fields = [
        {**field.dict(), "required": field.required or False}
        for field in payload.fields
    ]
    save_defaults(email, document_id, default_fields)
    return {"message": "Default fields saved", "document_id": document_id}


def save_templates(email: str, document_id: str, template_data: dict):
    key = f"{email}/{DOCUMENT_BASE_PATH}/{document_id}.json"
    try:
        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=key,
            Body=json.dumps(template_data, indent=2),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID
        )
        logger.info(f"Saved template data for document_id={document_id}")
    except Exception as e:
        logger.exception(f"Failed to save template: {e}")
        raise HTTPException(status_code=500, detail="Failed to save template")



async def get_pdf_s3(email, file_path):
        file_response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=file_path)
        encryption_service = EncryptionService()
        encryption_email = await encryption_service.resolve_encryption_email(email)
        cipher = AESCipher(encryption_email)
        encrypted_file_content = file_response["Body"].read()
        decrypted_file_content = cipher.decrypt(encrypted_file_content)
        return decrypted_file_content


def get_index_s3(email):
    index_key = f"{email}/index/document_index.json"
    response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=index_key)
    index_data = json.loads(response['Body'].read().decode('utf-8'))
    return index_data

def delete_s3(old_file_path):
    s3_client.delete_object(Bucket=config.S3_BUCKET, Key=old_file_path)


def put_folder(deleted_key):
    folder_prefix = '/'.join(deleted_key.split('/')[:-1]) + '/'
    response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=folder_prefix)
    # response = list_s3_objects(folder_prefix)
    # Count remaining objects except the one being deleted
    remaining = [obj for obj in response.get('Contents', []) if obj['Key'] != deleted_key]
    if not remaining:
        # Upload a placeholder file to retain the folder prefix
        keep_key = folder_prefix + '.keep'
        s3_client.put_object(Bucket=config.S3_BUCKET, Key=keep_key, Body=b'',
                             ServerSideEncryption="aws:kms",
                             SSEKMSKeyId=config.KMS_KEY_ID)

def put_new_folder(deleted_key):
    folder_prefix = '/'.join(deleted_key.split('/')[:-1]) + '/'
    # response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=folder_prefix)
    # response = list_s3_objects(folder_prefix)
    response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=folder_prefix)
    remaining = [obj for obj in response.get('Contents', []) if obj['Key'] != deleted_key]
    if not remaining:
       keep_key = folder_prefix + '.keep'
       s3_client.put_object(Bucket=config.S3_BUCKET, Key=keep_key, Body=b'',
                                     ServerSideEncryption="aws:kms",
                                     SSEKMSKeyId=config.KMS_KEY_ID)

def get_s3_js(index_key):
    response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=index_key)
    index_data = json.loads(response['Body'].read().decode('utf-8'))
    return index_data

def copy_data_s3(document_ids, email, ensure_folder_exists_after_deletion, is_file_key, new_folder,
                     results):
    index_key = f"{email}/index/document_index.json"
    index_data = get_s3_js(index_key)
    for document_id in document_ids:
        if document_id not in index_data:
            results[document_id] = {"error": "Document ID not found in index"}
            continue

        file_path = index_data[document_id].get("file_path")
        metadata_path = index_data[document_id].get("metadata_path")

        if not file_path or not metadata_path:
            results[document_id] = {"error": "Missing file or metadata path"}
            continue

        file_name = index_data[document_id].get("fileName")  # Fallback if not present
        new_file_path = f"{email}/files/{new_folder}/{file_name}"
        new_metadata_path = f"{email}/files/{new_folder}/{document_id}.json"

        try:
            # Copy files to new location
            s3_client.copy_object(Bucket=config.S3_BUCKET,
                                      CopySource={'Bucket': config.S3_BUCKET, 'Key': file_path}, Key=new_file_path)
            s3_client.copy_object(Bucket=config.S3_BUCKET,
                                      CopySource={'Bucket': config.S3_BUCKET, 'Key': metadata_path},
                                      Key=new_metadata_path)

            # Delete original files
            if is_file_key(file_path):
                delete_s3(file_path)
                ensure_folder_exists_after_deletion(file_path)

            if is_file_key(metadata_path):
                delete_s3(metadata_path)
                ensure_folder_exists_after_deletion(metadata_path)

                # Update index
            index_data[document_id]["file_path"] = new_file_path
            index_data[document_id]["metadata_path"] = new_metadata_path

            results[document_id] = {"status": "moved"}

        except ClientError as e:
            results[document_id] = {"error": str(e)}
    return index_data

def get_s3_meta_obj(key):
    metadata_obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
    metadata = json.loads(metadata_obj['Body'].read().decode('utf-8'))
    return metadata


def update_doc_s3(email):
    index_key = f"{email}/index/document_index.json"
    response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=index_key)
    raw_data = response['Body'].read()
    return index_key, raw_data

def get_s3_update_doc(email):
    index_key = f"{email}/index/document_index.json"
    response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=index_key)
    raw_data = response['Body'].read()
    try:
        index_data = json.loads(raw_data.decode('utf-8'))
    except UnicodeDecodeError as ude:
        logger.exception("Index file is not UTF-8 encoded or corrupted.")
        raise Exception("The document index file is not in a valid UTF-8 JSON format.") from ude
    except json.JSONDecodeError as jde:
        logger.exception("Index file is not valid JSON.")
        raise Exception("The document index file content is not valid JSON.") from jde
    return index_data, index_key


async def get_encrypted_file(email, file, file_content, overwrite: bool, pdf_key: str):
    try:
        s3_client.head_object(Bucket=config.S3_BUCKET, Key=pdf_key)
        if not overwrite:
            raise HTTPException(
                status_code=409,
                detail=f"File '{file.filename}' already exists."
            )
    except ClientError as e:
        if e.response['Error']['Code'] != "404":
            logger.error("Unexpected S3 error during file existence check.")
            raise

    # Encrypt and upload file
    encryption_service = EncryptionService()
    encryption_email = await encryption_service.resolve_encryption_email(email)
    cipher = AESCipher(encryption_email)
    encrypted_file_content = cipher.encrypt(file_content)

    s3_client.put_object(
        Body=encrypted_file_content,
        Bucket=config.S3_BUCKET,
        Key=pdf_key,
        ServerSideEncryption="aws:kms",
        SSEKMSKeyId=config.KMS_KEY_ID
    )

def _get_metadata_key(email: str, document_id: str, path_prefix: str = "") -> str:
    return str(PurePosixPath(email, "files", path_prefix, f"{document_id}.json"))

def _get_pdf_key(email: str, filename: str, path_prefix: str = "") -> str:
    return str(PurePosixPath(email, "files", path_prefix, filename))
async def udpate_meta_doc(document_id, email, file, overwrite, path_prefix):
    # Read file content
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    logger.info(f"Uploading file: {file.filename}, Size: {file_size / 1024:.2f} KB")
    file_content = file.file.read()

    # Generate S3 keys
    pdf_key = _get_pdf_key(email, file.filename, path_prefix)
    metadata_key = _get_metadata_key(email, document_id, path_prefix)

    # file_path = f"s3://{config.S3_BUCKET}/{pdf_key}"
    # metadata_path = f"s3://{config.S3_BUCKET}/{metadata_key}"

    # Upload PDF (replace if overwrite=True)
    await get_encrypted_file(email, file, file_content, overwrite, pdf_key)

    # Always replace metadata (no preservation logic needed)
    metadata = {
        "document_id": document_id,
        "fileName": file.filename,
        "fileSizeBytes": file_size,
        "contentType": file.content_type,
        "filePath": pdf_key,
        "metadataPath": metadata_key
    }

    logger.info(f"Storing metadata at: {metadata_key} (overwrite={overwrite})")
    s3_client.put_object(
        Body=json.dumps(metadata),
        Bucket=config.S3_BUCKET,
        Key=metadata_key,
        ServerSideEncryption="aws:kms",
        SSEKMSKeyId=config.KMS_KEY_ID
    )

    return metadata




def append_logs(entry, key):
    try:
        response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
        logs = json.loads(response["Body"].read().decode("utf-8"))
    except s3_client.exceptions.NoSuchKey:
        logs = []
    logs.append(entry)
    s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=key,
            Body=json.dumps(logs, indent=2),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID
        )

def get_logs(key):
    response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))


async def s3_head_upload(pdf_key):
    s3_client.head_object(Bucket=config.S3_BUCKET, Key=pdf_key)

def recursive_list(email):
    return s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=f"{email}/files/")

def s3_update(email, index_data):
    index_key = f"{email}/index/document_index.json"
    s3_client.put_object(
        Bucket=config.S3_BUCKET,
        Key=index_key,
        Body=json.dumps(index_data, indent=2),
        ContentType='application/json',
        ServerSideEncryption="aws:kms",
        SSEKMSKeyId=config.KMS_KEY_ID
    )
def s3_update_libraries(email, index_data, index_key):
    s3_client.put_object(
        Bucket=config.S3_BUCKET,
        Key=index_key,
        Body=json.dumps(index_data, indent=2),
        ContentType='application/json',
        ServerSideEncryption="aws:kms",
        SSEKMSKeyId=config.KMS_KEY_ID
    )



# @lru_cache(maxsize=64)
def get_document_index(email: str) -> Dict[str, str]:
    """
    Load and cache document index from S3.
    Returns: reverse_map: file_path -> document_id
    """
    index_key = f"{email}/index/document_index.json"
    try:
        response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=index_key)
        index_data = json.loads(response["Body"].read().decode("utf-8"))

        reverse_map = {}
        for doc_id, entry in index_data.items():
            file_path = entry.get("file_path")
            if file_path:
                reverse_map[file_path] = doc_id
        return reverse_map

    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"Index not found: {index_key}")
        return {}
    except Exception as e:
        logger.error(f"Failed to read index: {e}")
        return {}

from typing import List, Dict
from botocore.exceptions import ClientError
from datetime import datetime, timezone
from collections import OrderedDict

def list_objects_recursive(email: str, prefix: str = "") -> List[Dict]:
    reverse_index = get_document_index(email)

    def move_index_first(data: Dict) -> OrderedDict:
        """Ensure index appears first in dict."""
        if "index" in data:
            new_dict = OrderedDict()
            new_dict["index"] = data["index"]
            for k, v in data.items():
                if k == "index":
                    continue
                new_dict[k] = v
            return new_dict
        return data

    def recurse(current_prefix: str) -> List[Dict]:
        result = s3_client.list_objects_v2(
            Bucket=config.S3_BUCKET,
            Prefix=current_prefix,
            Delimiter="/"
        )

        items = []

        # --- Folders ---
        for common_prefix in result.get("CommonPrefixes", []):
            folder_name = common_prefix["Prefix"].rstrip("/").split("/")[-1]
            folder_prefix = common_prefix["Prefix"]

            folder_metadata = {}
            last_modified = None
            try:
                resp = s3_client.head_object(Bucket=config.S3_BUCKET, Key=folder_prefix)
                folder_metadata = resp.get("Metadata", {})
                last_modified = resp.get("LastModified")
            except ClientError:
                pass

            folder = {
                "type": "folder",
                "name": folder_name,
                "items": recurse(folder_prefix),
                "last_modified": (last_modified or datetime.min).replace(tzinfo=timezone.utc)
            }

            if folder_metadata:
                folder["created_by_name"] = folder_metadata.get("folder_created_by_name")
                folder["created_by_email"] = folder_metadata.get("folder_created_by_email")
                folder["created_at"] = folder_metadata.get("created_at")

            items.append(folder)

        # --- Files (PDF only) ---
        for content in result.get("Contents", []):
            key = content["Key"]
            if key == current_prefix or not key.lower().endswith(".pdf"):
                continue

            file_name = key.split("/")[-1]
            document_id = reverse_index.get(key)

            file_entry = {
                "type": "file",
                "name": file_name,
                "last_modified": (content.get("LastModified") or datetime.min).replace(tzinfo=timezone.utc)
            }

            if document_id:
                file_entry["document_id"] = document_id

            items.append(file_entry)

        # --- Sort by last_modified (latest first) ---
        items.sort(key=lambda x: x["last_modified"], reverse=True)

        # --- Assign index and reorder keys ---
        ordered_items = []
        for idx, item in enumerate(items, start=1):
            item["index"] = idx
            item.pop("last_modified", None)  # remove helper field
            ordered_items.append(move_index_first(item))

        return ordered_items

    return recurse(prefix)







import os
from typing import Dict
from botocore.exceptions import ClientError

def delete_folder(email: str, folder_name: str) -> Dict:
    """
    Deletes only the contents of the specified S3 'folder' if it only contains `.keep` files or subfolders.
    Ensures the parent folder has a `.keep` file (auto-created if missing), and that it is not deleted.
    """
    prefix = f"{email}/files/{folder_name}/"  # e.g. admin@example.com/files/empty1/empty2/
    parent_prefix = os.path.dirname(folder_name.rstrip('/'))  # e.g. empty1
    parent_keep_key = f"{email}/files/{parent_prefix}/.keep"

    try:
        # Step 1: Ensure parent folder has a .keep file
        # try:
        #     s3_client.head_object(Bucket=config.S3_BUCKET, Key=parent_keep_key)
        # except ClientError as e:
        #     if e.response["Error"]["Code"] == "404":
        #         s3_client.put_object(Bucket=config.S3_BUCKET, Key=parent_keep_key, Body=b"")
        #     else:
        #         raise e

        # Step 2: List objects only inside the folder to be deleted
        response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
        if "Contents" not in response:
            return {"status": "folder does not exist", "deleted": [], "errors": []}

        all_keys = [item["Key"] for item in response["Contents"]]

        # Step 3: Check if folder contains any file other than `.keep` or subfolder markers
        non_keep_files = [
            key for key in all_keys
            if not key.endswith(".keep") and not key.endswith("/")
        ]

        if non_keep_files:
            return {
                "detail": f"Folder '{prefix}' contains files other than .keep. Deletion denied.",
                "deleted": [],
                "errors": []
            }

        # Step 4: Delete all safe keys (only within target folder)
        deleted = []
        for key in all_keys:
            if key == parent_keep_key:
                continue  # explicitly skip the parent .keep file
            s3_client.delete_object(Bucket=config.S3_BUCKET, Key=key)
            deleted.append(key)

        return {
            "status": "folder deleted",
            "deleted": deleted,
            "errors": []
        }

    except ClientError as e:
        return {
            "status": "error",
            "deleted": [],
            "errors": [str(e)]
        }


def delete_library_folder(email: str, folder_name: str) -> Dict:
    """
    Deletes only the contents of the specified S3 'folder' if it only contains `.keep` files or subfolders.
    Ensures the parent folder has a `.keep` file (auto-created if missing), and that it is not deleted.
    """
    prefix = f"libraries/files/{folder_name}/"  # e.g. admin@example.com/files/empty1/empty2/
    parent_prefix = os.path.dirname(folder_name.rstrip('/'))  # e.g. empty1
    parent_keep_key = f"libraries/files/{parent_prefix}/.keep"

    try:

        response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
        if "Contents" not in response:
            return {"status": "folder does not exist", "deleted": [], "errors": []}

        all_keys = [item["Key"] for item in response["Contents"]]

        # Step 3: Check if folder contains any file other than `.keep` or subfolder markers
        non_keep_files = [
            key for key in all_keys
            if not key.endswith(".keep") and not key.endswith("/")
        ]

        if non_keep_files:
            return {
                "detail": f"Folder '{prefix}' contains files other than .keep. Deletion denied.",
                "deleted": [],
                "errors": []
            }

        # Step 4: Delete all safe keys (only within target folder)
        deleted = []
        for key in all_keys:
            if key == parent_keep_key:
                continue  # explicitly skip the parent .keep file
            s3_client.delete_object(Bucket=config.S3_BUCKET, Key=key)
            deleted.append(key)

        return {
            "status": "folder deleted",
            "deleted": deleted,
            "errors": []
        }

    except ClientError as e:
        return {
            "status": "error",
            "deleted": [],
            "errors": [str(e)]
        }




def create_folder_only(email: str, new_folder: str, name: str, user_email: str):
    folder_key = f"{email}/files/{new_folder}/"
    try:
        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=folder_key,
            Body=b'',
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID,
            Metadata={
                "folder_created_by_name": name,
                "folder_created_by_email": user_email,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        )
        return {"status": "folder created"}
    except ClientError as e:
        return {"error": str(e)}


# 15. Create an empty folder in S3 for a user
def create_folder(email: str, new_folder: str):
    folder_key = f"libraries/files/{new_folder}/"  # .keep is a dummy file to ensure folder exists
    try:
        s3_client.put_object(Bucket=config.S3_BUCKET, Key=folder_key, Body=b'',
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=config.KMS_KEY_ID)
        return {"status": "folder created"}
    except ClientError as e:
        return {"error": str(e)}

async def get_file_name(email: str, document_id: str) -> str:
    try:
        from app.api.routes.files_api import get_storage
        storage = get_storage(config.STORAGE_TYPE)
        encryption_service = EncryptionService()
        encryption_email = await encryption_service.resolve_encryption_email(email)
        cipher = AESCipher(encryption_email)
        meta = storage.get(cipher, email=email, document_id=document_id)

        file_name = meta.get("fileName")
        if not file_name:
            raise HTTPException(status_code=404, detail="fileName not found in metadata")

        return file_name

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve fileName: {str(e)}")
# 10. Render a signed PDF from S3 and return a PyMuPDF document object
async def rendered_sign_s3(email, document_id: str):
    try:
        from app.api.routes.files_api import get_storage
        storage = get_storage(config.STORAGE_TYPE)
        encryption_service = EncryptionService()
        encryption_email = await encryption_service.resolve_encryption_email(email)
        cipher = AESCipher(encryption_email)
        meta = storage.get(cipher, email=email, document_id=document_id)

        metadata_key = meta["metadata_path"]
        metadata_url = s3_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': config.S3_BUCKET, 'Key': metadata_key},
            ExpiresIn=7 * 24 * 60 * 60
        )

        response = requests.get(metadata_url)
        response.raise_for_status()
        metadata = response.json()

        file_name = meta["fileName"]
        if not file_name:
            raise ValueError("fileName not found in metadata")

        # Step 1: Fetch Encrypted PDF
        pdf_key = meta["file_path"]
        pdf_obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=pdf_key)
        encrypted_pdf_bytes = pdf_obj['Body'].read()

        # Step 2: Decrypt PDF
        encryption_service = EncryptionService()
        encryption_email = await encryption_service.resolve_encryption_email(email)
        cipher = AESCipher(encryption_email)
        decrypted_pdf_bytes = cipher.decrypt(encrypted_pdf_bytes)

        # Step 3: Render PDF using PyMuPDF
        pdf_doc = fitz.open(stream=decrypted_pdf_bytes, filetype="pdf")
        return pdf_doc, file_name

    except Exception as e:
        raise Exception(f"PDF rendering failed: {str(e)}")

# 11. Upload a rendered signed PDF to S3 and return its base64 string
async def render_sign_update(email, output_buffer, tracking_id, document_id):
    encryption_service = EncryptionService()
    encryption_email = await encryption_service.resolve_encryption_email(email)
    cipher = AESCipher(encryption_email)
    encrypted_buffer = cipher.encrypt(output_buffer)
    s3_client.put_object(
        Bucket=config.S3_BUCKET,
        Key=f"{email}/signed/{document_id}/{tracking_id}",
        Body=encrypted_buffer,
        ContentType="application/pdf",
        ServerSideEncryption="aws:kms",
        SSEKMSKeyId=config.KMS_KEY_ID
    )
    pdf_base64 = base64.b64encode(output_buffer).decode("utf-8")

    return pdf_base64

async def get_signed(email: str, tracking_id: str, document_id: str):
    try:
        s3_response = s3_client.get_object(
            Bucket=config.S3_BUCKET,
            Key=f"{email}/signed/{document_id}/{tracking_id}"
        )
        encrypted_bytes = s3_response["Body"].read()
        encryption_service = EncryptionService()
        encryption_email = await encryption_service.resolve_encryption_email(email)
        cipher = AESCipher(encryption_email)
        decrypted_bytes = cipher.decrypt(encrypted_bytes)
        return decrypted_bytes

    except NoCredentialsError:
        raise HTTPException(status_code=500, detail="AWS credentials not found.")

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            raise HTTPException(status_code=404, detail="Signed document not found.")
        elif error_code == 'NoSuchBucket':
            raise HTTPException(status_code=500, detail="S3 bucket does not exist.")
        else:
            raise HTTPException(status_code=500, detail=f"Unexpected S3 error: {e}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# # 2. Get signed PDF as base64 string
# def get_signed_pdf_base64(email, tracking_id,document_id):
#     metadata = MetadataService.get_metadata(email, tracking_id, document_id)
#     signed_base64 = metadata.get("signed_pdf")
#     if not signed_base64:
#         raise HTTPException(status_code=404, detail="Signed PDF not found")
#     return signed_base64


def get_document_name(email: str, document_id: str):
    index_key = f"{email}/index/document_index.json"
    try:
        response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=index_key)
        index_data = json.loads(response["Body"].read().decode("utf-8"))

        if document_id in index_data:
            return index_data[document_id].get("fileName")
        else:
            return None  # or raise an error
    except Exception as e:
        logging.exception("Error fetching file name from index.")
        return None

async def upload_file(email, file_bytes: bytes, document_id, tracking_id):
    s3_path = f"{email}/certificates/documents/{document_id}/tracking/{tracking_id}.pdf"
    encryption_service = EncryptionService()
    encryption_email = await encryption_service.resolve_encryption_email(email)
    cipher = AESCipher(encryption_email)
    encrypted_file = cipher.encrypt(file_bytes)
    s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=s3_path,
            Body=encrypted_file,
            ContentType="application/pdf"
        )
def get_folder_size(email: str) -> int:
    folder_prefix=email
    total_size = 0
    paginator = s3_client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=config.S3_BUCKET, Prefix=folder_prefix):
        for obj in page.get('Contents', []):
            total_size += obj['Size']
    return total_size


def s3_download_string(s3_key: str) -> str:
    obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=s3_key)
    return obj['Body'].read().decode()


def get_signature_entry(email: str, tracking_id: str, party_id: str) -> tuple[str, str]:
    """
    Retrieves the style and signature for a specific party_id from S3 signatures.json
    Returns (style, signature) or ("", "") if not found.
    """
    s3_key = f"{email}/signatures/{tracking_id}/signatures/{party_id}.json"

    try:
        obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=s3_key)
        data = json.loads(obj['Body'].read().decode())
    except ClientError as e:
        logger.warning(f"⚠️ signatures.json not found at {s3_key} - {e}")
        return "", ""
    except Exception as e:
        logger.error(f"❌ Error reading/parsing JSON: {e}")
        return "", ""

    party_data = data.get(str(party_id))
    if not party_data:
        logger.warning(f"⚠️ No entry for party_id {party_id} in {s3_key}")
        return "", ""

    style = party_data.get("style", "")
    signature = party_data.get("s3_key", "")
    return style, signature


def s3_delete_object(s3_key: str) -> None:
    s3_client.delete_object(Bucket=config.S3_BUCKET, Key=s3_key)

def s3_upload_bytes(file_bytes: json, s3_key: str, content_type="") -> bool:
    try:
        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type
        )
        return True
    except ClientError as e:
        logger.error(f"❌ Failed to upload to S3: {s3_key} - {e}")
        return False

def s3_upload_json(data: dict, key: str):
    try:
        json_data = json.dumps(data, indent=2).encode("utf-8")
        s3_client.put_object(
            Bucket=config.S3_BUCKET,
            Key=key,
            Body=json_data,
            ContentType="application/json"
        )
        logger.info(f"[s3_upload_json] Uploaded JSON to s3://{config.S3_BUCKET}/{key}")
    except ClientError as e:
        logger.exception(f"[s3_upload_json] Failed to upload JSON: {e}")
        raise

def s3_download_json(key: str) -> dict:
    try:
        response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
        content = response["Body"].read().decode("utf-8")
        return json.loads(content)
    except s3_client.exceptions.NoSuchKey:
        # Do not log as warning unless you expect the file to always exist
        return None
    except ClientError as e:
        logger.exception(f"[s3_download_json] Failed to download JSON: {e}")
        raise


def s3_delete_objects(key: str):
    try:
        s3_client.delete_object(Bucket=config.S3_BUCKET, Key=key)
        logger.info(f"[s3_delete_object] Deleted s3://{config.S3_BUCKET}/{key}")
    except ClientError as e:
        logger.exception(f"[s3_delete_object] Failed to delete object: {e}")
        raise

def s3_list_objects(prefix: str):
    response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
    contents = response.get("Contents")
    if not contents:
        return []

    keys = [item["Key"] for item in contents if item["Key"].endswith(".json")]
    return keys
def s3_list_object(prefix: str) -> list:
    response = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
    return [obj['Key'] for obj in response.get('Contents', [])]

def s3_download_bytes(key: str) -> bytes:
    response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
    return response['Body'].read()





def _list_objects(prefix: str) -> List[str]:
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=config.S3_BUCKET, Prefix=prefix)

        all_keys = []
        for page in pages:
            contents = page.get("Contents", [])
            for obj in contents:
                all_keys.append(obj["Key"])
        return all_keys
    except Exception as e:
        logger.error(f"Error listing objects from S3: {e}")
        return []


def load_tracking_metadata_by_tracking_id(email: str, tracking_id: str) -> dict:

    prefix = f"{email}/{TRACKING_BASE_PATH}/"
    paginator = s3_client.get_paginator("list_objects_v2")

    try:
        pages = paginator.paginate(Bucket=config.S3_BUCKET, Prefix=prefix, Delimiter="/")

        # Collect all document_id folders
        document_folders = []
        for page in pages:
            for prefix_obj in page.get("CommonPrefixes", []):
                folder = prefix_obj["Prefix"].split("/")[-2]  # e.g., metadata/tracking/{document_id}/
                document_folders.append(folder)

        # Search for the tracking_id.json file in each folder
        for doc_id in document_folders:
            key = f"{email}/{TRACKING_BASE_PATH}/{doc_id}/{tracking_id}.json"
            try:
                obj = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
                data = json.loads(obj["Body"].read().decode("utf-8"))
                return {
                    "document_id": doc_id,
                    "tracking_id": tracking_id,
                    "data": data
                }
            except s3_client.exceptions.NoSuchKey:
                continue  # Not in this doc_id folder

        logger.warning(f"Tracking ID '{tracking_id}' not found under any document for user: {email}")
        raise HTTPException(status_code=404, detail="Tracking-Id not found")


    except Exception as e:

        if isinstance(e, HTTPException):
            raise e

        logger.error(f"Error loading tracking metadata: {e}")

        raise HTTPException(status_code=500, detail="Error loading tracking metadata")

def get_json(key: str):
    try:
        response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=key)
        return json.loads(response["Body"].read().decode("utf-8"))
    except s3_client.exceptions.NoSuchKey:
        return None
    except Exception as e:
        print(f"Error reading from S3: {e}")
        return None

def put_json(key: str, data: dict):
    try:
        s3_client.put_object(
                Bucket=config.S3_BUCKET,
                Key=key,
                Body=json.dumps(data, indent=2),
                ContentType="application/json",
            )
    except Exception as e:
        print(f"Error writing to S3: {e}")
        raise

def get_role_document_ids(
    role: str,
    email: str ,):


    def extract_names(items):
        names = []
        for item in items:
            if item["type"] == "file":
                # Prefer document_id if available, else strip extension from name
                if "document_id" in item:
                    names.append(item["document_id"])
                else:
                    names.append(item["name"].rsplit(".", 1)[0])
            elif item["type"] == "folder":
                names.extend(extract_names(item["items"]))
        return names

    if role == "admin":
        prefix = f"{email}/files"
        all_items = list_objects_recursive(email, prefix)
        return {"documentNames": extract_names(all_items)}

    # Non-admin: read assignment
    user_json_key = f"{email}/roles/{role}.json"
    if not S3_user.exists(user_json_key):
        raise HTTPException(status_code=404, detail=f"No folder assignment found for role '{role}'.")

    try:
        user_data = S3_user.read_json(user_json_key)
        assignment = FolderAssignment(**user_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read folder assignment: {str(e)}")

    if not assignment.assigned_folders:
        raise HTTPException(status_code=403, detail=f"No folders assigned to role '{role}'.")

    ids = []
    for folder_map in assignment.assigned_folders:
        prefix = f"{email}/files/{folder_map.path}"
        folder_items = list_objects_recursive(email, prefix)
        ids.extend(extract_names(folder_items))

    return {"documentIds": ids}