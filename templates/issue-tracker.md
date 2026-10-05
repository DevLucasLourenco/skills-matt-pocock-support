# Tracker local

Cada fase tem uma pasta `.scratch/f<N>-<slug>/`, com uma spec opcional em `spec.md` e um arquivo por milestone em `issues/M<N>-<slug>.md`.

Exemplo: `.scratch/f1-nucleo/issues/M1-listagem.md`. Uma letra após o número identifica uma fase intermediária: `f1b-integracao`.

Cada ticket contém:

- Título `# M<N>: título`.
- Uma linha `**Status:**` com seu estado.
- Uma linha `**Blocked by:**` com dependências ou `None`.
- Checklist de aceite.
- Seção `## Comments` para decisões e pendências.

A `delivery-summary` registra pendências no ticket relacionado e usa `needs-info` quando o trabalho depende do mantenedor. A `phase-overview` lê os campos para calcular o progresso e os bloqueios.