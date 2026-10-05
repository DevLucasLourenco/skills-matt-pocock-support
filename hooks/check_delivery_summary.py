#!/usr/bin/env python3
"""Hook Stop opcional: verifica fechamento e pendências após edição ou delegação.

Exige o painel quando há evidência de uso de show_widget na sessão.
Erros internos liberam o encerramento para evitar travar a sessão.
As mensagens de bloqueio são fixas, pois voltam ao agente como instruções.
"""

from __future__ import annotations

import json
import sys
import unicodedata

SECAO = "decisoes humanas pendentes"
CABECALHO = "fechamento da entrega"
FERRAMENTAS_DE_EDICAO = frozenset({"Edit", "MultiEdit", "Write", "NotebookEdit"})
FERRAMENTAS_DE_DELEGACAO = frozenset({"Agent", "Task"})
MOTIVO = (
    'Inclua o fechamento gerado pela skill delivery-summary, com o cabeçalho '
    '"Fechamento da entrega" e a seção "Decisões humanas pendentes".'
)
MOTIVO_PAINEL = (
    "Exiba a saída --formato html da skill delivery-summary em show_widget "
    "e inclua a saída --formato marca na resposta."
)
MARCA = "detalhes no painel acima"
FERRAMENTA_DE_PAINEL = "show_widget"


def _normalizar(texto: str) -> str:
    """Sem acento, sem caixa e com espaços colapsados."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acento.casefold().split())


def tem_secao(mensagem: str) -> bool:
    """O fechamento gerado está na mensagem: cabeçalho do gerador e seção de pendências."""
    texto = _normalizar(mensagem)
    return CABECALHO in texto and SECAO in texto


def _conteudo(entrada: dict) -> object:
    mensagem = entrada.get("message")
    return mensagem.get("content") if isinstance(mensagem, dict) else None


def _e_prompt_do_usuario(entrada: dict) -> bool:
    """Mensagem digitada pelo usuário — não resultado de ferramenta nem injeção do sistema."""
    if entrada.get("type") != "user" or entrada.get("isMeta") or entrada.get("isSidechain"):
        return False
    conteudo = _conteudo(entrada)
    if isinstance(conteudo, str):
        return True
    if isinstance(conteudo, list):
        return not any(
            isinstance(bloco, dict) and bloco.get("type") == "tool_result" for bloco in conteudo
        )
    return False


def _usa_edicao(entrada: dict) -> bool:
    if entrada.get("type") != "assistant":
        return False
    conteudo = _conteudo(entrada)
    if not isinstance(conteudo, list):
        return False
    return any(
        isinstance(bloco, dict)
        and bloco.get("type") == "tool_use"
        and bloco.get("name") in FERRAMENTAS_DE_EDICAO | FERRAMENTAS_DE_DELEGACAO
        for bloco in conteudo
    )


def editou_no_turno(linhas: list[str]) -> bool:
    """Houve edição de arquivo, ou delegação a subagente, desde o último prompt do usuário?

    Percorre o transcript do fim para o começo e para no primeiro prompt, para
    não reprocessar a sessão inteira a cada turno.
    """
    for linha in reversed(linhas):
        try:
            entrada = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if not isinstance(entrada, dict):
            continue
        if _usa_edicao(entrada):
            return True
        if _e_prompt_do_usuario(entrada):
            return False
    return False


def _chamadas_de_painel(entrada: dict) -> list[str]:
    """Texto normalizado da entrada de cada chamada a `show_widget` nesta mensagem."""
    if entrada.get("type") != "assistant":
        return []
    conteudo = _conteudo(entrada)
    if not isinstance(conteudo, list):
        return []
    return [
        _normalizar(json.dumps(bloco.get("input"), ensure_ascii=False))
        for bloco in conteudo
        if isinstance(bloco, dict)
        and bloco.get("type") == "tool_use"
        and str(bloco.get("name", "")).endswith(FERRAMENTA_DE_PAINEL)
    ]


def _entradas(linhas: list[str]) -> list[dict]:
    entradas = []
    for linha in linhas:
        try:
            entrada = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(entrada, dict):
            entradas.append(entrada)
    return entradas


def painel_faltando(mensagem: str, linhas: list[str]) -> bool:
    """A sessão prova ter `show_widget` (ou a marca o indica) e o turno não exibiu o painel?"""
    entradas = _entradas(linhas)
    sessao_usa_painel = any(_chamadas_de_painel(e) for e in entradas)
    if not (sessao_usa_painel or MARCA in _normalizar(mensagem)):
        return False
    for entrada in reversed(entradas):
        if any(CABECALHO in chamada for chamada in _chamadas_de_painel(entrada)):
            return False
        if _e_prompt_do_usuario(entrada):
            break
    return True


def decidir(payload: dict) -> str | None:
    """Devolve o motivo do bloqueio, ou None para deixar o turno encerrar."""
    if payload.get("stop_hook_active"):
        # já bloqueamos uma vez neste encerramento; insistir criaria laço
        return None
    mensagem = payload.get("last_assistant_message")
    if not isinstance(mensagem, str):
        return None
    caminho = payload.get("transcript_path")
    if not isinstance(caminho, str) or not caminho:
        return None
    with open(caminho, encoding="utf-8", errors="replace") as arquivo:
        linhas = arquivo.readlines()
    if not editou_no_turno(linhas):
        return None
    if not tem_secao(mensagem):
        return MOTIVO
    return MOTIVO_PAINEL if painel_faltando(mensagem, linhas) else None


def main() -> int:
    try:
        # o payload chega em UTF-8; a codificação padrão do Windows corromperia os acentos
        sys.stderr.reconfigure(encoding="utf-8")
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        motivo = decidir(payload) if isinstance(payload, dict) else None
    except Exception as exc:  # falha aberta: ver docstring do módulo
        print(f"check_delivery_summary: erro interno ignorado: {exc}", file=sys.stderr)
        return 0
    if motivo is None:
        return 0
    print(motivo, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
