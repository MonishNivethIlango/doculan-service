"""
Apache Drill query examples for the document signing platform.

These queries demonstrate how to query the flattened metadata structure
stored in S3 for analytics and reporting purposes.
"""

# Sample Apache Drill queries for document analytics

DRILL_QUERIES = {
    "completed_documents": """
        SELECT 
            document_id,
            tracking_id,
            owner_email,
            created_at,
            tracking_status_timestamp
        FROM s3.`bucket-name/*/metadata/tracking/*/*`
        WHERE tracking_status = 'completed'
        ORDER BY tracking_status_timestamp DESC
    """,

    "documents_by_status": """
        SELECT 
            tracking_status,
            COUNT(*) as count,
            owner_email
        FROM s3.`bucket-name/*/metadata/tracking/*/*`
        GROUP BY tracking_status, owner_email
        ORDER BY owner_email, tracking_status
    """,

    "party_signing_analytics": """
        SELECT 
            parties_0_email as signer_email,
            parties_0_status as status,
            COUNT(*) as document_count,
            AVG(DATEDIFF(parties_0_status_timestamp, created_at)) as avg_days_to_sign
        FROM s3.`bucket-name/*/metadata/tracking/*/*`
        WHERE parties_0_email IS NOT NULL
        GROUP BY parties_0_email, parties_0_status
    """,

    "field_type_usage": """
        SELECT 
            fields_0_type as field_type,
            COUNT(*) as usage_count,
            SUM(CASE WHEN fields_0_signed = true THEN 1 ELSE 0 END) as signed_count
        FROM s3.`bucket-name/*/metadata/tracking/*/*`
        WHERE fields_0_type IS NOT NULL
        GROUP BY fields_0_type
        ORDER BY usage_count DESC
    """,

    "document_completion_time": """
        SELECT 
            document_id,
            tracking_id,
            created_at,
            tracking_status_timestamp,
            DATEDIFF(tracking_status_timestamp, created_at) as days_to_complete
        FROM s3.`bucket-name/*/metadata/tracking/*/*`
        WHERE tracking_status = 'completed'
        ORDER BY days_to_complete DESC
    """,

    "user_activity_summary": """
        SELECT 
            owner_email,
            COUNT(DISTINCT document_id) as total_documents,
            COUNT(*) as total_trackings,
            SUM(CASE WHEN tracking_status = 'completed' THEN 1 ELSE 0 END) as completed_trackings,
            SUM(CASE WHEN tracking_status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_trackings,
            SUM(CASE WHEN tracking_status = 'expired' THEN 1 ELSE 0 END) as expired_trackings
        FROM s3.`bucket-name/*/metadata/tracking/*/*`
        GROUP BY owner_email
        ORDER BY total_trackings DESC
    """,

    "audit_trail_analysis": """
        SELECT 
            action,
            COUNT(*) as action_count,
            COUNT(DISTINCT actor_email) as unique_actors,
            MIN(timestamp) as first_occurrence,
            MAX(timestamp) as last_occurrence
        FROM s3.`bucket-name/*/audit/global_audit.json`
        GROUP BY action
        ORDER BY action_count DESC
    """,

    "geographic_usage": """
        SELECT 
            location_info_country as country,
            location_info_city as city,
            COUNT(*) as action_count,
            COUNT(DISTINCT actor_email) as unique_users
        FROM s3.`bucket-name/*/audit/global_audit.json`
        WHERE location_info_country IS NOT NULL
        GROUP BY location_info_country, location_info_city
        ORDER BY action_count DESC
    """,

    "device_browser_analytics": """
        SELECT 
            device_info_browser as browser,
            device_info_os as operating_system,
            device_info_device as device_type,
            COUNT(*) as usage_count
        FROM s3.`bucket-name/*/audit/global_audit.json`
        WHERE device_info_browser IS NOT NULL
        GROUP BY device_info_browser, device_info_os, device_info_device
        ORDER BY usage_count DESC
    """,

    "monthly_document_trends": """
        SELECT 
            EXTRACT(YEAR FROM CAST(created_at AS TIMESTAMP)) as year,
            EXTRACT(MONTH FROM CAST(created_at AS TIMESTAMP)) as month,
            COUNT(*) as documents_created,
            SUM(CASE WHEN tracking_status = 'completed' THEN 1 ELSE 0 END) as documents_completed
        FROM s3.`bucket-name/*/metadata/tracking/*/*`
        GROUP BY EXTRACT(YEAR FROM CAST(created_at AS TIMESTAMP)), 
                 EXTRACT(MONTH FROM CAST(created_at AS TIMESTAMP))
        ORDER BY year DESC, month DESC
    """
}


def get_drill_query(query_name: str, bucket_name: str = "your-bucket-name") -> str:
    """
    Get a Drill query with the bucket name replaced

    Args:
        query_name: Name of the query from DRILL_QUERIES
        bucket_name: S3 bucket name to use in the query

    Returns:
        Formatted Drill query string
    """
    if query_name not in DRILL_QUERIES:
        raise ValueError(f"Query '{query_name}' not found. Available queries: {list(DRILL_QUERIES.keys())}")

    query = DRILL_QUERIES[query_name]
    return query.replace("bucket-name", bucket_name)


def list_available_queries() -> list:
    """List all available Drill queries"""
    return list(DRILL_QUERIES.keys())