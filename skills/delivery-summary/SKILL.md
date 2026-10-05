---
name: delivery-summary
description: "Complementa as skills do Matt Pocock com o fechamento de tarefas que alteraram arquivos, incluindo entregas parciais e pausas: resultado, mudanças, verificações, riscos, pendências e próximo passo."
---

# Delivery Summary

Complemento às skills do Matt Pocock para resumir cada entrega e reunir as pendências do mantenedor. Usa o estado da tarefa e, quando houver, seu ticket local.

Use ao concluir ou pausar uma tarefa que alterou arquivos. Gere o fechamento a partir do estado real do trabalho com `scripts/gerar_fechamento.py`.

## Processo

1. Reúna o resultado, as mudanças, os arquivos relevantes, as verificações executadas e os riscos, incluindo testes não executados.
2. Revise as perguntas e decisões abertas na conversa e no ticket relacionado. Para cada pendência, registre contexto, recomendação, justificativa e custo da alternativa. Preserve seu identificador entre fechamentos.
3. Se houver ticket relacionado, registre as pendências em `## Comments`. Use `needs-info` quando o trabalho depender da resposta do mantenedor. Sem tracker, mantenha as pendências no fechamento.
4. Salve os dados em JSON e execute o gerador. Corrija os problemas apontados antes de exibir a saída.
5. Com `show_widget` disponível, consulte sua documentação, exiba a saída HTML sem editar e inclua a linha de marca na resposta. Sem essa ferramenta, use Markdown.

```bash
python .claude/skills/delivery-summary/scripts/gerar_fechamento.py dados.json --formato html
python .claude/skills/delivery-summary/scripts/gerar_fechamento.py dados.json --formato marca
python .claude/skills/delivery-summary/scripts/gerar_fechamento.py dados.json --formato markdown
```

## Dados

| Campo | Conteúdo |
|---|---|
| `titulo` | Entrega em uma frase |
| `resultado` | `concluido`, `parcial`, `bloqueado` ou `falhou` |
| `motivo` | Explicação obrigatória quando o resultado não for `concluido` |
| `trabalho` | `local`, `commitado` ou `enviado`; os dois últimos exigem `commit` com o hash |
| `comportamentos` | Mudanças realizadas ou estado alcançado, ao menos uma linha |
| `arquivos` | Caminhos relevantes |
| `verificacoes` | Verificações executadas e seus resultados |
| `riscos` | Riscos residuais e testes não executados |
| `pendencias` | Decisões ou informações aguardando o mantenedor |
| `proximo_passo` | Próxima ação; obrigatório para resultados não concluídos, opcional nos demais |

As listas podem ser vazias, exceto `comportamentos`. Use crases para identificar código e caminhos nos textos.

Cada pendência contém:

- `id`: identificador único, de 2 a 20 caracteres minúsculos, como `cache`.
- `tipo`: `blocked`, `decisao`, `aceite-de-risco`, `aprovacao` ou `informacao`.
- `urgencia`: `agora`, `proximo` ou `pode-esperar`.
- `pergunta`, `contexto` e `enquanto`: questão, situação e efeito enquanto a resposta não chega.
- `recomendacao`: objeto com `opcao`, `base` e `custo`.
- `alternativas` e/ou `livre`: respostas possíveis ou descrição do que digitar.
- `premissa`: obrigatória em uma `decisao`, para registrar a opção adotada durante o trabalho.

Uma pendência `blocked` exige resultado `bloqueado` e urgência `agora`. Decisões e aceites de risco exigem alternativa ou resposta livre. Opções de resposta devem usar texto sem crases.

```json
{
  "titulo": "Cache da listagem",
  "resultado": "concluido",
  "trabalho": "local",
  "comportamentos": ["A listagem usa cache por usuário"],
  "arquivos": ["src/listagem.py"],
  "verificacoes": ["Testes da listagem passaram"],
  "riscos": [],
  "pendencias": [
    {
      "id": "cache",
      "tipo": "decisao",
      "urgencia": "proximo",
      "pergunta": "Compartilhar o cache por organização?",
      "contexto": "A listagem é cara de calcular.",
      "enquanto": "O cache segue por usuário.",
      "premissa": "Cache isolado por usuário.",
      "recomendacao": {
        "opcao": "manter por usuário",
        "base": "Preserva o isolamento entre usuários.",
        "custo": "Compartilhar exige revisar a chave e a invalidação."
      },
      "alternativas": ["compartilhar por organização"]
    }
  ],
  "proximo_passo": "Definir o escopo do cache"
}
```

## Respostas

Resolva as respostas pelo identificador: `cache manter por usuário`. `ok todas` aceita as recomendações do último fechamento. Identificador desconhecido ou resposta ambígua exige esclarecimento antes de agir.

No painel, selecionar uma opção permite trocá-la antes de usar “Enviar respostas”. O botão de aceitar todas seleciona as recomendações e envia uma única mensagem.
