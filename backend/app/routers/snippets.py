"""Rotas de prompts/templates pessoais salvos por usuário."""

from fastapi import APIRouter, Depends, HTTPException

from app.deps import requer_senha_atualizada
from app.repositories.snippets import criar_snippet, excluir_snippet, listar_snippets
from app.schemas import SnippetRequest

router = APIRouter(prefix="/snippets")


@router.get("")
def get_snippets(usuario: dict = Depends(requer_senha_atualizada)):
    return {"snippets": listar_snippets(usuario["id"])}


@router.post("")
def post_snippet(req: SnippetRequest, usuario: dict = Depends(requer_senha_atualizada)):
    titulo = req.titulo.strip()
    conteudo = req.conteudo.strip()
    if not titulo or not conteudo:
        raise HTTPException(status_code=400, detail="Título e conteúdo são obrigatórios")
    snippet_id = criar_snippet(usuario["id"], titulo[:80], conteudo)
    return {"id": snippet_id, "titulo": titulo[:80], "conteudo": conteudo}


@router.delete("/{snippet_id}")
def delete_snippet(snippet_id: int, usuario: dict = Depends(requer_senha_atualizada)):
    if not excluir_snippet(snippet_id, usuario["id"]):
        raise HTTPException(status_code=404, detail="Template não encontrado")
    return {"ok": True}
