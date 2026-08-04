"""Seam única entre os providers de LLM (DeepSeek e Anthropic).

Nenhum outro módulo deve importar `anthropic`/`openai` diretamente ou tocar
em `client`/`deepseek_client` de app/config.py — tudo passa por
`resposta_stream` (usada pelo /chat, que precisa de streaming + imagens +
cache_control) ou `resposta_simples` (usada por /compact e gerar_resumo_rag,
não-streaming e sem imagens). Isso mantém os call sites agnósticos de qual
provider está ativo (MODELO_PROVIDER) e concentra num só lugar as diferenças
de formato de mensagem, thinking mode e nomes de campos de usage.
"""

from dataclasses import dataclass
from typing import Iterator

import anthropic
import openai

from app.config import ANTHROPIC_MODEL, DEEPSEEK_MODEL, MODELO_PROVIDER, client, deepseek_client


@dataclass
class UsoNormalizado:
    """Mesmo shape que `registrar_uso_cache` já espera (mesmos nomes de
    atributo do `usage` nativo da Anthropic) — DeepSeek é traduzido pra cá,
    Anthropic já vem pronto no formato certo."""

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


def _traduzir_erro_anthropic(e: Exception) -> Exception:
    if isinstance(e, anthropic.APIStatusError):
        tipo = ""
        body = getattr(e, "body", None)
        if isinstance(body, dict):
            tipo = (body.get("error") or {}).get("type", "")
        if e.status_code == 529 or tipo == "overloaded_error":
            return LLMSobrecarregado(str(e))
        if e.status_code == 429 or tipo == "rate_limit_error":
            return LLMLimiteRequisicoes(str(e))
        return LLMErro(f"Erro da API ({tipo or e.status_code})")
    if isinstance(e, anthropic.APIConnectionError):
        return LLMConexaoFalhou(str(e))
    return e


def _traduzir_erro_openai(e: Exception) -> Exception:
    if isinstance(e, openai.RateLimitError):
        return LLMLimiteRequisicoes(str(e))
    if isinstance(e, openai.APIStatusError):
        if e.status_code == 503:
            return LLMSobrecarregado(str(e))
        return LLMErro(f"Erro da API ({e.status_code})")
    if isinstance(e, openai.APIConnectionError):
        return LLMConexaoFalhou(str(e))
    return e


def _blocos_para_texto(blocos: list[dict]) -> str:
    """Achata blocos de `system` (lista, formato Anthropic) numa string só —
    usado no branch DeepSeek. `cache_control` é ignorado de propósito: a
    DeepSeek cacheia automaticamente, sem marcação explícita no request."""
    return "\n\n".join(b["text"] for b in blocos)


def _mensagens_para_openai(messages: list[dict]) -> list[dict]:
    """Converte o array `messages` (formato Anthropic — content pode ser
    string ou lista de blocos texto/imagem) para o formato OpenAI. Assume que
    NÃO há blocos de imagem (o call site bloqueia imagem sob DeepSeek antes
    de chegar aqui — ver chat.py)."""
    convertidas = []
    for m in messages:
        conteudo = m["content"]
        if isinstance(conteudo, str):
            convertidas.append({"role": m["role"], "content": conteudo})
            continue
        # Lista de blocos (texto, possivelmente com cache_control — ignorado
        # aqui pelo mesmo motivo do system) — junta só os blocos de texto.
        texto = "\n\n".join(b["text"] for b in conteudo if b.get("type") == "text")
        convertidas.append({"role": m["role"], "content": texto})
    return convertidas


def resposta_stream(
    system_blocks: list[dict], messages: list[dict], max_tokens: int
) -> tuple[Iterator[str], "list[UsoNormalizado]"]:
    """Retorna (iterador de texto, lista-de-1-elemento que recebe o usage
    normalizado ao final do streaming — truque simples pra devolver um valor
    "por referência" de dentro de um generator sem precisar de classe extra).
    O chamador (chat.py) deve consumir o iterador inteiro antes de ler
    `usage_out[0]`."""
    usage_out: list[UsoNormalizado] = []

    if MODELO_PROVIDER == "anthropic":

        def _gen_anthropic():
            try:
                with client.messages.stream(
                    model=ANTHROPIC_MODEL,
                    max_tokens=max_tokens,
                    system=system_blocks,
                    messages=messages,
                ) as stream:
                    for texto in stream.text_stream:
                        yield texto
                    final = stream.get_final_message()
                usage_out.append(
                    UsoNormalizado(
                        input_tokens=final.usage.input_tokens,
                        cache_creation_input_tokens=getattr(
                            final.usage, "cache_creation_input_tokens", 0
                        )
                        or 0,
                        cache_read_input_tokens=getattr(
                            final.usage, "cache_read_input_tokens", 0
                        )
                        or 0,
                        output_tokens=final.usage.output_tokens,
                    )
                )
            except Exception as e:
                raise _traduzir_erro_anthropic(e) from e

        return _gen_anthropic(), usage_out

    # DeepSeek
    system_texto = _blocos_para_texto(system_blocks)
    mensagens_openai = [{"role": "system", "content": system_texto}] + _mensagens_para_openai(
        messages
    )

    def _gen_deepseek():
        try:
            stream = deepseek_client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                max_tokens=max_tokens,
                messages=mensagens_openai,
                thinking={"type": "disabled"},
                stream=True,
                stream_options={"include_usage": True},
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
            raise _traduzir_erro_openai(e) from e

    return _gen_deepseek(), usage_out


def resposta_simples(system_text: str, user_content: str, max_tokens: int) -> tuple[str, UsoNormalizado]:
    """Chamada não-streaming, sem imagens — usada por /compact (resumo de
    sessão) e gerar_resumo_rag (knowledge.py)."""
    if MODELO_PROVIDER == "anthropic":
        try:
            resp = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=max_tokens,
                system=system_text,
                messages=[{"role": "user", "content": user_content}],
            )
        except Exception as e:
            raise _traduzir_erro_anthropic(e) from e
        texto = "".join(b.text for b in resp.content if b.type == "text").strip()
        uso = UsoNormalizado(
            input_tokens=resp.usage.input_tokens,
            cache_creation_input_tokens=getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
            cache_read_input_tokens=getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
            output_tokens=resp.usage.output_tokens,
        )
        return texto, uso

    # DeepSeek
    try:
        resp = deepseek_client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_content},
            ],
            thinking={"type": "disabled"},
        )
    except Exception as e:
        raise _traduzir_erro_openai(e) from e
    texto = (resp.choices[0].message.content or "").strip()
    uso = UsoNormalizado(
        input_tokens=resp.usage.prompt_cache_miss_tokens or 0,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=resp.usage.prompt_cache_hit_tokens or 0,
        output_tokens=resp.usage.completion_tokens,
    )
    return texto, uso
