"""Geração de embeddings via Voyage AI (RAG).

A Voyage distingue o tipo do texto sendo embeddado (`input_type`):
- "document" ao indexar entradas da base de conhecimento;
- "query"    ao embeddar a pergunta do usuário na hora de recuperar.
Usar o tipo certo melhora a qualidade da recuperação.
"""

from app.config import EMBEDDING_DIM, VOYAGE_MODEL, voyage_client


def _embed(texto: str, input_type: str) -> list[float]:
    resp = voyage_client.embed(
        [texto],
        model=VOYAGE_MODEL,
        input_type=input_type,
        output_dimension=EMBEDDING_DIM,
    )
    return resp.embeddings[0]


def embed_documento(titulo: str, conteudo: str) -> list[float]:
    """Embedding de uma entrada da base. O título ancora o tema."""
    return _embed(f"{titulo}\n\n{conteudo}", "document")


def embed_documentos_batch(textos: list[str]) -> list[list[float]]:
    """Embedding de vários documentos numa ÚNICA requisição à Voyage.
    Usado no backfill/seed: uma chamada em vez de N evita estourar o rate
    limit (3 RPM na conta sem método de pagamento). Retorna os vetores na
    mesma ordem dos textos."""
    if not textos:
        return []
    resp = voyage_client.embed(
        textos,
        model=VOYAGE_MODEL,
        input_type="document",
        output_dimension=EMBEDDING_DIM,
    )
    return resp.embeddings


def embed_query(pergunta: str) -> list[float]:
    """Embedding da pergunta do usuário, para a busca por similaridade."""
    return _embed(pergunta, "query")
