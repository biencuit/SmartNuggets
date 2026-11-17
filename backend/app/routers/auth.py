"""Inscription, connexion et profil de l'éleveur, export et suppression du compte (RGPD)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.deps import AuthServiceDep, CurrentUser, SessionDep, SettingsDep
from app.errors import UnauthorizedError
from app.schemas import NotificationPrefs, NotificationPrefsUpdate, Token, UserCreate, UserRead
from app.services.account_service import AccountService

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


@router.get(
    "/me/export",
    summary="Télécharger toutes mes données (RGPD, art. 20)",
    description="Le compte, ses poulaillers, leurs passages et leurs alertes, en JSON. "
    "Les photos sont données par leur adresse dans l'API.",
)
async def export_my_data(
    user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> JSONResponse:
    data = await AccountService(session, settings).export(user)
    return JSONResponse(
        data,
        headers={"Content-Disposition": 'attachment; filename="smartnuggets-mes-donnees.json"'},
    )


@router.get(
    "/me/notifications",
    response_model=NotificationPrefs,
    summary="Mes préférences de notification",
)
async def my_notification_prefs(user: CurrentUser) -> NotificationPrefs:
    return NotificationPrefs.model_validate(user)


@router.patch(
    "/me/notifications",
    response_model=NotificationPrefs,
    summary="Activer ou régler mes notifications (Telegram)",
)
async def update_notification_prefs(
    data: NotificationPrefsUpdate, user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> NotificationPrefs:
    updated = await AccountService(session, settings).update_notification_prefs(user, data)
    return NotificationPrefs.model_validate(updated)


class AccountDelete(BaseModel):
    password: str


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer mon compte et toutes mes données (RGPD, art. 17)",
    description="Efface le compte, ses poulaillers, passages, alertes et photos. Le mot de "
    "passe est demandé une deuxième fois. Le Raspberry Pi est libéré pour un autre compte.",
    responses={401: {"description": "Mot de passe incorrect (rien n'est supprimé)"}},
)
async def delete_my_account(
    data: AccountDelete, user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> Response:
    await AccountService(session, settings).delete(user, data.password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
