from fastapi import APIRouter, Depends, HTTPException

from auth_app.app.api.routes.deps import require_roles, dynamic_permission_check
from auth_app.app.schema.ColumnSchema import ColumnAddRequest, ColumnUpdateRequest
from auth_app.app.schema.token_schema import UserTokenData
from auth_app.app.services.column_service import ColumnService

from central_logger import CentralLogger
logger = CentralLogger.get_logger()

router = APIRouter()

@router.get("/get-all-columns", dependencies=[Depends(dynamic_permission_check)])
async def get_all_columns():
    logger.info("Fetching all columns")
    return await ColumnService.get_all_columns()

@router.post("/add-column", dependencies=[Depends(dynamic_permission_check)])
async def add_column(
    payload: ColumnAddRequest
):
    await ColumnService.add_column(payload)
    logger.info(f"Added column: {payload.column_name}")
    return {"message": f"Field '{payload.column_name}' added to all users"}

@router.put("/{column_name}", dependencies=[Depends(dynamic_permission_check)])
async def update_column(
    column_name: str,
    payload: ColumnUpdateRequest
):
    await ColumnService.update_column(column_name, payload)
    logger.info(f"Updated column: {column_name}")
    return {"message": f"Field '{column_name}' updated for all users"}

@router.delete("/{column_name}", dependencies=[Depends(dynamic_permission_check)])
async def delete_column(
    column_name: str,
):
    success = await ColumnService.delete_column(column_name)
    if success:
        logger.info(f"Deleted column: {column_name}")
        return {"message": f"Field '{column_name}' removed from all users"}
    logger.error(f"Column not found for deletion: {column_name}")
    raise HTTPException(status_code=400, detail=f"Field '{column_name}' not found")