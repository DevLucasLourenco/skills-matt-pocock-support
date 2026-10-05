#!/usr/bin/env python3
"""Gera o panorama das fases e dos tickets de cada uma.

Lê `docs/panorama-das-fases.md` e `.scratch/f*/issues/M*.md`, calcula o estado
de cada ticket e de cada fase, e devolve painel HTML, linha de marca ou markdown.
É leitura pura: só abre arquivos do repositório e roda `git` somente leitura.
Só biblioteca padrão.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

CABECALHO = "Panorama das fases"

# estado do ticket: (rótulo, ícone Tabler, papel de cor)
ESTADOS = {
    "concluido": ("Concluído", "ti-circle-check", "success"),
    "implementado": ("Implementado", "ti-circle-check", "success"),
    "andamento": ("Em andamento", "ti-loader", "accent"),
    "pronto": ("Pronto para começar", "ti-player-play", "neutro"),
    "travado": ("Travado", "ti-lock", "warning"),
    "needs-info": ("Aguarda você", "ti-user-question", "warning"),
    "humano": ("Com o mantenedor", "ti-user", "warning"),
    "triagem": ("Em triagem", "ti-inbox", "neutro"),
    "descartado": ("Descartado", "ti-ban", "neutro"),
    "indefinido": ("Sem estado", "ti-help", "neutro"),
}
ENTREGUES = {"concluido", "implementado"}
# estados que viram "travado" quando um bloqueador ainda não foi entregue
PODE_TRAVAR = {"pronto", "triagem", "indefinido"}

ROTULO_FASE = {
    "concluida": "Concluída",
    "andamento": "Em andamento",
    "nao-iniciada": "Não iniciada",
    "sem-ticket": "Sem spec nem ticket",
}
PAPEL_FASE = {
    "concluida": "success",
    "andamento": "accent",
    "nao-iniciada": "neutro",
    "sem-ticket": "neutro",
}

MAX_AVISOS = 10
MAX_TITULO_AVISO = 80
MAX_TEXTO_AVISO = 400
MAX_TITULO_TICKET = 160
MAX_NOME_PROJETO = 60  # caracteres do nome do projeto no título do painel
MAX_BYTES = 1024 * 1024  # teto de leitura por arquivo
MAX_FAIXA = 200  # tickets numa faixa `M1 a M12` do Blocked by
MAX_REFS = 500  # referências expandidas por ticket
MAX_BLOQUEIO = 2000  # caracteres do campo Blocked by
MAX_TICKETS = 1000  # tickets lidos de .scratch
SEM_TICKET = " (sem ticket)"

# cores com reserva: se o app não definir a variável, o painel continua legível
COR_ENTREGUE = "var(--fill-success,var(--text-success))"
COR_ANDAMENTO = "var(--fill-accent,var(--text-accent))"
COR_PRONTO = "var(--border-stronger,var(--border-strong))"
COR_OUTROS = "var(--fill-warning,var(--text-warning))"


class ErroDados(Exception):
    """Dado de entrada ausente, inválido ou fora dos limites."""


# ---------------------------------------------------------------- leitura

_FASE = r"F\d+[a-z]?"
_RE_FASE_LINHA = re.compile(rf"^\|\s*\*\*({_FASE})\*\*\s*\|")
_RE_FASE_CABECALHO = re.compile(r"^\|\s*Fase\s*\|\s*Bloco\s*\|")
_RE_FASE_ID = re.compile(r"F(\d+)([a-z]?)")
_RE_FASE_DIR = re.compile(r"^f(\d+[a-z]?)-")
_RE_TICKET = re.compile(r"^M(\d+)-")
_RE_STATUS = re.compile(r"^\*\*Status:\*\*\s*(.*)$")
_RE_BLOQUEIO = re.compile(r"^\*\*Blocked by:\*\*\s*(.*)$")
_RE_ITEM = re.compile(r"^- \[( |x|X)\]")
# Aceita estado simples ou data logo após o estado; ressalvas anteriores não contam.
_RE_ENTREGUE = re.compile(r"(?:conclu[ií]d[oa]|implementado)(?: e fechado)?\s*(?:\(\d{4}-\d{2}-\d{2}\)|$)")
_RE_FAIXA_ESTRANHA = re.compile(
    r"M\d+\s*(?:[-–~…]|\.{2,}|até|ate|\bto\b)\s*(?:F\d+[a-z]?/)?M\d+", re.IGNORECASE
)
# "None" puro, ou "None" com um comentário de uma lista curta de frases inofensivas
_RE_NENHUM_SEGURO = re.compile(
    r"(?:none|nenhum|—|-)"
    r"(?:(?:\s+[—–-]\s+|\s*\(\s*|\s+)(?:pode começar|n[ãa]o depende|sem depend[êe]ncias?|nenhuma depend[êe]ncia|nada)\b.*)?",
    re.IGNORECASE,
)
_RE_REF = re.compile(
    r"(?<![A-Za-z0-9])(?:F(\d+[a-z]?)/)?M(\d{1,4})(?!\d)"
    r"(?:\s+a\s+(?:F(\d+[a-z]?)/)?M(\d{1,4})(?!\d))?"
)


def _chave_fase(fase: str) -> tuple[int, str]:
    m = _RE_FASE_ID.fullmatch(fase)
    return (int(m.group(1)), m.group(2)) if m else (10**9, fase)


def _id_fase(token: str) -> str:
    m = re.fullmatch(r"(\d+)([a-z]?)", token)
    return f"F{int(m.group(1))}{m.group(2)}" if m else f"F{token}"


def _ler_arquivo(caminho: Path) -> str:
    """Lê um arquivo de texto de tamanho limitado, em UTF-8 estrito (aceita BOM)."""
    try:
        if not caminho.is_file():
            raise ErroDados(f"{caminho.name}: não é um arquivo comum")
        if caminho.stat().st_size > MAX_BYTES:
            raise ErroDados(f"{caminho.name}: passa de {MAX_BYTES // 1024} KiB")
        return caminho.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ErroDados(f"{caminho.name}: não está em UTF-8") from exc
    except OSError as exc:
        raise ErroDados(f"{caminho.name}: não consegui ler ({exc.strerror or exc})") from exc


def _sem_invisiveis(texto: str, onde: str) -> str:
    """Recusa caractere invisível (categoria Unicode Cf) em Status e Blocked by."""
    if any(unicodedata.category(c) == "Cf" for c in texto):
        raise ErroDados(f"{onde}: caractere invisível em Status ou Blocked by")
    return texto


def _ler_do_repositorio(raiz: Path, caminho: Path) -> str:
    """Lê arquivo do repositório sem seguir link para fora dele."""
    try:
        caminho.resolve().relative_to(raiz.resolve())
    except (OSError, ValueError) as exc:
        raise ErroDados(f"{caminho.name}: aponta para fora do repositório") from exc
    if caminho.is_symlink():
        raise ErroDados(f"{caminho.name}: é um link simbólico")
    return _ler_arquivo(caminho)


def ler_fases(raiz: Path) -> dict[str, dict[str, str]]:
    caminho = raiz / "docs" / "panorama-das-fases.md"
    if not caminho.is_file():
        raise ErroDados("não encontrei docs/panorama-das-fases.md")
    fases: dict[str, dict[str, str]] = {}
    na_tabela = False
    for linha in _ler_do_repositorio(raiz, caminho).splitlines():
        if not na_tabela:
            na_tabela = bool(_RE_FASE_CABECALHO.match(linha))
            continue
        if not linha.startswith("|"):
            break  # fim da primeira tabela, a das fases
        if re.fullmatch(r"\|[\s:|-]+\|?\s*", linha):
            continue  # separador do cabeçalho
        achada = _RE_FASE_LINHA.match(linha)
        celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
        if not achada or len(celulas) < 4 or not celulas[3]:
            # fase que o script não entende some do painel: melhor recusar do que omitir
            raise ErroDados(f"docs/panorama-das-fases.md: linha de fase em formato desconhecido: {linha[:60]}")
        if achada.group(1) in fases:
            raise ErroDados(f"docs/panorama-das-fases.md: fase repetida: {achada.group(1)}")
        fases[achada.group(1)] = {
            "bloco": celulas[1],
            "entrega": celulas[2],
            "estado": celulas[3],
        }
    if not fases:
        raise ErroDados("a tabela de fases do docs/panorama-das-fases.md está vazia ou mudou de formato")
    return dict(sorted(fases.items(), key=lambda kv: _chave_fase(kv[0])))


def categoria_declarada(estado: str) -> str | None:
    """Estado simples que o `docs/panorama-das-fases.md` declara; None quando o texto é livre e não dá para comparar."""
    texto = estado.lower().strip(" *`_.")
    if "sem spec" in texto or "sem ticket" in texto:
        return "sem-ticket"
    if "não iniciada" in texto or "nao iniciada" in texto:
        return "nao-iniciada"
    if texto.startswith("em andamento"):
        return "andamento"
    if texto.startswith("conclu"):
        return "concluida"
    return None


def classificar(status: str) -> str:
    texto = status.lower().lstrip(" *`_")
    if _RE_ENTREGUE.match(texto):
        return "concluido" if texto.startswith("conclu") else "implementado"
    if texto.startswith(("em andamento", "em revisão", "em revisao")):
        return "andamento"
    if texto.startswith("needs-info"):
        return "needs-info"
    if texto.startswith("ready-for-agent"):
        return "pronto"
    if texto.startswith("ready-for-human"):
        return "humano"
    if texto.startswith("needs-triage"):
        return "triagem"
    if texto.startswith("wontfix"):
        return "descartado"
    return "indefinido"


def bloqueadores(texto: str, fase: str) -> list[tuple[str, int]]:
    """Referências `M<N>`, `F<N>/M<N>` e faixas `M1 a M12` do campo Blocked by."""
    texto = texto.strip()
    if len(texto) > MAX_BLOQUEIO:
        raise ErroDados(f"Blocked by com mais de {MAX_BLOQUEIO} caracteres: {texto[:60]}")
    # "None — depende de M5" não zera o bloqueio: referência em comentário também conta
    if re.search(r"(?<![A-Za-z0-9])M\d{5,}", texto):
        raise ErroDados(f"Blocked by com número de ticket fora do limite: {texto[:60]}")
    # só valem M<N>, F<N>/M<N> e "M<N> a M<N>": "M3 até M5", "F1-M3" ou "F2B/M3" não
    # resolvem para o ticket certo, então ficam de fora e o campo é recusado
    resto = _RE_REF.sub("", texto)
    if _RE_FAIXA_ESTRANHA.search(texto) or re.search(
        r"(?<![A-Za-z0-9])[Ff]\d|(?<![A-Za-z0-9])[Mm]\d", resto
    ):
        raise ErroDados(
            f"Blocked by com referência fora do formato M<N>, F<N>/M<N> ou M<N> a M<N>: {texto[:60]}"
        )
    refs: list[tuple[str, int]] = []
    for f1, n1, f2, n2 in _RE_REF.findall(texto):
        origem = _id_fase(f1) if f1 else fase
        if not n2:
            refs.append((origem, int(n1)))
        else:
            destino = _id_fase(f2) if f2 else origem
            if destino != origem or int(n2) < int(n1):
                refs += [(origem, int(n1)), (destino, int(n2))]
            elif int(n2) - int(n1) >= MAX_FAIXA:
                raise ErroDados(f"Blocked by com faixa maior que {MAX_FAIXA} tickets: {texto[:60]}")
            else:
                refs += [(origem, n) for n in range(int(n1), int(n2) + 1)]
        if len(refs) > MAX_REFS:
            raise ErroDados(f"Blocked by com mais de {MAX_REFS} referências: {texto[:60]}")
    return refs


def ler_tickets(raiz: Path) -> dict[tuple[str, int], dict]:
    base = raiz / ".scratch"
    tickets: dict[tuple[str, int], dict] = {}
    if not base.is_dir():
        return tickets
    for diretorio in sorted(base.glob("f*")):
        if not diretorio.is_dir():
            continue
        mf = _RE_FASE_DIR.match(diretorio.name)
        if not mf:
            # diretório de fase que o script não entende some do painel: recusar, não omitir
            raise ErroDados(f".scratch/{diretorio.name}: nome fora do padrão f<N>-<slug>")
        fase = _id_fase(mf.group(1))
        pasta = diretorio / "issues"
        for arquivo in sorted(pasta.iterdir()) if pasta.is_dir() else []:
            if arquivo.name == ".gitkeep":
                continue
            mt = _RE_TICKET.match(arquivo.name)
            if not mt or arquivo.is_dir() or arquivo.suffix != ".md":
                # ticket que o script não entende some do painel: recusar, não omitir
                raise ErroDados(f"{diretorio.name}/issues/{arquivo.name}: nome fora do padrão M<N>-<slug>.md")
            numero = int(mt.group(1))
            titulo = ""
            status: str | None = None
            bloqueio: str | None = None
            feitos = abertos = 0
            em_bloco = False
            for linha in _ler_do_repositorio(raiz, arquivo).splitlines():
                if linha.lstrip().startswith("```"):
                    em_bloco = not em_bloco
                    continue
                if em_bloco:
                    continue  # exemplo dentro de bloco de código não é campo do ticket
                if not titulo and linha.startswith("#"):
                    titulo = re.sub(r"^#+\s*M\d+:\s*", "", linha).strip()
                    continue
                ms = _RE_STATUS.match(linha)
                if ms:
                    if status is not None:
                        raise ErroDados(f"{arquivo.name}: campo Status repetido")
                    status = _sem_invisiveis(ms.group(1), arquivo.name).strip()
                    continue
                mb = _RE_BLOQUEIO.match(linha)
                if mb:
                    if bloqueio is not None:
                        raise ErroDados(f"{arquivo.name}: campo Blocked by repetido")
                    bloqueio = _sem_invisiveis(mb.group(1), arquivo.name).strip()
                    continue
                mi = _RE_ITEM.match(linha)
                if mi:
                    if mi.group(1) == " ":
                        abertos += 1
                    else:
                        feitos += 1
            titulo = titulo or arquivo.stem
            if len(titulo) > MAX_TITULO_TICKET:
                titulo = titulo[: MAX_TITULO_TICKET - 1] + "…"
            if (fase, numero) in tickets:
                raise ErroDados(f"número de ticket duplicado em {fase}: M{numero}")
            if len(tickets) >= MAX_TICKETS:
                raise ErroDados(f"mais de {MAX_TICKETS} tickets em .scratch")
            refs = bloqueadores(bloqueio or "", fase)
            tickets[(fase, numero)] = {
                "fase": fase,
                "numero": numero,
                "titulo": titulo,
                "status": status or "",
                "sem_status": status is None,
                "sem_bloqueio": bloqueio is None,
                "bloqueadores": refs,
                # campo presente, sem referência e que não é um "nenhum" inofensivo: pode ser
                # uma espera em texto livre, e não dá para saber de quem
                "bloqueio_ilegivel": bloqueio is not None
                and not refs
                and not _RE_NENHUM_SEGURO.fullmatch(bloqueio.strip()),
                "itens_feitos": feitos,
                "itens_abertos": abertos,
                "estado_base": classificar(status or ""),
            }
    return tickets


def aplicar_dependencias(tickets: dict[tuple[str, int], dict]) -> None:
    """Define `estado`, `espera` e `sem_ticket` de cada ticket.

    Bloqueador que não existe como ticket conta como pendente: dado ausente nunca
    vira "pronto".
    """
    for ticket in tickets.values():
        espera = [
            ref
            for ref in ticket["bloqueadores"]
            if ref not in tickets or tickets[ref]["estado_base"] not in ENTREGUES
        ]
        ticket["espera"] = espera
        ticket["sem_ticket"] = [ref for ref in espera if ref not in tickets]
        # só importa onde o ticket ainda pode andar: num ticket já entregue é ruído
        ticket["bloqueio_ilegivel"] = (
            ticket["bloqueio_ilegivel"] and ticket["estado_base"] in PODE_TRAVAR
        )
        if ticket["estado_base"] in PODE_TRAVAR and (espera or ticket["bloqueio_ilegivel"]):
            ticket["estado"] = "travado"
        else:
            ticket["estado"] = ticket["estado_base"]


def resumir_fases(
    declaradas: dict[str, dict[str, str]], tickets: dict[tuple[str, int], dict]
) -> list[dict]:
    nomes = set(declaradas) | {t["fase"] for t in tickets.values()}
    resumo: list[dict] = []
    for fase in sorted(nomes, key=_chave_fase):
        doc = declaradas.get(fase, {})
        todos = sorted(
            (t for t in tickets.values() if t["fase"] == fase), key=lambda t: t["numero"]
        )
        lista = [t for t in todos if t["estado"] != "descartado"]
        contagem = {estado: 0 for estado in ESTADOS}
        for t in lista:
            contagem[t["estado"]] += 1
        entregues = sum(contagem[e] for e in ENTREGUES)
        if not lista:
            calculado = "sem-ticket"
        elif entregues == len(lista):
            calculado = "concluida"
        elif entregues or contagem["andamento"]:
            calculado = "andamento"
        else:
            calculado = "nao-iniciada"
        declarado = doc.get("estado", "")
        resumo.append(
            {
                "fase": fase,
                "bloco": doc.get("bloco", fase),
                "entrega": doc.get("entrega", ""),
                "declarado": declarado,
                "calculado": calculado,
                "diverge": categoria_declarada(declarado) not in (None, calculado),
                "tickets": lista,
                "descartados": [t for t in todos if t["estado"] == "descartado"],
                "contagem": contagem,
                "total": len(lista),
                "entregues": entregues,
            }
        )
    return resumo


# --------------------------------------------------------------- git

def _git(raiz: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", *args],
            cwd=raiz,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def nome_do_projeto(raiz: Path, informado: str | None) -> str:
    """Nome do projeto: `--projeto`; senão o nome do repositório em `origin`; senão o da pasta."""
    candidato = (informado or "").strip()
    if not candidato:
        url = _git(raiz, "remote", "get-url", "origin")
        if url:
            candidato = re.split(r"[/:\\]", url.strip().rstrip("/"))[-1]
            if candidato.endswith(".git"):
                candidato = candidato[:-4]
    if not candidato:
        candidato = raiz.name
    # só caractere imprimível: o nome vem de configuração do git ou do nome da pasta
    imprimivel = "".join(c for c in candidato if c.isprintable())
    return imprimivel[:MAX_NOME_PROJETO].strip()


def estado_repositorio(raiz: Path) -> dict | None:
    ramo = _git(raiz, "rev-parse", "--abbrev-ref", "HEAD")
    if ramo is None:
        return None
    ramo = ramo.replace("`", "")  # o nome entra num trecho em `crase` nos avisos
    atras = adiante = None
    contagem = _git(raiz, "rev-list", "--left-right", "--count", "origin/main...HEAD")
    if contagem:
        partes = contagem.split()
        if len(partes) == 2 and all(p.isdigit() for p in partes):
            atras, adiante = int(partes[0]), int(partes[1])
    alteradas = _git(raiz, "status", "--porcelain")
    return {
        "ramo": ramo,
        "atras": atras,
        "adiante": adiante,
        "alterados": len(alteradas.splitlines()) if alteradas is not None else None,
    }


# ------------------------------------------------------------- avisos

def validar_avisos(dados: object) -> list[dict[str, str]]:
    problemas: list[str] = []
    if not isinstance(dados, list):
        raise ErroDados("avisos: o JSON precisa ser uma lista de objetos")
    if len(dados) > MAX_AVISOS:
        problemas.append(f"avisos: no máximo {MAX_AVISOS}")
    avisos: list[dict[str, str]] = []
    for i, item in enumerate(dados[:MAX_AVISOS], 1):
        if not isinstance(item, dict):
            problemas.append(f"aviso {i}: precisa ser um objeto")
            continue
        extras = sorted(set(item) - {"titulo", "texto"})
        if extras:
            problemas.append(f"aviso {i}: chave desconhecida: {', '.join(extras)}")
        titulo, texto = item.get("titulo"), item.get("texto")
        if not isinstance(titulo, str) or not titulo.strip():
            problemas.append(f"aviso {i}: falta `titulo`")
        elif len(titulo) > MAX_TITULO_AVISO:
            problemas.append(f"aviso {i}: `titulo` passa de {MAX_TITULO_AVISO} caracteres")
        if not isinstance(texto, str) or not texto.strip():
            problemas.append(f"aviso {i}: falta `texto`")
        elif len(texto) > MAX_TEXTO_AVISO:
            problemas.append(f"aviso {i}: `texto` passa de {MAX_TEXTO_AVISO} caracteres")
        if not problemas:
            avisos.append({"titulo": titulo.strip(), "texto": texto.strip()})
    if problemas:
        raise ErroDados("\n".join(problemas))
    return avisos


def _rotulo(ref: tuple[str, int], fase_atual: str | None = None) -> str:
    fase, numero = ref
    return f"M{numero}" if fase == fase_atual else f"{fase}/M{numero}"


def _espera(ticket: dict) -> str:
    itens = [
        _rotulo(r, ticket["fase"]) + (SEM_TICKET if r in ticket["sem_ticket"] else "")
        for r in ticket["espera"]
    ]
    if ticket["bloqueio_ilegivel"]:
        itens.append("bloqueio ilegível")
    return ", ".join(itens)


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def avisos_automaticos(
    fases: list[dict], repositorio: dict | None
) -> list[dict[str, str]]:
    avisos: list[dict[str, str]] = []
    todos = [t for f in fases for t in f["tickets"] + f["descartados"]]

    def _ids(lista: list[dict]) -> str:
        return ", ".join(_rotulo((t["fase"], t["numero"])) for t in lista)

    for f in fases:
        if f["diverge"]:
            avisos.append(
                {
                    "titulo": f"docs/panorama-das-fases.md desatualizado em {f['fase']}",
                    "texto": (
                        f"O documento diz «{f['declarado']}», mas os tickets indicam "
                        f"{ROTULO_FASE[f['calculado']].lower()} "
                        f"({f['entregues']} de {f['total']} entregues)."
                    ),
                }
            )
    esperando = [t for t in todos if t["estado"] in {"needs-info", "humano"}]
    if esperando:
        avisos.append({"titulo": "Tickets aguardando o mantenedor", "texto": _ids(esperando)})
    orfaos = [t for t in todos if t["sem_ticket"]]
    if orfaos:
        avisos.append(
            {
                "titulo": "Bloqueador sem ticket",
                "texto": "; ".join(
                    f"{_rotulo((t['fase'], t['numero']))} espera "
                    + ", ".join(_rotulo(r) for r in t["sem_ticket"])
                    for t in orfaos
                ),
            }
        )
    ilegiveis = [t for t in todos if t["bloqueio_ilegivel"]]
    if ilegiveis:
        avisos.append({"titulo": "Blocked by ilegível", "texto": _ids(ilegiveis)})
    inconsistentes = [
        t
        for t in todos
        if t["espera"] and t["estado_base"] in (ENTREGUES | {"andamento"})
    ]
    if inconsistentes:
        avisos.append(
            {"titulo": "Ticket entregue ou em andamento com bloqueador pendente", "texto": _ids(inconsistentes)}
        )
    com_itens = [t for t in todos if t["estado_base"] in ENTREGUES and t["itens_abertos"]]
    if com_itens:
        avisos.append({"titulo": "Ticket entregue com itens abertos no checklist", "texto": _ids(com_itens)})
    sem_status = [t for t in todos if t["sem_status"]]
    if sem_status:
        avisos.append({"titulo": "Ticket sem campo Status", "texto": _ids(sem_status)})
    fora = [t for t in todos if not t["sem_status"] and t["estado_base"] == "indefinido"]
    if fora:
        avisos.append({"titulo": "Status fora do vocabulário", "texto": _ids(fora)})
    sem_bloqueio = [t for t in todos if t["sem_bloqueio"]]
    if sem_bloqueio:
        avisos.append({"titulo": "Ticket sem campo Blocked by", "texto": _ids(sem_bloqueio)})
    descartados = [t for f in fases for t in f["descartados"]]
    if descartados:
        avisos.append(
            {"titulo": "Tickets descartados, fora da contagem", "texto": _ids(descartados)}
        )
    if repositorio:
        if repositorio["adiante"]:
            n = repositorio["adiante"]
            avisos.append(
                {
                    "titulo": "Commits locais sem push",
                    "texto": f"{_plural(n, 'commit', 'commits')} em `{repositorio['ramo']}` ainda não enviado{'' if n == 1 else 's'} a origin/main.",
                }
            )
        if repositorio["atras"]:
            n = repositorio["atras"]
            avisos.append(
                {
                    "titulo": "Checkout atrás do remoto",
                    "texto": f"{_plural(n, 'commit', 'commits')} de origin/main ainda não trazido{'' if n == 1 else 's'} (conforme o último fetch).",
                }
            )
        if repositorio["alterados"]:
            n = repositorio["alterados"]
            avisos.append(
                {
                    "titulo": "Alterações não commitadas",
                    "texto": f"{_plural(n, 'arquivo', 'arquivos')} com alteração no working tree.",
                }
            )
    return avisos


# ----------------------------------------------------------- totais

def totais(fases: list[dict]) -> dict:
    contagem = {estado: 0 for estado in ESTADOS}
    for f in fases:
        for estado, n in f["contagem"].items():
            contagem[estado] += n
    total = sum(contagem.values())
    entregues = sum(contagem[e] for e in ENTREGUES)
    return {
        "total": total,
        "entregues": entregues,
        "percentual": round(100 * entregues / total) if total else 0,
        "contagem": contagem,
    }


def _faixa(ids: list[str], ordem: list[str]) -> str:
    posicoes = [ordem.index(i) for i in ids]
    if len(posicoes) > 1 and posicoes == list(range(posicoes[0], posicoes[0] + len(posicoes))):
        return f"{ids[0]} a {ids[-1]}"
    return ", ".join(ids)


# --------------------------------------------------------- renderização

def _e(texto: object) -> str:
    return html.escape(str(texto), quote=True)


def _i(texto: object) -> str:
    """Escapa e converte `crase` em <code>; a conversão vem depois do escape."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", _e(texto))


