# Instalação

Instale as [skills do Matt Pocock](https://github.com/mattpocock/skills) conforme as instruções do repositório dele. Em seguida, adicione `delivery-summary` e `phase-overview` como complementos no mesmo projeto.

## Copiar os arquivos

```bash
python instalar.py "C:\caminho\do\projeto" --exemplo
```

O instalador copia:

| Destino | Conteúdo |
|---|---|
| `.claude/skills/` | As duas skills e seus geradores |
| `tools/governance/check_delivery_summary.py` | Hook opcional de fechamento |
| `tests/governance/` | Testes dos geradores e do hook |
| `docs/templates/task-completion-report.md` | Modelo opcional de relatório |

Com `--exemplo`, também cria a tabela de fases em `docs/panorama-das-fases.md`, um ticket em `.scratch/f0-inicio/issues/` e as referências do tracker em `docs/agents/`.

- `--dry-run`: mostra os arquivos que seriam copiados.
- `--force`: atualiza os arquivos do pacote, preservando arquivos extras nas pastas das skills.
- Os arquivos de exemplo existentes são sempre preservados.

## Configurar o uso automático

Adicione os trechos de [CLAUDE.trechos.md](../templates/CLAUDE.trechos.md) ao `CLAUDE.md` do projeto para orientar o agente a usar as skills.

## Ativar o hook opcional

Para exigir um fechamento nos turnos com edição ou delegação, adicione o bloco de [settings.stop-hook.json](../templates/settings.stop-hook.json) ao `.claude/settings.json`. Se já houver hooks, acrescente o item à lista `Stop` existente.

O hook verifica o cabeçalho do fechamento e a seção de pendências. Quando a sessão já usou `show_widget`, ou a resposta indica um painel, também verifica a chamada dessa ferramenta no turno. Ele verifica presença, não a qualidade do conteúdo.

Edições por `Edit`, `MultiEdit`, `Write` e `NotebookEdit`, e delegações por `Agent` ou `Task`, acionam a verificação. Edições por shell não são detectadas. Erros internos ou dados ausentes liberam o encerramento; `stop_hook_active` evita bloqueios repetidos.

## Conferir

Na pasta do projeto de destino:

```bash
python -m unittest discover -s tests/governance -p "test_*.py"
python .claude/skills/phase-overview/scripts/gerar_panorama.py --formato marca
```

O panorama precisa da tabela de fases e dos tickets. Use `--exemplo` se o projeto ainda não tiver essa estrutura.
