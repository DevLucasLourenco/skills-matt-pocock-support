#!/usr/bin/env python3
"""Instala as duas skills, seus testes, modelos e hook opcional.

Preserva arquivos existentes, salvo com --force. Use --exemplo para criar
a estrutura inicial de fases e tickets, ou --dry-run para conferir os destinos.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

# origem (no pacote) -> destino (no projeto)
COPIAS = [
    ("skills/delivery-summary", ".claude/skills/delivery-summary"),
    ("skills/phase-overview", ".claude/skills/phase-overview"),
    ("hooks/check_delivery_summary.py", "tools/governance/check_delivery_summary.py"),
    ("tests/test_gerar_fechamento.py", "tests/governance/test_gerar_fechamento.py"),
    ("tests/test_check_delivery_summary.py", "tests/governance/test_check_delivery_summary.py"),
    ("tests/test_gerar_panorama.py", "tests/governance/test_gerar_panorama.py"),
    ("templates/task-completion-report.md", "docs/templates/task-completion-report.md"),
]

# só com --exemplo: convenção opcional para o leitor legado do panorama
EXEMPLO = [
    ("templates/panorama-das-fases.exemplo.md", "docs/panorama-das-fases.md"),
    ("templates/ticket-M1.exemplo.md", ".scratch/f0-inicio/issues/M1-primeiro-ticket.md"),
    ("templates/issue-tracker.md", "docs/agents/issue-tracker.md"),
    ("templates/triage-labels.md", "docs/agents/triage-labels.md"),
]

# pacotes de teste: o `discover -t .` precisa deles
INITS = ["tests/__init__.py", "tests/governance/__init__.py"]

IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc")


def _copiar(origem: Path, destino: Path, force: bool, dry: bool) -> str:
    if destino.exists() and not force:
        return "pulado (já existe)"
    if origem.is_dir() != (destino.is_dir() if destino.exists() else origem.is_dir()):
        return "ERRO: o destino é de outro tipo (arquivo x pasta); resolva à mão"
    if dry:
        return "copiaria"
    destino.parent.mkdir(parents=True, exist_ok=True)
    if origem.is_dir():
        # por cima: arquivo extra que o projeto tenha dentro da pasta da Skill é mantido
        shutil.copytree(origem, destino, ignore=IGNORAR, dirs_exist_ok=True)
    else:
        shutil.copy2(origem, destino)
    return "copiado"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("projeto", type=Path, help="pasta raiz do projeto de destino")
    parser.add_argument("--exemplo", action="store_true", help="cria também docs/panorama-das-fases.md e um ticket de exemplo, se não existirem")
    parser.add_argument("--dry-run", action="store_true", help="só mostra o que faria")
    parser.add_argument("--force", action="store_true", help="sobrescreve arquivos que já existem")
    args = parser.parse_args(argv)
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    projeto = args.projeto.resolve()
    if not projeto.is_dir():
        print(f"A pasta do projeto não existe: {projeto}", file=sys.stderr)
        return 1
    if projeto == AQUI:
        print("Aponte para a pasta do projeto, não para este pacote.", file=sys.stderr)
        return 1

    itens = [(o, d, args.force) for o, d in COPIAS]
    if args.exemplo:
        # os arquivos de exemplo viram do projeto depois de criados: --force nunca os sobrescreve
        itens += [(o, d, False) for o, d in EXEMPLO]
    erros = 0
    for origem, destino, forcar in itens:
        fonte = AQUI / origem
        if not fonte.exists():
            print(f"Pacote incompleto: falta {origem}", file=sys.stderr)
            return 1
        resultado = _copiar(fonte, projeto / destino, forcar, args.dry_run)
        erros += resultado.startswith("ERRO")
        print(f"{resultado:<20} {destino}")
    if erros:
        print(f"\n{erros} item(ns) com erro; o resto foi tratado.", file=sys.stderr)
    for init in INITS:
        alvo = projeto / init
        if alvo.exists():
            print(f"{'pulado (já existe)':<20} {init}")
        elif args.dry_run:
            print(f"{'criaria':<20} {init}")
        else:
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_text("", encoding="utf-8")
            print(f"{'criado':<20} {init}")

    print(
        f"""
Configuração (veja docs/INSTALACAO.md):
  1. Hook Stop opcional: acrescente o bloco de {AQUI / 'templates' / 'settings.stop-hook.json'}
     ao `.claude/settings.json` do projeto.
  2. Regras: cole os trechos de {AQUI / 'templates' / 'CLAUDE.trechos.md'}
     no `CLAUDE.md` do projeto.
  3. Na pasta do projeto, rode: python -m unittest discover -s tests/governance -p "test_*.py"
     A phase-overview descobre as fontes existentes; --exemplo é uma convenção opcional."""
    )
    return 1 if erros else 0


if __name__ == "__main__":
    raise SystemExit(main())
