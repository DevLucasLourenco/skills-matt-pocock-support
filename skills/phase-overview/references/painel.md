# Painel opcional

O agente descobre e interpreta as fontes; o gerador apenas calcula dependências e renderiza os dados normalizados. Ele não exige que o projeto adote um layout ou esquema de tickets.

Execute `scripts/gerar_panorama.py` relativamente à pasta desta skill. Use `--dados -` para receber JSON pela entrada padrão, ou `--dados` com um arquivo temporário fora do projeto. `--formato` aceita `html`, `marca` e `markdown`. Use os mesmos dados e opções em todas as saídas. `--projeto` informa o título; `--data` informa a data da consulta.

Com uma ferramenta de painel, exiba o HTML e inclua a linha de marca na resposta. Sem essa ferramenta, ou se a cobertura não permitir um percentual confiável, apresente Markdown diretamente.

## Dados normalizados

```json
{
  "projeto": "Projeto consultado",
  "fases": [{"id": "Documentação", "titulo": "Documentação", "estado": "Em andamento"}],
  "tickets": [
    {
      "id": "T01",
      "fase": "Documentação",
      "titulo": "Documento inicial",
      "estado": "validacao",
      "dependencias": [],
      "evidencia": "Implementação local registrada; inspeção visual ainda pendente.",
      "pendencias": ["Renderizar e inspecionar o documento"],
      "fontes": ["Registro da entrega T01", "Mensagem do mantenedor"]
    },
    {
      "id": "T03",
      "fase": "Documentação",
      "titulo": "Próxima entrega",
      "estado": "planejado",
      "dependencias": ["T01"],
      "fontes": ["Plano do projeto"]
    }
  ],
  "avisos": [{"titulo": "Próximo passo", "texto": "Validar T01 antes de iniciar T03; fonte: registro T01."}]
}
```

- `fases`: lista de objetos com `id` e `titulo`; `estado` declarado e `entrega` são opcionais. Preserve a ordem do plano. Pode ser vazia quando não houver fases formais.
- `tickets`: até 1000 objetos com `id`, `titulo`, `estado` e `fontes` não vazias. `fase` é opcional; na ausência, o grupo é “Entregas”. Identificadores são livres e únicos no conjunto; para IDs repetidos por fase, use a referência qualificada original.
- `estado`: `concluido`, `implementado`, `validacao`, `andamento`, `planejado`, `pronto`, `travado`, `needs-info`, `humano`, `triagem`, `descartado` ou `indefinido`. `implementado` é exibido como validação pendente e não conta como entregue; use `concluido` quando toda a conclusão estiver comprovada. `indefinido` representa estado não confirmado.
- `dependencias`: lista de IDs exatos, opcional. Omitir significa que a relação não foi confirmada; `[]` significa ausência de dependências confirmada. O gerador só mantém `pronto` quando as dependências são conhecidas e estão concluídas; dependências pendentes ou ausentes travam itens planejados, em triagem ou prontos.
- `evidencia`: resumo opcional da evidência. `pendencias`: lista opcional de validações ou ações restantes. Pendência em item declarado concluído mantém o item em validação e gera um aviso.
- `fontes`: referências legíveis efetivamente consultadas, não arquivos que o script precisará abrir. Aceita mensagens e trackers; o gerador exibe essas referências como texto.
- `avisos`: lista opcional de até 10 objetos com `titulo` (80 caracteres) e `texto` (400 caracteres), para discrepâncias, limitações e próximos passos com suas fontes.

O JSON completo tem limite de 1 MiB. Uma entrada vazia é recusada; nesse caso, explique a falta de evidência diretamente em Markdown. O modo `--dados` não lê arquivos do projeto nem consulta Git.

## Compatibilidade

Sem `--dados`, o gerador preserva o leitor antigo para projetos que já usam a convenção de fases e milestones do pacote. Esse modo exige o layout antigo e recebe a raiz explicitamente por `--raiz`; não o use como etapa inicial de descoberta. Erros do leitor antigo não exigem reorganizar o projeto: use os dados descobertos ou Markdown direto.
