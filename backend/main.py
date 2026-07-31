"""
Backend da POC do Agente CAD/NX.

FastAPI + streaming (SSE) da API do Claude + autenticação de usuários no
PostgreSQL (email/senha) + memória pessoal por usuário + base de conhecimento
compartilhada no Postgres.

Fase consultiva apenas: o agente NÃO executa nada no NX.

Este arquivo é só o "composition root": cria o app, registra middlewares,
inclui os routers de cada área (app/routers/*) e cuida do fallback de SPA do
frontend React. Toda a lógica de negócio, acesso a dados e rotas em si vive
em app/ — ver app/config.py para o mapa geral dos módulos.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from app.config import FRONTEND_DIST, SESSION_SECRET, limiter
from app.db import garantir_schema
from app.repositories.users import seed_admins
from app.routers import admin, auth, chat, knowledge, pages, sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    garantir_schema()
    seed_admins()
    yield


app = FastAPI(title="Agente CAD/NX — POC", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    https_only=False,  # POC local em http
    same_site="lax",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Headers de segurança em toda resposta. CSP aqui só se aplica quando o
# FastAPI serve o HTML (produção, via frontend/dist) — em `npm run dev` o
# Vite serve o index.html diretamente, e a mesma política já está numa tag
# <meta http-equiv="Content-Security-Policy"> em frontend/index.html.
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "connect-src 'self'"
    )
    return response


app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(sessions.router)
app.include_router(knowledge.router)
app.include_router(chat.router)

# ---------------------------------------------------------------------------
# Frontend — o build do React (Vite) fica em frontend/dist. Os bundles JS/CSS
# são servidos em /assets; qualquer rota que não bata com nenhuma rota de API
# acima devolve index.html e o roteamento (login, chat, admin,
# change-password) passa a ser client-side (react-router).
# ---------------------------------------------------------------------------
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


# ---------------------------------------------------------------------------
# SPA fallback — DEVE ser a última rota registrada (Starlette casa rotas na
# ordem de declaração; se viesse antes, "engoliria" as rotas de API acima).
# ---------------------------------------------------------------------------
@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    index_path = FRONTEND_DIST / "index.html"
    if not index_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend não buildado — rode `npm run build` em frontend/.",
        )
    # Arquivos estáticos na raiz do build (favicon.svg, logo.png, icons.svg —
    # tudo que vem de frontend/public/) precisam ser servidos como estão; sem
    # isso, /favicon.svg cai neste fallback e devolve index.html (HTML em vez
    # de imagem), e o navegador mostra o ícone genérico de globo.
    candidato = FRONTEND_DIST / full_path
    if full_path and candidato.is_file() and candidato.resolve().is_relative_to(FRONTEND_DIST.resolve()):
        return FileResponse(candidato)
    return FileResponse(index_path)
