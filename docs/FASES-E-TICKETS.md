# Fases e tickets

A `phase-overview` lê a tabela de fases e os tickets locais para calcular o progresso.

## Fases

Use `docs/27-panorama-das-fases.md`. A primeira tabela deve ter este formato:

```markdown
| Fase | Bloco | O que entrega | Estado |
|---|---|---|---|
| **F0** | Fundação | Estrutura inicial | Não iniciada |
| **F1** | Núcleo | Regra de negócio | Sem spec nem ticket |
```

Identifique fases com `F<N>` ou `F<N><letra>`, como `F2b`. O estado declarado pode ser `Concluída`, `Em andamento`, `Não iniciada` ou `Sem spec nem ticket`. O script compara esses estados com os tickets; texto livre não gera comparação.

## Tickets

Crie um arquivo por milestone:

```text
.scratch/f1-nucleo/issues/M1-listagem.md
.scratch/f1-nucleo/issues/M2-exportacao.md
```

Use o [modelo de ticket](../templates/ticket-M1.exemplo.md). Cada arquivo precisa de um título `# M<N>: título`, uma linha `**Status:**` e uma linha `**Blocked by:**`. Números repetidos na mesma fase e campos repetidos são recusados. Campos ausentes geram avisos. Linhas dentro de blocos de código são ignoradas.

Diretórios de fase usam `f<N>[letra]-<slug>`; tickets usam `M<N>-<slug>.md`. Nomes incompatíveis nas pastas analisadas são recusados.

## Estados

| Status | Estado no painel |
|---|---|
| `concluído`, `implementado`, `implementado e fechado` | Entregue |
| `em andamento`, `em revisão` | Em andamento |
| `ready-for-agent` | Pronto, se as dependências estiverem entregues |
| `needs-info` | Aguarda você |
| `ready-for-human` | Com o mantenedor |
| `needs-triage` | Em triagem |
| `wontfix` | Descartado, fora da contagem |
| Outro texto | Sem estado, com aviso |

Estados de entrega podem aparecer sem data. O formato com data entre parênteses também é aceito. Ressalvas antes da data, como `concluído parcialmente`, não contam como entrega.

## Dependências

| Blocked by | Significado |
|---|---|
| `None`, `Nenhum`, `—` ou `-` | Sem dependência |
| `M5` | Ticket da mesma fase |
| `F0/M1`, `F2b/M3` | Ticket de outra fase |
| `M1 a M12` | Faixa de tickets da mesma fase |

Referências em comentários de `Blocked by` também contam. Um comentário sem referência após `None` deve começar por `pode começar`, `não depende`, `sem dependências`, `nenhuma dependência` ou `nada`; outros textos ficam como bloqueio ilegível.

Dependências ausentes ou pendentes travam tickets prontos, em triagem ou sem estado. Formas como `M3 até M5`, `F1-M3` e `M1..M12` são recusadas.

## Cálculo e avisos

Uma fase fica concluída quando todos os tickets estão entregues; em andamento quando algum foi entregue ou está em curso; não iniciada quando nenhum avançou. Tickets descartados não entram na contagem.

O painel destaca divergências da tabela de fases, pendências do mantenedor, bloqueadores ausentes, campos inválidos e tickets entregues com checklist aberto ou dependência pendente. O checklist usa `- [x]` e `- [ ]`.

O script lê arquivos UTF-8 de até 1 MiB e no máximo 1000 tickets. Cada dependência aceita até 2000 caracteres, 500 referências e faixas de até 200 tickets. Links simbólicos são recusados.