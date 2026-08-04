"""Rotas de administração (TI): usuários, economia de cache, base de conhecimento."""

from typing import Optional

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import EMAIL_RE, PRECO_HIT, PRECO_MISS, PRECO_OUTPUT
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
# Economia de cache (DeepSeek: cache automático de prefixo repetido)
# ---------------------------------------------------------------------------
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
            cur.execute(
                "SELECT count(*), "
                "coalesce(sum(input_tokens), 0), "
                "coalesce(sum(cache_creation_input_tokens), 0), "
                "coalesce(sum(cache_read_input_tokens), 0), "
                "coalesce(sum(output_tokens), 0) "
                f"FROM cache_usage_log {filtro}",
                params,
            )
            total_msgs, input_tok, cache_creation, cache_read, output_tok = cur.fetchone()
            cur.execute(
                "SELECT s.titulo, u.email, l.input_tokens, l.cache_creation_input_tokens, "
                "l.cache_read_input_tokens, l.output_tokens, l.criado_em "
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
                    "criado_em": r[6].isoformat(),
                }
                for r in cur.fetchall()
            ]

    # Custo real (com cache automático da DeepSeek) vs. custo hipotético se
    # tudo fosse cache miss. cache_creation_input_tokens sempre é 0 na
    # DeepSeek (sem conceito de "cache write" pago à parte).
    custo_real = input_tok * PRECO_MISS + cache_read * PRECO_HIT + output_tok * PRECO_OUTPUT
    custo_sem_cache = (input_tok + cache_creation + cache_read) * PRECO_MISS + output_tok * PRECO_OUTPUT
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


# ---------------------------------------------------------------------------
# Dashboard de uso — só admin (visão nominal por usuário é ponto sensível,
# combinado com o usuário: fica restrita ao painel admin).
# ---------------------------------------------------------------------------
@router.get("/dashboard")
def admin_dashboard(
    admin: dict = Depends(admin_atual),
    dias: int = Query(30, ge=1, le=365),
):
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            # Cards de resumo
            cur.execute(
                "SELECT count(*), count(DISTINCT session_id) "
                "FROM chat_messages WHERE papel = 'user' AND criado_em >= now() - (%s || ' days')::interval",
                (dias,),
            )
            total_mensagens, _sessoes_ativas = cur.fetchone()
            cur.execute(
                "SELECT count(DISTINCT s.user_id) FROM chat_messages m "
                "JOIN chat_sessions s ON s.id = m.session_id "
                "WHERE m.criado_em >= now() - (%s || ' days')::interval",
                (dias,),
            )
            usuarios_ativos = cur.fetchone()[0]
            cur.execute(
                "SELECT coalesce(sum(output_tokens), 0) FROM cache_usage_log "
                "WHERE criado_em >= now() - (%s || ' days')::interval",
                (dias,),
            )
            tokens_output = cur.fetchone()[0]

            # Volume por dia
            cur.execute(
                "SELECT date_trunc('day', criado_em)::date AS dia, count(*) "
                "FROM chat_messages "
                "WHERE papel = 'user' AND criado_em >= now() - (%s || ' days')::interval "
                "GROUP BY dia ORDER BY dia",
                (dias,),
            )
            volume_diario = [{"dia": r[0].isoformat(), "mensagens": r[1]} for r in cur.fetchall()]

            # Heatmap dia da semana (0=domingo) x hora
            cur.execute(
                "SELECT extract(dow FROM criado_em)::int, extract(hour FROM criado_em)::int, count(*) "
                "FROM chat_messages "
                "WHERE papel = 'user' AND criado_em >= now() - (%s || ' days')::interval "
                "GROUP BY 1, 2",
                (dias,),
            )
            heatmap = [{"dia_semana": r[0], "hora": r[1], "mensagens": r[2]} for r in cur.fetchall()]

            # Ranking de usuários (nominal — só admin)
            cur.execute(
                "SELECT u.email, count(m.id) AS mensagens, "
                "coalesce(sum(l.output_tokens), 0) AS tokens, max(m.criado_em) AS ultima "
                "FROM users u "
                "LEFT JOIN chat_sessions s ON s.user_id = u.id "
                "LEFT JOIN chat_messages m ON m.session_id = s.id AND m.papel = 'user' "
                "  AND m.criado_em >= now() - (%s || ' days')::interval "
                "LEFT JOIN cache_usage_log l ON l.session_id = s.id "
                "  AND l.criado_em >= now() - (%s || ' days')::interval "
                "GROUP BY u.id, u.email "
                "HAVING count(m.id) > 0 "
                "ORDER BY mensagens DESC",
                (dias, dias),
            )
            ranking = [
                {
                    "email": r[0],
                    "mensagens": r[1],
                    "tokens": int(r[2]),
                    "ultima_atividade": r[3].isoformat() if r[3] else None,
                }
                for r in cur.fetchall()
            ]

            # Sessões mais ativas
            cur.execute(
                "SELECT s.id, s.titulo, u.email, count(m.id) AS mensagens, "
                "coalesce(sum(l.output_tokens), 0) AS tokens "
                "FROM chat_sessions s "
                "JOIN users u ON u.id = s.user_id "
                "JOIN chat_messages m ON m.session_id = s.id "
                "LEFT JOIN cache_usage_log l ON l.session_id = s.id "
                "WHERE s.atualizado_em >= now() - (%s || ' days')::interval "
                "GROUP BY s.id, s.titulo, u.email "
                "ORDER BY mensagens DESC LIMIT 10",
                (dias,),
            )
            sessoes_ativas = [
                {
                    "id": r[0],
                    "titulo": r[1],
                    "usuario": r[2],
                    "mensagens": r[3],
                    "tokens": int(r[4]),
                }
                for r in cur.fetchall()
            ]

    media_por_dia = round(total_mensagens / dias, 1) if dias else 0.0

    return {
        "periodo_dias": dias,
        "total_mensagens": total_mensagens,
        "usuarios_ativos": usuarios_ativos,
        "media_mensagens_dia": media_por_dia,
        "tokens_output": int(tokens_output),
        "volume_diario": volume_diario,
        "heatmap": heatmap,
        "ranking": ranking,
        "sessoes_ativas": sessoes_ativas,
    }
