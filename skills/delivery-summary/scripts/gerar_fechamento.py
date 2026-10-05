#!/usr/bin/env python3
"""Valida os dados da entrega e gera HTML, Markdown ou resumo em texto."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys

RESULTADOS = {
    "concluido": "Concluído",
    "parcial": "Parcial",
    "bloqueado": "Bloqueado",
    "falhou": "Falhou",
}
TIPOS = {
    "blocked": "Bloqueio",
    "decisao": "Decisão",
    "aceite-de-risco": "Aceite de risco",
    "aprovacao": "Aprovação",
    "informacao": "Informação",
}
URGENCIAS = {
    "agora": "Bloqueia agora",
    "proximo": "Bloqueia o próximo passo",
    "pode-esperar": "Pode esperar",
}
TRABALHO = {"local": "Sem commit", "commitado": "Commitado", "enviado": "Enviado"}
CHAVES = {
    "titulo", "resultado", "motivo", "trabalho", "commit", "pendencias",
    "comportamentos", "arquivos", "verificacoes", "riscos", "proximo_passo",
}
CHAVES_PENDENCIA = {
    "id", "tipo", "urgencia", "pergunta", "contexto", "enquanto", "premissa",
    "recomendacao", "alternativas", "livre",
}
HASH = re.compile(r"^[0-9a-f]{7,40}$")
IDENTIFICADOR = re.compile(r"^[a-z][a-z0-9-]{1,19}$")
CABECALHO = "Fechamento da entrega"


class DadosInvalidos(Exception):
    def __init__(self, problemas: list[str]) -> None:
        super().__init__("\n".join(problemas))
        self.problemas = problemas


def _texto(valor: object) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def _lista_de_textos(dados: dict, chave: str, problemas: list[str]) -> list[str]:
    valor = dados.get(chave, [])
    if not isinstance(valor, list) or not all(_texto(item) for item in valor):
        problemas.append(f"{chave} deve ser uma lista de textos não vazios")
        return []
    return valor


def validar(dados: object) -> dict:
    """Confere os dados e devolve o fechamento pronto para renderizar."""
    if not isinstance(dados, dict):
        raise DadosInvalidos(["os dados devem ser um objeto JSON"])
    problemas: list[str] = []
    for chave in sorted(set(dados) - CHAVES):
        problemas.append(f"chave desconhecida: {chave}")

    resultado = dados.get("resultado")
    if resultado not in RESULTADOS:
        problemas.append(f"resultado deve ser um de {', '.join(RESULTADOS)}")
    motivo = dados.get("motivo", "")
    if not isinstance(motivo, str):
        problemas.append("motivo deve ser um texto")
    elif resultado in RESULTADOS and resultado != "concluido" and not _texto(motivo):
        problemas.append("motivo é obrigatório quando o resultado não for concluido")
    if not _texto(dados.get("titulo")):
        problemas.append("titulo é obrigatório")
    trabalho = dados.get("trabalho")
    commit = dados.get("commit")
    if trabalho not in TRABALHO:
        problemas.append(f"trabalho deve ser um de {', '.join(TRABALHO)} (estado do commit)")
    elif trabalho == "local" and commit is not None:
        problemas.append("trabalho local não tem commit")
    elif trabalho != "local" and not (isinstance(commit, str) and HASH.match(commit)):
        problemas.append("commit precisa do hash (7 a 40 caracteres hexadecimais) quando o trabalho foi commitado")

    pendencias = dados.get("pendencias", [])
    if not isinstance(pendencias, list):
        problemas.append("pendencias deve ser uma lista")
        pendencias = []
    vistos: set[str] = set()
    for indice, pendencia in enumerate(pendencias, start=1):
        rotulo = f"pendência {indice}"
        if not isinstance(pendencia, dict):
            problemas.append(f"{rotulo} deve ser um objeto")
            continue
        identificador = pendencia.get("id")
        if isinstance(identificador, str) and IDENTIFICADOR.match(identificador):
            rotulo = f"pendência {identificador}"
            if identificador in vistos:
                problemas.append(f"identificador repetido: {identificador}")
            vistos.add(identificador)
        else:
            problemas.append(f"{rotulo}: id deve ser uma palavra minúscula de 2 a 20 caracteres (ex.: adr18)")
        for chave in sorted(set(pendencia) - CHAVES_PENDENCIA):
            problemas.append(f"{rotulo}: chave desconhecida: {chave}")
        tipo = pendencia.get("tipo")
        if tipo not in TIPOS:
            problemas.append(f"{rotulo}: tipo deve ser um de {', '.join(TIPOS)}")
        if not _texto(pendencia.get("pergunta")):
            problemas.append(f"{rotulo}: pergunta é obrigatória")
        if not _texto(pendencia.get("contexto")):
            problemas.append(f"{rotulo}: contexto é obrigatório — explique a situação em linguagem simples")
        if not _texto(pendencia.get("enquanto")):
            problemas.append(f"{rotulo}: enquanto é obrigatório — o que segue ou fica travado até a resposta")
        urgencia = pendencia.get("urgencia")
        if urgencia not in URGENCIAS:
            problemas.append(f"{rotulo}: urgencia deve ser uma de {', '.join(URGENCIAS)}")
        if tipo == "blocked" and urgencia != "agora":
            problemas.append(f"{rotulo}: bloqueio tem urgência agora")
        recomendacao = pendencia.get("recomendacao")
        if not isinstance(recomendacao, dict) or not all(
            _texto(recomendacao.get(campo)) for campo in ("opcao", "base", "custo")
        ):
            problemas.append(f"{rotulo}: recomendacao precisa de opcao, base e custo")
        alternativas = pendencia.get("alternativas", [])
        if not isinstance(alternativas, list) or not all(_texto(item) for item in alternativas):
            problemas.append(f"{rotulo}: alternativas deve ser uma lista de textos")
            alternativas = []
        opcoes = [recomendacao.get("opcao")] if isinstance(recomendacao, dict) else []
        if any(isinstance(o, str) and "`" in o for o in opcoes + alternativas + [pendencia.get("livre")]):
            problemas.append(f"{rotulo}: opção de resposta sem crase — ela já vai dentro de um trecho de código")
        if "livre" in pendencia and not _texto(pendencia.get("livre")):
            problemas.append(f"{rotulo}: livre, quando presente, descreve o que digitar (ex.: alteração)")
        if tipo == "decisao" and not _texto(pendencia.get("premissa")):
            problemas.append(f"{rotulo}: decisão precisa da premissa adotada")
        if tipo in ("decisao", "aceite-de-risco") and not alternativas and not _texto(pendencia.get("livre")):
            problemas.append(f"{rotulo}: {TIPOS[tipo].lower()} precisa de alternativa ou de resposta livre")
        if tipo == "blocked" and resultado != "bloqueado":
            problemas.append(f"{rotulo}: bloqueio exige resultado bloqueado")

    comportamentos = _lista_de_textos(dados, "comportamentos", problemas)
    if not comportamentos:
        problemas.append("comportamentos precisa de ao menos uma linha: o que passou a funcionar ou mudou")
    arquivos = _lista_de_textos(dados, "arquivos", problemas)
    verificacoes = _lista_de_textos(dados, "verificacoes", problemas)
    riscos = _lista_de_textos(dados, "riscos", problemas)
    proximo = dados.get("proximo_passo")
    if proximo is not None and not isinstance(proximo, str):
        problemas.append("proximo_passo deve ser um texto")
    if resultado in RESULTADOS and resultado != "concluido" and not _texto(proximo):
        problemas.append("proximo_passo é obrigatório quando o resultado não for concluido")

    if problemas:
        raise DadosInvalidos(problemas)

    ordem = list(URGENCIAS)
    return {
        "titulo": dados["titulo"].strip(),
        "trabalho": TRABALHO[trabalho] + (f" em `{commit}`" if trabalho != "local" else ""),
        "estado": RESULTADOS[resultado],
        "motivo": motivo.strip(),
        # o que bloqueia agora vem primeiro; empate mantém a ordem dos dados
        "pendencias": sorted(pendencias, key=lambda p: ordem.index(p["urgencia"])),
        "comportamentos": comportamentos,
        "arquivos": arquivos,
        "verificacoes": verificacoes,
        "riscos": riscos,
        "proximo_passo": proximo.strip() if _texto(proximo) else "",
    }


def _resposta(pendencia: dict, opcao: str) -> str:
    return f"{pendencia['id']} {opcao.strip()}"


def _linha_resultado(f: dict) -> str:
    return f"`{f['estado']}` · {f['titulo']}"


def _urgencia(p: dict) -> str:
    return URGENCIAS[p["urgencia"]]


def _contagem_pendencias(n: int) -> str:
    return "Nenhuma decisão pendente" if n == 0 else "1 decisão espera você" if n == 1 else f"{n} decisões esperam você"


def _mostra_verificacoes_e_riscos(f: dict) -> tuple[bool, bool]:
    return bool(f["verificacoes"]), bool(f["riscos"])


# ---------------------------------------------------------------- texto

def renderizar_texto(f: dict) -> str:
    """Bloco curto da resposta: tudo que pede atenção, também quando o painel não renderiza."""
    linhas = [f"**{CABECALHO}**", "", f"**Resultado:** {_linha_resultado(f)}", f"**Trabalho:** {f['trabalho']}", ""]
    if f["motivo"]:
        linhas += [f"**Motivo:** {f['motivo']}", ""]
    pendencias = f["pendencias"]
    if not pendencias:
        linhas.append("**Decisões humanas pendentes:** Nenhuma.")
    else:
        dica = " ou `ok todas`" if len(pendencias) > 1 else ""
        linhas.append(f"**Decisões humanas pendentes** · {len(pendencias)} — responda pelo identificador{dica}")
        for p in pendencias:
            opcao = p["recomendacao"]["opcao"]
            linhas.append(
                f"- `{p['id']}` · {TIPOS[p['tipo']]} · {_urgencia(p).lower()}: {p['pergunta']}"
                f" → recomendo {opcao} (`{_resposta(p, opcao)}`)"
            )
    if f["riscos"]:
        linhas += ["", f"**Riscos e limitações** · {len(f['riscos'])}"]
        linhas += [f"- {risco}" for risco in f["riscos"]]
    return "\n".join(linhas) + "\n"


def renderizar_marca(f: dict) -> str:
    """Linha única que acompanha o painel: o que o hook confere, sem repetir o painel."""
    ids = [p["id"] for p in f["pendencias"]]
    pendencias = f"{len(ids)} ({', '.join(f'`{i}`' for i in ids)})" if ids else "nenhuma"
    return (f"**{CABECALHO}** · resultado `{f['estado']}` · Decisões humanas pendentes: "
            f"{pendencias} — detalhes no painel acima\n")


# ---------------------------------------------------------------- markdown

def _celula(texto: str) -> str:
    return " ".join(texto.split()).replace("|", "\\|")


def renderizar_markdown(f: dict) -> str:
    """Fechamento completo para quando o painel HTML não está disponível."""
    m = ["---", "", f"## {CABECALHO}", "",
         "| Resultado | Trabalho | Entrega |", "|:---:|:---:|---|",
         f"| `{f['estado']}` | {_celula(f['trabalho'])} | {_celula(f['titulo'])} |", ""]
    if f["motivo"]:
        m += [f"**Motivo:** {f['motivo']}", ""]

    pendencias = f["pendencias"]
    if not pendencias:
        m += ["### Decisões humanas pendentes", "", "Nenhuma.", ""]
    else:
        dica = " ou `ok todas` para aceitar todas as recomendações" if len(pendencias) > 1 else ""
        m += [f"### Decisões humanas pendentes · {len(pendencias)}", "",
              f"Responda pelo identificador{dica}.", ""]
        for p in pendencias:
            rec = p["recomendacao"]
            bloco = [f"> **`{p['id']}` · {TIPOS[p['tipo']]}:** {p['pergunta']}",
                     f"> {p['contexto']}",
                     f"> *{_urgencia(p)}.* Enquanto isso: {p['enquanto']}"]
            if _texto(p.get("premissa")):
                bloco.append(f"> Premissa adotada: {p['premissa']}")
            bloco.append(f"> **Recomendo {rec['opcao']}.** Base: {rec['base']} Custo da alternativa: {rec['custo']}")
            respostas = [f"`{_resposta(p, rec['opcao'])}`"] + [f"`{_resposta(p, a)}`" for a in p.get("alternativas", [])]
            if _texto(p.get("livre")):
                respostas.append(f"`{p['id']} <{p['livre'].strip()}>`")
            bloco.append(f"> Responda {' · '.join(respostas)}")
            m += ["  \n".join(bloco), ""]

    m += ["### Arquivos e comportamentos", ""]
    m += [f"- {c}" for c in f["comportamentos"]]
    m += [f"- `{a}`" for a in f["arquivos"]]
    m.append("")

    mostra_verificacoes, mostra_riscos = _mostra_verificacoes_e_riscos(f)
    if mostra_verificacoes:
        m += ["### Verificações e revisões", ""]
        m += [f"- {v}" for v in f["verificacoes"]] + [""]
    if mostra_riscos:
        m += ["### Riscos e limitações", ""] + [f"- {r}" for r in f["riscos"]] + [""]
    if f["proximo_passo"]:
        m += ["### Próximo passo", "", f["proximo_passo"], ""]
    m.append("---")
    return "\n".join(m) + "\n"


# ---------------------------------------------------------------- html

ESTILO = """<style>
.fx-chip{font-size:12px;padding:3px 10px;border-radius:var(--radius);border:0.5px solid var(--border);background:var(--surface-1);color:var(--text-secondary)}
.fx-lbl{font-size:13px;color:var(--text-secondary);margin:0 0 8px;display:flex;align-items:center;gap:6px}
.fx-card{border:0.5px solid var(--border);border-left:3px solid var(--border-accent);border-radius:0;padding:12px 14px;margin-bottom:10px;background:var(--surface-2)}
.fx-rec{font-size:13px;color:var(--text-secondary);margin:0 0 10px;background:var(--surface-1);border-radius:var(--radius);padding:8px 10px}
.fx-id{font-family:var(--font-mono);font-size:13px;font-weight:500;background:var(--surface-1);border:0.5px solid var(--border-strong);padding:1px 8px;border-radius:var(--radius)}
.fx-rec-btn{border-color:var(--border-accent);color:var(--text-accent)}
.fx-sel{background:var(--bg-accent);color:var(--text-accent);border-color:var(--border-accent)}
</style>"""

URGENCIA_COR = {
    "agora": ("var(--bg-danger)", "var(--text-danger)"),
    "proximo": ("var(--bg-accent)", "var(--text-accent)"),
    "pode-esperar": ("var(--surface-1)", "var(--text-secondary)"),
}

# Clicar numa opção só a seleciona (pode trocar e clicar de novo); um único envio
# manda todas as escolhidas, uma por linha, precedidas de quebra de linha para não
# grudar no que já está na caixa de mensagem. Nenhum texto dos dados entra no código.
SCRIPT_RESPOSTAS = """<script>(function(){
var sel={},ordem=[],texto=document.getElementById('fx-texto'),erro=document.getElementById('fx-erro');
document.querySelectorAll('.fx-card[data-id]').forEach(function(c){ordem.push(c.getAttribute('data-id'));});
function montar(){return ordem.filter(function(i){return sel[i];}).map(function(i){return sel[i];}).join('\\n');}
function atualizar(){document.querySelectorAll('button.fx-op').forEach(function(b){var on=sel[b.getAttribute('data-id')]===b.getAttribute('data-resposta');b.classList.toggle('fx-sel',on);b.setAttribute('aria-pressed',on?'true':'false');});var t=montar();texto.textContent=t||'nenhuma resposta escolhida ainda';if(t){erro.textContent='';}}
function enviar(){var t=montar();if(!t){erro.textContent='Escolha ao menos uma resposta';return;}sendPrompt('\\n'+t);}
document.querySelectorAll('button.fx-op').forEach(function(b){b.addEventListener('click',function(){sel[b.getAttribute('data-id')]=b.getAttribute('data-resposta');atualizar();});});
var todas=document.getElementById('fx-todas');if(todas){todas.addEventListener('click',function(){document.querySelectorAll('button.fx-op[data-recomendada]').forEach(function(b){sel[b.getAttribute('data-id')]=b.getAttribute('data-resposta');});atualizar();enviar();});}
document.getElementById('fx-enviar').addEventListener('click',enviar);
atualizar();})();</script>"""

COR_TIPO = {
    "blocked": ("var(--bg-danger)", "var(--text-danger)", "var(--border-danger)"),
    "decisao": ("var(--bg-accent)", "var(--text-accent)", "var(--border-accent)"),
    "aceite-de-risco": ("var(--bg-danger)", "var(--text-danger)", "var(--border-danger)"),
    "aprovacao": ("var(--surface-1)", "var(--text-primary)", "var(--border-strong)"),
    "informacao": ("var(--surface-1)", "var(--text-secondary)", "var(--border-strong)"),
}


def _e(texto: str) -> str:
    return html.escape(texto, quote=True)


def _i(texto: str) -> str:
    """Escapa e só então converte `trechos` em <code>: nada dos dados vira marcação crua."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", _e(texto))


