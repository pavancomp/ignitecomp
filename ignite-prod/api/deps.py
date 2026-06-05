"""
API dependencies: JWT auth, RBAC, audit logging.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import get_settings
from db.connection import get_db
from db.models import AdminUser, AuditLog, UserRole

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


def create_access_token(data: dict) -> str:
    from datetime import timedelta
    import copy
    payload = copy.deepcopy(data)
    payload["exp"] = (
        datetime.now(tz=timezone.utc)
        + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    ).timestamp()
    payload["type"] = "access"
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    from datetime import timedelta
    import copy
    payload = copy.deepcopy(data)
    payload["exp"] = (
        datetime.now(tz=timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    ).timestamp()
    payload["type"] = "refresh"
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("sub")
        token_type: str = payload.get("type")
        if user_id is None or token_type != "access":
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = await db.get(AdminUser, int(user_id))
    if not user or not user.is_active:
        raise credentials_exc
    return user


def require_role(*roles: UserRole):
    """Factory — returns a dependency that checks the user has one of the given roles."""
    async def _check(current_user: AdminUser = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {[r.value for r in roles]}",
            )
        return current_user
    return _check


require_admin   = require_role(UserRole.ADMIN)
require_finance = require_role(UserRole.ADMIN, UserRole.FINANCE)
require_viewer  = require_role(UserRole.ADMIN, UserRole.FINANCE, UserRole.VIEWER)


async def write_audit(
    db: AsyncSession,
    actor_id: Optional[int],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    old_value: Optional[dict] = None,
    new_value: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    ip = None
    if request:
        ip = request.client.host if request.client else None
    db.add(AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=json.dumps(old_value) if old_value else None,
        new_value=json.dumps(new_value) if new_value else None,
        ip_address=ip,
    ))
