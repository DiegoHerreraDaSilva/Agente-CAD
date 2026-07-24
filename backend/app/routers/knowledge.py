"""Base de conhecimento compartilhada — visão pública (só entradas aprovadas)."""

from fastapi import APIRouter, Depends

from app.deps import requer_senha_atualizada
from app.repositories.knowledge import listar_conhecimento

router = APIRouter()


@router.get("/knowledge")
def knowledge(usuario: dict = Depends(requer_senha_atualizada)):
    return {"entries": listar_conhecimento(status="aprovado")}
