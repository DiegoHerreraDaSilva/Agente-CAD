"""Dependências de autenticação/autorização do FastAPI."""

from fastapi import Depends, HTTPException, Request

from app.repositories.users import buscar_usuario_por_id


def usuario_atual(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Não autenticado")
    usuario = buscar_usuario_por_id(user_id)
    if not usuario:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Sessão inválida")
    return usuario


def requer_senha_atualizada(usuario: dict = Depends(usuario_atual)) -> dict:
    """Bloqueia o uso do app até o usuário trocar uma senha temporária/resetada."""
    if usuario.get("must_change_senha"):
        raise HTTPException(
            status_code=403,
            detail="Você precisa trocar sua senha antes de continuar.",
        )
    return usuario


def admin_atual(usuario: dict = Depends(requer_senha_atualizada)) -> dict:
    if usuario.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito à TI")
    return usuario
