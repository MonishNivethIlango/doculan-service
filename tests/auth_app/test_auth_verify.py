import sys
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel, EmailStr

# Patch all external dependencies before import
sys.modules["auth_app.app.database.connection"] = MagicMock()
sys.modules["app.services.email_service"] = MagicMock()
sys.modules["auth_app.app.api.routes.deps"] = MagicMock()
sys.modules["auth_app.app.services.auth_service"] = MagicMock()
sys.modules["auth_app.app.utils.auth_utils"] = MagicMock()
sys.modules["auth_app.app.utils"] = MagicMock()
sys.modules["auth_app.app.utils.security"] = MagicMock()
sys.modules["config"] = MagicMock()
sys.modules["utils.logger"] = MagicMock()

# Provide dummy schema classes for FastAPI to use
class DummyTokenResponse(BaseModel):
    access_token: str = "tok"
    token_type: str = "bearer"
    is_temp_password: bool = False
    subscription_status: str = "free"

class DummyUserLogin(BaseModel):
    email: EmailStr = "test@example.com"
    password: str = "pw"

class DummyPreferencesUpdate(BaseModel):
    timezone: str = None
    theme: str = "dark"

class DummyUserCreate(BaseModel):
    email: EmailStr = "test@example.com"
    password: str = "pw"

class DummyUserCreateAdmin(BaseModel):
    email: EmailStr = "test@example.com"
    password: str = "pw"

class DummyAdminUserCreate(BaseModel):
    email: EmailStr = "test@example.com"
    password: str = "pw"

# Patch the schema modules with these dummy classes
import types
authschema = types.SimpleNamespace(
    TokenResponse=DummyTokenResponse,
    UserLogin=DummyUserLogin,
    PreferencesUpdate=DummyPreferencesUpdate
)
userschema = types.SimpleNamespace(
    UserCreate=DummyUserCreate,
    UserCreateAdmin=DummyUserCreateAdmin,
    AdminUserCreate=DummyAdminUserCreate
)
sys.modules["auth_app.app.schema.AuthSchema"] = authschema
sys.modules["auth_app.app.schema.UserSchema"] = userschema

import pytest
from fastapi import HTTPException, Response, Request
from auth_app.app.api.routes import auth_verify


@pytest.mark.asyncio
async def test_protected_route():
    resp = await auth_verify.protected_route()
    assert resp == {"message": "You are authenticated!"}

@pytest.mark.asyncio
async def test_register_user_success():
    user = MagicMock()
    user.email = "test@example.com"
    with patch.object(auth_verify.AuthService, "register_user", new=AsyncMock(return_value="uid123")):
        resp = await auth_verify.register_user(user)
        assert resp == {"message": "User registered", "user_id": "uid123"}

@pytest.mark.asyncio
async def test_register_user_by_admin_success():
    user = MagicMock()
    current_user = {"role": "admin", "id": "id", "email": "admin@x.com", "subscription_status": "free"}
    with patch.object(auth_verify.AuthService, "register_user", new=AsyncMock(return_value="uid")), \
         patch.object(auth_verify, "EmailService") as MockEmailService:
        # Make EmailService() return a mock whose send_credentials_email is an AsyncMock
        instance = MockEmailService.return_value
        instance.send_credentials_email = AsyncMock()
        resp = await auth_verify.register_user_by_admin(user, current_user)
        assert resp["user_id"] == "uid"

@pytest.mark.asyncio
async def test_login_user_success():
    user = MagicMock()
    user.email = "test@example.com"
    user.password = "pw"
    db_user = {"is_temp_password": False}
    with patch.object(auth_verify.AuthService, "authenticate_user", new=AsyncMock(return_value=db_user)), \
         patch.object(auth_verify.AuthService, "create_token", new=AsyncMock(return_value=("tok", "free", "refresh"))), \
         patch.object(auth_verify, "config") as mock_config:
        mock_config.ENV = "dev"
        response = MagicMock()
        resp = await auth_verify.login_user(user, response)
        assert resp.token_type == "bearer"
        assert resp.access_token == "tok"
        assert resp.subscription_status == "free"
        response.set_cookie.assert_called_once()

