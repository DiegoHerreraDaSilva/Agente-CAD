"""Modelos Pydantic de request usados pelas rotas."""

from typing import Literal, Optional

from pydantic import BaseModel

Nivel = Literal["estagiario", "junior", "pleno", "senior"]
Role = Literal["engineer", "admin"]


class ChatRequest(BaseModel):
    session_id: int
    pergunta: str
    imagens: list[str] = []


class RenameRequest(BaseModel):
    titulo: str


class RegisterRequest(BaseModel):
    email: str
    senha: str
    nivel: Nivel


class LoginRequest(BaseModel):
    email: str
    senha: str


class MemoriaRequest(BaseModel):
    memoria: str


class AdminCreateUser(BaseModel):
    email: str
    senha: str
    nivel: Nivel
    role: Role = "engineer"


class AdminUpdateUser(BaseModel):
    email: Optional[str] = None
    nivel: Optional[Nivel] = None
    role: Optional[Role] = None


class AdminSenha(BaseModel):
    senha: str


class ChangePasswordRequest(BaseModel):
    senha_atual: str
    senha_nova: str


class AdminEditarConhecimento(BaseModel):
    titulo: Optional[str] = None
    conteudo: Optional[str] = None
    categoria: Optional[str] = None


class AdminCriarConhecimento(BaseModel):
    titulo: str
    conteudo: str
    categoria: str
