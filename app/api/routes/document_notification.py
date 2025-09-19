from fastapi import APIRouter, HTTPException, Response
from fastapi import Depends
from auth_app.app.api.routes.deps import dynamic_permission_check, get_email_from_token, get_user_email_from_token
from repositories.s3_repo import s3_download_json, s3_delete_object, \
    s3_list_objects


router = APIRouter()

@router.get("/notifications", dependencies=[Depends(dynamic_permission_check)])
def get_all_notifications(email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token)):
    prefix = f"{email}/notifications/{user_email}/"
    keys = s3_list_objects(prefix)

    if not keys:
        return []

    notifications = []
    for key in keys:
        notification = s3_download_json(key)
        if notification:
            notifications.append(notification)

    return notifications

@router.delete("/notifications/{notification_id}", dependencies=[Depends(dynamic_permission_check)])
def delete_notification(notification_id: str, email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token)):
    s3_key = f"{email}/notifications/{user_email}/{notification_id}.json"
    s3_delete_object(s3_key)
    return {"message": "Notification deleted"}

@router.get("/notifications/{notification_id}", dependencies=[Depends(dynamic_permission_check)])
def get_notification(notification_id: str, email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token)):
    s3_key = f"{email}/notifications/{user_email}/{notification_id}.json"
    notification = s3_download_json(s3_key)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.delete("/notifications/all", dependencies=[Depends(dynamic_permission_check)])
def delete_all_notifications(email: str = Depends(get_email_from_token), user_email: str = Depends(get_user_email_from_token)):
    prefix = f"{email}/notifications/{user_email}/"
    keys = s3_list_objects(prefix)
    if not keys:
        return {"message": "No notifications to delete"}
    for key in keys:
        s3_delete_object(key)
    return {"message": f"Deleted {len(keys)} notifications"}