@pytest.mark.asyncio
async def test_login_user_invalid_credentials():
    user = MagicMock()
    user.email = "test@example.com"
    user.password = "pw"
    with patch.object(auth_verify.AuthService, "authenticate_user", new=AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as exc:
            await auth_verify.login_user(user, MagicMock())
        assert exc.value.status_code == 401

@pytest.mark.asyncio
async def test_login_user_invalid_plan_prod():
    user = MagicMock()
    user.email = "test@example.com"
    user.password = "pw"
    db_user = {"is_temp_password": False}
    with patch.object(auth_verify.AuthService, "authenticate_user", new=AsyncMock(return_value=db_user)), \
         patch.object(auth_verify.AuthService, "create_token", new=AsyncMock(return_value=("tok", "invalid", "refresh"))), \
         patch.object(auth_verify, "config") as mock_config:
        mock_config.ENV = "prod"
        response = MagicMock()
        with pytest.raises(HTTPException) as exc:
            await auth_verify.login_user(user, response)
        assert exc.value.status_code == 403

@pytest.mark.asyncio
async def test_refresh_token_success():
    request = MagicMock()
    request.cookies.get.return_value = "refresh"
    with patch.object(auth_verify, "verify_token", return_value={
        "sub": "sub", "id": "id", "role": "role", "name": "name",
        "user_email": "user_email", "email": "email", "subscription_status": "free"
    }), patch.object(auth_verify, "create_access_token", return_value="newtoken"):
        response = MagicMock()
        resp = await auth_verify.refresh_token(request, response)
        assert resp == {"access_token": "newtoken", "token_type": "bearer"}

@pytest.mark.asyncio
async def test_refresh_token_missing_cookie():
    request = MagicMock()
    request.cookies.get.return_value = None
    with pytest.raises(HTTPException) as exc:
        await auth_verify.refresh_token(request, MagicMock())
    assert exc.value.status_code == 401

@pytest.mark.asyncio
async def test_refresh_token_invalid_token():
    request = MagicMock()
    request.cookies.get.return_value = "refresh"
    with patch.object(auth_verify, "verify_token", return_value=None):
        with pytest.raises(HTTPException) as exc:
            await auth_verify.refresh_token(request, MagicMock())
        assert exc.value.status_code == 401

def test_logout():
    response = MagicMock()
    resp = auth_verify.logout(response)
    response.delete_cookie.assert_called_once_with("refresh_token")
    assert resp == {"message": "Logged out"}

@pytest.mark.asyncio
async def test_forgot_password_success():
    email = "test@example.com"
    user = {"email": email, "name": "Test"}
    users = MagicMock()
    users.find_one = AsyncMock(return_value=user)
    users.update_one = AsyncMock()
    with patch.object(auth_verify.db, "__getitem__", return_value=users), \
         patch.object(auth_verify.security, "hash_password", return_value="hashed"), \
         patch.object(auth_verify, "EmailService") as mailer:
        mailer.return_value.send_email = MagicMock()
        resp = await auth_verify.forgot_password(email)
        assert resp == {"message": "Temporary password sent to your email"}

@pytest.mark.asyncio
async def test_forgot_password_user_not_found():
    email = "test@example.com"
    users = MagicMock()
    users.find_one = AsyncMock(return_value=None)
    with patch.object(auth_verify.db, "__getitem__", return_value=users):
        with pytest.raises(HTTPException) as exc:
            await auth_verify.forgot_password(email)
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_register_user_by_admin_not_admin():
    user = MagicMock()
    current_user = {"role": "user"}
    with pytest.raises(HTTPException) as exc:
        await auth_verify.register_user_by_admin(user, current_user)
    assert exc.value.status_code == 403

@pytest.mark.asyncio
async def test_register_user_by_admin_value_error():
    user = MagicMock()
    current_user = {"role": "admin", "id": "id", "email": "admin@x.com", "subscription_status": "free"}
    with patch.object(auth_verify.AuthService, "register_user", new=AsyncMock(side_effect=ValueError("fail"))):
        with pytest.raises(HTTPException) as exc:
            await auth_verify.register_user_by_admin(user, current_user)
        assert exc.value.status_code == 400

@pytest.mark.asyncio
async def test_update_user_preferences_success():
    preferences = MagicMock()
    preferences.timezone = None
    preferences.dict.return_value = {"theme": "dark"}
    current_user = {"id": "uid"}
    with patch.object(auth_verify.AuthService, "update_user_preferences", new=AsyncMock(return_value=True)):
        resp = await auth_verify.update_user_preferences(preferences, current_user)
        assert resp == {"message": "Preferences updated successfully"}

@pytest.mark.asyncio
async def test_update_user_preferences_invalid_timezone():
    preferences = MagicMock()
    preferences.timezone = "bad"
    preferences.dict.return_value = {"theme": "dark"}
    current_user = {"id": "uid"}
    with patch.object(auth_verify.AuthService, "validate_timezone", return_value=False):
        with pytest.raises(HTTPException) as exc:
            await auth_verify.update_user_preferences(preferences, current_user)
        assert exc.value.status_code == 400

@pytest.mark.asyncio
async def test_update_user_preferences_user_not_found():
    preferences = MagicMock()
    preferences.timezone = None
    preferences.dict.return_value = {"theme": "dark"}
    current_user = {"id": "uid"}
    with patch.object(auth_verify.AuthService, "update_user_preferences", new=AsyncMock(return_value=False)):
        with pytest.raises(HTTPException) as exc:
            await auth_verify.update_user_preferences(preferences, current_user)
        assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_update_password_success():
    current_user = {"email": "test@example.com"}
    with patch.object(auth_verify.security, "hash_password", return_value="hashed"), \
         patch.object(auth_verify.db["users"], "update_one", new=AsyncMock(return_value=MagicMock(modified_count=1))):
        resp = await auth_verify.update_password("newpassword", current_user)
        assert resp == {"message": "Password updated successfully"}

@pytest.mark.asyncio
async def test_update_password_too_short():
    current_user = {"email": "test@example.com"}
    with pytest.raises(HTTPException) as exc:
        await auth_verify.update_password("short", current_user)
    assert exc.value.status_code == 400

@pytest.mark.asyncio
async def test_update_password_failed():
    current_user = {"email": "test@example.com"}
    with patch.object(auth_verify.security, "hash_password", return_value="hashed"), \
         patch.object(auth_verify.db["users"], "update_one", new=AsyncMock(return_value=MagicMock(modified_count=0))):
        with pytest.raises(HTTPException) as exc:
            await auth_verify.update_password("longenough", current_user)
        assert exc.value.status_code == 400

@pytest.mark.asyncio
async def test_change_password_success():
    current_user = {"email": "test@example.com"}
    user = {"hashed_password": "oldhash"}
    with patch.object(auth_verify.db["users"], "find_one", new=AsyncMock(return_value=user)), \
         patch.object(auth_verify.security, "verify_password", return_value=True), \
         patch.object(auth_verify.security, "hash_password", return_value="hashed"), \
         patch.object(auth_verify.db["users"], "update_one", new=AsyncMock(return_value=MagicMock(modified_count=1))):
        resp = await auth_verify.change_password("oldpassword", "newpassword", current_user)
        assert resp == {"message": "Password changed successfully"}

@pytest.mark.asyncio
async def test_change_password_user_not_found():
    current_user = {"email": "test@example.com"}
    with patch.object(auth_verify.db["users"], "find_one", new=AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as exc:
            await auth_verify.change_password("old", "newpassword", current_user)
        assert exc.value.status_code == 404

@pytest.mark.asyncio
async def test_change_password_wrong_old():
    current_user = {"email": "test@example.com"}
    user = {"hashed_password": "oldhash"}
    with patch.object(auth_verify.db["users"], "find_one", new=AsyncMock(return_value=user)), \
         patch.object(auth_verify.security, "verify_password", return_value=False):
        with pytest.raises(HTTPException) as exc:
            await auth_verify.change_password("oldpassword", "newpassword", current_user)
        assert exc.value.status_code == 400

@pytest.mark.asyncio
async def test_change_password_new_too_short():
    current_user = {"email": "test@example.com"}
    user = {"hashed_password": "oldhash"}
    with patch.object(auth_verify.db["users"], "find_one", new=AsyncMock(return_value=user)), \
         patch.object(auth_verify.security, "verify_password", return_value=True):
        with pytest.raises(HTTPException) as exc:
            await auth_verify.change_password("oldpassword", "short", current_user)
        assert exc.value.status_code == 400

@pytest.mark.asyncio
async def test_change_password_update_failed():
    current_user = {"email": "test@example.com"}
    user = {"hashed_password": "oldhash"}
    with patch.object(auth_verify.db["users"], "find_one", new=AsyncMock(return_value=user)), \
         patch.object(auth_verify.security, "verify_password", return_value=True), \
         patch.object(auth_verify.security, "hash_password", return_value="hashed"), \
         patch.object(auth_verify.db["users"], "update_one", new=AsyncMock(return_value=MagicMock(modified_count=0))):
        with pytest.raises(HTTPException) as exc:
            await auth_verify.change_password("oldpassword", "newpassword", current_user)
        assert exc.value.status_code == 400