"""Chamadas ao LLM (DeepSeek, API OpenAI-compatible).

Nenhum outro módulo deve importar `openai` diretamente ou tocar em
`deepseek_client` de app/config.py — tudo passa por `resposta_stream` (usada
pelo /chat, que precisa de streaming) ou `resposta_simples` (usada por
/compact e gerar_resumo_rag, não-streaming). Isso concentra num só lugar o
formato de mensagem, o desligamento do thinking mode e a normalização de
usage.
"""

from dataclasses import dataclass
from typing import Iterator

import openai

from app.config import DEEPSEEK_MODEL, deepseek_client


@dataclass
class UsoNormalizado:
    """Shape que `registrar_uso_cache` espera: input_tokens ←
    prompt_cache_miss_tokens, cache_read_input_tokens ←
    prompt_cache_hit_tokens, cache_creation_input_tokens sempre 0 (a DeepSeek
    não tem conceito de "cache write" pago à parte — só miss/hit)."""

    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int


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
            stream = deepseek_client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                max_tokens=max_tokens,
                messages=mensagens_openai,
                stream=True,
                stream_options={"include_usage": True},
                # "thinking" é extensão específica da DeepSeek, fora do
                # schema padrão da OpenAI — o SDK só aceita via extra_body.
                extra_body={"thinking": {"type": "disabled"}},
            )
            for chunk in stream:
                if chunk.usage is not None:
                    usage_out.append(
                        UsoNormalizado(
                            input_tokens=chunk.usage.prompt_cache_miss_tokens or 0,
                            cache_creation_input_tokens=0,
                            cache_read_input_tokens=chunk.usage.prompt_cache_hit_tokens or 0,
                            output_tokens=chunk.usage.completion_tokens,
                        )
                    )
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
        resp = deepseek_client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_content},
            ],
            extra_body={"thinking": {"type": "disabled"}},
        )
    except Exception as e:
        raise _traduzir_erro(e) from e
    texto = (resp.choices[0].message.content or "").strip()
    uso = UsoNormalizado(
        input_tokens=resp.usage.prompt_cache_miss_tokens or 0,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=resp.usage.prompt_cache_hit_tokens or 0,
        output_tokens=resp.usage.completion_tokens,
    )
    return texto, uso