def _rotulo(texto: str) -> str:
    texto = texto.strip()
    return texto[:1].upper() + texto[1:]


def _botao(pendencia: dict, rotulo: str, resposta: str, recomendado: bool = False) -> str:
    extra = ' fx-rec-btn" data-recomendada="1' if recomendado else ""
    return (f'<button class="fx-op{extra}" aria-pressed="false" data-id="{_e(pendencia["id"])}" '
            f'data-resposta="{_e(resposta)}">{_e(rotulo)}</button>')


def _cor_estado(estado: str) -> tuple[str, str]:
    if estado == "Concluído":
        return "var(--bg-success)", "var(--text-success)"
    if estado == "Parcial":
        return "var(--bg-accent)", "var(--text-accent)"
    return "var(--bg-danger)", "var(--text-danger)"


def _pendencia_html(p: dict) -> str:
    fundo, texto, borda = COR_TIPO[p["tipo"]]
    rec = p["recomendacao"]
    fundo_urg, texto_urg = URGENCIA_COR[p["urgencia"]]
    partes = [
        f'<div class="fx-card" data-id="{_e(p["id"])}" style="border-left-color:{borda};">',
        f'<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px;"><span class="fx-id">{_e(p["id"])}</span>'
        f'<span style="background:{fundo};color:{texto};font-size:12px;padding:2px 8px;border-radius:var(--radius);">{_e(TIPOS[p["tipo"]])}</span>'
        f'<span style="background:{fundo_urg};color:{texto_urg};font-size:12px;padding:2px 8px;border-radius:var(--radius);">{_e(_urgencia(p))}</span></div>',
        f'<p style="font-size:15px;font-weight:500;margin:0 0 6px;">{_i(p["pergunta"])}</p>',
        f'<p style="font-size:14px;margin:0 0 8px;">{_i(p["contexto"])}</p>',
        f'<p style="font-size:13px;color:var(--text-secondary);margin:0 0 8px;">Enquanto isso: {_i(p["enquanto"])}</p>',
    ]
    if _texto(p.get("premissa")):
        partes.append(f'<p style="font-size:13px;color:var(--text-secondary);margin:0 0 8px;">Premissa adotada: {_i(p["premissa"])}</p>')
    partes.append(
        f'<p class="fx-rec"><span style="color:var(--text-primary);font-weight:500;">Recomendo {_e(rec["opcao"])}.</span> '
        f'Base: {_i(rec["base"])} Custo da alternativa: {_i(rec["custo"])}</p>'
    )
    botoes = [_botao(p, f"{_rotulo(rec['opcao'])} · recomendado", _resposta(p, rec["opcao"]), True)]
    botoes += [_botao(p, _rotulo(a), _resposta(p, a)) for a in p.get("alternativas", [])]
    livre = ""
    if _texto(p.get("livre")):
        livre = f'<span style="font-size:13px;color:var(--text-secondary);">ou digite <code>{_e(p["id"])} &lt;{_e(p["livre"].strip())}&gt;</code></span>'
    partes.append(f'<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">{"".join(botoes)}{livre}</div></div>')
    return "".join(partes)


