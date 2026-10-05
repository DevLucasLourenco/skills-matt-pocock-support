# Estados de triagem

Use estas strings no campo `**Status:**` dos tickets.

| Estado | Significado |
|---|---|
| `needs-triage` | Precisa de avaliação |
| `needs-info` | Aguarda informação ou decisão do mantenedor |
| `ready-for-agent` | Pronto para implementação pelo agente |
| `ready-for-human` | Requer trabalho do mantenedor |
| `wontfix` | Descartado |

Para estados próprios do projeto, ajuste a função `classificar` em `gerar_panorama.py`.