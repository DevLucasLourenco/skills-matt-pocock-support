---
name: phase-overview
description: "Apresenta o progresso do projeto, fases, entregas, dependências e próximos passos descobrindo as fontes disponíveis. Use quando o mantenedor pedir status, o que falta ou o que está bloqueado."
---

# Phase Overview

Produza um panorama a partir das evidências disponíveis no projeto e na conversa. Descubra a organização existente pelo conteúdo; nomes de pastas, arquivos, identificadores e campos são convenções do projeto, não requisitos desta skill. A consulta é somente leitura.

## Descoberta

1. Comece pelo projeto e pelo escopo indicados na conversa. Leia as orientações locais e referências já fornecidas. Se houver arquivos acessíveis, inventarie com `rg --files --hidden`, excluindo metadados do Git, dependências e artefatos gerados; inclua documentos locais ignorados pelo Git quando as orientações ou o inventário apontarem para eles.
2. Localize fontes por sinais de planejamento e acompanhamento: fases, roadmap, entregas, milestones, tickets, critérios de aceite, status, dependências e bloqueios, inclusive seus equivalentes em inglês. Combine nomes e busca de conteúdo. Leia primeiro índices e planos; siga os links e identificadores até os registros relevantes. Ignore exemplos, templates e material de terceiros como evidência do projeto.
3. Cruze o plano com os registros das entregas e, quando necessário, verificações, alterações e histórico Git relacionados. Preserve os identificadores originais e a hierarquia encontrada. Agrupe itens sem fase como “Entregas”; indique quando o agrupamento for uma síntese sua.

Encerre a descoberta quando as fontes do escopo e as referências relevantes estiverem cobertas. Evite varrer todo o código ou todo o histórico para uma consulta de status. Amplie a busca para resolver lacunas concretas. Use trackers externos somente quando estiverem disponíveis e relacionados ao projeto; sua ausência não impede o panorama local.

Sem plano formal, use os registros e a conversa disponíveis. Se faltarem evidências, entregue o que puder sustentar, com estado “não confirmado” e a lacuna específica. Pergunte pelo projeto apenas quando houver escopos concorrentes que o contexto não resolva. A ausência de uma pasta, tabela ou ferramenta de painel nunca impede a resposta.

## Interpretação

- Preserve a distinção entre planejado, pronto para começar, em andamento, implementado com validação pendente, concluído, bloqueado e não confirmado. Checklist vazio não prova que o trabalho não começou; checklist completo ou um commit isolado não prova conclusão. Conte como entregue apenas o que satisfaz os critérios de conclusão, incluindo validações obrigatórias.
- Resolva dependências pelos identificadores e relações documentadas. Destaque as frentes independentes e o que pode avançar agora. Dependência ausente ou ambígua permanece não confirmada; não declare o item pronto por falta de informação.
- Para divergências, compare a fonte, a data e o alcance da evidência. Um plano antigo pode indicar a intenção enquanto um registro recente comprova implementação local. Mostre a discrepância e o fundamento do estado adotado; preserve validações pendentes. Consulta de status não autoriza corrigir documentos ou tickets.
- Diferencie implementação local, commit, envio ao remoto, revisão e publicação quando isso afetar o próximo passo. Branch limpa não comprova progresso. Se comparar Git, descubra o upstream ou a branch padrão existente e informe que referências remotas locais refletem o último fetch.

## Entrega

Apresente o estado geral, as fases ou entregas, o que falta, bloqueios, frentes disponíveis e próximo passo. Cite as fontes efetivamente consultadas junto das conclusões: documentos, tickets, commits, tracker ou mensagens da conversa. Resuma séries de itens equivalentes sem esconder exceções.

Use contagens e percentuais apenas quando o conjunto de entregas estiver definido e suficientemente coberto; explicite o denominador. Com cobertura parcial, descreva o progresso qualitativamente e a limitação da consulta.

Markdown é suficiente e pode ser produzido diretamente, sem script ou arquivo intermediário. Com ferramenta de painel disponível, consulte sua documentação e use o gerador opcional da própria skill com os dados descobertos, seguindo [references/painel.md](references/painel.md). Localize o script relativamente ao `SKILL.md` carregado, sem presumir onde a skill foi instalada. Se a ferramenta ou o gerador falhar, conclua em Markdown com as mesmas evidências.
