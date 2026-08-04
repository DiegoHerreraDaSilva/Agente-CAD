"""Montagem do system prompt e do bloco de conhecimento recuperado por RAG."""

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
        "Base de conhecimento da equipe relevante para esta pergunta (recuperada "
        "por similaridade semântica). Use como referência de boas práticas e "
        "decisões já validadas:\n"
        "--- CONHECIMENTO RECUPERADO ---\n"
        f"{corpo}\n"
        "--- FIM DO CONHECIMENTO ---"
    )
