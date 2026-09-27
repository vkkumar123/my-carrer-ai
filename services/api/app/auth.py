"""Bearer-token auth.

Production uses Supabase Auth: the browser signs in with Supabase and sends its access token,
which we verify with the project's JWT secret (HS256). Locally, AUTH_MODE=dev lets
/auth/dev-login mint the same kind of token so no Supabase project is needed.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User


def issue_dev_token(user: User) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": user.id,
        "email": user.email,
        "aud": s.jwt_audience,
        "iat": now,
        "exp": now + timedelta(days=7),
        "user_metadata": {"name": user.name},
    }
    return jwt.encode(claims, s.jwt_secret, algorithm="HS256")


def _decode(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=["HS256"], audience=s.jwt_audience)
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from e


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    claims = _decode(authorization.split(" ", 1)[1])
    user_id, email = claims.get("sub"), claims.get("email")
    if not user_id or not email:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing subject or email")

    user = db.get(User, user_id)
    if user is None:
        # First request from a new Supabase user: create the local profile row.
        meta = claims.get("user_metadata") or {}
        user = User(id=user_id, email=email, name=meta.get("name") or meta.get("full_name"))
        db.add(user)
        db.commit()
    return user


def require_internal_key(x_internal_key: Annotated[str | None, Header()] = None) -> None:
    if x_internal_key != get_settings().internal_api_key:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")


CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[Session, Depends(get_db)]
