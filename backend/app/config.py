"""Configuração e constantes globais do backend."""

import os
import re
from pathlib import Path

import anthropic
import voyageai
from dotenv import load_dotenv
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

load_dotenv()

# Em redes corporativas com inspeção TLS (ex.: Schwaben), a chamada HTTPS para
# api.anthropic.com falha com "self-signed certificate in certificate chain".
# O truststore faz o Python usar a loja de certificados do próprio SO (Windows).
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

MODEL = "claude-haiku-4-5"

# Preços do claude-haiku-4-5 (USD por token) — para estimar a economia do
# prompt caching no painel de admin. Cache write custa 1.25x o input normal;
# cache read custa 0.1x.
PRECO_INPUT = 1.00 / 1_000_000
PRECO_OUTPUT = 5.00 / 1_000_000
MULT_CACHE_WRITE = 1.25
MULT_CACHE_READ = 0.1
PUBLIC_DIR = Path(__file__).parent.parent.parent / "public"
FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

# Limites de imagens coladas no chat (Ctrl+V) — evita payloads absurdos.
MAX_IMAGENS_POR_MENSAGEM = 4
MAX_BYTES_POR_IMAGEM = 5 * 1024 * 1024
MEDIA_TYPES_PERMITIDOS = {"image/png", "image/jpeg", "image/gif", "image/webp"}
DATA_URL_RE = re.compile(r"^data:(image/[a-zA-Z+]+);base64,(.+)$", re.DOTALL)

SESSION_SECRET = os.getenv("SESSION_SECRET")
if not SESSION_SECRET:
    SESSION_SECRET = "dev-insecure-please-set-SESSION_SECRET"
    print("[aviso] SESSION_SECRET não definido no .env — usando segredo de dev.")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Emails que viram admin (TI) automaticamente ao logar/cadastrar.
ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.getenv("ADMIN_EMAILS", "").split(",")
    if e.strip()
}

# Cliente Anthropic — lê ANTHROPIC_API_KEY do ambiente. max_retries=4 absorve
# picos de sobrecarga (429/5xx/529) com backoff exponencial automático.
client = anthropic.Anthropic(max_retries=4)

# --- RAG (Voyage AI) ---------------------------------------------------------
# Client Voyage — lê VOYAGE_API_KEY do ambiente. Como truststore.inject_into_ssl()
# acima patcheia o SSL do processo inteiro, a chamada à Voyage já confia no
# certificado da rede corporativa sem config extra.
voyage_client = voyageai.Client(max_retries=2)

VOYAGE_MODEL = os.getenv("VOYAGE_MODEL", "voyage-3.5")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))  # tem que bater com vector(N) no schema
RAG_TOP_N = int(os.getenv("RAG_TOP_N", "4"))             # nº de entradas recuperadas por pergunta
RAG_LIMIAR = float(os.getenv("RAG_LIMIAR", "0.4"))       # score mínimo de similaridade p/ injetar

# Rate limiting (em memória — um único processo uvicorn, sem réplicas).
# Prioridade: /auth/login (força bruta de senha) e rotas que chamam a API do
# Claude (/chat, /compact), onde cada requisição tem custo real.
limiter = Limiter(key_func=get_remote_address)


def get_user_or_ip(request: Request) -> str:
    # Para rotas já autenticadas (/chat, /compact), limitar por IP é o alvo
    # errado numa rede corporativa com NAT: todo mundo sai pelo mesmo IP
    # externo, e o teto vira compartilhado pela empresa toda em vez de por
    # pessoa. O SessionMiddleware roda como middleware ASGI, então
    # request.session já está populado aqui, antes do Depends(...) da rota
    # resolver — não precisamos esperar a dependência de auth rodar.
    user_id = request.session.get("user_id")
    return f"user:{user_id}" if user_id is not None else get_remote_address(request)
