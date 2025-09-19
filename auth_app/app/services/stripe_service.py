import stripe
import os
from dotenv import load_dotenv

from config import config
from utils.logger import logger

load_dotenv()
stripe.api_key =config.STRIPE_SECRET_KEY


class StripeService:
    @staticmethod
    def check_subscription_by_email(email: str, subscription_status: str) -> str:
        if config.ENV != "prod":
            return config.DEV_SUB

        # Mapping from Stripe price_id to plan name
        price_id_to_plan = {
            "price_1RnYsdKETjoHFd8cuHJLUTvi": "Free",
            "price_1RtXaqKETjoHFd8c1SF0uTJV": "Starter",
            "price_1RtXaqKETjoHFd8c0z18ugi3": "Professional",
            "price_1RtXaqKETjoHFd8czn4U0ozr": "Enterprise",
            "price_1RtXaqKETjoHFd8cy3H7kXju": "Starter",
            "price_1RtXaqKETjoHFd8clWY9QTib": "Professional",
            "price_1RtbJqKETjoHFd8clu6OEoAQ": "Enterprise"
        }

        try:
            customers = stripe.Customer.list(email=email).data
            if not customers:
                return f"Customer not found for {email}"
            customer_id = customers[0].id
            subscriptions = stripe.Subscription.list(customer=customer_id, status="all").data

            active_subs = [sub for sub in subscriptions if sub.status == "active" or "trialing"]

            if not active_subs:
                return f"No active subscription found for {email} for the {subscription_status} plan."

            price_id = active_subs[0].plan.id

            plan_name = price_id_to_plan.get(price_id, "Unknown Plan")
            return plan_name

        except Exception as e:
            return f"Subscription check failed: {str(e)}"
