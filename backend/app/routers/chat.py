"""Rota de chat (protegida) — streaming SSE, usa nível e memória do usuário logado."""

import json

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import MODEL, client, get_user_or_ip, limiter
from app.deps import requer_senha_atualizada
from app.prompt import montar_system_prompt, validar_imagens
from app.repositories.knowledge import buscar_conhecimento_texto, registrar_uso_cache
from app.repositories.sessions import (
    adicionar_mensagem,
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

    # A mensagem atual, se tiver imagens coladas, vai para a API com os bytes
    # reais (blocos de imagem) — mensagens antigas do histórico permanecem só
    # texto (a marcação Markdown acima é só para exibição ao recarregar).
    if imagens_validas:
        blocos = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64data},
            }
            for media_type, b64data in imagens_validas
        ]
        blocos.append({"type": "text", "text": req.pergunta or "Veja a(s) imagem(ns) anexada(s)."})
        messages[-1] = {"role": "user", "content": blocos}

    conhecimento = buscar_conhecimento_texto()
    system_prompt = montar_system_prompt(
        usuario["nivel"], conhecimento, usuario["memoria"], sessao["resumo"]
    )

    def gerar():
        partes: list[str] = []
        try:
            with client.messages.stream(
                model=MODEL,
                max_tokens=8192,
                system=system_prompt,
                messages=messages,
            ) as stream:
                for texto in stream.text_stream:
                    partes.append(texto)
                    yield f"data: {json.dumps({'text': texto})}\n\n"
                final = stream.get_final_message()
            # Sucesso: persiste a resposta do assistente e o uso de cache.
            resposta = "".join(partes)
            if resposta.strip():
                adicionar_mensagem(req.session_id, "assistant", resposta)
                registrar_uso_cache(req.session_id, usuario["id"], final.usage)
        except anthropic.APIStatusError as e:
            tipo = ""
            body = getattr(e, "body", None)
            if isinstance(body, dict):
                tipo = (body.get("error") or {}).get("type", "")
            if e.status_code == 529 or tipo == "overloaded_error":
                msg = "⚠️ A API do Claude está sobrecarregada agora. Tente novamente em alguns segundos."
            elif e.status_code == 429 or tipo == "rate_limit_error":
                msg = "⚠️ Limite de requisições atingido. Aguarde um momento e tente de novo."
            else:
                msg = f"⚠️ Erro da API ({tipo or e.status_code}). Tente novamente."
            yield f"data: {json.dumps({'text': msg})}\n\n"
        except anthropic.APIConnectionError:
            yield f"data: {json.dumps({'text': '⚠️ Falha de conexão com a API. Verifique a rede e tente novamente.'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'text': f'⚠️ Erro inesperado: {e}'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gerar(), media_type="text/event-stream")