def _md(texto: object) -> str:
    """Escapa markdown em dado de ticket, aviso ou documento; trecho em `crase` fica como está."""
    partes = re.split(r"(`[^`]+`)", " ".join(str(texto).split()))
    return "".join(
        p.replace("|", "\\|") if i % 2 else re.sub(r"([\\*_\[\]()<>!#|~])", r"\\\1", p)
        for i, p in enumerate(partes)
    )


def _cor(papel: str) -> str:
    return {
        "success": "background:var(--bg-success,var(--surface-1));color:var(--text-success,var(--text-primary));",
        "accent": "background:var(--bg-accent,var(--surface-1));color:var(--text-accent,var(--text-primary));",
        "warning": "background:var(--bg-warning,var(--surface-1));color:var(--text-warning,var(--text-primary));",
        "neutro": "background:var(--surface-1);color:var(--text-secondary);",
    }[papel]


def _barra(contagem: dict[str, int], total: int, altura: int = 8) -> str:
    if not total:
        return ""
    entregues = sum(contagem[e] for e in ENTREGUES)
    outros = total - entregues - contagem["andamento"] - contagem["pronto"]
    trechos = (
        (entregues, COR_ENTREGUE),
        (contagem["andamento"], COR_ANDAMENTO),
        (contagem["pronto"], COR_PRONTO),
        (outros, COR_OUTROS),
    )
    pecas = "".join(
        f'<div style="width:{100 * n / total:.2f}%;background:{cor};"></div>'
        for n, cor in trechos
        if n
    )
    return (
        f'<div role="img" aria-label="{entregues} de {total} entregues" '
        f'style="display:flex;height:{altura}px;border-radius:{altura // 2}px;overflow:hidden;'
        f'background:var(--surface-1);border:0.5px solid var(--border);">{pecas}</div>'
    )


