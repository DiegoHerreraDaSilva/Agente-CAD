"""Acesso a dados da base de conhecimento compartilhada e do log de cache."""

from typing import Optional

import psycopg
from pgvector.psycopg import register_vector

from app.config import (
    MODEL,
    RAG_JANELA_REINJECAO,
    RAG_LIMIAR,
    RAG_TOP_N,
    RESUMO_RAG_MIN_CHARS,
    client,
)
from app.db import _pg_conninfo
from app.embeddings import embed_documento, embed_documentos_batch, embed_query


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
    atualizar_embedding_se_aprovado(entry_id)  # entra aprovada → já indexa p/ RAG
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
    if afetadas > 0 and status == "aprovado":
        atualizar_embedding_se_aprovado(entry_id)  # virou aprovada → indexa p/ RAG
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
    if afetadas > 0:
        # Re-embeddar só se a entrada estiver aprovada (a função checa o status).
        # Editar uma pendente não precisa: ela ainda não é recuperável.
        atualizar_embedding_se_aprovado(entry_id)
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


def gerar_resumo_rag(titulo: str, conteudo: str) -> Optional[str]:
    """Gera uma versão condensada do conteúdo, para injeção no turno atual do
    chat (não para embedding — embedding sempre usa o conteúdo completo).
    Só vale a pena para entradas longas; entradas curtas já são o caso ótimo
    e retornam None (a injeção cai de volta no conteúdo completo)."""
    if len(conteudo) <= RESUMO_RAG_MIN_CHARS:
        return None
    resp = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=(
            "Condense a entrada de base de conhecimento técnica abaixo para "
            "injeção direta num prompt de chat. Preserve TODOS os parâmetros, "
            "números, nomes de comandos/ferramentas e recomendações — corte só "
            "explicação redundante e contexto que não muda a ação recomendada. "
            "Responda só com o texto condensado, em português do Brasil, sem "
            "preâmbulo."
        ),
        messages=[{"role": "user", "content": f"## {titulo}\n{conteudo}"}],
    )
    texto = "".join(b.text for b in resp.content if b.type == "text").strip()
    return texto or None


def atualizar_embedding_se_aprovado(entry_id: int) -> None:
    """Gera/atualiza o embedding (e, se o conteúdo for longo, o resumo_rag) de
    uma entrada, se ela estiver aprovada. Só entradas aprovadas são recuperáveis
    pelo RAG. Falha ao embeddar (ex.: Voyage fora) não quebra a operação de
    origem (aprovar/criar/editar): loga e deixa o embedding como está — a
    entrada fica sem ser recuperada até um reindex
    (scripts/reindex_knowledge.py). Falha ao gerar resumo_rag também não quebra
    nada: a coluna fica NULL e a injeção usa COALESCE(resumo_rag, conteudo)."""
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT titulo, conteudo, status FROM knowledge_entries WHERE id = %s",
                (entry_id,),
            )
            row = cur.fetchone()
            if not row:
                return
            titulo, conteudo, status = row
            if status != "aprovado":
                return
            try:
                vetor = embed_documento(titulo, conteudo)
            except Exception as e:
                print(f"[rag] falha ao gerar embedding da entrada {entry_id}: {e}")
                return
            register_vector(conn)
            cur.execute(
                "UPDATE knowledge_entries SET embedding = %s WHERE id = %s",
                (vetor, entry_id),
            )
            try:
                resumo_rag = gerar_resumo_rag(titulo, conteudo)
            except Exception as e:
                print(f"[rag] falha ao gerar resumo_rag da entrada {entry_id}: {e}")
                resumo_rag = None
            if resumo_rag is not None:
                cur.execute(
                    "UPDATE knowledge_entries SET resumo_rag = %s WHERE id = %s",
                    (resumo_rag, entry_id),
                )
        conn.commit()


def backfill_resumo_rag(apenas_faltando: bool = True) -> tuple[int, int]:
    """Backfill de resumo_rag para entradas aprovadas longas (acima de
    RESUMO_RAG_MIN_CHARS) que ainda não têm resumo. Retorna (processadas,
    falhas). Idempotente — pular entradas já resumidas é o padrão
    (apenas_faltando=True); passe False para regenerar tudo (ex.: após ajustar
    o prompt de resumo)."""
    filtro = "AND resumo_rag IS NULL" if apenas_faltando else ""
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, titulo, conteudo FROM knowledge_entries "
                f"WHERE status = 'aprovado' AND length(conteudo) > %s {filtro} "
                f"ORDER BY id",
                (RESUMO_RAG_MIN_CHARS,),
            )
            linhas = cur.fetchall()

    processadas, falhas = 0, 0
    for entry_id, titulo, conteudo in linhas:
        try:
            resumo = gerar_resumo_rag(titulo, conteudo)
        except Exception as e:
            print(f"[rag] falha ao gerar resumo_rag da entrada {entry_id}: {e}")
            falhas += 1
            continue
        if resumo is None:
            continue
        with psycopg.connect(_pg_conninfo()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE knowledge_entries SET resumo_rag = %s WHERE id = %s",
                    (resumo, entry_id),
                )
            conn.commit()
        processadas += 1
    return processadas, falhas


