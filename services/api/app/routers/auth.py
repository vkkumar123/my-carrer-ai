from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api_schemas import DevLoginIn, TokenOut, UserOut
from app.auth import DB, CurrentUser, issue_dev_token
from app.config import get_settings
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/dev-login", response_model=TokenOut)
def dev_login(body: DevLoginIn, db: DB) -> TokenOut:
    """Passwordless login for local development only (AUTH_MODE=dev)."""
    if get_settings().auth_mode != "dev":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None:
        user = User(email=body.email.lower(), name=body.name)
        db.add(user)
        db.commit()
    return TokenOut(
        access_token=issue_dev_token(user),
        user=UserOut(id=user.id, email=user.email, name=user.name),
    )


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut(id=user.id, email=user.email, name=user.name)
