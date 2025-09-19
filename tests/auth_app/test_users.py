import sys
from unittest.mock import MagicMock

# Patch BEFORE any app imports!
mock_db_module = MagicMock()
mock_db_module.db = MagicMock()
mock_db_module.DB_NAME = "testdb"
mock_db_module.async_client = MagicMock()
sys.modules['auth_app.app.database.connection'] = mock_db_module

import pytest
from unittest.mock import patch, AsyncMock
from fastapi import HTTPException
from auth_app.app.api.routes import users as users_module
import sys
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_get_all_users():
    mock_users = [{"_id": "1", "name": "A"}, {"_id": "2", "name": "B"}]
    with patch.object(users_module.UserCRUD, "get_all_users", new=AsyncMock(return_value=mock_users)):
        users = await users_module.get_all_users()
        assert users[0]["id"] == "1"
        assert users[1]["id"] == "2"
        assert "_id" not in users[0]

@pytest.mark.asyncio
async def test_get_users_created_by_me_admin():
    mock_user = {"id": "adminid", "role": "admin"}
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[{"_id": "1", "name": "A"}])
    with patch.object(users_module, "db") as mock_db:
        mock_db.__getitem__.return_value.find.return_value = mock_cursor
        users = await users_module.get_users_created_by_me(current_user=mock_user)
        assert users[0]["id"] == "1"

@pytest.mark.asyncio
async def test_get_users_created_by_me_non_admin():
    mock_user = {"id": "uid", "role": "user"}
    with pytest.raises(HTTPException) as exc:
        await users_module.get_users_created_by_me(current_user=mock_user)
    assert exc.value.status_code == 403

@pytest.mark.asyncio
async def test_get_user_found():
    with patch.object(users_module.UserCRUD, "get_user_by_email", new=AsyncMock(return_value={"id": "1"})):
        user = await users_module.get_user("test@example.com")
        assert user["id"] == "1"

