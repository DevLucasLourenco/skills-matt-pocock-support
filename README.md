# skills-matt-pocock-support

Duas skills para acompanhar o desenvolvimento de projetos no Claude Code.

| Skill | Função |
|---|---|
| `delivery-summary` | Resume a entrega: resultado, mudanças, verificações, riscos, pendências e próximo passo. |
| `phase-overview` | Mostra o progresso das fases e dos milestones, suas dependências e pontos de atenção. |

As duas usam scripts Python para gerar um painel HTML ou uma resposta em Markdown. Funcionam de forma independente.

## Instalação

Requer Python 3.10 ou superior, sem dependências externas.

```bash
python instalar.py "C:\caminho\do\projeto" --exemplo
```

O instalador copia as skills para `.claude/skills/`, junto com testes, modelos e um hook opcional de fechamento. `--exemplo` cria uma estrutura inicial de fases e tickets. Arquivos existentes são preservados; use `--dry-run` para conferir a instalação ou `--force` para atualizar os arquivos do pacote.

Veja [Instalação](docs/INSTALACAO.md) para configurar o uso automático e o hook.

## Uso

- Peça um fechamento de entrega ou use `$delivery-summary` após uma tarefa que alterou arquivos.
- Peça o progresso do projeto ou use `$phase-overview` para consultar fases, milestones e bloqueios.

Com `show_widget` disponível, as skills exibem o painel. Nos demais ambientes, usam Markdown.

O panorama lê `docs/27-panorama-das-fases.md` e os tickets em `.scratch/f<N>-<slug>/issues/M<N>-<slug>.md`. O fechamento pode registrar pendências nesses tickets quando eles existirem.

## Referências

- [Requisitos das skills](docs/DEPENDENCIAS.md)
- [Formato das fases e dos tickets](docs/FASES-E-TICKETS.md)
- [Instruções do fechamento](skills/delivery-summary/SKILL.md)
- [Instruções do panorama](skills/phase-overview/SKILL.md)

## Testes

No repositório:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

No projeto de destino:

```bash
python -m unittest discover -s tests/governance -p "test_*.py"
```