"""Rotas de sessões de chat (protegidas), incluindo /compact."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import get_user_or_ip, limiter
from app.deps import requer_senha_atualizada
from app.llm import LLMConexaoFalhou, LLMErro, LLMLimiteRequisicoes, LLMSobrecarregado, resposta_simples
from app.repositories.knowledge import criar_conhecimento_pendente
from app.repositories.sessions import (
    apagar_mensagens,
    carregar_mensagens,
    criar_sessao,
    definir_resumo,
    excluir_sessao,
    gerar_titulo_conhecimento,
    listar_sessoes,
    renomear_sessao,
    sessao_do_usuario,
)
from app.schemas import RenameRequest

router = APIRouter(prefix="/sessions")


@router.get("")
def get_sessions(usuario: dict = Depends(requer_senha_atualizada)):
    return {"sessions": listar_sessoes(usuario["id"])}


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
