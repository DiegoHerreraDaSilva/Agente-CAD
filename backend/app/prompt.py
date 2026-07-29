"""Montagem do system prompt (blocos cacheáveis) e validação de imagens anexadas."""

import base64

from fastapi import HTTPException

from app.config import (
    DATA_URL_RE,
    MAX_BYTES_POR_IMAGEM,
    MAX_IMAGENS_POR_MENSAGEM,
    MEDIA_TYPES_PERMITIDOS,
)

TOM_POR_NIVEL = {
    "estagiario": (
        "O engenheiro é estagiário, em início de aprendizado. Explique de forma "
        "bem didática e acolhedora, partindo do básico e sem pressupor experiência "
        "prévia. Defina TODOS os termos técnicos, dê exemplos simples e concretos, "
        "e sugira o próximo passo de estudo. Evite jargão; quando usar, explique."
    ),
    "junior": (
        "O engenheiro é júnior. Explique conceitos do zero, defina termos técnicos, "
        "e dê o passo a passo com bastante detalhe. Evite jargão sem explicação."
    ),
    "pleno": (
        "O engenheiro é pleno. Seja direto e prático, assuma familiaridade com o NX "
        "e conceitos de CAD, mas ainda justifique recomendações não óbvias."
    ),
    "senior": (
        "O engenheiro é sênior. Seja conciso e de alto nível, foque em trade-offs, "
        "casos de borda e boas práticas avançadas. Pode usar jargão livremente."
    ),
}


def montar_system_prompt(nivel: str, memoria: str, resumo: str = "") -> list[dict]:
    """Monta o system prompt (prefixo ESTÁVEL da sessão): tom por nível, memória
    pessoal e, se houver, o resumo da sessão. Um único `cache_control` ephemeral
    no último bloco cacheia todo o system de uma vez.

    O conhecimento da base NÃO entra aqui: pós-RAG ele é dinâmico (muda a cada
    pergunta) e iria invalidar o cache do histórico a cada turno — por isso vai
    no turno atual (ver montar_bloco_conhecimento + chat.py). O resumo entra no
    bloco cacheável porque só muda em /compact (infrequente): quando muda, o
    prefixo re-escreve uma vez, custo aceitável.
    """
    tom = TOM_POR_NIVEL.get(nivel, TOM_POR_NIVEL["pleno"])
    memoria_txt = memoria.strip() or "(sem memória pessoal registrada ainda)"

    bloco_tom = (
        "Você é um consultor técnico de engenharia CAD especializado em Siemens NX. "
        "Você é ESTRITAMENTE CONSULTIVO: oriente, explique e recomende, mas NUNCA "
        "afirme que executou ou executará qualquer ação dentro do NX — você não tem "
        "acesso ao software. Responda em português do Brasil.\n\n"
        f"Ajuste de tom para este usuário: {tom}\n\n"
        "Regras de forma (valem para todos os níveis, inclusive estagiário/júnior — "
        "não reduzem a explicação do conteúdo técnico, só cortam texto de forma):\n"
        "- Comece pela resposta. Não recapitule a pergunta nem anuncie o que vai fazer.\n"
        "- Não termine com um resumo do que acabou de dizer.\n"
        "- Não repita informação já dita nesta conversa — referencie em vez de repetir "
        '(ex.: "como vimos no passo 2").'
    )
    bloco_memoria = (
        "A seguir, a memória pessoal do engenheiro. Use-a para personalizar as "
        "respostas (preferências, histórico e projetos recentes):\n"
        "--- MEMÓRIA PESSOAL ---\n"
        f"{memoria_txt}\n"
        "--- FIM DA MEMÓRIA ---"
    )

    blocks = [
        {"type": "text", "text": bloco_tom},
        {"type": "text", "text": bloco_memoria},
    ]
    if resumo.strip():
        blocks.append(
            {
                "type": "text",
                "text": (
                    "Esta conversa foi compactada. Use o resumo abaixo como o "
                    "histórico anterior desta sessão (o que veio antes das "
                    "mensagens atuais):\n"
                    "--- RESUMO DA CONVERSA ATÉ AQUI (Markdown) ---\n"
                    f"{resumo.strip()}\n"
                    "--- FIM DO RESUMO ---"
                ),
            }
        )
    # Um único breakpoint de cache no fim do system cacheia todo o prefixo estável.
    blocks[-1]["cache_control"] = {"type": "ephemeral"}
    return blocks


def montar_bloco_conhecimento(entradas: list[dict]) -> str:
    """Texto do conhecimento recuperado por RAG, para injetar no TURNO ATUAL
    (não no system — ver montar_system_prompt). Retorna '' se nada foi
    recuperado, e nesse caso o turno segue sem bloco de conhecimento."""
    if not entradas:
        return ""
    corpo = "\n\n---\n\n".join(
        f"## {e['titulo']}\n{e['conteudo']}" for e in entradas
    )
    return (
        "Base de conhecimento da equipe relevante para esta pergunta (recuperada "
        "por similaridade semântica). Use como referência de boas práticas e "
        "decisões já validadas:\n"
        "--- CONHECIMENTO RECUPERADO ---\n"
        f"{corpo}\n"
        "--- FIM DO CONHECIMENTO ---"
    )


def validar_imagens(imagens: list[str]) -> list[tuple[str, str]]:
    """Valida e decodifica data URLs de imagens coladas no chat.
    Retorna [(media_type, base64_data), ...]. Levanta HTTPException se algo
    estiver fora do esperado (evita repassar lixo/arquivos grandes à API)."""
    if len(imagens) > MAX_IMAGENS_POR_MENSAGEM:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo de {MAX_IMAGENS_POR_MENSAGEM} imagens por mensagem.",
        )
    validas = []
    for data_url in imagens:
        m = DATA_URL_RE.match(data_url)
        if not m:
            raise HTTPException(status_code=400, detail="Imagem em formato inválido.")
        media_type, b64data = m.group(1), m.group(2)
        if media_type not in MEDIA_TYPES_PERMITIDOS:
            raise HTTPException(status_code=400, detail=f"Tipo de imagem não suportado: {media_type}")
        try:
            bruto = base64.b64decode(b64data, validate=True)
        except Exception:
            raise HTTPException(status_code=400, detail="Imagem corrompida (base64 inválido).")
        if len(bruto) > MAX_BYTES_POR_IMAGEM:
            raise HTTPException(status_code=400, detail="Imagem excede o limite de 5 MB.")
        validas.append((media_type, b64data))
    return validas