def _selo_estado(estado: str) -> str:
    rotulo, icone, papel = ESTADOS[estado]
    return (
        f'<span style="{_cor(papel)}font-size:12px;padding:2px 8px;border-radius:var(--radius);'
        f'white-space:nowrap;"><i class="ti {icone}" aria-hidden="true"></i> {rotulo}</span>'
    )


def _linha_ticket(t: dict) -> str:
    extra = ""
    if t["estado"] == "andamento" and (t["itens_feitos"] or t["itens_abertos"]):
        total = t["itens_feitos"] + t["itens_abertos"]
        extra = (
            f'<div style="font-size:12px;color:var(--text-secondary);margin-top:2px;">'
            f'{t["itens_feitos"]} de {total} itens</div>'
        )
    espera = _e(_espera(t)) if t["estado"] == "travado" else "—"
    return (
        '<tr style="border-top:0.5px solid var(--border);">'
        f'<td style="padding:6px 8px 6px 0;font-family:var(--font-mono);font-size:13px;">M{t["numero"]}</td>'
        f'<td style="padding:6px 8px;font-size:14px;">{_i(t["titulo"])}{extra}</td>'
        f'<td style="padding:6px 8px;">{_selo_estado(t["estado"])}</td>'
        f'<td style="padding:6px 0 6px 8px;font-size:13px;color:var(--text-secondary);">{espera}</td>'
        "</tr>"
    )


