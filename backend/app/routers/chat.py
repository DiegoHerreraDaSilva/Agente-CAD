"""Rota de chat (protegida) — streaming SSE, usa nível e memória do usuário logado."""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import MODELO_PROVIDER, get_user_or_ip, limiter
from app.deps import requer_senha_atualizada
from app.llm import LLMConexaoFalhou, LLMErro, LLMLimiteRequisicoes, LLMSobrecarregado, resposta_stream
from app.prompt import montar_bloco_conhecimento, montar_system_prompt, validar_imagens
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

    # Suporte a imagem não está confirmado na DeepSeek (formato OpenAI-compatible
    # de vision) — desativado sob esse provider. A UI já esconde o botão de
    # anexar/colar; isso é defesa em profundidade caso a requisição chegue
    # mesmo assim (ex.: sessão antiga com o provider trocado no meio do caminho).
    if req.imagens and MODELO_PROVIDER == "deepseek":
        raise HTTPException(
            status_code=400,
            detail="Anexos de imagem não são suportados com o provider atual (DeepSeek).",
        )

    imagens_validas = validar_imagens(req.imagens)

    # Título automático só quando a sessão é realmente nova (sem mensagens e
    # sem resumo) — após um /compact as mensagens são apagadas, e isso não deve
    # disparar renomeação.
    if not sessao["tem_mensagens"] and not sessao["resumo"]:
        definir_titulo(req.session_id, gerar_titulo(req.pergunta))

    # Persiste a mensagem do usuário (texto + marcações Markdown das imagens,
    # para que reapareçam ao recarregar a sessão) e monta o histórico (multi-turn).
    conteudo_armazenado = req.pergunta
    if req.imagens:
        anexos_md = "\n".join(f"![imagem colada]({url})" for url in req.imagens)
        conteudo_armazenado = (conteudo_armazenado + "\n\n" + anexos_md).strip()
    adicionar_mensagem(req.session_id, "user", conteudo_armazenado)
    historico = carregar_mensagens(req.session_id)
    messages = [{"role": m["papel"], "content": m["conteudo"]} for m in historico]

    # Cache de prefixo do histórico: marca a última mensagem ANTERIOR ao turno
    # atual (messages[-1] é a pergunta recém-adicionada) com um cache_control.
    # Isso faz o prefixo `system + turnos 1..N-1` ser cacheado; a cada turno o
    # breakpoint "anda" para frente. O turno atual carrega o conhecimento
    # recuperado (dinâmico) e fica sem cache. Só há o que cachear a partir do
    # 2º turno (com histórico anterior).
    if len(messages) >= 2:
        anterior = messages[-2]
        messages[-2] = {
            "role": anterior["role"],
            "content": [
                {
                    "type": "text",
                    "text": anterior["content"],
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }

    # RAG: recupera as entradas mais relevantes para a pergunta e injeta no
    # TURNO ATUAL (não no system — senão invalidaria o cache do histórico).
    # Degrada graciosamente: recuperar_conhecimento retorna [] se a Voyage cair.
    # turno_atual = nº de mensagens do usuário até aqui (a atual incluída) —
    # base para a janela de reinjeção (dedup por sessão).
    turno_atual = sum(1 for m in historico if m["papel"] == "user")
    entradas, novo_rag_injetadas = recuperar_conhecimento(
        req.pergunta, sessao["rag_injetadas"], turno_atual
    )
    if novo_rag_injetadas != sessao["rag_injetadas"]:
        atualizar_rag_injetadas(req.session_id, novo_rag_injetadas)
    bloco_conhecimento = montar_bloco_conhecimento(entradas)

    # Monta o content do turno atual: conhecimento recuperado → imagens → pergunta.
    # (Mensagens antigas do histórico permanecem só texto; a marcação Markdown
    # das imagens acima é só para exibição ao recarregar a sessão.)
    turno_atual: list[dict] = []
    if bloco_conhecimento:
        turno_atual.append({"type": "text", "text": bloco_conhecimento})
    for media_type, b64data in imagens_validas:
        turno_atual.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64data},
            }
        )
    turno_atual.append(
        {"type": "text", "text": req.pergunta or "Veja a(s) imagem(ns) anexada(s)."}
    )
    messages[-1] = {"role": "user", "content": turno_atual}

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
                    registrar_uso_cache(req.session_id, usuario["id"], usage_out[0], MODELO_PROVIDER)
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
