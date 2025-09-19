import sys
from unittest.mock import MagicMock

# Patch database connection BEFORE importing columns
sys.modules["auth_app.app.database.connection"] = MagicMock()

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import HTTPException
from auth_app.app.api.routes import columns

@pytest.mark.asyncio
async def test_get_all_columns_returns_columns():
    mock_columns = [{"name": "col1"}, {"name": "col2"}]
    with patch.object(columns.ColumnService, "get_all_columns", new=AsyncMock(return_value=mock_columns)):
        result = await columns.get_all_columns()
        assert result == mock_columns

@pytest.mark.asyncio
async def test_get_all_columns_returns_empty():
    with patch.object(columns.ColumnService, "get_all_columns", new=AsyncMock(return_value=[])):
        result = await columns.get_all_columns()
        assert result == []

@pytest.mark.asyncio
async def test_get_all_columns_service_exception():
    with patch.object(columns.ColumnService, "get_all_columns", new=AsyncMock(side_effect=Exception("fail"))):
        with pytest.raises(Exception):
            await columns.get_all_columns()

@pytest.mark.asyncio
async def test_add_column_success():
    payload = MagicMock()
    payload.column_name = "new_col"
    with patch.object(columns.ColumnService, "add_column", new=AsyncMock()) as mock_add:
        resp = await columns.add_column(payload)
        mock_add.assert_awaited_once_with(payload)
        assert resp == {"message": "Field 'new_col' added to all users"}

@pytest.mark.asyncio
async def test_add_column_payload_column_name_none():
    payload = MagicMock()
    payload.column_name = None
    with patch.object(columns.ColumnService, "add_column", new=AsyncMock()):
        resp = await columns.add_column(payload)
        assert resp == {"message": "Field 'None' added to all users"}

@pytest.mark.asyncio
async def test_add_column_service_exception():
    payload = MagicMock()
    payload.column_name = "fail_col"
    with patch.object(columns.ColumnService, "add_column", new=AsyncMock(side_effect=Exception("fail"))):
        with pytest.raises(Exception):
            await columns.add_column(payload)

@pytest.mark.asyncio
async def test_update_column_success():
    payload = MagicMock()
    with patch.object(columns.ColumnService, "update_column", new=AsyncMock()) as mock_update:
        resp = await columns.update_column("colA", payload)
        mock_update.assert_awaited_once_with("colA", payload)
        assert resp == {"message": "Field 'colA' updated for all users"}

@pytest.mark.asyncio
async def test_update_column_payload_column_name_empty():
    payload = MagicMock()
    with patch.object(columns.ColumnService, "update_column", new=AsyncMock()):
        resp = await columns.update_column("", payload)
        assert resp == {"message": "Field '' updated for all users"}

@pytest.mark.asyncio
async def test_update_column_service_exception():
    payload = MagicMock()
    with patch.object(columns.ColumnService, "update_column", new=AsyncMock(side_effect=Exception("fail"))):
        with pytest.raises(Exception):
            await columns.update_column("colA", payload)

@pytest.mark.asyncio
async def test_delete_column_success():
    with patch.object(columns.ColumnService, "delete_column", new=AsyncMock(return_value=True)) as mock_del:
        resp = await columns.delete_column("colB")
        mock_del.assert_awaited_once_with("colB")
        assert resp == {"message": "Field 'colB' removed from all users"}

@pytest.mark.asyncio
async def test_delete_column_not_found():
    with patch.object(columns.ColumnService, "delete_column", new=AsyncMock(return_value=False)):
        with pytest.raises(HTTPException) as exc:
            await columns.delete_column("colC")
        assert exc.value.status_code == 400
        assert "not found" in exc.value.detail

@pytest.mark.asyncio
async def test_delete_column_empty_name():
    with patch.object(columns.ColumnService, "delete_column", new=AsyncMock(return_value=False)):
        with pytest.raises(HTTPException) as exc:
            await columns.delete_column("")
        assert exc.value.status_code == 400
        assert "not found" in exc.value.detail

@pytest.mark.asyncio
async def test_delete_column_service_exception():
    with patch.object(columns.ColumnService, "delete_column", new=AsyncMock(side_effect=Exception("fail"))):
        with pytest.raises(Exception):
            await columns.delete_column("colD")