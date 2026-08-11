"""Chamadas ao LLM (DeepSeek).

Nenhum outro módulo deve importar `openai` diretamente ou tocar em
`llm_client`/`LLM_MODEL` de app/config.py — tudo passa por `resposta_stream`
(usada pelo /chat, que precisa de streaming) ou `resposta_simples` (usada por
/compact e gerar_resumo_rag, não-streaming). Isso concentra num só lugar o
formato de mensagem, o desligamento do thinking mode e a normalização de
usage.
"""

from dataclasses import dataclass
from typing import Iterator

import openai

from app.config import LLM_MODEL, llm_client


@dataclass
class UsoNormalizado:
    """Shape que `registrar_uso_cache` espera: input_tokens ←
    prompt_cache_miss_tokens, cache_read_input_tokens ← prompt_cache_hit_tokens
    (cache_creation_input_tokens sempre 0 — a DeepSeek não tem conceito de
    "cache write" pago à parte, só miss/hit)."""

    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int


def _normalizar_usage(usage) -> UsoNormalizado:
    """Os campos prompt_cache_miss_tokens/prompt_cache_hit_tokens são uma
    extensão específica da DeepSeek — getattr com default evita AttributeError
    caso a API pare de mandar esse detalhe."""
    miss = getattr(usage, "prompt_cache_miss_tokens", None)
    hit = getattr(usage, "prompt_cache_hit_tokens", None) or 0
    if miss is None:
        miss = (usage.prompt_tokens or 0) - hit
    return UsoNormalizado(
        input_tokens=miss,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=hit,
        output_tokens=usage.completion_tokens or 0,
    )


# "thinking" é extensão específica da DeepSeek (fora do schema padrão da
# OpenAI) pra desligar o reasoning mode — sem isso, cada resposta gasta muito
# mais tokens de saída (e dinheiro) do que parece.
_EXTRA_BODY_DEEPSEEK = {"thinking": {"type": "disabled"}}


class LLMErro(Exception):
    """Erro genérico do provider, sem tratamento especial no chamador."""


class LLMSobrecarregado(LLMErro):
    pass


class LLMLimiteRequisicoes(LLMErro):
    pass


class LLMConexaoFalhou(LLMErro):
    pass


def _traduzir_erro(e: Exception) -> Exception:
    if isinstance(e, openai.RateLimitError):
        return LLMLimiteRequisicoes(str(e))
    if isinstance(e, openai.APIStatusError):
        if e.status_code == 503:
            return LLMSobrecarregado(str(e))
        # Loga o corpo real do erro (não exposto ao usuário) — status code
        # sozinho ("Erro da API (400)") não dá pista nenhuma de causa.
        print(f"[llm] erro {e.status_code} do provider: {e}")
        return LLMErro(f"Erro da API ({e.status_code})")
    if isinstance(e, openai.APIConnectionError):
        return LLMConexaoFalhou(str(e))
    return e


def resposta_stream(
    system_text: str, messages: list[dict], max_tokens: int
) -> tuple[Iterator[str], "list[UsoNormalizado]"]:
    """Retorna (iterador de texto, lista-de-1-elemento que recebe o usage
    normalizado ao final do streaming — truque simples pra devolver um valor
    "por referência" de dentro de um generator sem precisar de classe extra).
    O chamador (chat.py) deve consumir o iterador inteiro antes de ler
    `usage_out[0]`."""
    usage_out: list[UsoNormalizado] = []
    mensagens_openai = [{"role": "system", "content": system_text}, *messages]

    def _gen():
        try:
            stream = llm_client.chat.completions.create(
                model=LLM_MODEL,
                max_tokens=max_tokens,
                messages=mensagens_openai,
                stream=True,
                stream_options={"include_usage": True},
                extra_body=_EXTRA_BODY_DEEPSEEK,
            )
            for chunk in stream:
                if chunk.usage is not None:
                    usage_out.append(_normalizar_usage(chunk.usage))
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
        except Exception as e:
            raise _traduzir_erro(e) from e

    return _gen(), usage_out


def resposta_simples(system_text: str, user_content: str, max_tokens: int) -> tuple[str, UsoNormalizado]:
    """Chamada não-streaming, sem imagens — usada por /compact (resumo de
    sessão) e gerar_resumo_rag (knowledge.py)."""
    try:
        resp = llm_client.chat.completions.create(
            model=LLM_MODEL,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_content},
            ],
            extra_body=_EXTRA_BODY_DEEPSEEK,
        )
    except Exception as e:
        raise _traduzir_erro(e) from e
    texto = (resp.choices[0].message.content or "").strip()
    uso = _normalizar_usage(resp.usage)
    return texto, uso
