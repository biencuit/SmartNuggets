"""Inscription et connexion des éleveurs."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import ConflictError
from app.models import User
from app.repositories import UserRepository
from app.security import create_access_token, hash_password, verify_password
from app.timeutils import utcnow


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)

    async def register(self, email: str, password: str) -> User:
        if await self.users.get_by_email(email) is not None:
            raise ConflictError("Un compte existe déjà avec cette adresse email")
        user = await self.users.add(
            User(email=email, password_hash=hash_password(password), created_at=utcnow())
        )
        await self.session.commit()
        return user

    async def authenticate(self, email: str, password: str) -> User | None:
        user = await self.users.get_by_email(email)
        password_hash = user.password_hash if user is not None else None
        if not verify_password(password_hash, password):
            return None
        return user

    def create_token(self, user: User) -> str:
        if self.settings.jwt_secret_key is None:
            raise RuntimeError("jwt_secret_key doit être définie (create_app s'en charge)")
        return create_access_token(
            user.id,
            self.settings.jwt_secret_key,
            self.settings.jwt_algorithm,
            self.settings.access_token_expire_minutes,
        )
