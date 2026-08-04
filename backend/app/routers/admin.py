"""Rotas de administração (TI): usuários, economia de cache, base de conhecimento."""

from typing import Optional

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import EMAIL_RE, PRECOS
from app.db import _pg_conninfo
from app.deps import admin_atual
from app.repositories.knowledge import (
    criar_conhecimento_aprovado,
    definir_status_conhecimento,
    editar_conhecimento,
    excluir_conhecimento,
    excluir_conhecimento_pendente,
    listar_conhecimento,
)
from app.repositories.users import (
    atualizar_senha,
    atualizar_usuario,
    buscar_usuario_por_id,
    criar_usuario,
    excluir_usuario,
    listar_usuarios,
)
from app.schemas import (
    AdminCreateUser,
    AdminCriarConhecimento,
    AdminEditarConhecimento,
    AdminSenha,
    AdminUpdateUser,
)
from app.security import hash_senha

router = APIRouter(prefix="/admin")


# ---------------------------------------------------------------------------
# Gestão de usuários
# ---------------------------------------------------------------------------
@router.get("/users")
def admin_listar_usuarios(admin: dict = Depends(admin_atual)):
    return {"users": listar_usuarios()}


@router.post("/users")
def admin_criar_usuario(req: AdminCreateUser, admin: dict = Depends(admin_atual)):
    email = req.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Email inválido")
    if len(req.senha) < 8:
        raise HTTPException(status_code=400, detail="A senha deve ter ao menos 8 caracteres")
    try:
        user_id = criar_usuario(email, hash_senha(req.senha), req.nivel, req.role)
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Email já cadastrado")
    return {"id": user_id, "email": email, "nivel": req.nivel, "role": req.role}


@router.patch("/users/{user_id}")
def admin_editar_usuario(
    user_id: int, req: AdminUpdateUser, admin: dict = Depends(admin_atual)
):
    alvo = buscar_usuario_por_id(user_id)
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    email = req.email.strip().lower() if req.email is not None else None
    if email is not None and not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Email inválido")

    # Evita o admin rebaixar a própria conta e se auto-trancar.
    if user_id == admin["id"] and req.role is not None and req.role != "admin":
        raise HTTPException(status_code=400, detail="Você não pode remover seu próprio acesso de admin")

    try:
        atualizar_usuario(user_id, email=email, nivel=req.nivel, role=req.role)
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Email já cadastrado")
    return {"ok": True}


