"""Rotas de sessões de chat (protegidas), incluindo /compact."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import get_user_or_ip, limiter
from app.deps import requer_senha_atualizada
from app.llm import LLMConexaoFalhou, LLMErro, LLMLimiteRequisicoes, LLMSobrecarregado, resposta_simples
from app.repositories.knowledge import criar_conhecimento_pendente
from app.repositories.sessions import (
    apagar_mensagens,
    buscar_mensagens,
    buscar_sessoes_por_titulo,
    carregar_mensagens,
    criar_sessao,
    definir_pin,
    definir_resumo,
    excluir_mensagens_a_partir_de,
    excluir_sessao,
    excluir_ultima_mensagem,
    gerar_titulo_conhecimento,
    listar_sessoes,
    mensagem_pertence_a_sessao,
    renomear_sessao,
    sessao_do_usuario,
)
from app.schemas import PinRequest, RenameRequest

router = APIRouter(prefix="/sessions")


@router.get("")
def get_sessions(usuario: dict = Depends(requer_senha_atualizada)):
    return {"sessions": listar_sessoes(usuario["id"])}


@router.get("/search")
def search_sessions(q: str, usuario: dict = Depends(requer_senha_atualizada)):
    termo = q.strip()
    if len(termo) < 2:
        return {"sessoes": [], "mensagens": []}
    return {
        "sessoes": buscar_sessoes_por_titulo(usuario["id"], termo),
        "mensagens": buscar_mensagens(usuario["id"], termo),
    }


@router.post("")
def post_session(usuario: dict = Depends(requer_senha_atualizada)):
    return criar_sessao(usuario["id"])


@router.get("/{session_id}")
def get_session(session_id: int, usuario: dict = Depends(requer_senha_atualizada)):
    sessao = sessao_do_usuario(session_id, usuario["id"])
    if not sessao:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return {
        "id": sessao["id"],
        "titulo": sessao["titulo"],
        "resumo": sessao["resumo"],
        "mensagens": carregar_mensagens(session_id),
    }


@router.patch("/{session_id}")
def patch_session(
    session_id: int, req: RenameRequest, usuario: dict = Depends(requer_senha_atualizada)
):
    titulo = req.titulo.strip() or "Nova sessão"
    if not renomear_sessao(session_id, usuario["id"], titulo[:120]):
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return {"id": session_id, "titulo": titulo[:120]}


@router.delete("/{session_id}")
def delete_session(session_id: int, usuario: dict = Depends(requer_senha_atualizada)):
    if not excluir_sessao(session_id, usuario["id"]):
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return {"ok": True}


@router.patch("/{session_id}/pin")
def patch_pin(session_id: int, req: PinRequest, usuario: dict = Depends(requer_senha_atualizada)):
    if not definir_pin(session_id, usuario["id"], req.pinned):
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return {"ok": True, "pinned": req.pinned}


@router.post("/{session_id}/regenerate")
def regenerate(session_id: int, usuario: dict = Depends(requer_senha_atualizada)):
    """Remove a última resposta + a pergunta que a gerou; devolve a pergunta
    para o front reenviar via /chat (fonte única de verdade do fluxo de envio)."""
    sessao = sessao_do_usuario(session_id, usuario["id"])
    if not sessao:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    msgs = carregar_mensagens(session_id)
    if len(msgs) < 2 or msgs[-1]["papel"] != "assistant" or msgs[-2]["papel"] != "user":
        raise HTTPException(status_code=400, detail="Nada para regenerar.")
    pergunta = msgs[-2]["conteudo"]
    excluir_ultima_mensagem(session_id, "assistant")
    excluir_ultima_mensagem(session_id, "user")
    return {"ok": True, "pergunta": pergunta}


@router.delete("/{session_id}/messages/{message_id}/rest")
def delete_message_and_rest(
    session_id: int, message_id: int, usuario: dict = Depends(requer_senha_atualizada)
):
    """Apaga a mensagem e tudo depois dela — usado para editar+reenviar."""
    sessao = sessao_do_usuario(session_id, usuario["id"])
    if not sessao:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    if not mensagem_pertence_a_sessao(message_id, session_id):
        raise HTTPException(status_code=404, detail="Mensagem não encontrada")
    excluir_mensagens_a_partir_de(session_id, message_id)
    return {"ok": True}


@router.post("/{session_id}/compact")
@limiter.limit("10/minute", key_func=get_user_or_ip)
def compact_session(
    request: Request, session_id: int, usuario: dict = Depends(requer_senha_atualizada)
):
    sessao = sessao_do_usuario(session_id, usuario["id"])
    if not sessao:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    msgs = carregar_mensagens(session_id)
    if not msgs and not sessao["resumo"].strip():
        return {"ok": False, "mensagem": "Nada para compactar."}
    if not msgs:
        # Já compactado e sem mensagens novas desde então.
        return {"ok": False, "mensagem": "Nada novo para compactar."}

    # Monta o material a resumir: resumo anterior (se houver) + mensagens novas.
    partes_texto = []
    if sessao["resumo"].strip():
        partes_texto.append(
            "RESUMO ANTERIOR DA CONVERSA:\n" + sessao["resumo"].strip() + "\n"
        )
    partes_texto.append("MENSAGENS DESDE O ÚLTIMO RESUMO:")
    for m in msgs:
        autor = "Engenheiro" if m["papel"] == "user" else "Consultor"
        partes_texto.append(f"{autor}: {m['conteudo']}")
    conteudo = "\n".join(partes_texto)

    system_resumo = (
        "Você resume conversas de consultoria de engenharia CAD/Siemens NX. "
        "Produza um resumo em Markdown conciso que preserve: o contexto do problema, "
        "as decisões e recomendações dadas, termos e parâmetros técnicos citados, e "
        "pendências em aberto. Escreva em português do Brasil. Se houver um resumo "
        "anterior, incorpore-o num único resumo coeso e atualizado."
    )

    try:
        novo_resumo, _uso = resposta_simples(system_resumo, conteudo, max_tokens=4096)
    except LLMSobrecarregado:
        return {"ok": False, "mensagem": "⚠️ API sobrecarregada. Tente compactar em alguns segundos."}
    except LLMLimiteRequisicoes:
        return {"ok": False, "mensagem": "⚠️ Limite de requisições. Tente de novo em instantes."}
    except LLMConexaoFalhou:
        return {"ok": False, "mensagem": "⚠️ Falha de conexão com a API."}
    except LLMErro as e:
        return {"ok": False, "mensagem": f"⚠️ Erro da API ({e})."}

    if not novo_resumo:
        return {"ok": False, "mensagem": "⚠️ Não foi possível gerar o resumo."}

    definir_resumo(session_id, novo_resumo)
    apagar_mensagens(session_id)

    # Envia o resumo para a fila de aprovação da base de conhecimento
    # compartilhada — só entra de fato (e no prompt do chat) depois que um
    # admin aprovar no painel /admin.
    criar_conhecimento_pendente(
        titulo=gerar_titulo_conhecimento(sessao["titulo"]),
        conteudo=novo_resumo,
        categoria="resumo_sessao",
        criado_por=usuario["email"],
    )

    return {"ok": True, "resumo": novo_resumo}
