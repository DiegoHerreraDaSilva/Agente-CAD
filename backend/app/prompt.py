"""Montagem do system prompt, do bloco de conhecimento recuperado por RAG e
validação de imagens anexadas."""

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
        "prévia. Defina TODOS os termos técnicos e dê exemplos simples e concretos. "
        "Evite jargão; quando usar, explique."
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


def montar_system_prompt(nivel: str, memoria: str, resumo: str = "") -> str:
    """Monta o system prompt (prefixo estável da sessão): tom por nível,
    memória pessoal e, se houver, o resumo da sessão. A DeepSeek cacheia esse
    prefixo automaticamente (sem marcação no request) quando repete entre
    turnos — ver README, seção "LLM: DeepSeek".

    O conhecimento da base NÃO entra aqui: pós-RAG ele é dinâmico (muda a cada
    pergunta) — por isso vai no turno atual (ver montar_bloco_conhecimento +
    chat.py), não no prefixo estável.
    """
    tom = TOM_POR_NIVEL.get(nivel, TOM_POR_NIVEL["pleno"])
    memoria_txt = memoria.strip() or "(sem memória pessoal registrada ainda)"

    bloco_tom = (
        "Você é um consultor técnico de engenharia CAD especializado em Siemens NX da Schwaben Engineering, "
        "empresa especializada em desenvolvimento de produtos automotivos (caminhões, carros e ônibus)."
        "Você é ESTRITAMENTE CONSULTIVO: oriente, explique e recomende, mas NUNCA "
        "afirme que executou ou executará qualquer ação dentro do NX — você não tem "
        "acesso ao software. Responda em português do Brasil.\n\n"
        f"Ajuste de tom para este usuário: {tom}\n\n"
        "Regras de forma (valem para todos os níveis, inclusive estagiário/júnior — "
        "não reduzem a explicação do conteúdo técnico, só cortam texto de forma):\n"
        "- Comece pela resposta. Não recapitule a pergunta nem anuncie o que vai fazer.\n"
        "- Não termine com um resumo do que acabou de dizer.\n"
        "- Não repita informação já dita nesta conversa — referencie em vez de repetir "
        '(ex.: "como vimos no passo 2").\n'
        "- Nunca afirme que o engenheiro já viu, sabe ou praticou algo (ex.: \"conceitos "
        "que você já viu\", \"como você domina X\") a menos que isso tenha aparecido "
        "literalmente nesta conversa (no histórico de mensagens ou no resumo abaixo, se "
        "houver). Sem essa base, trate o assunto como novo para o engenheiro.\n"
        "- Não seja proativo: responda só ao que foi perguntado, sem propor exercícios, "
        'próximos passos ou perguntas do tipo "o que você quer fazer agora?"/"quer que '
        'eu...?" a menos que o engenheiro peça isso explicitamente (ex.: "me dá um '
        'roteiro", "o que eu faço depois"). Só pergunte de volta se houver ambiguidade '
        "real que impede responder à pergunta atual — nunca como forma de manter a "
        "conversa andando."
    )
    bloco_memoria = (
        "A seguir, a memória pessoal do engenheiro. Use-a para personalizar as "
        "respostas (preferências, histórico e projetos recentes):\n"
        "--- MEMÓRIA PESSOAL ---\n"
        f"{memoria_txt}\n"
        "--- FIM DA MEMÓRIA ---"
    )

    blocos = [bloco_tom, bloco_memoria]
    if resumo.strip():
        blocos.append(
            "Esta conversa foi compactada. Use o resumo abaixo como o "
            "histórico anterior desta sessão (o que veio antes das "
            "mensagens atuais):\n"
            "--- RESUMO DA CONVERSA ATÉ AQUI (Markdown) ---\n"
            f"{resumo.strip()}\n"
            "--- FIM DO RESUMO ---"
        )
    return "\n\n".join(blocos)


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
        "Material de apoio recuperado por similaridade semântica (pode ou não "
        "ser relevante — a busca é automática, não é garantia de relação com a "
        "pergunta). Use como referência SÓ SE o assunto abaixo tiver relação "
        "direta com o que o engenheiro perguntou de fato. Se não tiver relação, "
        "ignore este bloco por completo e responda apenas à pergunta em si — "
        "NUNCA trate o conteúdo abaixo como se fosse o assunto perguntado:\n"
        "--- CONHECIMENTO RECUPERADO (pode ser irrelevante) ---\n"
        f"{corpo}\n"
        "--- FIM DO CONHECIMENTO ---"
    )


def validar_imagens(imagens: list[str]) -> list[str]:
    """Valida data URLs de imagens coladas/anexadas no chat (formato, tipo
    MIME e tamanho). Retorna a mesma lista de data URLs (já validada) — o
    formato OpenAI-compatible aceita a data URL inteira em `image_url.url`,
    sem precisar separar media_type/base64 como no formato da Anthropic.
    Levanta HTTPException se algo estiver fora do esperado (evita repassar
    lixo/arquivos grandes à API)."""
    if len(imagens) > MAX_IMAGENS_POR_MENSAGEM:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo de {MAX_IMAGENS_POR_MENSAGEM} imagens por mensagem.",
        )
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
    return imagens
