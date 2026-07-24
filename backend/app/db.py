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
            conn.commit()
    except Exception as e:  # Postgres pode ainda não estar de pé
        print(f"[startup] não foi possível garantir o schema de users: {e}")