@router.delete("/users/{user_id}")
def admin_excluir_usuario(user_id: int, admin: dict = Depends(admin_atual)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Você não pode excluir sua própria conta")
    if not buscar_usuario_por_id(user_id):
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    excluir_usuario(user_id)
    return {"ok": True}


@router.post("/users/{user_id}/senha")
def admin_trocar_senha(
    user_id: int, req: AdminSenha, admin: dict = Depends(admin_atual)
):
    if len(req.senha) < 8:
        raise HTTPException(status_code=400, detail="A senha deve ter ao menos 8 caracteres")
    if not buscar_usuario_por_id(user_id):
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    atualizar_senha(user_id, hash_senha(req.senha))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Economia de prompt caching
# ---------------------------------------------------------------------------
def _custo_provider(
    provider: str, input_tok: int, cache_creation: int, cache_read: int, output_tok: int
) -> tuple[float, float]:
    """Retorna (custo_real, custo_sem_cache) em USD para um grupo de tokens de
    UM provider só. As fórmulas são estruturalmente diferentes — Anthropic
    cobra input×multiplicador de cache; DeepSeek cobra preço absoluto por
    cache miss/hit (cache_creation sempre 0 nela) — por isso nunca dá pra
    somar tokens brutos de providers diferentes e aplicar um preço genérico."""
    p = PRECOS[provider]
    if provider == "anthropic":
        custo_real = (
            input_tok * p["input"]
            + cache_creation * p["input"] * p["cache_write_mult"]
            + cache_read * p["input"] * p["cache_read_mult"]
            + output_tok * p["output"]
        )
        custo_sem_cache = (input_tok + cache_creation + cache_read) * p["input"] + output_tok * p["output"]
    else:  # deepseek
        custo_real = input_tok * p["miss"] + cache_read * p["hit"] + output_tok * p["output"]
        custo_sem_cache = (input_tok + cache_creation + cache_read) * p["miss"] + output_tok * p["output"]
    return custo_real, custo_sem_cache


@router.get("/cache-stats")
def admin_cache_stats(
    admin: dict = Depends(admin_atual),
    usuario_id: Optional[int] = Query(None),
):
    filtro = "WHERE user_id = %s" if usuario_id is not None else ""
    filtro_join = "WHERE l.user_id = %s" if usuario_id is not None else ""
    params = (usuario_id,) if usuario_id is not None else ()

    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            # Agrupado por provider: cada grupo tem sua própria fórmula de
            # custo (ver _custo_provider) — soma-se o CUSTO EM DÓLAR de cada
            # grupo no fim, nunca os tokens brutos entre providers.
            cur.execute(
                "SELECT provider, count(*), "
                "coalesce(sum(input_tokens), 0), "
                "coalesce(sum(cache_creation_input_tokens), 0), "
                "coalesce(sum(cache_read_input_tokens), 0), "
                "coalesce(sum(output_tokens), 0) "
                f"FROM cache_usage_log {filtro} GROUP BY provider",
                params,
            )
            grupos = cur.fetchall()
            cur.execute(
                "SELECT s.titulo, u.email, l.input_tokens, l.cache_creation_input_tokens, "
                "l.cache_read_input_tokens, l.output_tokens, l.provider, l.criado_em "
                "FROM cache_usage_log l "
                "JOIN chat_sessions s ON s.id = l.session_id "
                "JOIN users u ON u.id = l.user_id "
                f"{filtro_join} "
                "ORDER BY l.id DESC LIMIT 20",
                params,
            )
            recentes = [
                {
                    "sessao": r[0],
                    "usuario": r[1],
                    "input_tokens": r[2],
                    "cache_creation_input_tokens": r[3],
                    "cache_read_input_tokens": r[4],
                    "output_tokens": r[5],
                    "provider": r[6],
                    "criado_em": r[7].isoformat(),
                }
                for r in cur.fetchall()
            ]

    total_msgs = 0
    input_tok = cache_creation = cache_read = output_tok = 0
    custo_real = custo_sem_cache = 0.0
    for provider, msgs, i_tok, c_creation, c_read, o_tok in grupos:
        total_msgs += msgs
        input_tok += i_tok
        cache_creation += c_creation
        cache_read += c_read
        output_tok += o_tok
        real_grupo, sem_cache_grupo = _custo_provider(provider, i_tok, c_creation, c_read, o_tok)
        custo_real += real_grupo
        custo_sem_cache += sem_cache_grupo

    economia_usd = max(custo_sem_cache - custo_real, 0.0)
    economia_pct = (economia_usd / custo_sem_cache * 100) if custo_sem_cache > 0 else 0.0

    return {
        "total_mensagens": total_msgs,
        "input_tokens": input_tok,
        "cache_creation_input_tokens": cache_creation,
        "cache_read_input_tokens": cache_read,
        "output_tokens": output_tok,
        "custo_real_usd": round(custo_real, 4),
        "custo_sem_cache_usd": round(custo_sem_cache, 4),
        "economia_usd": round(economia_usd, 4),
        "economia_pct": round(economia_pct, 1),
        "recentes": recentes,
    }


# ---------------------------------------------------------------------------
# Fila de aprovação da base de conhecimento
# ---------------------------------------------------------------------------
@router.get("/knowledge")
def admin_listar_conhecimento(
    admin: dict = Depends(admin_atual),
    status: Optional[str] = Query(None),
):
    if status is not None and status not in ("pendente", "aprovado", "rejeitado"):
        raise HTTPException(status_code=400, detail="Status inválido")
    return {"entries": listar_conhecimento(status=status)}


@router.post("/knowledge")
def admin_criar_conhecimento(req: AdminCriarConhecimento, admin: dict = Depends(admin_atual)):
    titulo = req.titulo.strip()
    categoria = req.categoria.strip()
    conteudo = req.conteudo.strip()
    if not titulo or not categoria or not conteudo:
        raise HTTPException(status_code=400, detail="Título, categoria e conteúdo são obrigatórios")
    entry_id = criar_conhecimento_aprovado(titulo, conteudo, categoria, admin["email"])
    return {"id": entry_id}


@router.post("/knowledge/{entry_id}/aprovar")
def admin_aprovar_conhecimento(entry_id: int, admin: dict = Depends(admin_atual)):
    if not definir_status_conhecimento(entry_id, "aprovado"):
        raise HTTPException(status_code=404, detail="Entrada pendente não encontrada")
    return {"ok": True}


@router.post("/knowledge/{entry_id}/rejeitar")
def admin_rejeitar_conhecimento(entry_id: int, admin: dict = Depends(admin_atual)):
    # Rejeitar exclui a entrada de knowledge_entries (não é só um status) —
    # o resumo de origem em chat_sessions.resumo não é afetado, e a sessão do
    # usuário continua exatamente como estava.
    if not excluir_conhecimento_pendente(entry_id):
        raise HTTPException(status_code=404, detail="Entrada pendente não encontrada")
    return {"ok": True}


@router.patch("/knowledge/{entry_id}")
def admin_editar_conhecimento(
    entry_id: int, req: AdminEditarConhecimento, admin: dict = Depends(admin_atual)
):
    # Funciona em qualquer status — permite revisar/corrigir uma entrada
    # pendente antes de aprovar, ou corrigir uma já aprovada sem precisar
    # rejeitar e esperar um novo /compact gerar outra.
    if not editar_conhecimento(entry_id, titulo=req.titulo, conteudo=req.conteudo, categoria=req.categoria):
        raise HTTPException(status_code=404, detail="Entrada não encontrada")
    return {"ok": True}


@router.delete("/knowledge/{entry_id}")
def admin_excluir_conhecimento(entry_id: int, admin: dict = Depends(admin_atual)):
    # Diferente de "rejeitar" (só para pendentes): remove uma entrada já
    # aprovada da base compartilhada, tirando-a do prompt do chat na próxima
    # mensagem.
    if not excluir_conhecimento(entry_id):
        raise HTTPException(status_code=404, detail="Entrada não encontrada")
    return {"ok": True}
