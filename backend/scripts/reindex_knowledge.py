"""Backfill de embeddings da base de conhecimento (RAG).

Script utilitário de linha de comando — NÃO é chamado pelo app em runtime.
Gera/atualiza o embedding de toda entrada APROVADA, em lote. Idempotente:
pode rodar quantas vezes quiser (re-embedda tudo).

⚠️ No uso NORMAL você NÃO precisa deste script. Aprovar/criar/editar uma
entrada pelo painel /admin já gera o embedding automaticamente (hooks em
app/repositories/knowledge.py). Use este script só nos casos de MANUTENÇÃO:

  1. Backfill inicial — indexar entradas que já existiam no banco antes do RAG.
  2. Reprocessar falhas — se a Voyage estava fora/rate-limited na hora que a
     entrada foi aprovada, ela fica aprovada mas sem embedding (não é
     recuperável até rodar isto). Rodar de novo pega só as que faltam.
  3. Trocar o modelo/dimensão de embedding — regera todos os vetores.

Seguro em produção (mexe só na coluna embedding de entradas já aprovadas).

Rodar a partir de backend/ (com o .venv ativo e o .env preenchido):
    python scripts/reindex_knowledge.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg  # noqa: E402

from app.db import _pg_conninfo  # noqa: E402
from app.repositories.knowledge import reindexar_aprovadas  # noqa: E402


def main() -> None:
    # Embedda em lote (uma requisição à Voyage por chunk) — não estoura o rate
    # limit de 3 RPM da conta sem método de pagamento.
    processadas, falhas = reindexar_aprovadas()
    print(f"[reindex] {processadas} entradas processadas, {falhas} falhas.")

    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM knowledge_entries "
                "WHERE status = 'aprovado' AND embedding IS NULL"
            )
            faltando = cur.fetchone()[0]
    print(f"[reindex] concluído. Aprovadas ainda sem embedding: {faltando}")


if __name__ == "__main__":
    main()
