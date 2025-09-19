import sys
from unittest.mock import AsyncMock, MagicMock

# Patch db before importing admin_router
sys.modules["auth_app.app.database.connection"] = MagicMock()
import pytest
from fastapi import HTTPException
from auth_app.app.api.routes import admin

@pytest.mark.asyncio
async def test_get_routes_grouped_by_tag_basic():
    mock_routes = [
        {"path": "/a", "method": "GET", "name": "A", "tags": ["tag1"]},
        {"path": "/b", "method": "POST", "name": "B", "tags": ["tag2"]},
        {"path": "/c", "method": "GET", "name": "C"},  # Untagged
    ]
    admin.db.routes.find.return_value.to_list = AsyncMock(return_value=mock_routes)
    result = await admin.get_routes_grouped_by_tag()
    assert "tag1" in result
    assert "tag2" in result
    assert "Untagged" in result
    assert {"path": "/a", "method": "GET", "name": "A"} in result["tag1"]
    assert {"path": "/b", "method": "POST", "name": "B"} in result["tag2"]
    assert {"path": "/c", "method": "GET", "name": "C"} in result["Untagged"]

@pytest.mark.asyncio
async def test_get_routes_grouped_by_tag_duplicate():
    mock_routes = [
        {"path": "/a", "method": "GET", "name": "A", "tags": ["tag1"]},
        {"path": "/a", "method": "GET", "name": "A", "tags": ["tag1"]},
    ]
    admin.db.routes.find.return_value.to_list = AsyncMock(return_value=mock_routes)
    result = await admin.get_routes_grouped_by_tag()
    assert len(result["tag1"]) == 1

@pytest.mark.asyncio
async def test_create_or_update_role_success():
    payload = MagicMock()
    payload.role_name = "admin"
    payload.api_permissions = ["perm1"]
    payload.ui_permissions = [MagicMock(dict=MagicMock(return_value={"ui": "perm"}))]
    admin.db.__getitem__.return_value.update_one = AsyncMock()
    resp = await admin.create_or_update_role(payload)
    admin.db.__getitem__.return_value.update_one.assert_awaited_once()
    assert resp == {"msg": "Role 'admin' created/updated"}

@pytest.mark.asyncio
async def test_get_all_roles_returns_roles():
    mock_roles = [
        {"_id": "id1", "role_name": "admin"},
        {"_id": "id2", "role_name": "user"},
    ]
    admin.db.roles.find.return_value.to_list = AsyncMock(return_value=mock_roles)
    # Patch convert_objectid to just return the role for simplicity
    result = await admin.get_all_roles()
    assert isinstance(result, list)
    assert all("_id" in r for r in result)

@pytest.mark.asyncio
async def test_get_permission_matrix_basic():
    mock_roles = [
        {"name": "admin", "permissions": [{"method": "GET", "path": "/a"}]},
        {"name": "user", "permissions": []},
    ]
    mock_routes = [
        {"path": "/a", "method": "GET", "tags": ["tag1"]},
        {"path": "/b", "method": "POST", "tags": ["tag2"]},
    ]
    admin.db.roles.find.return_value.to_list = AsyncMock(return_value=mock_roles)
    admin.db.routes.find.return_value.to_list = AsyncMock(return_value=mock_routes)
    matrix = await admin.get_permission_matrix()
    assert isinstance(matrix, list)
    assert matrix[0]["admin"] is True
    assert matrix[0]["user"] is False
    assert matrix[1]["admin"] is False
    assert matrix[1]["user"] is False

@pytest.mark.asyncio
async def test_get_permission_matrix_empty():
    admin.db.roles.find.return_value.to_list = AsyncMock(return_value=[])
    admin.db.routes.find.return_value.to_list = AsyncMock(return_value=[])
    matrix = await admin.get_permission_matrix()
    assert matrix == []

@pytest.mark.asyncio
async def test_get_routes_grouped_by_tag_empty():
    admin.db.routes.find.return_value.to_list = AsyncMock(return_value=[])
    result = await admin.get_routes_grouped_by_tag()
    assert result == {}

@pytest.mark.asyncio
async def test_get_all_roles_empty():
    admin.db.roles.find.return_value.to_list = AsyncMock(return_value=[])
    result = await admin.get_all_roles()
    assert result == []