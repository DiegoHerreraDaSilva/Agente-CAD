"""Rotas de autenticação (/auth/*)."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import MODELO_PROVIDER, limiter
from app.deps import requer_senha_atualizada, usuario_atual
from app.repositories.users import (
    atualizar_memoria,
    atualizar_senha,
    buscar_usuario_por_email,
    promover_se_admin,
)
from app.schemas import ChangePasswordRequest, LoginRequest, MemoriaRequest
from app.security import hash_senha, verificar_senha

router = APIRouter(prefix="/auth")


@router.post("/register")
def register():
    # Autocadastro desabilitado: contas são criadas pela TI no painel /admin.
    raise HTTPException(
        status_code=403,
        detail="Cadastro desabilitado. Peça a um administrador (TI) para criar sua conta.",
    )


@router.post("/login")
@limiter.limit("5/minute")
def login(req: LoginRequest, request: Request):
    email = req.email.strip().lower()
    usuario = buscar_usuario_por_email(email)
    if not usuario or not verificar_senha(req.senha, usuario["senha_hash"]):
        raise HTTPException(status_code=401, detail="Email ou senha inválidos")
    request.session["user_id"] = usuario["id"]
    promover_se_admin(usuario)
    return {
        "email": usuario["email"],
        "nivel": usuario["nivel"],
        "must_change_senha": usuario["must_change_senha"],
    }


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.post("/change-password")
def change_password(req: ChangePasswordRequest, usuario: dict = Depends(usuario_atual)):
    if not verificar_senha(req.senha_atual, usuario["senha_hash"]):
        raise HTTPException(status_code=401, detail="Senha atual incorreta")
    if len(req.senha_nova) < 8:
        raise HTTPException(status_code=400, detail="A nova senha deve ter ao menos 8 caracteres")
    atualizar_senha(usuario["id"], hash_senha(req.senha_nova), must_change_senha=False)
    return {"ok": True}


@router.get("/me")
def me(usuario: dict = Depends(usuario_atual)):
    return {
        "id": usuario["id"],
        "email": usuario["email"],
        "nivel": usuario["nivel"],
        "memoria": usuario["memoria"],
        "role": usuario["role"],
        "must_change_senha": usuario["must_change_senha"],
        # Provider ativo (config global, não por usuário) — reaproveita este
        # fetch, que o frontend já faz no boot, pra decidir se mostra a
        # feature de anexar imagem (não suportada sob DeepSeek).
        "provider": MODELO_PROVIDER,
    }


@router.put("/me/memoria")
def salvar_memoria(req: MemoriaRequest, usuario: dict = Depends(requer_senha_atualizada)):
    atualizar_memoria(usuario["id"], req.memoria)
    return {"ok": True}
