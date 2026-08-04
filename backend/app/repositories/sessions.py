"""Acesso a dados de sessões e mensagens de chat."""

import json
from typing import Optional

import psycopg

from app.db import _pg_conninfo


def listar_sessoes(user_id: int) -> list[dict]:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, titulo, atualizado_em, pinned FROM chat_sessions "
                "WHERE user_id = %s ORDER BY pinned DESC, atualizado_em DESC",
                (user_id,),
            )
            linhas = [
                {"id": r[0], "titulo": r[1], "atualizado_em": r[2].isoformat(), "pinned": r[3]}
                for r in cur.fetchall()
            ]
    return linhas


def definir_pin(session_id: int, user_id: int, pinned: bool) -> bool:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chat_sessions SET pinned = %s WHERE id = %s AND user_id = %s",
                (pinned, session_id, user_id),
            )
            afetadas = cur.rowcount
        conn.commit()
    return afetadas > 0


def buscar_mensagens(user_id: int, termo: str, limite: int = 30) -> list[dict]:
    """Busca por conteúdo (ILIKE) nas mensagens do usuário, com trecho de contexto."""
    padrao = f"%{termo}%"
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.id, m.session_id, s.titulo, m.papel, m.conteudo, m.criado_em
                FROM chat_messages m
                JOIN chat_sessions s ON s.id = m.session_id
                WHERE s.user_id = %s AND m.conteudo ILIKE %s
                ORDER BY m.criado_em DESC
                LIMIT %s
                """,
                (user_id, padrao, limite),
            )
            linhas = cur.fetchall()
    resultados = []
    for r in linhas:
        conteudo = r[4]
        idx = conteudo.lower().find(termo.lower())
        if idx >= 0:
            inicio = max(0, idx - 40)
            trecho = ("…" if inicio > 0 else "") + conteudo[inicio: idx + len(termo) + 60].strip()
        else:
            trecho = conteudo[:100]
        resultados.append(
            {
                "message_id": r[0],
                "session_id": r[1],
                "session_titulo": r[2],
                "papel": r[3],
                "trecho": trecho,
                "criado_em": r[5].isoformat(),
            }
        )
    return resultados


def buscar_sessoes_por_titulo(user_id: int, termo: str, limite: int = 15) -> list[dict]:
    padrao = f"%{termo}%"
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, titulo, atualizado_em FROM chat_sessions "
                "WHERE user_id = %s AND titulo ILIKE %s "
                "ORDER BY atualizado_em DESC LIMIT %s",
                (user_id, padrao, limite),
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
    """Retorna {id, titulo, resumo, rag_injetadas, tem_mensagens} se a sessão for do usuário."""
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, titulo, resumo, rag_injetadas FROM chat_sessions "
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
        "rag_injetadas": row[3] or {},
        "tem_mensagens": total > 0,
    }


def atualizar_rag_injetadas(session_id: int, rag_injetadas: dict[str, int]) -> None:
    """Persiste o mapa {entry_id: turno_injetado} de dedup do RAG para a sessão."""
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chat_sessions SET rag_injetadas = %s WHERE id = %s",
                (json.dumps(rag_injetadas), session_id),
            )
        conn.commit()


def carregar_mensagens(session_id: int) -> list[dict]:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, papel, conteudo, criado_em FROM chat_messages "
                "WHERE session_id = %s ORDER BY id",
                (session_id,),
            )
            msgs = [
                {"id": r[0], "papel": r[1], "conteudo": r[2], "criado_em": r[3].isoformat()}
                for r in cur.fetchall()
            ]
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
    # Zera rag_injetadas na MESMA transação do DELETE: se o resumo gerado pelo
    # /compact não capturou o conteúdo de uma entrada já injetada, filtrá-la
    # como "já mandada" depois de apagar as mensagens a tornaria irrecuperável
    # (não sobra registro dela em lugar nenhum).
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_messages WHERE session_id = %s", (session_id,)
            )
            cur.execute(
                "UPDATE chat_sessions SET rag_injetadas = '{}'::jsonb WHERE id = %s",
                (session_id,),
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


def excluir_ultima_mensagem(session_id: int, papel: str) -> None:
    """Apaga a última mensagem de um dado papel (usada por regenerar/editar)."""
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_messages WHERE id = ("
                "  SELECT id FROM chat_messages"
                "  WHERE session_id = %s AND papel = %s"
                "  ORDER BY id DESC LIMIT 1"
                ")",
                (session_id, papel),
            )
        conn.commit()


def excluir_mensagens_a_partir_de(session_id: int, message_id: int) -> None:
    """Apaga a mensagem `message_id` e tudo que vem depois dela (edição+reenvio)."""
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_messages WHERE session_id = %s AND id >= %s",
                (session_id, message_id),
            )
        conn.commit()


def mensagem_pertence_a_sessao(message_id: int, session_id: int) -> bool:
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM chat_messages WHERE id = %s AND session_id = %s",
                (message_id, session_id),
            )
            return cur.fetchone() is not None


def gerar_titulo(pergunta: str) -> str:
    """Título automático: 1ª linha da pergunta, truncada em ~50 caracteres."""
    texto = pergunta.strip().splitlines()[0].strip() if pergunta.strip() else "Nova sessão"
    if len(texto) > 50:
        texto = texto[:50].rstrip() + "…"
    return texto or "Nova sessão"


def gerar_titulo_conhecimento(titulo_sessao: str) -> str:
    base = f"Resumo de sessão: {titulo_sessao}".strip()
    return base[:120]
