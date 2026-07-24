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


def montar_system_prompt(
    nivel: str, conhecimento: str, memoria: str, resumo: str = ""
) -> list[dict]:
    """Monta o system prompt como blocos cacheáveis (prompt caching):
    1) tom por nível, 2) conhecimento compartilhado, 3) memória pessoal —
    cada um com cache_control ephemeral. O resumo de sessão (volátil, muda a
    cada /compact) vai por último, sem cache_control, conforme recomendação
    de deixar conteúdo variável após o último breakpoint.
    """
    tom = TOM_POR_NIVEL.get(nivel, TOM_POR_NIVEL["pleno"])
    memoria_txt = memoria.strip() or "(sem memória pessoal registrada ainda)"

    bloco_tom = (
        "Você é um consultor técnico de engenharia CAD especializado em Siemens NX. "
        "Você é ESTRITAMENTE CONSULTIVO: oriente, explique e recomende, mas NUNCA "
        "afirme que executou ou executará qualquer ação dentro do NX — você não tem "
        "acesso ao software. Responda em português do Brasil.\n\n"
        f"Ajuste de tom para este usuário: {tom}"
    )
    bloco_conhecimento = (
        "A seguir, a base de conhecimento compartilhada da equipe. Use-a como "
        "referência de boas práticas e decisões já validadas:\n"
        "--- BASE DE CONHECIMENTO COMPARTILHADA ---\n"
        f"{conhecimento}\n"
        "--- FIM DA BASE ---"
    )
    bloco_memoria = (
        "A seguir, a memória pessoal do engenheiro. Use-a para personalizar as "
        "respostas (preferências, histórico e projetos recentes):\n"
        "--- MEMÓRIA PESSOAL ---\n"
        f"{memoria_txt}\n"
        "--- FIM DA MEMÓRIA ---"
    )

    blocks = [
        {"type": "text", "text": bloco_tom, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": bloco_conhecimento, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": bloco_memoria, "cache_control": {"type": "ephemeral"}},
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
                # Sem cache_control: conteúdo por sessão, muda a cada /compact.
            }
        )
    return blocks


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
