import uuid

import pytest

from app.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "s" * 64


def test_hash_argon2id_et_verification() -> None:
    password_hash = hash_password("poule-rousse")

    assert password_hash.startswith("$argon2id$")
    assert "poule-rousse" not in password_hash
    assert verify_password(password_hash, "poule-rousse")
    assert not verify_password(password_hash, "renard")


def test_hash_invalide_ou_absent_refuse() -> None:
    assert not verify_password("!", "nimporte")
    assert not verify_password(None, "nimporte")


def test_jeton_aller_retour() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id, SECRET, "HS256", 5)
    assert decode_access_token(token, SECRET, "HS256") == user_id


@pytest.mark.parametrize(
    "token",
    [
        create_access_token(uuid.uuid4(), SECRET, "HS256", -1),  # expiré
        create_access_token(uuid.uuid4(), "autre-cle" * 8, "HS256", 5),  # mauvaise signature
        "pas.un.jeton",
    ],
)
def test_jeton_refuse(token: str) -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, SECRET, "HS256")