@pytest.mark.asyncio
async def test_get_user_not_found():
    with patch.object(users_module.UserCRUD, "get_user_by_email", new=AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as exc:
            await users_module.get_user("test@example.com")
        assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_update_user_success():
    with patch.object(users_module.UserCRUD, "update_user_by_email", new=AsyncMock(return_value=True)):
        resp = await users_module.update_user("test@example.com", user_data=MagicMock())
        assert resp["message"] == "User updated successfully"

@pytest.mark.asyncio
async def test_update_user_not_found():
    with patch.object(users_module.UserCRUD, "update_user_by_email", new=AsyncMock(return_value=False)):
        with pytest.raises(HTTPException) as exc:
            await users_module.update_user("test@example.com", user_data=MagicMock())
        assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_delete_user_success():
    with patch.object(users_module.UserCRUD, "deactivate_user_by_email", new=AsyncMock(return_value=True)):
        resp = await users_module.delete_user("test@example.com")
        assert resp["message"] == "User deleted successfully"

@pytest.mark.asyncio
async def test_delete_user_not_found():
    with patch.object(users_module.UserCRUD, "deactivate_user_by_email", new=AsyncMock(return_value=False)):
        with pytest.raises(HTTPException) as exc:
            await users_module.delete_user("test@example.com")
        assert exc.value.status_code == 404

def test_assign_role_to_user_success():
    mock_result = MagicMock(modified_count=1)
    with patch.object(users_module, "db") as mock_db:
        mock_db.__getitem__.return_value.update_one.return_value = mock_result
        payload = MagicMock(email="a", role="admin")
        resp = users_module.assign_role_to_user(payload=payload)
        assert resp["msg"] == "Roles assigned to user"

def test_assign_role_to_user_not_found():
    mock_result = MagicMock(modified_count=0)
    with patch.object(users_module, "db") as mock_db:
        mock_db.__getitem__.return_value.update_one.return_value = mock_result
        payload = MagicMock(email="a", role="admin")
        resp = users_module.assign_role_to_user(payload=payload)
        assert resp["msg"] == "User not found or roles unchanged"

@pytest.mark.asyncio
async def test_upload_signatures():
    mock_doc = {"signatures": []}
    mock_update = MagicMock(modified_count=1, upserted_id=None)
    with patch.object(users_module, "db") as mock_db:
        mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=mock_doc)
        mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=mock_update)
        # Patch BEFORE any app imports!
        mock_db_module = MagicMock()
        mock_db_module.db = MagicMock()
        mock_db_module.DB_NAME = "testdb"
        mock_db_module.async_client = MagicMock()
        sys.modules['auth_app.app.database.connection'] = mock_db_module


        @pytest.mark.asyncio
        async def test_get_me():
            user = {"id": "1", "email": "a@b.com"}
            resp = await users_module.get_me(current_user=user)
            assert resp == user

        @pytest.mark.asyncio
        async def test_get_all_users_empty():
            with patch.object(users_module.UserCRUD, "get_all_users", new=AsyncMock(return_value=[])):
                users = await users_module.get_all_users()
                assert users == []

        @pytest.mark.asyncio
        async def test_get_users_created_by_me_empty():
            mock_user = {"id": "adminid", "role": "admin"}
            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(return_value=[])
            with patch.object(users_module, "db") as mock_db:
                mock_db.__getitem__.return_value.find.return_value = mock_cursor
                users = await users_module.get_users_created_by_me(current_user=mock_user)
                assert users == []

        @pytest.mark.asyncio
        async def test_get_user_found_with_extra_fields():
            with patch.object(users_module.UserCRUD, "get_user_by_email", new=AsyncMock(return_value={"id": "1", "foo": "bar"})):
                user = await users_module.get_user("test@example.com")
                assert user["id"] == "1"
                assert user["foo"] == "bar"

        @pytest.mark.asyncio
        async def test_update_user_partial_update():
            with patch.object(users_module.UserCRUD, "update_user_by_email", new=AsyncMock(return_value=True)):
                resp = await users_module.update_user("test@example.com", user_data=MagicMock())
                assert resp["message"] == "User updated successfully"

        @pytest.mark.asyncio
        async def test_delete_user_already_deleted():
            with patch.object(users_module.UserCRUD, "deactivate_user_by_email", new=AsyncMock(return_value=False)):
                with pytest.raises(HTTPException) as exc:
                    await users_module.delete_user("deleted@example.com")
                assert exc.value.status_code == 404

        def test_assign_role_to_user_db_error():
            with patch.object(users_module, "db") as mock_db:
                mock_db.__getitem__.return_value.update_one.side_effect = Exception("DB error")
                payload = MagicMock(email="a", role="admin")
                with pytest.raises(Exception):
                    users_module.assign_role_to_user(payload=payload)

        @pytest.mark.asyncio
        async def test_upload_signatures_multiple():
            mock_doc = {"signatures": []}
            mock_update = MagicMock(modified_count=2, upserted_id=None)
            with patch.object(users_module, "db") as mock_db:
                mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=mock_doc)
                mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=mock_update)
                sig1 = MagicMock(name="sig1", type="draw", value="val", isDefault=True)
                sig2 = MagicMock(name="sig2", type="draw", value="val2", isDefault=False)
                resp = await users_module.upload_signatures([sig1, sig2], email="test@example.com")
                assert resp["msg"] == "Signatures added"
                assert len(resp["added_signatures"]) == 2

        @pytest.mark.asyncio
        async def test_upload_signatures_existing_duplicate_name():
            mock_doc = {"signatures": [{"id": "old", "name": "sig1", "type": "draw", "value": "v", "isDefault": False}]}
            mock_update = MagicMock(modified_count=1, upserted_id=None)
            with patch.object(users_module, "db") as mock_db:
                mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=mock_doc)
                mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=mock_update)
                sig = MagicMock(name="sig1", type="draw", value="val", isDefault=True)
                resp = await users_module.upload_signatures([sig], email="test@example.com")
                assert resp["msg"] == "Signatures added"
                assert any(s["name"] == "sig1" for s in resp["added_signatures"])

        @pytest.mark.asyncio
        async def test_get_signatures_with_name_and_no_signatures():
            doc = {"signatures": []}
            with patch.object(users_module, "db") as mock_db:
                mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
                with pytest.raises(HTTPException) as exc:
                    await users_module.get_signatures(name="sig1", email="test@example.com")
                assert exc.value.status_code == 404

        @pytest.mark.asyncio
        async def test_delete_signatures_by_name_empty_list():
            doc = {"signatures": []}
            mock_update = MagicMock(modified_count=1)
            with patch.object(users_module, "db") as mock_db:
                mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
                mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=mock_update)
                resp = await users_module.delete_signatures(name="sig1", email="test@example.com")
                assert resp["msg"] == "Signature with name sig1 deleted"

        @pytest.mark.asyncio
        async def test_get_all_signatures_empty():
            doc = {"signatures": []}
            with patch.object(users_module, "db") as mock_db:
                mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
                resp = await users_module.get_all_signatures(email="test@example.com")
                assert resp["signatures"] == []

        @pytest.mark.asyncio
        async def test_update_signature_set_isDefault_true_resets_others():
            doc = {"signatures": [
                {"name": "sig1", "isDefault": False},
                {"name": "sig2", "isDefault": True}
            ]}
            mock_update = MagicMock(modified_count=1)
            update_req = MagicMock(old_name="sig1", new_name=None, isDefault=True)
            with patch.object(users_module, "db") as mock_db:
                mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
                mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=mock_update)
                resp = await users_module.update_signature(update_req=update_req, email="test@example.com")
                assert resp["msg"] == "Signature updated"
                assert any(s["name"] == "sig1" and s["isDefault"] for s in resp["signatures"])
                assert not any(s["name"] == "sig2" and s["isDefault"] for s in resp["signatures"])

        @pytest.mark.asyncio
        async def test_update_signature_db_update_error():
            doc = {"signatures": [{"name": "sig1", "isDefault": False}]}
            update_req = MagicMock(old_name="sig1", new_name="sig2", isDefault=True)
            with patch.object(users_module, "db") as mock_db:
                mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
                mock_db.__getitem__.return_value.update_one.side_effect = Exception("DB error")
                with pytest.raises(Exception):
                    await users_module.update_signature(update_req=update_req, email="test@example.com")
        with pytest.raises(HTTPException) as exc:
            await users_module.get_signatures(name="sig2", email="test@example.com")
        assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_delete_signatures_all():
    doc = {"signatures": [{"name": "sig1"}]}
    mock_update = MagicMock(modified_count=1)
    with patch.object(users_module, "db") as mock_db:
        mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
        mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=mock_update)
        resp = await users_module.delete_signatures(email="test@example.com")
        assert resp["msg"] == "All signatures deleted"

