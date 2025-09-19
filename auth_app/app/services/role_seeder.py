# app/core/role_seeder.py
from auth_app.app.database.connection import db
from auth_app.app.utils.default_roles import default_roles


async def seed_default_roles():
    for role in default_roles:
        existing_role = await db["roles"].find_one({"role_name": role["role_name"]})

        if not existing_role or existing_role["permissions"] != role["permissions"]:
            await db["roles"].update_one(
                {"role_name": role["role_name"]},
                {"$set": {"permissions": role["permissions"]}},
                upsert=True
            )
