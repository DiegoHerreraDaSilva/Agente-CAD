"""Acesso a dados da base de conhecimento compartilhada e do log de cache."""

from typing import Optional

import psycopg

from app.db import _pg_conninfo


def criar_conhecimento_pendente(titulo: str, conteudo: str, categoria: str, criado_por: str) -> int:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO knowledge_entries (titulo, conteudo, categoria, criado_por, status) "
                "VALUES (%s, %s, %s, %s, 'pendente') RETURNING id",
                (titulo, conteudo, categoria, criado_por),
            )
            entry_id = cur.fetchone()[0]
        conn.commit()
    return entry_id


def criar_conhecimento_aprovado(titulo: str, conteudo: str, categoria: str, criado_por: str) -> int:
    # Diferente de criar_conhecimento_pendente: entra direto como 'aprovado' —
    # admin já revisou o conteúdo ao digitá-lo, não faz sentido passar por fila.
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO knowledge_entries (titulo, conteudo, categoria, criado_por, status) "
                "VALUES (%s, %s, %s, %s, 'aprovado') RETURNING id",
                (titulo, conteudo, categoria, criado_por),
            )
            entry_id = cur.fetchone()[0]
        conn.commit()
    return entry_id


def listar_conhecimento(status: Optional[str] = None) -> list[dict]:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    "SELECT id, titulo, conteudo, categoria, criado_por, status, criado_em "
                    "FROM knowledge_entries WHERE status = %s ORDER BY id DESC",
                    (status,),
                )
            else:
                cur.execute(
                    "SELECT id, titulo, conteudo, categoria, criado_por, status, criado_em "
                    "FROM knowledge_entries ORDER BY id DESC"
                )
            colunas = ["id", "titulo", "conteudo", "categoria", "criado_por", "status", "criado_em"]
            linhas = [dict(zip(colunas, row)) for row in cur.fetchall()]
    for linha in linhas:
        linha["criado_em"] = linha["criado_em"].isoformat()
    return linhas


def definir_status_conhecimento(entry_id: int, status: str) -> bool:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE knowledge_entries SET status = %s WHERE id = %s AND status = 'pendente'",
                (status, entry_id),
            )
            afetadas = cur.rowcount
        conn.commit()
    return afetadas > 0


def excluir_conhecimento_pendente(entry_id: int) -> bool:
    # Rejeitar não é "mudar status" — a entrada some de knowledge_entries de
    # vez (diferente de aprovar). O resumo original continua intacto em
    # chat_sessions.resumo, que é uma tabela totalmente separada: rejeitar
    # aqui nunca apaga nada do histórico/chat do usuário.
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM knowledge_entries WHERE id = %s AND status = 'pendente'",
                (entry_id,),
            )
            afetadas = cur.rowcount
        conn.commit()
    return afetadas > 0


def editar_conhecimento(
    entry_id: int,
    titulo: Optional[str] = None,
    conteudo: Optional[str] = None,
    categoria: Optional[str] = None,
) -> bool:
    # Funciona em qualquer status (pendente ou já aprovado) — editar uma
    # entrada aprovada altera o texto que já está no prompt do chat na
    # próxima mensagem; editar uma pendente só muda o que o admin vai revisar.
    campos, valores = [], []
    if titulo is not None:
        campos.append("titulo = %s")
        valores.append(titulo)
    if conteudo is not None:
        campos.append("conteudo = %s")
        valores.append(conteudo)
    if categoria is not None:
        campos.append("categoria = %s")
        valores.append(categoria)
    if not campos:
        return False
    valores.append(entry_id)
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE knowledge_entries SET {', '.join(campos)} WHERE id = %s",
                tuple(valores),
            )
            afetadas = cur.rowcount
        conn.commit()
    return afetadas > 0


def excluir_conhecimento(entry_id: int) -> bool:
    # Diferente de excluir_conhecimento_pendente: aqui remove independente do
    # status — usado para tirar uma entrada já aprovada da base compartilhada.
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM knowledge_entries WHERE id = %s", (entry_id,))
            afetadas = cur.rowcount
        conn.commit()
    return afetadas > 0


def buscar_conhecimento_texto() -> str:
    """Texto determinístico da base compartilhada, para virar um bloco cacheável
    do system prompt. Ordem estável (id) e sem timestamps/valores incidentais.
    Só entra aqui o que já foi aprovado — pendentes ainda não viram conhecimento
    compartilhado de fato."""
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT titulo, conteudo, categoria FROM knowledge_entries "
                "WHERE status = 'aprovado' ORDER BY id"
            )
            linhas = cur.fetchall()
    if not linhas:
        return "(nenhuma entrada cadastrada ainda)"
    return "\n\n---\n\n".join(
        f"## {titulo} ({categoria})\n{conteudo}" for titulo, conteudo, categoria in linhas
    )


def registrar_uso_cache(session_id: int, user_id: int, usage) -> None:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cache_usage_log "
                "(session_id, user_id, input_tokens, cache_creation_input_tokens, "
                "cache_read_input_tokens, output_tokens) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    session_id,
                    user_id,
                    usage.input_tokens,
                    getattr(usage, "cache_creation_input_tokens", 0) or 0,
                    getattr(usage, "cache_read_input_tokens", 0) or 0,
                    usage.output_tokens,
                ),
            )
        conn.commit()
