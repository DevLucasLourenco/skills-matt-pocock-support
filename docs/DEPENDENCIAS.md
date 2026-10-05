# Requisitos

As duas skills complementam o fluxo de desenvolvimento com as skills do Matt Pocock. Usam Python 3.10 ou superior e apenas a biblioteca padrão. Cada complemento funciona separadamente.

A integração usa os arquivos da tarefa e do tracker local. O panorama exige o formato de fases e tickets deste pacote, descrito em [Fases e tickets](FASES-E-TICKETS.md).

## delivery-summary

- Um arquivo JSON com os dados da entrega, conforme a [skill](../skills/delivery-summary/SKILL.md).
- Tickets locais são opcionais: servem para registrar pendências do mantenedor.
- O modelo de [relatório de conclusão](../templates/task-completion-report.md) é opcional.
- O hook `Stop` é opcional: verifica a presença do fechamento ao encerrar um turno com edição ou delegação.

## phase-overview

- `docs/panorama-das-fases.md` com a tabela de fases.
- Tickets em `.scratch/f<N>[letra]-<slug>/issues/M<N>-<slug>.md`.
- Campos `**Status:**` e `**Blocked by:**` em cada ticket.

O script lê os arquivos locais diretamente. Git é opcional e acrescenta avisos sobre arquivos alterados e commits em relação a `origin/main`, conforme o último fetch.

## Exibição

Com `show_widget`, use o HTML gerado e a linha de marca na resposta. Sem essa ferramenta, use Markdown. Os botões do fechamento enviam respostas pelo identificador da pendência; o mantenedor também pode digitá-las na conversa.