def _bloco_fase(f: dict) -> str:
    cabeca = (
        '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
        f'<span style="font-family:var(--font-mono);font-size:13px;font-weight:500;'
        f'background:var(--surface-1);border:0.5px solid var(--border-strong);padding:1px 8px;'
        f'border-radius:var(--radius);">{_e(f["fase"])}</span>'
        f'<span style="font-size:15px;font-weight:500;">{_e(f["bloco"])}</span>'
        f'<span style="{_cor(PAPEL_FASE[f["calculado"]])}font-size:12px;padding:2px 8px;'
        f'border-radius:var(--radius);margin-left:auto;">{ROTULO_FASE[f["calculado"]]}</span>'
        "</div>"
    )
    if not f["total"]:
        resumo = _e(f["entrega"][:160] + ("…" if len(f["entrega"]) > 160 else ""))
        return (
            '<div style="border:0.5px solid var(--border);border-radius:var(--radius);'
            f'padding:10px 12px;margin-bottom:8px;">{cabeca}'
            f'<p style="font-size:13px;color:var(--text-secondary);margin:6px 0 0;">{resumo}</p></div>'
        )
    abertos = [t for t in f["tickets"] if t["estado"] not in ENTREGUES]
    entregues = [t for t in f["tickets"] if t["estado"] in ENTREGUES]
    tabela = ""
    if abertos:
        linhas = "".join(_linha_ticket(t) for t in abertos)
        tabela = (
            '<table style="width:100%;border-collapse:collapse;table-layout:fixed;margin-top:10px;">'
            '<colgroup><col style="width:48px"><col><col style="width:170px"><col style="width:120px"></colgroup>'
            '<thead><tr style="font-size:12px;color:var(--text-secondary);text-align:left;">'
            '<th style="padding:0 8px 4px 0;font-weight:400;">Ticket</th>'
            '<th style="padding:0 8px 4px;font-weight:400;">O que entrega</th>'
            '<th style="padding:0 8px 4px;font-weight:400;">Estado</th>'
            '<th style="padding:0 0 4px 8px;font-weight:400;">Espera</th></tr></thead>'
            f"<tbody>{linhas}</tbody></table>"
        )
    chips = ""
    if entregues:
        itens = "".join(
            '<span class="pf-chip" title="{}">M{}</span>'.format(
                _e(f"M{t['numero']} — {t['titulo']}"), t["numero"]
            )
            for t in entregues
        )
        chips = (
            '<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:10px;">'
            '<span style="font-size:12px;color:var(--text-secondary);">Entregues</span>'
            f"{itens}</div>"
        )
    return (
        '<div style="border:0.5px solid var(--border);border-radius:var(--radius);'
        f'padding:12px 14px;margin-bottom:10px;background:var(--surface-2);">{cabeca}'
        '<div style="display:flex;align-items:center;gap:10px;margin-top:8px;">'
        f'<div style="flex:1;">{_barra(f["contagem"], f["total"])}</div>'
        f'<span style="font-size:13px;color:var(--text-secondary);white-space:nowrap;">'
        f'{f["entregues"]} de {f["total"]}</span></div>{tabela}{chips}</div>'
    )


