"""Rota de chat (protegida) — streaming SSE, usa nível e memória do usuário logado."""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import get_user_or_ip, limiter
from app.deps import requer_senha_atualizada
from app.llm import LLMConexaoFalhou, LLMErro, LLMLimiteRequisicoes, LLMSobrecarregado, resposta_stream
from app.prompt import montar_bloco_conhecimento, montar_system_prompt
from app.repositories.knowledge import recuperar_conhecimento, registrar_uso_cache
from app.repositories.sessions import (
    adicionar_mensagem,
    atualizar_rag_injetadas,
    carregar_mensagens,
    definir_titulo,
    gerar_titulo,
    sessao_do_usuario,
)
from app.schemas import ChatRequest

router = APIRouter()


@router.post("/chat")
@limiter.limit("20/minute", key_func=get_user_or_ip)
def chat(request: Request, req: ChatRequest, usuario: dict = Depends(requer_senha_atualizada)):
    sessao = sessao_do_usuario(req.session_id, usuario["id"])
    if not sessao:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    # Suporte a imagem não é suportado pela DeepSeek (formato OpenAI-compatible
    # de vision não confirmado) — a UI já esconde o botão de anexar/colar;
    # isso é defesa em profundidade caso a requisição chegue mesmo assim.
    if req.imagens:
        raise HTTPException(
            status_code=400,
            detail="Anexos de imagem não são suportados.",
        )

    # Título automático só quando a sessão é realmente nova (sem mensagens e
    # sem resumo) — após um /compact as mensagens são apagadas, e isso não deve
    # disparar renomeação.
    if not sessao["tem_mensagens"] and not sessao["resumo"]:
        definir_titulo(req.session_id, gerar_titulo(req.pergunta))

    # Persiste a mensagem do usuário e monta o histórico (multi-turn).
    adicionar_mensagem(req.session_id, "user", req.pergunta)
    historico = carregar_mensagens(req.session_id)
    messages = [{"role": m["papel"], "content": m["conteudo"]} for m in historico]

    # RAG: recupera as entradas mais relevantes para a pergunta e injeta no
    # TURNO ATUAL. Degrada graciosamente: recuperar_conhecimento retorna []
    # se a Voyage cair. numero_do_turno = nº de mensagens do usuário até aqui
    # (a atual incluída) — base para a janela de reinjeção (dedup por sessão).
    numero_do_turno = sum(1 for m in historico if m["papel"] == "user")
    entradas, novo_rag_injetadas = recuperar_conhecimento(
        req.pergunta, sessao["rag_injetadas"], numero_do_turno
    )
    if novo_rag_injetadas != sessao["rag_injetadas"]:
        atualizar_rag_injetadas(req.session_id, novo_rag_injetadas)
    bloco_conhecimento = montar_bloco_conhecimento(entradas)

    # Conteúdo do turno atual: conhecimento recuperado (se houver) + pergunta.
    conteudo_turno = req.pergunta
    if bloco_conhecimento:
        conteudo_turno = f"{bloco_conhecimento}\n\n{req.pergunta}"
    messages[-1] = {"role": "user", "content": conteudo_turno}

    system_prompt = montar_system_prompt(
        usuario["nivel"], usuario["memoria"], sessao["resumo"]
    )

    def gerar():
        partes: list[str] = []
        try:
            texto_stream, usage_out = resposta_stream(system_prompt, messages, max_tokens=8192)
            for texto in texto_stream:
                partes.append(texto)
                yield f"data: {json.dumps({'text': texto})}\n\n"
            # Sucesso: persiste a resposta do assistente e o uso de cache.
            resposta = "".join(partes)
            if resposta.strip():
                adicionar_mensagem(req.session_id, "assistant", resposta)
                if usage_out:
                    registrar_uso_cache(req.session_id, usuario["id"], usage_out[0])
        except LLMSobrecarregado:
            msg = "⚠️ A API do modelo está sobrecarregada agora. Tente novamente em alguns segundos."
            yield f"data: {json.dumps({'text': msg})}\n\n"
        except LLMLimiteRequisicoes:
            msg = "⚠️ Limite de requisições atingido. Aguarde um momento e tente de novo."
            yield f"data: {json.dumps({'text': msg})}\n\n"
        except LLMConexaoFalhou:
            yield f"data: {json.dumps({'text': '⚠️ Falha de conexão com a API. Verifique a rede e tente novamente.'})}\n\n"
        except LLMErro as e:
            yield f"data: {json.dumps({'text': f'⚠️ {e}. Tente novamente.'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'text': f'⚠️ Erro inesperado: {e}'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gerar(), media_type="text/event-stream")
