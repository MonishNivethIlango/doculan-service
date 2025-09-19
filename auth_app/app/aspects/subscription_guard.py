from fastapi import Depends, HTTPException, status
from datetime import datetime

from auth_app.app.services.subscription_service import (
    has_feature, check_send_limit
)
from auth_app.app.database.connection import increment_send_counter_for_user
from auth_app.app.api.routes.deps import get_email_from_token, get_user_email_from_token


async def enforce_send_document_policy(email: str = Depends(get_user_email_from_token)):
    if not await has_feature(email, "can_send_doc"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your subscription does not allow sending documents."
        )

    if not await check_send_limit(email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You have exceeded your monthly document E-Sign limit."
        )

    # Track successful usage
    now = datetime.utcnow()
    await increment_send_counter_for_user(email, now.year, now.month)

# def enforce_send_document_policy_logic(email: str):
#     if not has_feature(email, "can_send_doc"):
#         raise HTTPException(status_code=403, detail="Your plan does not allow document sending.")
#     if not check_send_limit(email):
#         raise HTTPException(status_code=429, detail="Monthly send limit exceeded.")
#     increment_send_counter_for_user(email, datetime.utcnow().year, datetime.utcnow().month)