def renderizar_html(
    fases: list[dict],
    repositorio: dict | None,
    avisos: list[dict[str, str]],
    data: str,
    projeto: str = "",
) -> str:
    t = totais(fases)
    c = t["contagem"]
    resumo_sr = (
        f"{CABECALHO}: {t['entregues']} de {t['total']} tickets entregues ({t['percentual']}%), "
        f"{c['andamento']} em andamento, {c['pronto']} prontos, {c['travado']} travados."
    )
    chips = [
        f'<span style="font-size:13px;font-weight:500;padding:3px 12px;border-radius:var(--radius);'
        f'{_cor("success")}">{t["entregues"]} de {t["total"]} tickets · {t["percentual"]}%</span>'
    ]
    for chave, rotulo, papel in (
        ("andamento", "em andamento", "accent"),
        ("pronto", "prontos", "neutro"),
        ("travado", "travados", "warning"),
        ("indefinido", "sem estado", "warning"),
    ):
        if c[chave]:
            chips.append(
                f'<span style="{_cor(papel)}font-size:12px;padding:3px 10px;'
                f'border-radius:var(--radius);">{c[chave]} {rotulo}</span>'
            )
    if repositorio:
        if repositorio["adiante"]:
            chips.append(
                f'<span class="pf-chip"><i class="ti ti-git-commit" aria-hidden="true"></i> '
                f'{repositorio["adiante"]} sem push</span>'
            )
        if repositorio["alterados"]:
            chips.append(
                f'<span class="pf-chip"><i class="ti ti-file-diff" aria-hidden="true"></i> '
                f'{repositorio["alterados"]} alterados</span>'
            )
    legenda = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:4px;font-size:12px;'
        f'color:var(--text-secondary);"><span style="width:8px;height:8px;border-radius:50%;'
        f'background:{cor};display:inline-block;"></span>{rotulo}</span>'
        for rotulo, cor in (
            ("Entregue", COR_ENTREGUE),
            ("Em andamento", COR_ANDAMENTO),
            ("Pronto", COR_PRONTO),
            ("Travado ou aguardando", COR_OUTROS),
        )
    )
    corpo = "".join(_bloco_fase(f) for f in fases)
    bloco_avisos = ""
    todos = avisos_automaticos(fases, repositorio) + avisos
    if todos:
        itens = "".join(
            '<div style="display:flex;gap:8px;padding:6px 0;border-top:0.5px solid var(--border);">'
            '<i class="ti ti-alert-triangle" style="font-size:16px;color:var(--text-warning,var(--text-primary));margin-top:2px;" aria-hidden="true"></i>'
            f'<div><div style="font-size:14px;font-weight:500;">{_i(a["titulo"])}</div>'
            f'<div style="font-size:13px;color:var(--text-secondary);">{_i(a["texto"])}</div></div></div>'
            for a in todos
        )
        bloco_avisos = (
            '<p class="pf-lbl"><i class="ti ti-alert-triangle" style="font-size:16px;" aria-hidden="true"></i>'
            f"Pontos de atenção · {len(todos)}</p>"
            '<div style="margin-bottom:14px;border:0.5px solid var(--border-warning,var(--border-strong));'
            f'border-radius:var(--radius);padding:4px 12px;">{itens}</div>'
        )
    primeira, ultima = fases[0]["fase"], fases[-1]["fase"]
    titulo = f"{projeto} · {primeira} a {ultima}" if projeto else f"Fases {primeira} a {ultima}"
    return (
        f'<h2 class="sr-only">{_e(resumo_sr)}</h2>\n'
        "<style>\n"
        ".pf-chip{font-size:12px;padding:3px 10px;border-radius:var(--radius);border:0.5px solid var(--border);background:var(--surface-1);color:var(--text-secondary)}\n"
        ".pf-lbl{font-size:13px;color:var(--text-secondary);margin:0 0 8px;display:flex;align-items:center;gap:6px}\n"
        "</style>\n"
        '<div style="background:var(--surface-2);border:0.5px solid var(--border-strong);border-radius:12px;padding:1.25rem 1.5rem;margin:0.5rem 0;">\n'
        '<div style="display:flex;align-items:center;gap:8px;"><i class="ti ti-timeline" style="font-size:22px;color:var(--text-accent);" aria-hidden="true"></i>'
        f'<span style="font-size:13px;color:var(--text-secondary);">{CABECALHO}</span></div>\n'
        f'<p style="font-size:20px;font-weight:500;margin:8px 0 10px;">{_e(titulo)}</p>\n'
        '<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">' + "".join(chips) + "</div>\n"
        f'<div style="margin:12px 0 4px;">{_barra(c, t["total"], 10)}</div>\n'
        f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;">{legenda}</div>\n'
        + corpo
        + bloco_avisos
        + f'<p style="font-size:12px;color:var(--text-secondary);margin:6px 0 0;">Fonte: tickets em <code>.scratch/</code> e <code>docs/panorama-das-fases.md</code>, lidos em {_e(data)}</p>\n'
        "</div>"
    )