def reindexar_aprovadas(apenas_faltando: bool = False, chunk: int = 100) -> tuple[int, int]:
    """Backfill de embeddings de TODAS as entradas aprovadas, embeddando em
    LOTE (uma requisição à Voyage por chunk) — assim o backfill não estoura o
    rate limit de 3 RPM da conta sem método de pagamento. Retorna
    (processadas, falhas). Idempotente.

    apenas_faltando=True indexa só as que estão sem embedding (útil pra retomar
    depois de uma falha parcial sem re-embeddar o que já foi feito)."""
    filtro = "AND embedding IS NULL" if apenas_faltando else ""
    with psycopg.connect(_pg_conninfo()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, titulo, conteudo FROM knowledge_entries "
                f"WHERE status = 'aprovado' {filtro} ORDER BY id"
            )
            linhas = cur.fetchall()

    processadas, falhas = 0, 0
    for i in range(0, len(linhas), chunk):
        lote = linhas[i : i + chunk]
        textos = [f"{titulo}\n\n{conteudo}" for _id, titulo, conteudo in lote]
        try:
            vetores = embed_documentos_batch(textos)
        except Exception as e:
            print(f"[rag] falha ao embeddar lote (offset {i}): {e}")
            falhas += len(lote)
            continue
        with psycopg.connect(_pg_conninfo()) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                for (entry_id, _t, _c), vetor in zip(lote, vetores):
                    cur.execute(
                        "UPDATE knowledge_entries SET embedding = %s WHERE id = %s",
                        (vetor, entry_id),
                    )
            conn.commit()
        processadas += len(lote)
    return processadas, falhas


def recuperar_conhecimento(
    pergunta: str, rag_injetadas: dict[str, int], turno_atual: int
) -> tuple[list[dict], dict[str, int]]:
    """RAG: recupera as top-N entradas aprovadas mais similares à pergunta,
    deduplicando contra o que já foi injetado nesta sessão (rag_injetadas =
    {entry_id: turno_injetado}, chaves como string por serem chaves de JSON).

    Busca o dobro de candidatas (top-2N) e filtra as já injetadas há menos de
    RAG_JANELA_REINJECAO turnos, completando de volta até N com as próximas
    melhores — assim uma conversa longa não perde contexto útil só porque o
    tema já apareceu antes. Uma entrada filtrada nesta rodada permanece
    disponível: se ninguém a substituir, ela reaparece no top-2N de novo na
    próxima pergunta.

    Retorna (entradas_selecionadas, rag_injetadas_atualizado) — o chamador
    persiste o segundo valor na sessão. Degrada graciosamente: se a Voyage
    falhar, retorna ([], rag_injetadas inalterado) e o chat segue sem
    conhecimento recuperado (NÃO cai de volta na base inteira)."""
    try:
        vetor = embed_query(pergunta)
    except Exception as e:
        print(f"[rag] falha ao embeddar a pergunta, seguindo sem RAG: {e}")
        return [], rag_injetadas
    with psycopg.connect(_pg_conninfo()) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            # %s::vector força o cast do parâmetro (uma list Python é adaptada
            # como array) para vector, que é o tipo que o operador <=> exige.
            # COALESCE(resumo_rag, conteudo): a recuperação (acima) sempre usa
            # o embedding do conteúdo completo; só o texto DEVOLVIDO para
            # injeção usa a versão condensada quando existir — recall e
            # injeção têm objetivos opostos de tamanho.
            cur.execute(
                "SELECT id, titulo, COALESCE(resumo_rag, conteudo) AS texto, "
                "1 - (embedding <=> %s::vector) AS score "
                "FROM knowledge_entries "
                "WHERE status = 'aprovado' AND embedding IS NOT NULL "
                "ORDER BY embedding <=> %s::vector LIMIT %s",
                (vetor, vetor, RAG_TOP_N * 2),
            )
            candidatas = cur.fetchall()

    candidatas = [
        {"id": eid, "titulo": t, "conteudo": texto, "score": float(s)}
        for eid, t, texto, s in candidatas
        if s is not None and float(s) >= RAG_LIMIAR
    ]

    selecionadas: list[dict] = []
    for cand in candidatas:
        if len(selecionadas) >= RAG_TOP_N:
            break
        turno_injetado = rag_injetadas.get(str(cand["id"]))
        if turno_injetado is not None and (turno_atual - turno_injetado) <= RAG_JANELA_REINJECAO:
            continue  # já mandada recentemente nesta sessão — pula, mas fica disponível pra próxima rodada
        selecionadas.append(cand)

    novo_rag_injetadas = dict(rag_injetadas)
    for cand in selecionadas:
        novo_rag_injetadas[str(cand["id"])] = turno_atual

    return selecionadas, novo_rag_injetadas


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
