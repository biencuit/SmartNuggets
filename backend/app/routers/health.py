from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["santé"])


@router.get("/health", summary="Vérifie que l'API répond")
async def health() -> dict[str, str]:
    return {"status": "ok"}
