SUBSCRIPTION_PLANS = {
    # Public Plans
    "free": {
        "features": {
            "can_send_doc": True
        },
        "limits": {
            "monthly_send_limit": 10
        }
    },
    "starter": {
        "features": {
            "can_send_doc": True
        },
        "limits": {
            "monthly_send_limit": 50
        }
    },
    "professional": {
        "features": {
            "can_send_doc": True
        },
        "limits": {
            "monthly_send_limit": None
        }
    },
    "enterprise": {
        "features": {
            "can_send_doc": True
        },
        "limits": {
            "monthly_send_limit": 300  # unlimited
        }
    },

    # Developer Plans (for internal testing)
    "developer-free": {
        "features": {
            "can_send_doc": True
        },
        "limits": {
            "monthly_send_limit": 10
        }
    },
    "developer-starter": {
        "features": {
            "can_send_doc": True
        },
        "limits": {
            "monthly_send_limit": 50
        }
    },
    "developer-professional": {
        "features": {
            "can_send_doc": True
        },
        "limits": {
            "monthly_send_limit": None
        }
    },
    "developer-enterprise": {
        "features": {
            "can_send_doc": True
        },
        "limits": {
            "monthly_send_limit": 300  # unlimited
        }
    }
}
