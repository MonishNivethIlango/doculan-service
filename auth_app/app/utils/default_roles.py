default_roles = [
    {
        "role_name": "admin",
        "api_permissions": [
            # File Operation
            {"method": "POST", "url": "/files/upload/"},
            {"method": "GET", "url": "/files/"},
            {"method": "GET", "url": "/files/{document_id}"},
            {"method": "DELETE", "url": "/files/{document_id}"},
            {"method": "GET", "url": "/files/folder-structure"},
            {"method": "DELETE", "url": "/files/folders/"},
            {"method": "PUT", "url": "/files/move/"},
            # E-Sign Template
            {"method": "POST", "url": "/templates"},
            {"method": "GET", "url": "/templates"},
            {"method": "GET", "url": "/templates/{template_name}"},
            {"method": "PUT", "url": "/templates/{template_name}"},
            {"method": "DELETE", "url": "/templates/{template_name}"},
            # Document Tracking
            {"method": "POST", "url": "/documents/send"},
            {"method": "POST", "url": "/documents/resend"},
            {"method": "GET", "url": "/documents/status"},
            {"method": "GET", "url": "/documents/all-status"},
            {"method": "GET", "url": "/documents/party-status"},
            {"method": "POST", "url": "/documents/send-otp"},
            {"method": "POST", "url": "/documents/verify-otp"},
            {"method": "POST", "url": "/documents/sign"},
            {"method": "GET", "url": "/documents/signed-pdf"},
            {"method": "POST", "url": "/documents/log-action"},
            {"method": "GET", "url": "/documents/tracking-ids/"},
            {"method": "GET", "url": "/documents/trackings-status"},
            {"method": "GET", "url": "/documents/complete-certificates"},
            {"method": "GET", "url": "/documents/merged-pdf"},
            {"method": "GET", "url": "/documents/signed-package"},
            {"method": "POST", "url": "/documents/upload-attachment"},
            # Notifications
            {"method": "DELETE", "url": "/notifications/{notification_id}"},
            {"method": "GET", "url": "/notifications"},
            {"method": "GET", "url": "/notifications/{notification_id}"},
            # AI
            {"method": "POST", "url": "/summarize"},
            {"method": "POST", "url": "/ask-pdf"},
            {"method": "POST", "url": "/generate"},
            # Forms
            {"method": "POST", "url": "/forms/"},
            {"method": "GET", "url": "/forms/"},
            {"method": "GET", "url": "/forms/{form_id}"},
            {"method": "PUT", "url": "/forms/{form_id}"},
            {"method": "DELETE", "url": "/forms/{form_id}"},
            {"method": "POST", "url": "/forms/send"},
            {"method": "POST", "url": "/forms/resend"},
            {"method": "POST", "url": "/forms/{form_id}/cancel"},
            {"method": "POST", "url": "/forms/submit"},
            {"method": "POST", "url": "/forms/send-otp"},
            {"method": "POST", "url": "/forms/verify-otp"},
            {"method": "GET", "url": "/forms/{form_id}/trackings"},
            {"method": "GET", "url": "/forms/{form_id}/parties/{party_email}/download"},
            {"method": "GET", "url": "/forms/{form_id}/statuses"},
            {"method": "GET", "url": "/forms/statuses/count"},
            {"method": "GET", "url": "/forms/trackings-status/count"},
            {"method": "GET", "url": "/forms/{form_id}/trackings/status"},
            {"method": "GET", "url": "/forms/trackings/all"},
            {"method": "POST", "url": "/forms/upload-attachments"},
            {"method": "GET", "url": "/forms/{form_id}/{party_email}/attachments"},
            {"method": "GET", "url": "/forms/merged/pdf"},
            {"method": "GET", "url": "/forms/{form_id}/attachments/{filename"},

            # User Management
            {"method": "POST", "url": "/auth/register-by-admin"},
            {"method": "GET", "url": "/users/get-my-users"},
            {"method": "PUT", "url": "/users/{user_email}"},
            {"method": "DELETE", "url": "/users/{user_email}"},
            {"method": "POST", "url": "/add-column"},
            {"method": "GET", "url": "/get-all-columns"},
            {"method": "PUT", "url": "/{column_name}"},
            {"method": "POST", "url": "/roles"},
            {"method": "POST", "url": "/users/assign-role"},
            {"method": "POST", "url": "/users/signatures/upload"},
            {"method": "GET", "url": "/users/signatures/get"},
            {"method": "GET", "url": "/users/signatures/get-all"},
            {"method": "PUT", "url": "/users/signatures/update"},
            {"method": "DELETE", "url": "/users/signatures/delete"},

            # Settings
            {"method": "PUT", "url": "/auth/user/preferences"},
            {"method": "GET", "url": "/settings"},

            # Contacts
            {"method": "POST", "url": "/contacts/"},
            {"method": "GET", "url": "/contacts/"},
            {"method": "GET", "url": "/contacts/{contact_id}"},
            {"method": "PUT", "url": "/contacts/{contact_id}"},
            {"method": "DELETE", "url": "/contacts/{contact_id}"}
        ],
        "ui_permissions": [
            {"page": "sidebar",
             "content_permissions": ["dashboard", "documents", "templates", "forms", "team", "contact", "integration"]},
            {"page": "dashboard", "content_permissions": []},
            {"page": "documents",
             "content_permissions": ["uploadFile", "createFolder", "actions", "editFolder", "deleteFolder",
                                     "previewFile", "downloadFile", "deleteFile", "cancelFile",
                                     "resendFile", "auditFile"]},
            {"page": "user-list", "content_permissions": []},
            {"page": "pdf-viewer",
             "content_permissions": ["eSign", "summarize", "downloadFile", "deleteFile"]},
            {"page": "pdf-esign", "content_permissions": ["deleteTemplate", "saveTemplate"]},
            {"page": "templates", "content_permissions": []},
            {"page": "template-viewer", "content_permissions": []},
            {"page": "forms",
             "content_permissions": ["createForm", "actions", "viewFormValues", "cloneForm",
                                     "deleteForm", "auditForm", "viewForm", "downloadForm", "resendForm",
                                     "cancelForm"]},
            {"page": "form-viewer", "content_permissions": []},
            {"page": "team", "content_permissions": []},
            {"page": "roles", "content_permissions": []},
            {"page": "contact", "content_permissions": []},
            {"page": "integration", "content_permissions": []},
            {"page": "profile", "content_permissions": []},
            {"page": "plans", "content_permissions": []},
            {"page": "settings", "content_permissions": []}
        ]
    },
    {
        "role_name": "editor",
        "api_permissions": [
            {"method": "POST", "url": "/files/upload/"},
            {"method": "GET", "url": "/files/"},
            {"method": "GET", "url": "/files/{document_id}"},
            {"method": "DELETE", "url": "/files/{document_id}"},
            {"method": "GET", "url": "/files/folder-structure"},
            {"method": "DELETE", "url": "/files/folders/"},
            {"method": "PUT", "url": "/files/move/"},
            # // E-Sign Template
            {"method": "POST", "url": "/templates"},
            {"method": "GET", "url": "/templates"},
            {"method": "GET", "url": "/templates/{template_name}"},
            {"method": "PUT", "url": "/templates/{template_name}"},
            {"method": "DELETE", "url": "/templates/{template_name}"},
            # // Document Tracking
            {"method": "POST", "url": "/documents/send"},
            {"method": "POST", "url": "/documents/update"},
            {"method": "POST", "url": "/documents/resend"},
            {"method": "GET", "url": "/documents/status"},
            {"method": "GET", "url": "/documents/all-status"},
            {"method": "GET", "url": "/documents/party-status"},
            {"method": "POST", "url": "/documents/send-otp"},
            {"method": "POST", "url": "/documents/verify-otp"},
            {"method": "POST", "url": "/documents/sign"},
            {"method": "GET", "url": "/documents/signed-pdf"},
            {"method": "POST", "url": "/documents/log-action"},
            {"method": "GET", "url": "/documents/tracking-ids/"},
            {"method": "GET", "url": "/documents/trackings-status"},
            {"method": "GET", "url": "/documents/complete-certificates"},
            {"method": "GET", "url": "/documents/merged-pdf"},
            {"method": "GET", "url": "/documents/signed-package"},
            {"method": "POST", "url": "/documents/upload-attachment"},
            {"method": "POST", "url": "/roles"},
            {"method": "GET", "url": "/roles"},
            {"method": "PUT", "url": "/roles"},
            {"method": "POST", "url": "/auth/change-password"},

            # Notifications
            {"method": "DELETE", "url": "/notifications/{notification_id}"},
            {"method": "GET", "url": "/notifications"},
            {"method": "GET", "url": "/notifications/{notification_id}"},
            # AI
            {"method": "POST", "url": "/ai-assistants/summarize"},
            {"method": "POST", "url": "/ai-assistants/ask-pdf"},
            {"method": "POST", "url": "/ai-assistants/generate"},
            # Forms
            {"method": "POST", "url": "/forms/"},
            {"method": "GET", "url": "/forms/"},
            {"method": "GET", "url": "/forms/{form_id}"},
            {"method": "PUT", "url": "/forms/{form_id}"},
            {"method": "POST", "url": "/forms/send"},
            {"method": "POST", "url": "/forms/resend"},
            {"method": "POST", "url": "/forms/{form_id}/cancel"},
            {"method": "POST", "url": "/forms/submit"},
            {"method": "POST", "url": "/forms/send-otp"},
            {"method": "POST", "url": "/forms/verify-otp"},
            {"method": "GET", "url": "/forms/{form_id}/trackings"},
            {"method": "GET", "url": "/forms/{form_id}/parties/{party_email}/download"},
            {"method": "GET", "url": "/forms/{form_id}/statuses"},
            {"method": "GET", "url": "/forms/statuses/count"},
            {"method": "GET", "url": "/forms/trackings-status/count"},
            {"method": "GET", "url": "/forms/{form_id}/trackings/status"},
            {"method": "GET", "url": "/forms/trackings/all"},
            {"method": "POST", "url": "/forms/upload-attachments"},
            {"method": "GET", "url": "/forms/{form_id}/{party_email}/attachments"},
            {"method": "GET", "url": "/forms/merged/pdf"},
            {"method": "GET", "url": "/forms/{form_id}/attachments/{filename"},

            # Profile
            {"method": "PUT", "url": "/users/{user_email}"},

            # Settings
            {"method": "PUT", "url": "/auth/user/preferences"},
            {"method": "PUT", "url": "/auth/logout"},
            {"method": "GET", "url": "/settings"},

            # Default Signatures
            {"method": "POST", "url": "/users/signatures/upload"},
            {"method": "GET", "url": "/users/signatures/get"},
            {"method": "GET", "url": "/users/signatures/get-all"},
            {"method": "PUT", "url": "/users/signatures/update"},
            {"method": "DELETE", "url": "/users/signatures/delete"},

            # Contacts
            {"method": "POST", "url": "/contacts/"},
            {"method": "GET", "url": "/contacts/"},
            {"method": "GET", "url": "/contacts/{contact_id}"},
            {"method": "PUT", "url": "/contacts/{contact_id}"},
            {"method": "DELETE", "url": "/contacts/{contact_id}"},
        ],
        "ui_permissions": [
            {"page": "sidebar", "content_permissions": ["dashboard", "documents", "templates", "forms", "contact"]},
            {"page": "dashboard", "content_permissions": []},
            {"page": "documents",
             "content_permissions": ["uploadFile", "createFolder", "actions", "editFolder", "deleteFolder",
                                     "previewFile", "downloadFile", "deleteFile", "cancelFile",
                                     "resendFile", "auditFile"]},
            {"page": "user-list", "content_permissions": []},
            {"page": "pdf-viewer",
             "content_permissions": ["eSign", "summarize", "downloadFile", "deleteFile"]},
            {"page": "pdf-esign", "content_permissions": ["deleteTemplate", "saveTemplate"]},
            {"page": "templates", "content_permissions": []},
            {"page": "template-viewer", "content_permissions": []},
            {"page": "forms",
             "content_permissions": ["createForm", "actions", "viewFormValues", "cloneForm",
                                     "deleteForm", "auditForm", "viewForm", "downloadForm", "resendForm",
                                     "cancelForm"]},
            {"page": "form-viewer", "content_permissions": []},
            {"page": "contact", "content_permissions": []},
            {"page": "profile", "content_permissions": []},
            {"page": "settings", "content_permissions": []},
        ]
    },
    {
        "role_name": "viewer",
        "api_permissions": [
            # // File Operation
            {"method": "GET", "url": "/files/"},
            {"method": "GET", "url": "/files/{document_id}"},
            {"method": "GET", "url": "/files/folder-structure"},

            # // E-Sign Template
            {"method": "GET", "url": "/templates"},
            {"method": "GET", "url": "/templates/{template_name}"},

            # // Document Tracking
            {"method": "GET", "url": "/documents/status"},
            {"method": "GET", "url": "/documents/all-status"},
            {"method": "GET", "url": "/documents/party-status"},
            {"method": "GET", "url": "/documents/signed-pdf"},
            {"method": "GET", "url": "/documents/tracking-ids/"},
            {"method": "GET", "url": "/documents/trackings-status"},
            {"method": "GET", "url": "/documents/complete-certificates"},
            {"method": "GET", "url": "/documents/merged-pdf"},
            {"method": "GET", "url": "/documents/signed-package"},
            {"method": "POST", "url": "/documents/upload-attachment"},
            {"method": "GET", "url": "/roles"},
            {"method": "POST", "url": "/auth/change-password"},

            # Notifications
            {"method": "DELETE", "url": "/notifications/{notification_id}"},
            {"method": "GET", "url": "/notifications"},
            {"method": "GET", "url": "/notifications/{notification_id}"},

            # AI
            {"method": "POST", "url": "/ai-assistants/summarize"},
            {"method": "POST", "url": "/ai-assistants/ask-pdf"},
            {"method": "POST", "url": "/ai-assistants/generate"},
            # Forms
            {"method": "GET", "url": "/forms/"},
            {"method": "GET", "url": "/forms/{form_id}"},
            {"method": "GET", "url": "/forms/{form_id}/trackings"},
            {"method": "GET", "url": "/forms/{form_id}/parties/{party_email}/download"},
            {"method": "GET", "url": "/forms/{form_id}/statuses"},
            {"method": "GET", "url": "/forms/statuses/count"},
            {"method": "GET", "url": "/forms/trackings-status/count"},
            {"method": "GET", "url": "/forms/{form_id}/trackings/status"},
            {"method": "GET", "url": "/forms/trackings/all"},
            {"method": "GET", "url": "/forms/{form_id}/{party_email}/attachments"},
            {"method": "GET", "url": "/forms/merged/pdf"},
            {"method": "GET", "url": "/forms/{form_id}/attachments/{filename"},

            # Profile
            {"method": "PUT", "url": "/users/{user_email}"},

            # Settings
            {"method": "GET", "url": "/settings"},
            {"method": "PUT", "url": "/auth/user/preferences"},
            {"method": "PUT", "url": "/auth/logout"},

            # Contacts
            {"method": "GET", "url": "/contacts/"},
            {"method": "GET", "url": "/contacts/{contact_id}"},
        ],
        "ui_permissions": [
            {"page": "sidebar", "content_permissions": ["dashboard", "documents", "forms", "contact"]},
            {"page": "dashboard"},
            {"page": "documents",
             "content_permissions": ["actions", "previewFile", "downloadFile", "auditFile"]},
            {"page": "user-list", "content_permissions": []},
            {"page": "pdf-viewer", "content_permissions": ["summarize", "downloadFile"]},
            {"page": "forms", "content_permissions": ["actions", "viewFormValues", "auditForm", "viewForm", "downloadForm"]},
            {"page": "form-viewer", "content_permissions": []},
            {"page": "contact", "content_permissions": []},
            {"page": "profile", "content_permissions": []},
            {"page": "settings", "content_permissions": []},
        ]

    },
    {
        "role_name": "signer",
        "api_permissions": [
            # // File Operation
            {"method": "GET", "url": "/files/"},
            {"method": "GET", "url": "/files/{document_id}"},
            {"method": "GET", "url": "/files/folder-structure"},
            # // E-Sign Template
            {"method": "GET", "url": "/templates"},
            {"method": "GET", "url": "/templates/{template_name}"},
            # // Document Tracking
            {"method": "POST", "url": "/documents/send"},
            {"method": "POST", "url": "/documents/resend"},
            {"method": "GET", "url": "/documents/status"},
            {"method": "GET", "url": "/documents/all-status"},
            {"method": "GET", "url": "/documents/party-status"},
            {"method": "GET", "url": "/documents/signed-pdf"},
            {"method": "GET", "url": "/documents/tracking-ids/"},
            {"method": "GET", "url": "/documents/trackings-status"},
            {"method": "GET", "url": "/documents/complete-certificates"},
            {"method": "GET", "url": "/documents/merged-pdf"},
            {"method": "GET", "url": "/documents/signed-package"},
            {"method": "POST", "url": "/documents/upload-attachment"},
            {"method": "GET", "url": "/roles"},
            {"method": "POST", "url": "/auth/change-password"},

            # Notifications
            {"method": "DELETE", "url": "/notifications/{notification_id}"},
            {"method": "GET", "url": "/notifications"},
            {"method": "GET", "url": "/notifications/{notification_id}"},
            # AI
            {"method": "POST", "url": "/ai-assistants/summarize"},
            {"method": "POST", "url": "/ai-assistants/ask-pdf"},
            {"method": "POST", "url": "/ai-assistants/generate"},

            # Profile
            {"method": "PUT", "url": "/users/{user_email}"},

            # // Settings
            {"method": "PUT", "url": "/auth/user/preferences"},
            {"method": "GET", "url": "/settings"},
            {"method": "PUT", "url": "/auth/logout"},

            # Default Signatures
            {"method": "POST", "url": "/users/signatures/upload"},
            {"method": "GET", "url": "/users/signatures/get"},
            {"method": "GET", "url": "/users/signatures/get-all"},
            {"method": "PUT", "url": "/users/signatures/update"},
            {"method": "DELETE", "url": "/users/signatures/delete"},

            # Contacts
            {"method": "POST", "url": "/contacts/"},
            {"method": "GET", "url": "/contacts/"},
            {"method": "GET", "url": "/contacts/{contact_id}"},
            {"method": "PUT", "url": "/contacts/{contact_id}"},
            {"method": "DELETE", "url": "/contacts/{contact_id}"},

        ],
        "ui_permissions": [
            {"page": "sidebar", "content_permissions": ["dashboard", "documents", "contact"]},
            {"page": "dashboard", "content_permissions": []},
            {"page": "documents",
             "content_permissions": ["actions", "previewFile", "downloadFile", "resendFile",
                                     "auditFile"]},
            {"page": "user-list", "content_permissions": []},
            {"page": "pdf-viewer", "content_permissions": ["eSign", "summarize", "downloadFile"]},
            {"page": "pdf-esign", "content_permissions": []},
            {"page": "profile", "content_permissions": []},
            {"page": "settings", "content_permissions": []},
            {"page": "contact", "content_permissions": []},
        ]
    },
    {
        "role_name": "third-party",
        "api_permissions": [
            {"method": "POST", "url": "/documents/send-otp"},
            {"method": "POST", "url": "/documents/verify-otp"},
            {"method": "POST", "url": "/documents/log-action"},
            {"method": "POST", "url": "/documents/sign"},
            {"method": "GET", "url": "/documents/signed-pdf"},
            {"method": "GET", "url": "/documents/status"},
            {"method": "GET", "url": "/files/{document_id}"},
            {"method": "GET", "url": "/documents/party-status"},
            {"method": "GET", "url": "/documents/complete-certificates"},
            {"method": "GET", "url": "/documents/merged-pdf"},
            {"method": "GET", "url": "/documents/signed-package"},
            {"method": "POST", "url": "/documents/upload-attachment"},
            {"method": "GET", "url": "/users/signatures/get-all"},
            {"method": "GET", "url": "/roles"},

            # // AI
            {"method": "POST", "url": "/ai-assistants/summarize"},
            {"method": "POST", "url": "/ai-assistants/ask-pdf"},

        ],
        "ui_permissions": []
    },
    {
        "role_name": "third-party-form",
        "api_permissions": [
            {"method": "POST", "url": "/forms/send-otp"},
            {"method": "POST", "url": "/forms/verify-otp"},
            {"method": "POST", "url": "/forms/submit"},
            {"method": "GET", "url": "/forms/{form_id}"},
            {"method": "GET", "url": "/users/current-user"},
            {"method": "GET", "url": "/forms/{form_id}/trackings/status"},
            {"method": "GET", "url": "/forms/merged/pdf"},
            {"method": "GET", "url": "/forms/{form_id}/parties/{party_email}/download"},
            {"method": "GET", "url": "/forms/{form_id}/{party_email}/attachments"},
            {"method": "POST", "url": "/forms/upload-attachments"},
            {"method": "GET", "url": "/roles"},

            # // AI
            {"method": "POST", "url": "/ai-assistants/summarize"},
            {"method": "POST", "url": "/ai-assistants/ask-pdf"},
        ],
        "ui_permissions": []
    }
]


