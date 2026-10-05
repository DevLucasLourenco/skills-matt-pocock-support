# Fases e tickets

A `phase-overview` descobre o progresso pelos registros existentes. Este documento descreve uma convenção opcional e o leitor legado do gerador, usado sem `--dados`; não é requisito para usar a skill. Para renderizar dados de outras organizações, consulte [Painel opcional](../skills/phase-overview/references/painel.md). Uma **fase** agrupa uma parte do desenvolvimento; um **milestone** é uma entrega dessa fase, descrita em um ticket.

## Estrutura do projeto

```text
docs/
  panorama-das-fases.md
.scratch/
  f0-fundacao/
    issues/
      M1-estrutura-inicial.md
  f1-nucleo/
    issues/
      M1-listagem.md
      M2-exportacao.md
```

O documento lista as fases. Os tickets descrevem as entregas e informam seu estado e suas dependências. Os nomes das fases, os títulos e as entregas são definidos por cada projeto.

## Fases

Crie `docs/panorama-das-fases.md` no projeto de destino, ou use `python instalar.py "caminho/do/projeto" --exemplo` para gerar um modelo. A primeira tabela deve ter este formato:

```markdown
| Fase | Bloco | O que entrega | Estado |
|---|---|---|---|
| **F0** | Fundação | Estrutura inicial | Não iniciada |
| **F1** | Núcleo | Regra de negócio | Sem spec nem ticket |
```

Use `F` para fase e um número para sua ordem: `F0`, `F1`, `F2`. Uma letra identifica uma fase intermediária, como `F2b`. O estado declarado pode ser `Concluída`, `Em andamento`, `Não iniciada` ou `Sem spec nem ticket` (fase ainda sem especificação ou entregas detalhadas). O script compara esses estados com os tickets; texto livre não gera comparação.

## Tickets

Crie um arquivo por milestone:

```text
.scratch/f1-nucleo/issues/M1-listagem.md
.scratch/f1-nucleo/issues/M2-exportacao.md
```

Use `M` para milestone, numerado a partir de `M1` dentro de cada fase. Um ticket contém, por exemplo:

```markdown
# M1: Listagem

**What to build:** permitir consultar os itens cadastrados.
**Status:** ready-for-agent
**Blocked by:** None

- [ ] Exibir os itens cadastrados
- [ ] Mostrar uma mensagem quando a lista estiver vazia

## Comments
```

O [modelo de ticket](../templates/ticket-M1.exemplo.md) segue esse formato. `Status` informa o estado; `Blocked by` informa quais entregas precisam terminar antes desta. Números repetidos na mesma fase e campos repetidos são recusados. Campos ausentes geram avisos. Linhas dentro de blocos de código são ignoradas.

As pastas usam o número da fase em minúsculas e um nome curto, como `f1-nucleo`. Os arquivos usam o número do milestone e um nome curto, como `M1-listagem.md`. Nomes incompatíveis nas pastas analisadas são recusados.

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
