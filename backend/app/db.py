"""Conexão com o Postgres e schema (idempotente)."""

import os

import psycopg


def _pg_conninfo() -> str:
    return (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'nx_agent_kb')} "
        f"user={os.getenv('POSTGRES_USER', 'nx_agent')} "
        f"password={os.getenv('POSTGRES_PASSWORD', '')}"
    )


# ---------------------------------------------------------------------------
# Schema (idempotente) — garante a tabela users mesmo em volume Docker já criado
# ---------------------------------------------------------------------------
def garantir_schema() -> None:
    try:
        with psycopg.connect(_pg_conninfo()) as conn:
            with conn.cursor() as cur:
                # Extensão de vetores (RAG) — requer a imagem pgvector/pgvector:pg16.
                # Precisa vir antes de qualquer coluna vector(...) abaixo.
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id         SERIAL PRIMARY KEY,
                        email      TEXT UNIQUE NOT NULL,
                        senha_hash TEXT NOT NULL,
                        nivel      TEXT NOT NULL
                                   CHECK (nivel IN ('estagiario','junior','pleno','senior')),
                        memoria    TEXT NOT NULL DEFAULT '',
                        criado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        id            SERIAL PRIMARY KEY,
                        user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        titulo        TEXT NOT NULL DEFAULT 'Nova sessão',
                        criado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
                        atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id         SERIAL PRIMARY KEY,
                        session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                        papel      TEXT NOT NULL CHECK (papel IN ('user','assistant')),
                        conteudo   TEXT NOT NULL,
                        criado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                    """
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_chat_messages_session "
                    "ON chat_messages (session_id, id);"
                )
                # Coluna de resumo (compactação) — idempotente p/ volumes já criados.
                cur.execute(
                    "ALTER TABLE chat_sessions "
                    "ADD COLUMN IF NOT EXISTS resumo TEXT NOT NULL DEFAULT '';"
                )
                # Papel do usuário (admin/engineer) — idempotente.
                cur.execute(
                    "ALTER TABLE users "
                    "ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'engineer';"
                )
                # Obriga troca de senha no primeiro login de contas criadas por
                # terceiros (admin/bootstrap) — idempotente.
                cur.execute(
                    "ALTER TABLE users "
                    "ADD COLUMN IF NOT EXISTS must_change_senha BOOLEAN NOT NULL DEFAULT false;"
                )
                # Log de uso de prompt caching — tabela nova, idempotente.
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cache_usage_log (
                        id                          SERIAL PRIMARY KEY,
                        session_id                  INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                        user_id                     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        input_tokens                INTEGER NOT NULL,
                        cache_creation_input_tokens INTEGER NOT NULL,
                        cache_read_input_tokens     INTEGER NOT NULL,
                        output_tokens               INTEGER NOT NULL,
                        criado_em                   TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                    """
                )
                # Fila de aprovação da base de conhecimento — resumos de sessão
                # (via /compact) entram como 'pendente' e só viram parte do
                # prompt do chat depois que um admin aprova. Idempotente.
                cur.execute(
                    "ALTER TABLE knowledge_entries "
                    "ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'aprovado' "
                    "CHECK (status IN ('pendente', 'aprovado', 'rejeitado'));"
                )
                # Coluna de embedding (RAG) — dimensão tem que bater com EMBEDDING_DIM
                # em config.py (voyage-3.5 = 1024). Idempotente.
                cur.execute(
                    "ALTER TABLE knowledge_entries "
                    "ADD COLUMN IF NOT EXISTS embedding vector(1024);"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_knowledge_embedding "
                    "ON knowledge_entries USING hnsw (embedding vector_cosine_ops);"
                )
                # Dedup de RAG por sessão: mapa {entry_id: turno_injetado} das
                # entradas já injetadas nesta conversa, para não repetir a
                # mesma entrada a cada pergunta próxima do mesmo tema.
                # Idempotente.
                cur.execute(
                    "ALTER TABLE chat_sessions "
                    "ADD COLUMN IF NOT EXISTS rag_injetadas JSONB NOT NULL DEFAULT '{}'::jsonb;"
                )
                # resumo_rag: versão condensada do conteúdo, usada só na
                # INJEÇÃO no turno atual (o embedding sempre usa o conteúdo
                # completo — recall e injeção têm objetivos opostos de
                # tamanho). NULL = sem resumo gerado ainda; a injeção cai de
                # volta no conteúdo completo (COALESCE). Idempotente.
                cur.execute(
                    "ALTER TABLE knowledge_entries "
                    "ADD COLUMN IF NOT EXISTS resumo_rag TEXT;"
                )
                # App migrou 100% para DeepSeek (só provider suportado) — a
                # coluna provider (que existiu brevemente durante a
                # convivência com Anthropic) não faz mais sentido. Idempotente.
                cur.execute(
                    "ALTER TABLE cache_usage_log DROP COLUMN IF EXISTS provider;"
                )
                # Favoritar/pinar sessões — idempotente.
                cur.execute(
                    "ALTER TABLE chat_sessions "
                    "ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT false;"
                )
                # Prompts/templates pessoais salvos por usuário.
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS prompt_snippets (
                        id        SERIAL PRIMARY KEY,
                        user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        titulo    TEXT NOT NULL,
                        conteudo  TEXT NOT NULL,
                        criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                    """
                )
                # Busca full-text simples (ILIKE) sobre mensagens — índice trigram
                # acelera LIKE '%termo%' sem precisar de tsvector/tsquery.
                cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_chat_messages_conteudo_trgm "
                    "ON chat_messages USING gin (conteudo gin_trgm_ops);"
                )
            conn.commit()
    except Exception as e:  # Postgres pode ainda não estar de pé
        print(f"[startup] não foi possível garantir o schema de users: {e}")
