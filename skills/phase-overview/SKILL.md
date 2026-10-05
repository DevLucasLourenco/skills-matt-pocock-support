---
name: phase-overview
description: "Complementa as skills do Matt Pocock com o panorama das fases, milestones, dependências e pontos de atenção. Use quando o mantenedor pedir o status do projeto, o que falta ou o que está bloqueado."
---

# Phase Overview

Complemento às skills do Matt Pocock para acompanhar o trabalho registrado em tickets locais. Organize esses tickets no formato de fases e milestones descrito abaixo.

Gere o panorama com `scripts/gerar_panorama.py`. O script lê `docs/panorama-das-fases.md` e os tickets em `.scratch/f<N>[letra]-<slug>/issues/M<N>-<slug>.md`; os tickets determinam o progresso. A consulta não altera arquivos.

## Processo

1. Execute o gerador na raiz do projeto.
2. Se houver uma decisão ou limitação que o script não derive, passe `--avisos avisos.json` com uma lista de objetos `{"titulo": "...", "texto": "..."}`. Cite o ticket ou documento que sustenta cada aviso. Limites: 10 avisos, título de 80 caracteres e texto de 400.
3. Com `show_widget` disponível, consulte sua documentação, exiba a saída HTML sem editar e inclua a linha de marca na resposta. Sem essa ferramenta, use Markdown.
4. Corrija entradas inválidas apontadas pelo script antes de gerar novamente. Complemente a resposta apenas quando o pedido incluir informações fora do panorama.

```bash
python .claude/skills/phase-overview/scripts/gerar_panorama.py --formato html
python .claude/skills/phase-overview/scripts/gerar_panorama.py --formato marca
python .claude/skills/phase-overview/scripts/gerar_panorama.py --formato markdown
```

Use as mesmas opções em todas as saídas. `--projeto "Nome"` define o título; sem essa opção, o nome vem de `origin` ou da pasta. `--raiz caminho` permite consultar outro repositório confiável.

## Formato dos dados

A primeira tabela de `docs/panorama-das-fases.md` deve conter `Fase | Bloco | O que entrega | Estado`, com fases como `**F0**` ou `**F2b**`.

Cada ticket contém `# M<N>: título`, uma linha `**Status:**` e uma linha `**Blocked by:**`.

| Status | Interpretação |
|---|---|
| `concluído`, `implementado`, `implementado e fechado` | Entregue; aceita também data entre parênteses |
| `em andamento`, `em revisão` | Em andamento |
| `ready-for-agent` | Pronto quando as dependências estão entregues |
| `needs-info`, `ready-for-human` | Aguarda o mantenedor |
| `needs-triage` | Em triagem |
| `wontfix` | Descartado, fora da contagem |

`Blocked by` aceita `None`, `Nenhum`, `—`, `-`, referências como `M5` e `F0/M1`, ou faixas como `M1 a M12`. Referências em comentários também contam. Dependências pendentes, ausentes ou ilegíveis travam tickets prontos, em triagem ou sem estado.

## Cálculo e limites

- Uma fase fica concluída quando todos os tickets estão entregues e em andamento quando algum foi entregue ou está em curso.
- O painel destaca divergências entre a tabela e os tickets, pendências do mantenedor, checklists abertos, campos inválidos e bloqueadores ausentes.
- Nomes incompatíveis, identificadores repetidos e campos duplicados são recusados. Use arquivos UTF-8; linhas dentro de blocos de código são ignoradas.
- O script lê até 1 MiB por arquivo e 1000 tickets, recusa links simbólicos e mantém a tabela de fases intacta.
- Os avisos do Git usam dados locais do último fetch e comparam com `origin/main`.