def renderizar_html(f: dict) -> str:
    """Painel para a ferramenta de widget visual do app; usa as variáveis de tema dela."""
    pendencias = f["pendencias"]
    fundo_estado, texto_estado = _cor_estado(f["estado"])
    resumo = (f"Fechamento da entrega: resultado {f['estado']}, "
              f"{len(pendencias)} decisões pendentes, {len(f['riscos'])} riscos.")
    h = [f'<h2 class="sr-only">{_e(resumo)}</h2>', ESTILO,
         '<div style="background:var(--surface-2);border:0.5px solid var(--border-strong);border-radius:12px;padding:1.25rem 1.5rem;margin:0.5rem 0;">',
         '<div style="display:flex;align-items:center;gap:8px;"><i class="ti ti-clipboard-check" style="font-size:22px;color:var(--text-accent);" aria-hidden="true"></i>'
         f'<span style="font-size:13px;color:var(--text-secondary);">{CABECALHO}</span></div>',
         f'<p style="font-size:20px;font-weight:500;margin:8px 0 10px;">{_i(f["titulo"])}</p>',
         '<div style="display:flex;gap:6px;flex-wrap:wrap;padding-bottom:14px;border-bottom:0.5px solid var(--border);">',
         f'<span style="font-size:13px;font-weight:500;padding:3px 12px;border-radius:var(--radius);background:{fundo_estado};color:{texto_estado};">Resultado {_e(f["estado"])}</span>',
         f'<span class="fx-chip"><i class="ti ti-git-commit" aria-hidden="true"></i> {_i(f["trabalho"])}</span>']
    cor_pend = ("var(--bg-accent)", "var(--text-accent)") if pendencias else ("var(--bg-success)", "var(--text-success)")
    h.append(f'<span style="font-size:13px;font-weight:500;padding:3px 12px;border-radius:var(--radius);background:{cor_pend[0]};color:{cor_pend[1]};">'
             f'<i class="ti ti-user-question" aria-hidden="true"></i> {_e(_contagem_pendencias(len(pendencias)))}</span>')
    if f["riscos"]:
        h.append(f'<span class="fx-chip" style="border-color:var(--border-danger);color:var(--text-danger);"><i class="ti ti-alert-triangle" aria-hidden="true"></i> {len(f["riscos"])} risco{"s" if len(f["riscos"]) > 1 else ""}</span>')
    h.append('</div>')
    if f["motivo"]:
        h.append(f'<p style="font-size:14px;margin:12px 0;">Motivo: {_i(f["motivo"])}</p>')

    if pendencias:
        h.append('<div style="border:2px solid var(--border-accent);border-radius:12px;padding:14px 16px;margin:16px 0 18px;">'
                 '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px;">'
                 '<span style="font-size:16px;font-weight:500;color:var(--text-accent);">Decisões humanas pendentes</span>')
        if len(pendencias) > 1:
            h.append(f'<button id="fx-todas" style="margin-left:auto;">Aceitar as {len(pendencias)} recomendações e enviar ↗</button>')
        h.append('</div>' + "".join(_pendencia_html(p) for p in pendencias))
        h.append('<div style="border-top:0.5px solid var(--border);padding-top:12px;margin-top:4px;">'
                 '<p style="font-size:13px;color:var(--text-secondary);margin:0 0 6px;">Suas respostas — clique nas opções acima; dá para trocar antes de enviar</p>'
                 '<pre id="fx-texto" style="font-family:var(--font-mono);font-size:13px;white-space:pre-wrap;margin:0 0 8px;'
                 'background:var(--surface-1);border-radius:var(--radius);padding:8px 10px;">nenhuma resposta escolhida ainda</pre>'
                 '<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;"><button id="fx-enviar">Enviar respostas ↗</button>'
                 '<span id="fx-erro" style="font-size:13px;color:var(--text-danger);"></span></div></div></div>')
    else:
        h.append('<div style="background:var(--bg-success);border-radius:var(--radius);padding:10px 14px;margin:16px 0 18px;">'
                 '<span style="font-size:15px;font-weight:500;color:var(--text-success);">Decisões humanas pendentes: nenhuma</span></div>')

    h.append('<p class="fx-lbl"><i class="ti ti-file-diff" style="font-size:16px;" aria-hidden="true"></i>Arquivos e comportamentos</p><div style="margin-bottom:18px;">')
    h += [f'<p style="font-size:14px;margin:0 0 4px;">{_i(c)}</p>' for c in f["comportamentos"]]
    if f["arquivos"]:
        h.append('<p style="font-size:13px;color:var(--text-secondary);margin:8px 0 0;">' + " · ".join(f"<code>{_e(a)}</code>" for a in f["arquivos"]) + '</p>')
    h.append('</div>')

    mostra_verificacoes, mostra_riscos = _mostra_verificacoes_e_riscos(f)
    if mostra_verificacoes:
        h.append('<p class="fx-lbl"><i class="ti ti-shield-check" style="font-size:16px;" aria-hidden="true"></i>Verificações e revisões</p><div style="margin-bottom:18px;"><div style="display:flex;gap:6px;flex-wrap:wrap;">')
        h += [f'<span class="fx-chip">{_i(v)}</span>' for v in f["verificacoes"]]
        h.append('</div>')
        h.append('</div>')
    if mostra_riscos:
        h.append(f'<p class="fx-lbl"><i class="ti ti-alert-triangle" style="font-size:16px;" aria-hidden="true"></i>Riscos e limitações · {len(f["riscos"])}</p>'
                 '<div style="margin-bottom:18px;border:0.5px solid var(--border-danger);border-radius:var(--radius);padding:10px 12px;">')
        h += [f'<p style="font-size:14px;margin:0 0 4px;">{_i(r)}</p>' for r in f["riscos"]]
        h.append('</div>')
    if f["proximo_passo"]:
        h.append('<div style="display:flex;align-items:center;gap:10px;padding-top:14px;border-top:0.5px solid var(--border);">'
                 '<i class="ti ti-arrow-right" style="font-size:18px;color:var(--text-accent);" aria-hidden="true"></i>'
                 '<span style="font-size:13px;color:var(--text-secondary);">Próximo passo</span>'
                 f'<span style="font-size:14px;">{_i(f["proximo_passo"])}</span></div>')
    h.append('</div>')
    if pendencias:
        h.append(SCRIPT_RESPOSTAS)
    return "\n".join(h) + "\n"


RENDERIZADORES = {
    "html": renderizar_html,
    "marca": renderizar_marca,
    "texto": renderizar_texto,
    "markdown": renderizar_markdown,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dados", help="arquivo JSON com os dados do fechamento, ou - para ler da entrada padrão")
    parser.add_argument("--formato", choices=sorted(RENDERIZADORES), required=True)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        bruto = sys.stdin.buffer.read() if args.dados == "-" else open(args.dados, "rb").read()
        fechamento = validar(json.loads(bruto.decode("utf-8")))
    except DadosInvalidos as erro:
        print("Dados do fechamento inválidos — corrija e rode de novo:", file=sys.stderr)
        for problema in erro.problemas:
            print(f"- {problema}", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erro:
        print(f"Não foi possível ler os dados: {erro}", file=sys.stderr)
        return 1
    sys.stdout.write(RENDERIZADORES[args.formato](fechamento))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
