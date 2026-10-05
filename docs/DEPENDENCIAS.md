# Requisitos

As duas skills complementam o fluxo de desenvolvimento com as skills do Matt Pocock. Usam Python 3.10 ou superior e apenas a biblioteca padrão. Cada complemento funciona separadamente.

A integração usa os registros existentes e o contexto da conversa. O panorama descobre as fontes sem exigir um formato ou layout do projeto.

## delivery-summary

- Um arquivo JSON com os dados da entrega, conforme a [skill](../skills/delivery-summary/SKILL.md).
- Tickets locais são opcionais: servem para registrar pendências do mantenedor.
- O modelo de [relatório de conclusão](../templates/task-completion-report.md) é opcional.
- O hook `Stop` é opcional: verifica a presença do fechamento ao encerrar um turno com edição ou delegação.

## phase-overview

- Planos, tickets, registros de entrega ou mensagens disponíveis no contexto do projeto. Sem evidências suficientes, informa as lacunas e os estados não confirmados.
- Markdown direto não exige Python, script, arquivo intermediário ou tracker.
- O painel opcional usa JSON normalizado, conforme [Painel opcional](../skills/phase-overview/references/painel.md). Com `--dados -`, recebe a entrada padrão e não consulta arquivos do projeto ou Git.

O leitor antigo permanece disponível sem `--dados`, para projetos que já seguem a [convenção de fases e tickets](FASES-E-TICKETS.md). Apenas esse modo lê os caminhos antigos e acrescenta avisos Git em relação a `origin/main`, conforme o último fetch.

## Exibição

Com `show_widget`, use o HTML gerado e a linha de marca na resposta. Sem essa ferramenta, use Markdown. Os botões do fechamento enviam respostas pelo identificador da pendência; o mantenedor também pode digitá-las na conversa.
