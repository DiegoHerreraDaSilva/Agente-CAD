"""Rotas utilitárias (não fazem parte da API de fato)."""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.config import PUBLIC_DIR

router = APIRouter()


@router.get("/logo.png")
def logo():
    return FileResponse(PUBLIC_DIR / "logo.png")


@router.get("/health")
def health():
    return {"status": "ok"}
