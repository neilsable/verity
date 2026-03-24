"""
VERITY — Authentication Routes
JWT-based auth with Supabase integration.
Endpoints: register, login, refresh, logout, me.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.models.schemas import TokenResponse, UserCreate, UserResponse

logger = structlog.get_logger(__name__)
settings = get_settings()
router = APIRouter()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.app_secret_key, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> dict:
    """
    FastAPI dependency — validates JWT and returns the current user payload.
    Inject this into any protected endpoint.

    Usage:
        async def my_endpoint(user: dict = Depends(get_current_user)):
            user_id = user["sub"]
    """
    payload = decode_token(credentials.credentials)
    return payload


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate) -> UserResponse:
    """Register a new user. Returns the created user (no password)."""
    # In production this would use Supabase Auth
    # For now, we return a mock response to validate the schema
    logger.info("user_registered", email=body.email)
    return UserResponse(
        id=uuid.uuid4(),
        email=body.email,
        full_name=body.full_name,
        created_at=datetime.now(timezone.utc),
        is_active=True,
    )


@router.post("/login", response_model=TokenResponse)
async def login(email: str, password: str) -> TokenResponse:
    """Login with email + password. Returns a JWT access token."""
    # TODO: validate against DB in Phase 2
    # Mock for now — Phase 1 focus is structure
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id, email)
    logger.info("user_logged_in", email=email, user_id=user_id)
    return TokenResponse(
        access_token=token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> UserResponse:
    """Return the currently authenticated user."""
    return UserResponse(
        id=uuid.UUID(current_user["sub"]),
        email=current_user["email"],
        created_at=datetime.now(timezone.utc),
        is_active=True,
    )
