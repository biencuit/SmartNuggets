"""Inscription, connexion et profil de l'éleveur."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.deps import AuthServiceDep, CurrentUser
from app.errors import UnauthorizedError
from app.schemas import Token, UserCreate, UserRead

router = APIRouter(prefix="/api/v1/auth", tags=["authentification"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte éleveur",
    responses={409: {"description": "Adresse email déjà utilisée"}},
)
async def register(data: UserCreate, service: AuthServiceDep) -> UserRead:
    user = await service.register(data.email, data.password)
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=Token,
    summary="Se connecter",
    description="Formulaire OAuth2 : `username` = adresse email, `password` = mot de passe.",
    responses={401: {"description": "Email ou mot de passe incorrect"}},
)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], service: AuthServiceDep
) -> Token:
    user = await service.authenticate(form.username, form.password)
    if user is None:
        raise UnauthorizedError("Email ou mot de passe incorrect")
    return Token(access_token=service.create_token(user))


@router.get("/me", response_model=UserRead, summary="Profil de l'utilisateur connecté")
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
