"""Acesso a dados de sessões e mensagens de chat."""

from typing import Optional

import psycopg

from app.db import _pg_conninfo


def listar_sessoes(user_id: int) -> list[dict]:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, titulo, atualizado_em FROM chat_sessions "
                "WHERE user_id = %s ORDER BY atualizado_em DESC",
                (user_id,),
            )
            linhas = [
                {"id": r[0], "titulo": r[1], "atualizado_em": r[2].isoformat()}
                for r in cur.fetchall()
            ]
    return linhas


def criar_sessao(user_id: int) -> dict:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_sessions (user_id) VALUES (%s) RETURNING id, titulo",
                (user_id,),
            )
            sid, titulo = cur.fetchone()
        conn.commit()
    return {"id": sid, "titulo": titulo}


def sessao_do_usuario(session_id: int, user_id: int) -> Optional[dict]:
    """Retorna {id, titulo, resumo, tem_mensagens} se a sessão for do usuário."""
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, titulo, resumo FROM chat_sessions "
                "WHERE id = %s AND user_id = %s",
                (session_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute(
                "SELECT count(*) FROM chat_messages WHERE session_id = %s", (session_id,)
            )
            total = cur.fetchone()[0]
    return {
        "id": row[0],
        "titulo": row[1],
        "resumo": row[2],
        "tem_mensagens": total > 0,
    }


def carregar_mensagens(session_id: int) -> list[dict]:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT papel, conteudo FROM chat_messages "
                "WHERE session_id = %s ORDER BY id",
                (session_id,),
            )
            msgs = [{"papel": r[0], "conteudo": r[1]} for r in cur.fetchall()]
    return msgs


def adicionar_mensagem(session_id: int, papel: str, conteudo: str) -> None:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_messages (session_id, papel, conteudo) "
                "VALUES (%s, %s, %s)",
                (session_id, papel, conteudo),
            )
            cur.execute(
                "UPDATE chat_sessions SET atualizado_em = now() WHERE id = %s",
                (session_id,),
            )
        conn.commit()


def renomear_sessao(session_id: int, user_id: int, titulo: str) -> bool:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chat_sessions SET titulo = %s WHERE id = %s AND user_id = %s",
                (titulo, session_id, user_id),
            )
            afetadas = cur.rowcount
        conn.commit()
    return afetadas > 0


def definir_titulo(session_id: int, titulo: str) -> None:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chat_sessions SET titulo = %s WHERE id = %s",
                (titulo, session_id),
            )
        conn.commit()


def excluir_sessao(session_id: int, user_id: int) -> bool:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_sessions WHERE id = %s AND user_id = %s",
                (session_id, user_id),
            )
            afetadas = cur.rowcount
        conn.commit()
    return afetadas > 0


def apagar_mensagens(session_id: int) -> None:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_messages WHERE session_id = %s", (session_id,)
            )
        conn.commit()


def definir_resumo(session_id: int, resumo: str) -> None:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chat_sessions SET resumo = %s, atualizado_em = now() "
                "WHERE id = %s",
                (resumo, session_id),
            )
        conn.commit()


def gerar_titulo(pergunta: str) -> str:
    """Título automático: 1ª linha da pergunta, truncada em ~50 caracteres."""
    texto = pergunta.strip().splitlines()[0].strip() if pergunta.strip() else "Nova sessão"
    if len(texto) > 50:
        texto = texto[:50].rstrip() + "…"
    return texto or "Nova sessão"


def gerar_titulo_conhecimento(titulo_sessao: str) -> str:
    base = f"Resumo de sessão: {titulo_sessao}".strip()
    return base[:120]
