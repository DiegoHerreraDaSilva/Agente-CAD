"""Configuração e constantes globais do backend."""

import os
import re
from pathlib import Path

import anthropic
import voyageai
from dotenv import load_dotenv
from fastapi import Request
from openai import OpenAI
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

ANTHROPIC_MODEL = "claude-haiku-4-5"

# --- Provider de LLM: DeepSeek (default) ou Anthropic ------------------------
# DeepSeek é OpenAI-compatible e custa ~15x menos que o Haiku no fluxo deste
# app (ver README, seção "Provider de LLM"). MODELO_PROVIDER=anthropic mantém
# o comportamento anterior (streaming + imagens + cache_control nativo).
MODELO_PROVIDER = os.getenv("MODELO_PROVIDER", "deepseek").strip().lower()
if MODELO_PROVIDER not in ("deepseek", "anthropic"):
    raise RuntimeError(
        f"MODELO_PROVIDER inválido: {MODELO_PROVIDER!r} — use 'deepseek' ou 'anthropic'."
    )

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
# Slug explícito — os aliases legados deepseek-chat/deepseek-reasoner foram
# descontinuados em 24/07/2026.
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

if MODELO_PROVIDER == "deepseek" and not DEEPSEEK_API_KEY:
    # Falha rápido: diferente do aviso brando de SESSION_SECRET, sem essa
    # chave o provider DEFAULT do app não funciona de jeito nenhum — melhor
    # travar no startup do que só descobrir na primeira mensagem de chat.
    raise RuntimeError(
        "MODELO_PROVIDER=deepseek (default) mas DEEPSEEK_API_KEY não está "
        "definida no .env. Defina a chave (platform.deepseek.com) ou mude "
        "MODELO_PROVIDER=anthropic."
    )

# Client DeepSeek (OpenAI-compatible) — só instanciado se a chave existir;
# truststore.inject_into_ssl() acima já cobre o TLS corporativo pra qualquer
# host, sem config extra por client.
deepseek_client = (
    OpenAI(base_url="https://api.deepseek.com", api_key=DEEPSEEK_API_KEY, max_retries=4)
    if DEEPSEEK_API_KEY
    else None
)

# Preços por provider (USD por token), pra estimar a economia no painel de
# admin (/admin/cache-stats). Estruturalmente diferentes: Anthropic cobra
# input × multiplicador de cache write/read; DeepSeek cobra preço absoluto
# por cache miss/hit (sem conceito de "cache write" — cache_creation é
# sempre 0 nela). Nunca somar tokens brutos entre providers e aplicar um
# preço só — ver admin.py.
PRECOS = {
    "anthropic": {
        "input": 1.00 / 1_000_000,
        "output": 5.00 / 1_000_000,
        "cache_write_mult": 1.25,
        "cache_read_mult": 0.1,
    },
    "deepseek": {
        "miss": 0.14 / 1_000_000,
        "hit": 0.0028 / 1_000_000,
        "output": 0.28 / 1_000_000,
    },
}

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
RAG_JANELA_REINJECAO = int(os.getenv("RAG_JANELA_REINJECAO", "10"))  # turnos até reinjetar uma entrada já mandada

# resumo_rag: só gera versão condensada pra injeção quando o conteúdo passa
# deste tamanho (aprox. 800 tokens ~ 4 chars/token). Entradas curtas já são o
# caso ótimo — resumir não ajuda e arrisca cortar detalhe técnico importante.
RESUMO_RAG_MIN_CHARS = int(os.getenv("RESUMO_RAG_MIN_CHARS", "3200"))

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
