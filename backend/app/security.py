"""Mots de passe (Argon2id) et jetons d'accès (JWT)."""

import uuid
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.timeutils import utcnow

# Paramètres par défaut d'argon2-cffi : Argon2id, recommandé par l'OWASP.
_hasher = PasswordHasher()

# Hash d'un mot de passe aléatoire : sert à garder un temps de réponse identique quand
# l'email n'existe pas (sinon on pourrait deviner quels comptes existent).
_DUMMY_HASH = _hasher.hash(uuid.uuid4().hex)


class InvalidTokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(
    user_id: uuid.UUID, secret_key: str, algorithm: str, expires_minutes: int
) -> str:
    now = utcnow()
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=expires_minutes)}
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_access_token(token: str, secret_key: str, algorithm: str) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token, secret_key, algorithms=[algorithm], options={"require": ["exp", "sub"]}
        )
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise InvalidTokenError("Jeton invalide ou expiré") from exc
