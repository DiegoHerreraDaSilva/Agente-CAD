"""Backfill de resumo_rag da base de conhecimento (RAG).

Script utilitário de linha de comando — NÃO é chamado pelo app em runtime.
Gera a versão condensada (resumo_rag) de entradas APROVADAS longas, usada só
na INJEÇÃO no turno atual do chat (o embedding sempre usa o conteúdo
completo). Idempotente: por padrão, só processa entradas que ainda não têm
resumo_rag.

⚠️ No uso NORMAL você NÃO precisa deste script. Aprovar/criar/editar uma
entrada pelo painel /admin já gera o resumo_rag automaticamente quando o
conteúdo é longo o bastante (hooks em app/repositories/knowledge.py). Use
este script só nos casos de MANUTENÇÃO:

  1. Backfill inicial — resumir entradas que já existiam antes desta feature.
  2. Reprocessar falhas — se a API estava fora/rate-limited na hora que a
     entrada foi aprovada, ela fica aprovada mas sem resumo_rag (a injeção
     usa o conteúdo completo até rodar isto de novo).
  3. Trocar o prompt de resumo — rode com apenas_faltando=False (edite a
     chamada abaixo) para regenerar todos os resumos existentes.

Seguro em produção (mexe só na coluna resumo_rag de entradas já aprovadas).

Rodar a partir de backend/ (com o .venv ativo e o .env preenchido):
    python scripts/backfill_resumo_rag.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg  # noqa: E402

from app.config import RESUMO_RAG_MIN_CHARS  # noqa: E402
from app.db import _pg_conninfo  # noqa: E402
from app.repositories.knowledge import backfill_resumo_rag  # noqa: E402


def main() -> None:
    processadas, falhas = backfill_resumo_rag()
    print(f"[backfill_resumo_rag] {processadas} entradas processadas, {falhas} falhas.")

    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM knowledge_entries "
                "WHERE status = 'aprovado' AND resumo_rag IS NULL AND length(conteudo) > %s",
                (RESUMO_RAG_MIN_CHARS,),
            )
            faltando = cur.fetchone()[0]
    print(f"[backfill_resumo_rag] concluído. Entradas longas ainda sem resumo_rag: {faltando}")


if __name__ == "__main__":
    main()