@pytest.mark.asyncio
async def test_delete_signatures_by_name():
    doc = {"signatures": [{"name": "sig1"}, {"name": "sig2"}]}
    mock_update = MagicMock(modified_count=1)
    with patch.object(users_module, "db") as mock_db:
        mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
        mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=mock_update)
        resp = await users_module.delete_signatures(name="sig1", email="test@example.com")
        assert resp["msg"] == "Signature with name sig1 deleted"

@pytest.mark.asyncio
async def test_delete_signatures_not_found():
    with patch.object(users_module, "db") as mock_db:
        mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc:
            await users_module.delete_signatures(email="test@example.com")
        assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_get_all_signatures_found():
    doc = {"signatures": [{"name": "sig1"}]}
    with patch.object(users_module, "db") as mock_db:
        mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
        resp = await users_module.get_all_signatures(email="test@example.com")
        assert resp["signatures"][0]["name"] == "sig1"

@pytest.mark.asyncio
async def test_get_all_signatures_not_found():
    with patch.object(users_module, "db") as mock_db:
        mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=None)
        resp = await users_module.get_all_signatures(email="test@example.com")
        assert resp["signatures"] == []

@pytest.mark.asyncio
async def test_update_signature_success():
    doc = {"signatures": [{"name": "sig1", "isDefault": False}]}
    # Patch BEFORE any app imports!
    mock_db_module = MagicMock()
    mock_db_module.db = MagicMock()
    mock_db_module.DB_NAME = "testdb"
    mock_db_module.async_client = MagicMock()
    sys.modules['auth_app.app.database.connection'] = mock_db_module


    @pytest.mark.asyncio
    async def test_get_me():
        user = {"id": "1", "email": "a@b.com"}
        resp = await users_module.get_me(current_user=user)
        assert resp == user

    @pytest.mark.asyncio
    async def test_get_all_users():
        mock_users = [{"_id": "1", "name": "A"}, {"_id": "2", "name": "B"}]
        with patch.object(users_module.UserCRUD, "get_all_users", new=AsyncMock(return_value=mock_users)):
            users = await users_module.get_all_users()
            assert users[0]["id"] == "1"
            assert users[1]["id"] == "2"
            assert "_id" not in users[0]

    @pytest.mark.asyncio
    async def test_get_users_created_by_me_admin():
        mock_user = {"id": "adminid", "role": "admin"}
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[{"_id": "1", "name": "A"}])
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find.return_value = mock_cursor
            users = await users_module.get_users_created_by_me(current_user=mock_user)
            assert users[0]["id"] == "1"

    @pytest.mark.asyncio
    async def test_get_users_created_by_me_non_admin():
        mock_user = {"id": "uid", "role": "user"}
        with pytest.raises(HTTPException) as exc:
            await users_module.get_users_created_by_me(current_user=mock_user)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_user_found():
        with patch.object(users_module.UserCRUD, "get_user_by_email", new=AsyncMock(return_value={"id": "1"})):
            user = await users_module.get_user("test@example.com")
            assert user["id"] == "1"

    @pytest.mark.asyncio
    async def test_get_user_not_found():
        with patch.object(users_module.UserCRUD, "get_user_by_email", new=AsyncMock(return_value=None)):
            with pytest.raises(HTTPException) as exc:
                await users_module.get_user("test@example.com")
            assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_user_success():
        with patch.object(users_module.UserCRUD, "update_user_by_email", new=AsyncMock(return_value=True)):
            resp = await users_module.update_user("test@example.com", user_data=MagicMock())
            assert resp["message"] == "User updated successfully"

    @pytest.mark.asyncio
    async def test_update_user_not_found():
        with patch.object(users_module.UserCRUD, "update_user_by_email", new=AsyncMock(return_value=False)):
            with pytest.raises(HTTPException) as exc:
                await users_module.update_user("test@example.com", user_data=MagicMock())
            assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_user_success():
        with patch.object(users_module.UserCRUD, "deactivate_user_by_email", new=AsyncMock(return_value=True)):
            resp = await users_module.delete_user("test@example.com")
            assert resp["message"] == "User deleted successfully"

    @pytest.mark.asyncio
    async def test_delete_user_not_found():
        with patch.object(users_module.UserCRUD, "deactivate_user_by_email", new=AsyncMock(return_value=False)):
            with pytest.raises(HTTPException) as exc:
                await users_module.delete_user("test@example.com")
            assert exc.value.status_code == 404

    def test_assign_role_to_user_success():
        mock_result = MagicMock(modified_count=1)
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.update_one.return_value = mock_result
            payload = MagicMock(email="a", role="admin")
            resp = users_module.assign_role_to_user(payload=payload)
            assert resp["msg"] == "Roles assigned to user"

    def test_assign_role_to_user_not_found():
        mock_result = MagicMock(modified_count=0)
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.update_one.return_value = mock_result
            payload = MagicMock(email="a", role="admin")
            resp = users_module.assign_role_to_user(payload=payload)
            assert resp["msg"] == "User not found or roles unchanged"

    @pytest.mark.asyncio
    async def test_upload_signatures():
        mock_doc = {"signatures": []}
        mock_update = MagicMock(modified_count=1, upserted_id=None)
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=mock_doc)
            mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=mock_update)
            sig = MagicMock(name="sig1", type="draw", value="val", isDefault=True)
            resp = await users_module.upload_signatures([sig], email="test@example.com")
            assert resp["msg"] == "Signatures added"
            assert resp["modified"] == 1

    @pytest.mark.asyncio
    async def test_upload_signatures_existing():
        mock_doc = {"signatures": [{"id": "old", "name": "oldsig", "type": "draw", "value": "v", "isDefault": False}]}
        mock_update = MagicMock(modified_count=1, upserted_id=None)
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=mock_doc)
            mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=mock_update)
            sig = MagicMock(name="sig2", type="draw", value="val2", isDefault=False)
            resp = await users_module.upload_signatures([sig], email="test@example.com")
            assert resp["msg"] == "Signatures added"
            assert len(resp["added_signatures"]) == 1

    @pytest.mark.asyncio
    async def test_get_signatures_found():
        doc = {"signatures": [{"name": "sig1"}]}
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
            resp = await users_module.get_signatures(email="test@example.com")
            assert resp["signatures"][0]["name"] == "sig1"

    @pytest.mark.asyncio
    async def test_get_signatures_not_found():
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=None)
            resp = await users_module.get_signatures(email="test@example.com")
            assert resp["signatures"] == []

    @pytest.mark.asyncio
    async def test_get_signatures_by_name_found():
        doc = {"signatures": [{"name": "sig1"}]}
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
            resp = await users_module.get_signatures(name="sig1", email="test@example.com")
            assert resp["signature"]["name"] == "sig1"

    @pytest.mark.asyncio
    async def test_get_signatures_by_name_not_found():
        doc = {"signatures": [{"name": "sig1"}]}
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
            with pytest.raises(HTTPException) as exc:
                await users_module.get_signatures(name="sig2", email="test@example.com")
            assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_signatures_all():
        doc = {"signatures": [{"name": "sig1"}]}
        mock_update = MagicMock(modified_count=1)
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
            mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=mock_update)
            resp = await users_module.delete_signatures(email="test@example.com")
            assert resp["msg"] == "All signatures deleted"

    @pytest.mark.asyncio
    async def test_delete_signatures_by_name():
        doc = {"signatures": [{"name": "sig1"}, {"name": "sig2"}]}
        mock_update = MagicMock(modified_count=1)
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
            mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=mock_update)
            resp = await users_module.delete_signatures(name="sig1", email="test@example.com")
            assert resp["msg"] == "Signature with name sig1 deleted"

    @pytest.mark.asyncio
    async def test_delete_signatures_not_found():
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=None)
            with pytest.raises(HTTPException) as exc:
                await users_module.delete_signatures(email="test@example.com")
            assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_all_signatures_found():
        doc = {"signatures": [{"name": "sig1"}]}
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
            resp = await users_module.get_all_signatures(email="test@example.com")
            assert resp["signatures"][0]["name"] == "sig1"

    @pytest.mark.asyncio
    async def test_get_all_signatures_not_found():
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=None)
            resp = await users_module.get_all_signatures(email="test@example.com")
            assert resp["signatures"] == []

    @pytest.mark.asyncio
    async def test_update_signature_success():
        doc = {"signatures": [{"name": "sig1", "isDefault": False}]}
        mock_update = MagicMock(modified_count=1)
        update_req = MagicMock(old_name="sig1", new_name="sig2", isDefault=True)
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
            mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=mock_update)
            resp = await users_module.update_signature(update_req=update_req, email="test@example.com")
            assert resp["msg"] == "Signature updated"
            assert resp["signatures"][0]["name"] == "sig2"
            assert resp["signatures"][0]["isDefault"] is True

    @pytest.mark.asyncio
    async def test_update_signature_not_found():
        doc = {"signatures": [{"name": "sig1", "isDefault": False}]}
        update_req = MagicMock(old_name="sig2", new_name=None, isDefault=None)
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
            with pytest.raises(HTTPException) as exc:
                await users_module.update_signature(update_req=update_req, email="test@example.com")
            assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_signature_no_signatures():
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=None)
            update_req = MagicMock(old_name="sig1", new_name="sig2", isDefault=True)
            with pytest.raises(HTTPException) as exc:
                await users_module.update_signature(update_req=update_req, email="test@example.com")
            assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_signature_no_update_fields():
        doc = {"signatures": [{"name": "sig1", "isDefault": False}]}
        update_req = MagicMock(old_name="sig1", new_name=None, isDefault=None)
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
            with pytest.raises(HTTPException) as exc:
                await users_module.update_signature(update_req=update_req, email="test@example.com")
            assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_signature_set_isDefault_false():
        doc = {"signatures": [{"name": "sig1", "isDefault": True}, {"name": "sig2", "isDefault": False}]}
        mock_update = MagicMock(modified_count=1)
        update_req = MagicMock(old_name="sig1", new_name=None, isDefault=False)
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
            mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=mock_update)
            resp = await users_module.update_signature(update_req=update_req, email="test@example.com")
            assert resp["msg"] == "Signature updated"
            assert resp["signatures"][0]["isDefault"] is False

    @pytest.mark.asyncio
    async def test_upload_signatures_upsert():
        mock_doc = None
        mock_update = MagicMock(modified_count=0, upserted_id="newid")
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=mock_doc)
            mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=mock_update)
            sig = MagicMock(name="sig1", type="draw", value="val", isDefault=True)
            resp = await users_module.upload_signatures([sig], email="test@example.com")
            assert resp["upserted"] is True

    @pytest.mark.asyncio
    async def test_delete_signatures_by_name_not_found():
        doc = {"signatures": [{"name": "sig1"}]}
        mock_update = MagicMock(modified_count=0)
        with patch.object(users_module, "db") as mock_db:
            mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)
            mock_db.__getitem__.return_value.update_one = AsyncMock(return_value=mock_update)
            resp = await users_module.delete_signatures(name="sig2", email="test@example.com")
            assert resp["msg"] == "Signature with name sig2 deleted"