# app/core/role_initializer.py
from motor.motor_asyncio import AsyncIOMotorDatabase


async def seed_roles(db: AsyncIOMotorDatabase):
    collection = db.default_roles  # use one collection for default roles

    for role in default_roles:
        if role["role_name"] == "admin":
            continue  # Skip admin; handled separately with dynamic route seeding

        existing = await collection.find_one({"role_name": role["role_name"]})

        if existing:
            should_update = (
                existing.get("api_permissions", []) != role["api_permissions"] or
                existing.get("ui_permissions", []) != role["ui_permissions"]
            )
            if should_update:
                await collection.update_one(
                    {"role_name": role["role_name"]},
                    {"$set": {
                        "api_permissions": role["api_permissions"],
                        "ui_permissions": role["ui_permissions"]
                    }}
                )
                print(f"🔄 Updated role: {role['role_name']}")
            else:
                print(f"✅ Role already up-to-date: {role['role_name']}")
        else:
            await collection.insert_one(role)
            print(f"✨ Inserted new role: {role['role_name']}")




from fastapi.routing import APIRoute


async def seed_admin_role_with_dynamic_routes(db: AsyncIOMotorDatabase, app):
    # Step 1: Collect all routes as dynamic api_permissions
    collection = db.default_roles
    routes_info = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                if method not in {"HEAD", "OPTIONS"}:
                    routes_info.append({
                        "method": method,
                        "url": route.path
                    })

    # Remove duplicates
    unique_routes = {(r["method"], r["url"]): r for r in routes_info}
    api_permissions = list(unique_routes.values())

    # Step 2: Define static ui_permissions
    ui_permissions = [
        {"page": "sidebar",
         "content_permissions": ["dashboard", "documents", "templates", "forms", "team", "contact", "integration"]},
        {"page": "dashboard", "content_permissions": []},
        {"page": "documents",
         "content_permissions": ["uploadFile", "createFolder", "actions", "editFolder", "deleteFolder",
                                 "previewFile", "downloadFile", "deleteFile", "cancelFile",
                                 "resendFile", "auditFile"]},
        {"page": "user-list", "content_permissions": []},
        {"page": "pdf-viewer",
         "content_permissions": ["eSign", "summarize", "downloadFile", "deleteFile"]},
        {"page": "pdf-esign", "content_permissions": ["deleteTemplate", "saveTemplate"]},
        {"page": "templates", "content_permissions": []},
        {"page": "template-viewer", "content_permissions": []},
        {"page": "forms",
         "content_permissions": ["createForm", "actions", "viewFormValues", "cloneForm",
                                 "deleteForm", "auditForm", "viewForm", "downloadForm", "resendForm",
                                 "cancelForm"]},
        {"page": "form-viewer", "content_permissions": []},
        {"page": "team", "content_permissions": []},
        {"page": "roles", "content_permissions": []},
        {"page": "contact", "content_permissions": []},
        {"page": "integration", "content_permissions": []},
        {"page": "profile", "content_permissions": []},
        {"page": "plans", "content_permissions": []},
        {"page": "settings", "content_permissions": []}
    ]

    # Step 3: Upsert admin role
    await collection.update_one(
        {"role_name": "admin"},
        {
            "$set": {
                "api_permissions": api_permissions,
                "ui_permissions": ui_permissions
            }
        },
        upsert=True
    )
    print(f"✅ Admin role seeded with {len(api_permissions)} dynamic API permissions and static UI permissions.")


async def seed_client_role(db: AsyncIOMotorDatabase):
    client_allowed_patterns = [
        ("POST", "/send-otp"),
        ("POST", "/api/verify-otp"),
        ("POST", "/api/sign"),
        ("GET", "/api/signed-pdf"),
        ("GET", "/api/document/party-status"),
        ("GET", "/file/{document_id}"),
    ]

    api_permissions = [{"method": m, "url": u} for m, u in client_allowed_patterns]

    await db.roles.update_one(
        {"role_name": "client"},
        {"$set": {
            "api_permissions": api_permissions,
            "ui_permissions": []
        }},
        upsert=True
    )
    print(f"✅ Client role seeded with {len(api_permissions)} static permissions.")