"""Backfill de embeddings da base de conhecimento (RAG).

Gera/atualiza o embedding de toda entrada APROVADA. Idempotente — pode rodar
quantas vezes quiser (re-embedda tudo). Use após ativar a feature pela primeira
vez, ou depois de trocar o modelo/dimensão de embedding.

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
