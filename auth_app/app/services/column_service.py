from auth_app.app.database.connection import get_user_collection
from auth_app.app.schema.ColumnSchema import ColumnAddRequest, ColumnUpdateRequest


class ColumnService:

    @staticmethod
    async def get_all_columns():
        collection = get_user_collection()
        sample_user = await collection.find_one()
        if not sample_user:
            return []
        # Exclude MongoDB internal ID
        return [field for field in sample_user.keys() if field != "_id"]

    @staticmethod
    async def add_column(payload: ColumnAddRequest):
        collection = get_user_collection()
        await collection.update_many(
            {payload.column_name: {"$exists": False}},
            {"$set": {payload.column_name: payload.default_value}},
        )

    @staticmethod
    async def update_column(column_name: str, payload: ColumnUpdateRequest):
        collection = get_user_collection()
        await collection.update_many(
            {column_name: {"$exists": True}},
            {"$set": {column_name: payload.new_value}},
        )

    @staticmethod
    async def delete_column(column_name: str) -> bool:
        collection = get_user_collection()
        result = await collection.update_many(
            {column_name: {"$exists": True}},
            {"$unset": {column_name: ""}},
        )
        return result.modified_count > 0