def renderizar_marca(fases: list[dict]) -> str:
    t = totais(fases)
    partes = [
        f"**{CABECALHO}** · {t['entregues']} de {t['total']} tickets entregues ({t['percentual']}%)"
    ]
    ordem = [f["fase"] for f in fases]
    sem_ticket: list[str] = []
    for f in fases:
        if f["calculado"] == "sem-ticket":
            sem_ticket.append(f["fase"])
        elif f["calculado"] == "concluida":
            partes.append(f"{f['fase']} concluída")
        else:
            partes.append(
                f"{f['fase']} {ROTULO_FASE[f['calculado']].lower()} ({f['entregues']}/{f['total']})"
            )
    if sem_ticket:
        partes.append(f"{_faixa(sem_ticket, ordem)} sem ticket")
    return " · ".join(partes) + " — detalhes no painel acima"


def renderizar_markdown(
    fases: list[dict],
    repositorio: dict | None,
    avisos: list[dict[str, str]],
    data: str,
    projeto: str = "",
) -> str:
    t = totais(fases)
    linhas = [
        f"## {CABECALHO} · {_md(projeto)}" if projeto else f"## {CABECALHO}",
        "",
        f"**{t['entregues']} de {t['total']} tickets entregues ({t['percentual']}%)**, lidos em {data}.",
        "",
        "| Fase | Bloco | Estado | Progresso |",
        "|---|---|---|---|",
    ]
    for f in fases:
        progresso = f"{f['entregues']} de {f['total']}" if f["total"] else "—"
        linhas.append(
            f"| {f['fase']} | {_md(f['bloco'])} | {ROTULO_FASE[f['calculado']]} | {progresso} |"
        )
    for f in fases:
        abertos = [t_ for t_ in f["tickets"] if t_["estado"] not in ENTREGUES]
        if not abertos:
            continue
        linhas += ["", f"### {f['fase']} — o que falta", "", "| Ticket | O que entrega | Estado | Espera |", "|---|---|---|---|"]
        for tk in abertos:
            espera = _md(_espera(tk)) if tk["estado"] == "travado" else "—"
            linhas.append(
                f"| M{tk['numero']} | {_md(tk['titulo'])} | {ESTADOS[tk['estado']][0]} | {espera} |"
            )
    todos = avisos_automaticos(fases, repositorio) + avisos
    if todos:
        linhas += ["", "### Pontos de atenção", ""]
        linhas += [f"- **{_md(a['titulo'])}** — {_md(a['texto'])}" for a in todos]
    return "\n".join(linhas)


