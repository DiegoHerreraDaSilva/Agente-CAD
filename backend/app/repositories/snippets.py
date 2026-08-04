"""Acesso a dados de prompts/templates pessoais salvos por usuário."""

import psycopg

from app.db import _pg_conninfo


def listar_snippets(user_id: int) -> list[dict]:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, titulo, conteudo FROM prompt_snippets "
                "WHERE user_id = %s ORDER BY criado_em DESC",
                (user_id,),
            )
            return [{"id": r[0], "titulo": r[1], "conteudo": r[2]} for r in cur.fetchall()]


def criar_snippet(user_id: int, titulo: str, conteudo: str) -> int:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO prompt_snippets (user_id, titulo, conteudo) "
                "VALUES (%s, %s, %s) RETURNING id",
                (user_id, titulo, conteudo),
            )
            snippet_id = cur.fetchone()[0]
        conn.commit()
    return snippet_id


def excluir_snippet(snippet_id: int, user_id: int) -> bool:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM prompt_snippets WHERE id = %s AND user_id = %s",
                (snippet_id, user_id),
            )
            afetadas = cur.rowcount
        conn.commit()
    return afetadas > 0
