from auth_app.app.api.routes.deps import get_current_user
from auth_app.app.database.connection import get_document_send_count_for_user_this_month, db
from auth_app.app.utils.subscription_plans import SUBSCRIPTION_PLANS



from fastapi import Depends, HTTPException, status

async def get_subscription_status(email: str) -> str:
    try:
        user = await db["users"].find_one({"email": email})
        if not user:
            return "Unknown"
        return user.get("subscription_status", "Unknown")
    except Exception as e:
        # Log error in production environment
        return "Unknown"



async def has_feature(email: str, feature: str) -> bool:
    plan_name = await get_subscription_status(email)
    _plan = plan_name.lower()
    plan = SUBSCRIPTION_PLANS.get(_plan, {})
    return plan.get("features", {}).get(feature, False)

async def check_send_limit(email: str) -> bool:
    plan_name = await get_subscription_status(email)
    _plan = plan_name.lower()
    plan = SUBSCRIPTION_PLANS.get(_plan, {})
    limit = plan.get("limits", {}).get("monthly_send_limit", None)

    if limit is None:
        return True  # Unlimited usage (e.g., enterprise plan)

    current_usage = await get_document_send_count_for_user_this_month(email)  # FIXED: Added `await`
    return current_usage < limit