# ----------------------------------------------------------------- CLI

def montar(raiz: Path) -> tuple[list[dict], dict | None]:
    declaradas = ler_fases(raiz)
    tickets = ler_tickets(raiz)
    aplicar_dependencias(tickets)
    return resumir_fases(declaradas, tickets), estado_repositorio(raiz)


def main(argv: list[str] | None = None) -> int:
    padrao = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raiz", type=Path, default=padrao, help="raiz do repositório (só um repositório confiável)"
    )
    parser.add_argument("--avisos", type=Path, help="JSON com avisos extras (lista de {titulo, texto})")
    parser.add_argument("--data", help="data de leitura AAAA-MM-DD (padrão: hoje)")
    parser.add_argument(
        "--projeto",
        help="nome do projeto no título (padrão: nome do repositório em origin, ou o da pasta)",
    )
    parser.add_argument("--formato", choices=("html", "marca", "markdown"), required=True)
    args = parser.parse_args(argv)
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    try:
        data = args.data or datetime.date.today().isoformat()
        datetime.date.fromisoformat(data)
        fases, repositorio = montar(args.raiz.resolve())
        extras: list[dict[str, str]] = []
        if args.avisos:
            try:
                extras = validar_avisos(json.loads(_ler_arquivo(args.avisos)))
            except json.JSONDecodeError as exc:
                raise ErroDados(f"avisos: o JSON não é válido ({exc.msg})") from exc
    except (ErroDados, ValueError) as exc:
        print(f"Dados do panorama inválidos — corrija e rode de novo:\n{exc}", file=sys.stderr)
        return 1
    projeto = nome_do_projeto(args.raiz.resolve(), args.projeto)
    if args.formato == "html":
        print(renderizar_html(fases, repositorio, extras, data, projeto))
    elif args.formato == "marca":
        print(renderizar_marca(fases))
    else:
        print(renderizar_markdown(fases, repositorio, extras, data, projeto))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
