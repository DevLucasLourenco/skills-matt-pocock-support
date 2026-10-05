# skills-matt-pocock-support

Duas skills complementares às [skills do Matt Pocock](https://github.com/mattpocock/skills), para acompanhar o progresso e fechar entregas durante o desenvolvimento no Claude Code.

| Skill | Função |
|---|---|
| `delivery-summary` | Resume a entrega: resultado, mudanças, verificações, riscos, pendências e próximo passo. |
| `phase-overview` | Mostra o progresso das fases e dos milestones, suas dependências e pontos de atenção. |

As duas usam scripts Python para gerar um painel HTML ou uma resposta em Markdown. Funcionam de forma independente.

## Uso com as skills do Matt Pocock

Use as skills do Matt Pocock no planejamento, na implementação e na revisão do projeto. Estes complementos ajudam a acompanhar esse trabalho:

- `phase-overview` apresenta o progresso dos tickets organizados em fases e milestones.
- `delivery-summary` fecha cada entrega com o resultado e as pendências para o mantenedor.

A integração acontece pelos arquivos do projeto. Para o panorama, organize os tickets locais conforme o [formato de fases e tickets](docs/FASES-E-TICKETS.md) deste pacote.

## Instalação

Requer Python 3.10 ou superior, sem dependências externas.

Instale as skills do Matt Pocock seguindo as instruções do [repositório dele](https://github.com/mattpocock/skills). Depois, adicione estes complementos ao mesmo projeto:

```bash
python instalar.py "C:\caminho\do\projeto" --exemplo
```

O instalador copia as skills para `.claude/skills/`, junto com testes, modelos e um hook opcional de fechamento. `--exemplo` cria uma estrutura inicial de fases e tickets. Arquivos existentes são preservados; use `--dry-run` para conferir a instalação ou `--force` para atualizar os arquivos do pacote.

Veja [Instalação](docs/INSTALACAO.md) para configurar o uso automático e o hook.

## Uso

- Peça um fechamento de entrega ou use `$delivery-summary` após uma tarefa que alterou arquivos.
- Peça o progresso do projeto ou use `$phase-overview` para consultar fases, milestones e bloqueios.

Com `show_widget` disponível, as skills exibem o painel. Nos demais ambientes, usam Markdown.

O panorama lê `docs/panorama-das-fases.md` e os tickets em `.scratch/f<N>-<slug>/issues/M<N>-<slug>.md`. O fechamento pode registrar pendências nesses tickets quando eles existirem.

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
