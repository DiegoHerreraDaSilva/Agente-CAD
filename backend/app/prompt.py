"""Montagem do system prompt e do bloco de conhecimento recuperado por RAG."""

import re

# Casa a marcação Markdown que versões anteriores usavam pra persistir imagem
# colada/anexada no chat (feature removida) — a data URL inteira (base64),
# que podia ter megabytes, ficava embutida no texto da mensagem. Mantido só
# pra sanear sessões antigas que ainda têm esse conteúdo salvo no banco;
# NUNCA deve ser reenviado como texto puro pro LLM (ver sanitizar_historico_para_llm).
IMAGEM_MD_RE = re.compile(r"!\[imagem colada\]\(data:[^)]*\)")


def sanitizar_historico_para_llm(mensagens: list[dict]) -> list[dict]:
    """Substitui data URLs de imagem embutidas em mensagens ANTIGAS do
    histórico (de sessões de quando o anexo de imagem ainda existia) por um
    placeholder curto, antes de mandar pro LLM — sem isso, esse blob de texto
    gigante seria reenviado LITERALMENTE como parte do histórico em todo
    turno seguinte e estoura a janela de contexto da DeepSeek, derrubando a
    chamada com 400."""
    saneadas = []
    for m in mensagens:
        content = m["content"]
        if isinstance(content, str) and IMAGEM_MD_RE.search(content):
            content = IMAGEM_MD_RE.sub("[imagem anexada anteriormente]", content)
            saneadas.append({**m, "content": content})
        else:
            saneadas.append(m)
    return saneadas


def montar_system_prompt(memoria: str, resumo: str = "") -> str:
    """Monta o system prompt (prefixo estável da sessão): tom fixo, memória
    pessoal e, se houver, o resumo da sessão. A DeepSeek cacheia esse
    prefixo automaticamente (sem marcação no request) quando repete entre
    turnos — ver README, seção "LLM: DeepSeek".

    O conhecimento da base NÃO entra aqui: pós-RAG ele é dinâmico (muda a cada
    pergunta) — por isso vai no turno atual (ver montar_bloco_conhecimento +
    chat.py), não no prefixo estável.
    """
    memoria_txt = memoria.strip() or "(sem memória pessoal registrada ainda)"

    bloco_tom = (
        "Você é um consultor técnico de engenharia CAD especializado em Siemens NX da empresa Schwaben Engineering, "
        "empresa especializada em desenvolvimento de produtos automotivos (caminhões, carros e ônibus)."
        "Você é ESTRITAMENTE CONSULTIVO: oriente, explique e recomende, mas NUNCA "
        "afirme que executou ou executará qualquer ação dentro do NX — você não tem "
        "acesso ao software. Responda em português do Brasil. Seja direto e prático, "
        "mas justifique recomendações não óbvias.\n\n"
        "Regras de forma (não reduzem a explicação do conteúdo técnico, só cortam "
        "texto de forma):\n"
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
