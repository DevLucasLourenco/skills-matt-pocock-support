"""Testes do gerador do panorama das fases (Skill phase-overview)."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

REPO = next(p for p in Path(__file__).resolve().parents
            if (p / "skills/phase-overview/scripts/gerar_panorama.py").is_file()
            or (p / ".claude/skills/phase-overview/scripts/gerar_panorama.py").is_file())
SCRIPT = REPO / "skills/phase-overview/scripts/gerar_panorama.py"
if not SCRIPT.is_file():
    SCRIPT = REPO / ".claude/skills/phase-overview/scripts/gerar_panorama.py"
_spec = importlib.util.spec_from_file_location("gerar_panorama", SCRIPT)
gp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gp)

FASES_EXEMPLO = """# Panorama das fases

| Fase | Bloco | O que entrega | Estado |
|---|---|---|---|
| **F0** | Estrutura | Ferramentas | Concluída |
| **F1** | Núcleo | Regras de negócio | Spec e 3 tickets, não iniciada |
| **F2** | Plataforma | Fundação | Em andamento |
| **F3** | Interface | Telas | Sem spec nem ticket |
| **F4** | Integrações | Serviços externos | Sem spec nem ticket |

| Fase | Diretório | Tickets |
|---|---|---|
| F0 | `.scratch/f0-x/` | M1 |
"""


def _ticket(raiz: Path, pasta: str, n: int, titulo: str, status: str, bloqueio: str = "None", itens: str = "") -> None:
    caminho = raiz / ".scratch" / pasta / "issues" / f"M{n}-slug.md"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        f"# M{n}: {titulo}\n\n**What to build:** x\n\n**Blocked by:** {bloqueio}\n\n**Status:** {status}\n\n{itens}",
        encoding="utf-8",
    )


class PanoramaTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)
        (self.raiz / "docs").mkdir()
        (self.raiz / "docs/panorama-das-fases.md").write_text(FASES_EXEMPLO, encoding="utf-8")
        _ticket(self.raiz, "f0-x", 1, "Scripts", "concluído (2026-09-21)")
        _ticket(self.raiz, "f1-y", 1, "Estrutura inicial", "concluído (2026-10-02)")
        _ticket(self.raiz, "f1-y", 2, "Listagem", "implementado (2026-10-02) com pendência", "M1")
        _ticket(self.raiz, "f1-y", 3, "Saída", "ready-for-agent", "M2")
        _ticket(self.raiz, "f1-y", 4, "Filtros", "ready-for-agent", "M3, F0/M1")
        _ticket(self.raiz, "f2-z", 1, "Base", "concluído (2026-10-01)")
        _ticket(self.raiz, "f2-z", 2, "Endurecimento", "em andamento (2026-10-01)", "M1 a M1",
                "- [x] um\n- [ ] dois\n- [ ] tres\n")

    def _fases(self) -> dict[str, dict]:
        fases, _ = gp.montar(self.raiz)
        return {f["fase"]: f for f in fases}

    def _estados(self, fase: str) -> dict[int, str]:
        return {t["numero"]: t["estado"] for t in self._fases()[fase]["tickets"]}

    # --- estado do ticket
    def test_classifica_os_estados_convencionais(self) -> None:
        casos = {
            "concluído (2026-09-21)": "concluido",
            "Concluida (2026-01-01)": "concluido",
            "implementado e fechado (2026-10-02)": "implementado",
            "em andamento (2026)": "andamento",
            "em revisão": "andamento",
            "needs-info — aguarda": "needs-info",
            "ready-for-agent": "pronto",
            "ready-for-human": "humano",
            "needs-triage": "triagem",
            "wontfix": "descartado",
            "qualquer coisa": "indefinido",
            "": "indefinido",
        }
        for texto, esperado in casos.items():
            self.assertEqual(gp.classificar(texto), esperado, texto)

    def test_ticket_pronto_com_bloqueador_pendente_fica_travado(self) -> None:
        estados = self._estados("F1")
        self.assertEqual(estados[3], "pronto")  # M2 está implementado
        self.assertEqual(estados[4], "travado")  # M3 ainda não foi entregue

    def test_ticket_travado_lista_o_que_espera(self) -> None:
        m4 = next(t for t in self._fases()["F1"]["tickets"] if t["numero"] == 4)
        self.assertEqual(m4["espera"], [("F1", 3)])

    def test_bloqueador_de_outra_fase_entregue_nao_trava(self) -> None:
        self.assertEqual(self._estados("F1")[4], "travado")
        _ticket(self.raiz, "f1-y", 3, "Saída", "concluído (2026-10-01)", "M2")
        self.assertEqual(self._estados("F1")[4], "pronto")  # F0/M1 está concluído

    def test_bloqueadores_aceitam_referencia_cruzada_e_faixa(self) -> None:
        self.assertEqual(gp.bloqueadores("M4, M5, M6", "F2"), [("F2", 4), ("F2", 5), ("F2", 6)])
        self.assertEqual(gp.bloqueadores("F0/M1 (scripts)", "F2"), [("F0", 1)])
        self.assertEqual(gp.bloqueadores("M1 a M3 (todos)", "F2"), [("F2", 1), ("F2", 2), ("F2", 3)])
        self.assertEqual(gp.bloqueadores("None — F0/M2 concluído", "F0"), [("F0", 2)])
        self.assertEqual(gp.bloqueadores("—", "F0"), [])

    def test_andamento_com_bloqueador_pendente_continua_andamento(self) -> None:
        _ticket(self.raiz, "f2-z", 2, "Endurecimento", "em andamento", "M9")
        _ticket(self.raiz, "f2-z", 9, "Outro", "ready-for-agent")
        self.assertEqual(self._estados("F2")[2], "andamento")

    # --- estado da fase
    def test_estado_da_fase_vem_dos_tickets(self) -> None:
        fases = self._fases()
        self.assertEqual(fases["F0"]["calculado"], "concluida")
        self.assertEqual(fases["F1"]["calculado"], "andamento")
        self.assertEqual(fases["F2"]["calculado"], "andamento")
        self.assertEqual(fases["F3"]["calculado"], "sem-ticket")

    def test_fase_com_tickets_e_nenhum_entregue_nao_iniciada(self) -> None:
        _ticket(self.raiz, "f3-w", 1, "Primeiro", "ready-for-agent")
        self.assertEqual(self._fases()["F3"]["calculado"], "nao-iniciada")

    def test_contagem_e_totais(self) -> None:
        fases, _ = gp.montar(self.raiz)
        t = gp.totais(fases)
        self.assertEqual((t["total"], t["entregues"], t["percentual"]), (7, 4, 57))

    # --- divergência com o docs/panorama-das-fases.md
    def test_aponta_divergencia_do_documento_de_fases(self) -> None:
        fases = self._fases()
        self.assertTrue(fases["F1"]["diverge"])  # diz "não iniciada", tickets andamento
        self.assertFalse(fases["F0"]["diverge"])
        self.assertFalse(fases["F3"]["diverge"])

    def test_texto_livre_no_documento_de_fases_nao_conta_como_divergencia(self) -> None:
        texto = FASES_EXEMPLO.replace("Spec e 3 tickets, não iniciada", "Spec e 3 tickets; M1 e M2 concluídos, M3 e M4 abertos")
        (self.raiz / "docs/panorama-das-fases.md").write_text(texto, encoding="utf-8")
        self.assertFalse(self._fases()["F1"]["diverge"])

    def test_divergencia_vira_ponto_de_atencao(self) -> None:
        fases, _ = gp.montar(self.raiz)
        titulos = [a["titulo"] for a in gp.avisos_automaticos(fases, None)]
        self.assertIn("Estado declarado diverge em F1", titulos)

    def test_ticket_que_aguarda_o_mantenedor_vira_ponto_de_atencao(self) -> None:
        _ticket(self.raiz, "f2-z", 3, "Decisão", "needs-info (2026-10-01)")
        fases, _ = gp.montar(self.raiz)
        avisos = gp.avisos_automaticos(fases, None)
        achados = [a for a in avisos if a["titulo"] == "Tickets aguardando o mantenedor"]
        self.assertEqual([a["texto"] for a in achados], ["F2/M3"])

    def test_estado_do_repositorio_vira_ponto_de_atencao(self) -> None:
        fases, _ = gp.montar(self.raiz)
        repo = {"ramo": "main", "atras": 2, "adiante": 4, "alterados": 1}
        titulos = [a["titulo"] for a in gp.avisos_automaticos(fases, repo)]
        self.assertIn("Commits locais sem push", titulos)
        self.assertIn("Checkout atrás do remoto", titulos)
        self.assertIn("Alterações não commitadas", titulos)

    def test_fora_de_um_repositorio_git_o_script_continua(self) -> None:
        fases, repositorio = gp.montar(self.raiz)
        self.assertIsNone(repositorio)
        self.assertTrue(gp.renderizar_html(fases, None, [], "2026-10-05"))

    # --- avisos extras
    def test_avisos_validos_passam(self) -> None:
        self.assertEqual(gp.validar_avisos([{"titulo": " a ", "texto": "b"}]), [{"titulo": "a", "texto": "b"}])

    def test_avisos_invalidos_sao_recusados(self) -> None:
        recusados = [
            {"titulo": "a"},
            [{"titulo": "a", "texto": "b", "extra": 1}],
            [{"titulo": "", "texto": "b"}],
            [{"titulo": "x" * 81, "texto": "b"}],
            [{"titulo": "a", "texto": "y" * 401}],
            [{"titulo": "a", "texto": "b"}] * 11,
            ["texto solto"],
        ]
        for dados in recusados:
            with self.assertRaises(gp.ErroDados, msg=repr(dados)[:40]):
                gp.validar_avisos(dados)

    # --- renderização
    def _html(self, avisos: list[dict[str, str]] | None = None) -> str:
        fases, repo = gp.montar(self.raiz)
        return gp.renderizar_html(fases, repo, avisos or [], "2026-10-05")

    def test_html_e_so_informacao(self) -> None:
        saida = self._html()
        for proibido in ("<script", "<button", "sendPrompt", "onclick"):
            self.assertNotIn(proibido, saida)

    def test_html_mostra_progresso_tabela_e_estados(self) -> None:
        saida = self._html()
        self.assertIn("4 de 7 tickets · 57%", saida)
        self.assertIn("<table", saida)
        self.assertIn("Pronto para começar", saida)
        self.assertIn("Travado", saida)
        self.assertIn("1 de 3 itens", saida)  # M2 da F2 em andamento: 1 de 3 itens
        self.assertIn("Sem spec nem ticket", saida)

    def test_html_escapa_dados_dos_tickets_e_dos_avisos(self) -> None:
        _ticket(self.raiz, "f2-z", 5, "<script>alert(1)</script> `ok`", "ready-for-agent")
        saida = self._html([{"titulo": "<img src=x onerror=1>", "texto": "a & b"}])
        self.assertNotIn("<script>alert", saida)
        self.assertNotIn("<img", saida)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; <code>ok</code>", saida)
        self.assertIn("a &amp; b", saida)

    def test_html_nao_deixa_tag_de_dado_virar_codigo_pela_crase(self) -> None:
        _ticket(self.raiz, "f2-z", 6, "`<b>x</b>`", "ready-for-agent")
        self.assertIn("<code>&lt;b&gt;x&lt;/b&gt;</code>", self._html())

    def test_entregues_ficam_em_chips_com_titulo_e_so_o_que_falta_em_tabela(self) -> None:
        saida = self._html()
        self.assertIn('title="M1 — Estrutura inicial"', saida)
        self.assertNotIn(">Estrutura inicial<", saida)

    def test_marca_e_uma_linha_sem_repetir_o_painel(self) -> None:
        fases, _ = gp.montar(self.raiz)
        marca = gp.renderizar_marca(fases)
        self.assertNotIn("\n", marca)
        self.assertTrue(marca.startswith("**Panorama das fases** · 4 de 7 tickets entregues (57%)"))
        self.assertIn("F0 concluída", marca)
        self.assertIn("F1 em andamento (2/4)", marca)
        self.assertIn("F3 a F4 sem ticket", marca)
        self.assertTrue(marca.endswith("detalhes no painel acima"))

    def test_markdown_traz_tabela_de_fases_e_o_que_falta(self) -> None:
        fases, repo = gp.montar(self.raiz)
        md = gp.renderizar_markdown(fases, repo, [{"titulo": "T", "texto": "x"}], "2026-10-05")
        self.assertIn("| F1 | Núcleo | Em andamento | 2 de 4 |", md)
        self.assertIn("### F1 — o que falta", md)
        self.assertIn("| M4 | Filtros | Travado | M3 |", md)
        self.assertIn("- **T** — x", md)

    def test_faixa_de_fases(self) -> None:
        ordem = ["F2", "F2b", "F3", "F4", "F5"]
        self.assertEqual(gp._faixa(["F3", "F4", "F5"], ordem), "F3 a F5")
        self.assertEqual(gp._faixa(["F2b", "F3"], ordem), "F2b a F3")
        self.assertEqual(gp._faixa(["F3", "F5"], ordem), "F3, F5")
        self.assertEqual(gp._faixa(["F3"], ordem), "F3")

    # --- fase com sufixo (F2b), bloqueador sem ticket e limites
    def test_fase_com_sufixo_entra_na_ordem_certa(self) -> None:
        texto = FASES_EXEMPLO.replace("| **F3** |", "| **F2b** | Mapa | Pacote | Sem spec nem ticket |\n| **F3** |")
        (self.raiz / "docs/panorama-das-fases.md").write_text(texto, encoding="utf-8")
        fases, _ = gp.montar(self.raiz)
        self.assertEqual([f["fase"] for f in fases], ["F0", "F1", "F2", "F2b", "F3", "F4"])
        self.assertIn("F2b a F4 sem ticket", gp.renderizar_marca(fases))

    def test_ticket_de_fase_com_sufixo_e_referencia_cruzada(self) -> None:
        texto = FASES_EXEMPLO.replace("| **F3** |", "| **F2b** | Mapa | Pacote | Em andamento |\n| **F3** |")
        (self.raiz / "docs/panorama-das-fases.md").write_text(texto, encoding="utf-8")
        _ticket(self.raiz, "f2b-mapa", 1, "Pacote", "concluído (2026-10-01)")
        _ticket(self.raiz, "f3-w", 1, "Zonas", "ready-for-agent", "F2b/M1")
        _ticket(self.raiz, "f3-w", 2, "Telas", "ready-for-agent", "F3/M1")
        fases = {f["fase"]: f for f in gp.montar(self.raiz)[0]}
        self.assertEqual(fases["F2b"]["calculado"], "concluida")
        estados = {t["numero"]: t["estado"] for t in fases["F3"]["tickets"]}
        self.assertEqual(estados, {1: "pronto", 2: "travado"})

    def test_linha_de_fase_em_formato_desconhecido_e_recusada(self) -> None:
        texto = FASES_EXEMPLO.replace("| **F3** |", "| **Fx** | Bloco | Entrega | Estado |\n| **F3** |")
        (self.raiz / "docs/panorama-das-fases.md").write_text(texto, encoding="utf-8")
        with self.assertRaises(gp.ErroDados):
            gp.montar(self.raiz)

    def test_bloqueador_que_nao_existe_como_ticket_trava(self) -> None:
        _ticket(self.raiz, "f2-z", 3, "Depende de fase futura", "ready-for-agent", "F3/M1, M9")
        ticket = next(t for t in self._fases()["F2"]["tickets"] if t["numero"] == 3)
        self.assertEqual(ticket["estado"], "travado")
        self.assertEqual(ticket["espera"], [("F3", 1), ("F2", 9)])
        self.assertEqual(gp._espera(ticket), "F3/M1 (sem ticket), M9 (sem ticket)")
        self.assertIn("(sem ticket)", self._html())

    def test_bloqueador_sem_ticket_vira_ponto_de_atencao(self) -> None:
        _ticket(self.raiz, "f2-z", 3, "Depende", "ready-for-agent", "F3/M1")
        fases, _ = gp.montar(self.raiz)
        avisos = {a["titulo"]: a["texto"] for a in gp.avisos_automaticos(fases, None)}
        self.assertEqual(avisos["Bloqueador sem ticket"], "F2/M3 espera F3/M1")

    def test_nenhum_so_vale_quando_e_o_texto_inteiro(self) -> None:
        self.assertEqual(gp.bloqueadores("None until M5", "F0"), [("F0", 5)])
        self.assertEqual(gp.bloqueadores("- M3", "F0"), [("F0", 3)])
        self.assertEqual(gp.bloqueadores("None (pode começar já)", "F0"), [])
        self.assertEqual(gp.bloqueadores("Nenhum — F0/M2 concluído", "F0"), [("F0", 2)])

    def test_faixa_gigante_e_numero_absurdo_sao_recusados(self) -> None:
        for texto in ("M1 a M999999999", "M1 a M300", "M123456"):
            with self.assertRaises(gp.ErroDados, msg=texto):
                gp.bloqueadores(texto, "F2")
        self.assertEqual(len(gp.bloqueadores("M1 a M200", "F2")), 200)

    def test_blocked_by_hostil_e_recusado_ou_rapido(self) -> None:
        import time

        # campo enorme: recusado antes de qualquer regex
        with self.assertRaises(gp.ErroDados):
            gp.bloqueadores("none" + " " * 40000 + "x", "F2")
        # no limite do campo, o casamento de "none" segue linear
        inicio = time.monotonic()
        self.assertEqual(gp.bloqueadores("none" + " " * 1900 + "x", "F2"), [])  # sem referência
        self.assertLess(time.monotonic() - inicio, 5.0)  # folgado: o que protege é o teto do campo

    def test_teto_de_referencias_vale_para_o_campo_inteiro(self) -> None:
        with self.assertRaises(gp.ErroDados):
            gp.bloqueadores(", ".join(["M1 a M200"] * 4), "F2")  # 800 referências
        self.assertEqual(len(gp.bloqueadores(", ".join(["M1 a M200"] * 2), "F2")), 400)

    def test_markdown_escapa_barra_dentro_de_crase_e_ramo_sem_crase(self) -> None:
        self.assertEqual(gp._md("a `x|y` b|c"), r"a `x\|y` b\|c")

    def test_ticket_com_campo_blocked_by_gigante_derruba_o_panorama_com_erro_claro(self) -> None:
        caminho = self.raiz / ".scratch/f2-z/issues/M9-hostil.md"
        caminho.write_text(
            "# M9: hostil\n\n**Blocked by:** M1 a M200, " * 1 + "M1 a M200, " * 300 + "\n\n**Status:** ready-for-agent\n",
            encoding="utf-8",
        )
        with self.assertRaises(gp.ErroDados):
            gp.montar(self.raiz)

    def test_numero_de_ticket_duplicado_na_fase_e_recusado(self) -> None:
        duplicado = self.raiz / ".scratch/f2-z/issues/M1-outro.md"
        duplicado.write_text("# M1: Duplicado\n\n**Blocked by:** None\n\n**Status:** ready-for-agent\n", encoding="utf-8")
        with self.assertRaises(gp.ErroDados) as ctx:
            gp.montar(self.raiz)
        self.assertIn("duplicado", str(ctx.exception))

    def test_blocked_by_ilegivel_trava_o_ticket_e_gera_aviso(self) -> None:
        for n, texto in ((3, "aguardando decisão do cliente"), (4, "ADR-0019"), (5, "")):
            _ticket(self.raiz, "f2-z", n, f"Ilegível {n}", "ready-for-agent", texto)
        fases, _ = gp.montar(self.raiz)
        f2 = next(f for f in fases if f["fase"] == "F2")
        for t in f2["tickets"]:
            if t["numero"] in (3, 4, 5):
                self.assertEqual(t["estado"], "travado", t["numero"])
                self.assertEqual(gp._espera(t), "bloqueio ilegível")
        avisos = {a["titulo"]: a["texto"] for a in gp.avisos_automaticos(fases, None)}
        self.assertEqual(avisos["Blocked by ilegível"], "F2/M3, F2/M4, F2/M5")
        self.assertIn("bloqueio ilegível", self._html())

    def test_blocked_by_legivel_nao_vira_ilegivel(self) -> None:
        _ticket(self.raiz, "f2-z", 3, "Ok", "ready-for-agent", "None — F0/M1 concluído")
        _ticket(self.raiz, "f2-z", 4, "Ok2", "ready-for-agent", "M1")
        fases, _ = gp.montar(self.raiz)
        for t in next(f for f in fases if f["fase"] == "F2")["tickets"]:
            self.assertFalse(t["bloqueio_ilegivel"], t["numero"])
        avisos = [a["titulo"] for a in gp.avisos_automaticos(fases, None)]
        self.assertNotIn("Blocked by ilegível", avisos)

    def test_teto_de_tickets_em_scratch(self) -> None:
        for n in range(1, gp.MAX_TICKETS + 2):
            _ticket(self.raiz, "f9-massa", n, "x", "concluído (2026-10-01)")
        with self.assertRaises(gp.ErroDados):
            gp.montar(self.raiz)

    def test_arquivo_de_ticket_com_nome_fora_do_padrao_e_recusado(self) -> None:
        for nome in ("M2.md", "m3-x.md", "ticket-4.md"):
            caminho = self.raiz / ".scratch/f2-z/issues" / nome
            caminho.write_text("# M2: x\n\n**Blocked by:** None\n\n**Status:** ready-for-agent\n", encoding="utf-8")
            with self.assertRaises(gp.ErroDados, msg=nome):
                gp.montar(self.raiz)
            caminho.unlink()
        self.assertTrue(gp.montar(self.raiz))

    def test_diretorio_de_fase_fora_do_padrao_e_recusado(self) -> None:
        (self.raiz / ".scratch/f1x/issues").mkdir(parents=True)
        with self.assertRaises(gp.ErroDados):
            gp.montar(self.raiz)

    def test_campo_status_ou_blocked_by_repetido_e_recusado(self) -> None:
        caminho = self.raiz / ".scratch/f2-z/issues/M9-repetido.md"
        caminho.write_text("# M9: x\n\n**Blocked by:** None\n\n**Status:** ready-for-agent\n\n**Blocked by:** M2\n", encoding="utf-8")
        with self.assertRaises(gp.ErroDados) as ctx:
            gp.montar(self.raiz)
        self.assertIn("Blocked by repetido", str(ctx.exception))
        caminho.write_text("# M9: x\n\n**Blocked by:** None\n\n**Status:** ready-for-agent\n\n**Status:** concluído\n", encoding="utf-8")
        with self.assertRaises(gp.ErroDados) as ctx:
            gp.montar(self.raiz)
        self.assertIn("Status repetido", str(ctx.exception))

    def test_none_com_referencia_pendente_no_comentario_ainda_trava(self) -> None:
        _ticket(self.raiz, "f2-z", 3, "Comentário engana", "ready-for-agent", "None — depende de M2")
        _ticket(self.raiz, "f2-z", 4, "Comentário honesto", "ready-for-agent", "None — F0/M1 concluído")
        estados = self._estados("F2")
        self.assertEqual(estados[3], "travado")  # M2 está em andamento
        self.assertEqual(estados[4], "pronto")  # F0/M1 está entregue

    def test_status_simples_entrega_e_ressalvas_nao(self) -> None:
        com_ressalva = (
            "Concluído parcialmente", "concluido, falta teste", "Implementado (sem testes)",
            "concluído — exceto M5", "implementado mas sem revisão", "Concluídos",
            "Concluído com ressalvas", "Concluído, porém falta X", "Concluído — pendente de merge",
            "Concluído em parte", "Concluído (revertido)", "Concluído; aguardando aprovação",
            "Concluído (WIP)", "Implementado, não testado", "Implementado (stub)", "**Concluído**",
            "concluído sem pendências", "concluído (ontem)", "concluído (2026-13)",
        )
        for texto in com_ressalva:
            self.assertEqual(gp.classificar(texto), "indefinido", texto)
        for texto in ("concluído", "implementado", "implementado e fechado", "concluído (2026-09-24) — testes passaram", "implementado e fechado (2026-10-02): QA em PASS",
                      "implementado (2026-10-02), com QA em PASS; o item segue aberto", "**Concluído (2026-09-29)**"):
            self.assertIn(gp.classificar(texto), ("concluido", "implementado"), texto)

    def test_caractere_invisivel_em_status_ou_blocked_by_e_recusado(self) -> None:
        caminho = self.raiz / ".scratch/f2-z/issues/M9-invisivel.md"
        casos = (
            "# M9: x\n\n**Blocked by:** None\n\n**Status:** concluído​ (2026-10-01)\n",
            "# M9: x\n\n**Status:** ready-for-agent\n\n**Blocked by:** None​\n",
        )
        for conteudo in casos:
            caminho.write_text(conteudo, encoding="utf-8")
            with self.assertRaises(gp.ErroDados, msg=conteudo):
                gp.montar(self.raiz)

    def test_faixa_com_pontos_til_ou_reticencias_e_recusada(self) -> None:
        for texto in ("M1..M12", "M1 ~ M12", "M1…M12", "M1 ... M12", "M1 to M12"):
            with self.assertRaises(gp.ErroDados, msg=texto):
                gp.bloqueadores(texto, "F2")

    def test_none_com_comentario_so_e_seguro_para_frases_conhecidas(self) -> None:
        livres = ("None — bloqueio do cliente", "None — needs client input", "None — needs-info",
                  "None — requer aprovação", "None — decisão do mantenedor", "None — precisa do ADR",
                  "None — hold", "None — parado", "None — sujeito à aprovação", "None — após decisão do cliente",
                  "None — só depois", "None; aguardando cliente", "None (ver spec)")
        for i, texto in enumerate(livres, start=10):
            _ticket(self.raiz, "f2-z", i, f"Livre {i}", "ready-for-agent", texto)
        for i, texto in enumerate(livres, start=10):
            self.assertEqual(self._estados("F2")[i], "travado", texto)
        for i, texto in enumerate(("None", "—", "-", "Nenhum", "None — pode começar já",
                                   "None (pode começar imediatamente — não depende de nada)",
                                   "None — sem dependências", "None — nenhuma dependência"), start=40):
            _ticket(self.raiz, "f2-z", i, f"Seguro {i}", "ready-for-agent", texto)
            self.assertEqual(self._estados("F2")[i], "pronto", texto)

    def test_ticket_entregue_com_checklist_aberto_vira_ponto_de_atencao(self) -> None:
        _ticket(self.raiz, "f2-z", 3, "Quase", "concluído (2026-10-01)", "None", "- [x] a\n- [ ] b\n")
        fases, _ = gp.montar(self.raiz)
        avisos = {a["titulo"]: a["texto"] for a in gp.avisos_automaticos(fases, None)}
        self.assertEqual(avisos["Ticket entregue com itens abertos no checklist"], "F2/M3")

    def test_referencia_fora_do_formato_documentado_e_recusada(self) -> None:
        for texto in ("M3 até M5", "M3-M5", "F1-M3", "F1.M3", "F1 / M3", "F2B/M3", "m3"):
            with self.assertRaises(gp.ErroDados, msg=texto):
                gp.bloqueadores(texto, "F9")
        self.assertEqual(gp.bloqueadores("F1/M3, M4 (e mais nada)", "F9"), [("F1", 3), ("F9", 4)])

    def test_none_que_declara_espera_em_texto_livre_e_ilegivel(self) -> None:
        for n, texto in ((3, "None — waiting client"), (4, "None — espera o cliente"), (5, "None — aguarda decisão")):
            _ticket(self.raiz, "f2-z", n, f"Espera {n}", "ready-for-agent", texto)
        _ticket(self.raiz, "f2-z", 6, "Livre", "ready-for-agent", "None (pode começar já — não depende de nada)")
        estados = self._estados("F2")
        self.assertEqual([estados[3], estados[4], estados[5], estados[6]], ["travado", "travado", "travado", "pronto"])
        with self.assertRaises(gp.ErroDados):  # "F3" solto, fora do formato F<N>/M<N>
            gp.bloqueadores("None — espera a F3", "F2")

    def test_subdiretorio_e_arquivo_de_outro_tipo_em_issues_sao_recusados(self) -> None:
        pasta = self.raiz / ".scratch/f2-z/issues"
        (pasta / "arquivo").mkdir()
        with self.assertRaises(gp.ErroDados):
            gp.montar(self.raiz)
        (pasta / "arquivo").rmdir()
        (pasta / "M9-x.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(gp.ErroDados):
            gp.montar(self.raiz)
        (pasta / "M9-x.txt").unlink()
        (pasta / ".gitkeep").write_text("", encoding="utf-8")
        self.assertTrue(gp.montar(self.raiz))

    def test_tabela_de_fases_do_documento_de_fases_e_lida_com_rigor(self) -> None:
        def com(linha_nova: str) -> str:
            return FASES_EXEMPLO.replace("| **F3** |", linha_nova + "\n| **F3** |")
        casos = {
            "fase repetida": com("| **F2** | Outra | x | Em andamento |"),
            "estado em branco": com("| **F2b** | Mapa | x |  |"),
            "fase em minúscula": com("| **f2b** | Mapa | x | Sem spec nem ticket |"),
            "sem negrito": com("| F2b | Mapa | x | Sem spec nem ticket |"),
        }
        for nome, texto in casos.items():
            (self.raiz / "docs/panorama-das-fases.md").write_text(texto, encoding="utf-8")
            with self.assertRaises(gp.ErroDados, msg=nome):
                gp.montar(self.raiz)
        (self.raiz / "docs/panorama-das-fases.md").write_text(FASES_EXEMPLO, encoding="utf-8")
        self.assertTrue(gp.montar(self.raiz))  # a segunda tabela, a de diretórios, não atrapalha

    def test_arquivo_com_bom_e_crlf_e_lido_e_com_codificacao_invalida_e_recusado(self) -> None:
        caminho = self.raiz / ".scratch/f2-z/issues/M7-win.md"
        caminho.write_bytes("﻿# M7: Windows\r\n\r\n**Blocked by:** None\r\n\r\n**Status:** concluído (2026-10-01)\r\n".encode("utf-8"))
        ticket = next(t for t in self._fases()["F2"]["tickets"] if t["numero"] == 7)
        self.assertEqual((ticket["titulo"], ticket["estado"], ticket["sem_status"]), ("Windows", "concluido", False))
        caminho.write_bytes(b"# M7: ruim \xff\xfe\n\n**Blocked by:** None\n\n**Status:** concluido\n")
        with self.assertRaises(gp.ErroDados):
            gp.montar(self.raiz)

    def test_exemplo_em_bloco_de_codigo_nao_e_campo_do_ticket(self) -> None:
        caminho = self.raiz / ".scratch/f2-z/issues/M7-exemplo.md"
        caminho.write_text(
            "# M7: Exemplo\n\n**Blocked by:** None\n\n**Status:** ready-for-agent\n\n"
            "```\n**Status:** concluído\n**Blocked by:** M99\n- [x] fantasma\n```\n",
            encoding="utf-8",
        )
        ticket = next(t for t in self._fases()["F2"]["tickets"] if t["numero"] == 7)
        self.assertEqual((ticket["estado"], ticket["bloqueadores"], ticket["itens_feitos"]), ("pronto", [], 0))

    def test_ticket_entregue_com_bloqueador_pendente_vira_ponto_de_atencao(self) -> None:
        _ticket(self.raiz, "f2-z", 3, "Pendente", "ready-for-agent")
        _ticket(self.raiz, "f2-z", 4, "Entregue antes da hora", "concluído (2026-10-01)", "M3")
        fases, _ = gp.montar(self.raiz)
        avisos = {a["titulo"]: a["texto"] for a in gp.avisos_automaticos(fases, None)}
        self.assertEqual(avisos["Ticket entregue ou em andamento com bloqueador pendente"], "F2/M4")

    def test_ticket_com_dado_ausente_vira_ponto_de_atencao(self) -> None:
        caminho = self.raiz / ".scratch/f2-z/issues/M7-sem-campos.md"
        caminho.write_text("# M7: Sem campos\n\ntexto solto\n", encoding="utf-8")
        _ticket(self.raiz, "f2-z", 8, "Status estranho", "talvez amanhã", "None")
        fases, _ = gp.montar(self.raiz)
        avisos = {a["titulo"]: a["texto"] for a in gp.avisos_automaticos(fases, None)}
        self.assertEqual(avisos["Ticket sem campo Status"], "F2/M7")
        self.assertEqual(avisos["Ticket sem campo Blocked by"], "F2/M7")
        self.assertEqual(avisos["Status fora do vocabulário"], "F2/M8")
        self.assertIn("sem estado", self._html())

    def test_descartado_sai_da_contagem_mas_aparece_nos_avisos(self) -> None:
        _ticket(self.raiz, "f0-x", 2, "Ideia abandonada", "wontfix")
        fases, _ = gp.montar(self.raiz)
        f0 = next(f for f in fases if f["fase"] == "F0")
        self.assertEqual((f0["total"], f0["calculado"]), (1, "concluida"))
        avisos = {a["titulo"]: a["texto"] for a in gp.avisos_automaticos(fases, None)}
        self.assertEqual(avisos["Tickets descartados, fora da contagem"], "F0/M2")

    def test_barra_de_progresso_soma_cem_por_cento_e_bate_com_as_contagens(self) -> None:
        fases, _ = gp.montar(self.raiz)
        t = gp.totais(fases)
        barra = gp._barra(t["contagem"], t["total"], 10)
        self.assertIn('aria-label="4 de 7 entregues"', barra)
        larguras = [float(v) for v in re.findall(r"width:([\d.]+)%", barra)]
        self.assertAlmostEqual(sum(larguras), 100.0, places=1)
        # 4 entregues, 1 em andamento, 1 pronto, 1 travado: a barra mostra 4 trechos
        self.assertEqual([round(v) for v in larguras], [57, 14, 14, 14])
        _ticket(self.raiz, "f2-z", 3, "Aguarda", "needs-info")
        fases, _ = gp.montar(self.raiz)
        t = gp.totais(fases)
        larguras = [float(v) for v in re.findall(r"width:([\d.]+)%", gp._barra(t["contagem"], t["total"]))]
        self.assertAlmostEqual(sum(larguras), 100.0, places=1)
        self.assertEqual(len(larguras), 4)

    def test_fase_so_com_tickets_descartados_conta_como_sem_ticket(self) -> None:
        (self.raiz / ".scratch/f0-x/issues/M1-slug.md").unlink()
        _ticket(self.raiz, "f0-x", 1, "Abandonado", "wontfix")
        fases = {f["fase"]: f for f in gp.montar(self.raiz)[0]}
        f0 = fases["F0"]
        self.assertEqual((f0["total"], f0["calculado"]), (0, "sem-ticket"))
        self.assertTrue(f0["diverge"])  # o docs/panorama-das-fases.md diz "Concluída"
        self.assertIn("F0, F3, F4 sem ticket", gp.renderizar_marca(list(fases.values())))
        fases_lista, _ = gp.montar(self.raiz)
        avisos = {a["titulo"] for a in gp.avisos_automaticos(fases_lista, None)}
        self.assertIn("Tickets descartados, fora da contagem", avisos)

    def test_cli_aceita_avisos_extras_e_escapa_na_saida(self) -> None:
        avisos = self.raiz / "avisos.json"
        avisos.write_text(json.dumps([{"titulo": "Premissa <b>x</b>", "texto": "aguarda `F1/M3` & mais"}]), encoding="utf-8")
        html_ = self._rodar("--formato", "html", "--avisos", str(avisos), "--data", "2026-10-05")
        self.assertEqual(html_.returncode, 0, html_.stderr)
        self.assertIn("Premissa &lt;b&gt;x&lt;/b&gt;", html_.stdout)
        self.assertIn("aguarda <code>F1/M3</code> &amp; mais", html_.stdout)
        md = self._rodar("--formato", "markdown", "--avisos", str(avisos), "--data", "2026-10-05")
        self.assertEqual(md.returncode, 0, md.stderr)
        self.assertIn(r"Premissa \<b\>x\</b\>", md.stdout)

    def test_barra_conta_todo_ticket_que_nao_esta_entregue(self) -> None:
        _ticket(self.raiz, "f2-z", 3, "Aguarda", "needs-info")
        saida = self._html()
        self.assertIn("var(--fill-warning,var(--text-warning))", saida)

    # --- markdown escapa dado do ticket
    def test_markdown_nao_deixa_dado_virar_link_imagem_ou_titulo(self) -> None:
        _ticket(self.raiz, "f2-z", 3, "![x](http://e.com/?q=1) [a](b) <i>", "ready-for-agent")
        fases, repo = gp.montar(self.raiz)
        md = gp.renderizar_markdown(fases, repo, [{"titulo": "T", "texto": "linha\n# Titulo falso"}], "2026-10-05")
        self.assertNotIn("![x](", md)
        self.assertNotIn("[a](", md)
        self.assertIn(r"\!\[x\]\(http://e.com/?q=1\)", md)
        self.assertIn(r"linha \# Titulo falso", md)
        self.assertEqual(gp._md("use `a_b` e c_d"), r"use `a_b` e c\_d")

    def test_titulo_enorme_de_ticket_e_cortado(self) -> None:
        _ticket(self.raiz, "f2-z", 3, "x" * 500, "ready-for-agent")
        ticket = next(t for t in self._fases()["F2"]["tickets"] if t["numero"] == 3)
        self.assertEqual(len(ticket["titulo"]), gp.MAX_TITULO_TICKET)

    # --- leitura de arquivos
    def test_arquivo_grande_demais_e_recusado(self) -> None:
        grande = self.raiz / ".scratch/f2-z/issues/M9-grande.md"
        grande.write_text("# M9: grande\n" + "x" * (gp.MAX_BYTES + 1), encoding="utf-8")
        with self.assertRaises(gp.ErroDados):
            gp.montar(self.raiz)

    def test_link_simbolico_para_fora_do_repositorio_e_recusado(self) -> None:
        fora = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(fora, ignore_errors=True))
        (fora / "segredo.md").write_text("# M1: SEGREDO\n\n**Status:** ready-for-agent\n", encoding="utf-8")
        elo = self.raiz / ".scratch/f2-z/issues/M9-elo.md"
        try:
            elo.symlink_to(fora / "segredo.md")
        except (OSError, NotImplementedError):
            self.skipTest("o sistema não permite criar link simbólico")
        with self.assertRaises(gp.ErroDados):
            gp.montar(self.raiz)

    # --- entradas inválidas
    def test_sem_documento_de_fases_recusa(self) -> None:
        (self.raiz / "docs/panorama-das-fases.md").unlink()
        with self.assertRaises(gp.ErroDados):
            gp.montar(self.raiz)

    def test_documento_de_fases_sem_tabela_de_fases_recusa(self) -> None:
        (self.raiz / "docs/panorama-das-fases.md").write_text("# nada\n", encoding="utf-8")
        with self.assertRaises(gp.ErroDados):
            gp.montar(self.raiz)

    # --- linha de comando
    def _rodar(self, *args: str, raiz: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--raiz", str(raiz or self.raiz), *args],
            capture_output=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "cp1252"},
            check=False,
        )

    def test_cli_emite_utf8_mesmo_com_codificacao_estreita(self) -> None:
        r = self._rodar("--formato", "markdown", "--data", "2026-10-05")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Concluída", r.stdout)
        self.assertIn("Em andamento", r.stdout)

    def test_cli_recusa_avisos_invalidos_com_a_lista_de_problemas(self) -> None:
        avisos = self.raiz / "avisos.json"
        avisos.write_text(json.dumps([{"titulo": "a"}]), encoding="utf-8")
        r = self._rodar("--formato", "html", "--avisos", str(avisos))
        self.assertEqual(r.returncode, 1)
        self.assertIn("falta `texto`", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_cli_recusa_json_quebrado_e_data_invalida(self) -> None:
        quebrado = self.raiz / "x.json"
        quebrado.write_text("{", encoding="utf-8")
        self.assertEqual(self._rodar("--formato", "html", "--avisos", str(quebrado)).returncode, 1)
        self.assertEqual(self._rodar("--formato", "html", "--data", "ontem").returncode, 1)

    def test_cli_fecha_fases_e_totais(self) -> None:
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--raiz", str(self.raiz), "--formato", "marca"],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"\*\*Panorama das fases\*\* · \d+ de \d+ tickets entregues \(\d+%\)")
        self.assertIn("F0", r.stdout)
        self.assertEqual(len(r.stdout.strip().splitlines()), 1)

    # --- nome do projeto, dinâmico
    def test_nome_do_projeto_cai_para_o_nome_da_pasta(self) -> None:
        self.assertEqual(gp.nome_do_projeto(self.raiz, None), self.raiz.name)
        self.assertEqual(gp.nome_do_projeto(self.raiz, "   "), self.raiz.name)

    def test_nome_do_projeto_informado_vence(self) -> None:
        self.assertEqual(gp.nome_do_projeto(self.raiz, "  Meu App  "), "Meu App")

    def test_nome_do_projeto_vem_do_remoto_origin(self) -> None:
        casos = {
            "git@github.com:acme/app-x.git": "app-x",
            "https://github.com/acme/Repo-Y.git": "Repo-Y",
            "https://github.com/acme/sem-sufixo/": "sem-sufixo",
        }
        for url, esperado in casos.items():
            repo = Path(tempfile.mkdtemp())
            self.addCleanup(lambda p=repo: __import__("shutil").rmtree(p, ignore_errors=True))
            try:
                subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
                subprocess.run(["git", "remote", "add", "origin", url], cwd=repo, check=True, capture_output=True)
            except (OSError, subprocess.CalledProcessError):
                self.skipTest("git indisponível")
            self.assertEqual(gp.nome_do_projeto(repo, None), esperado, url)
            self.assertEqual(gp.nome_do_projeto(repo, "Outro"), "Outro")

    def test_nome_do_projeto_so_leva_caractere_imprimivel_e_tem_teto(self) -> None:
        sujo = "a\x1b[31mb​c\nd" + "x" * 200
        nome = gp.nome_do_projeto(self.raiz, sujo)
        self.assertNotIn("\x1b", nome)
        self.assertNotIn("​", nome)
        self.assertNotIn("\n", nome)
        self.assertEqual(len(nome), gp.MAX_NOME_PROJETO)

    def test_titulo_do_painel_e_do_markdown_usa_o_nome_escapado(self) -> None:
        fases, repo = gp.montar(self.raiz)
        html_ = gp.renderizar_html(fases, repo, [], "2026-10-05", "Meu <App>")
        self.assertIn("Meu &lt;App&gt; · F0 a F4", html_)
        self.assertNotIn("Meu <App>", html_)
        md = gp.renderizar_markdown(fases, repo, [], "2026-10-05", "Meu *App*")
        self.assertIn(r"## Panorama das fases · Meu \*App\*", md)

    def test_sem_nome_o_titulo_nao_cita_projeto_nenhum(self) -> None:
        fases, repo = gp.montar(self.raiz)
        self.assertIn("Fases F0 a F4", gp.renderizar_html(fases, repo, [], "2026-10-05"))
        primeira = gp.renderizar_markdown(fases, repo, [], "2026-10-05").splitlines()[0]
        self.assertEqual(primeira, "## Panorama das fases")

    def test_cli_usa_projeto_informado_ou_o_nome_da_pasta(self) -> None:
        com_nome = self._rodar("--formato", "html", "--projeto", "Acme Web", "--data", "2026-10-05")
        self.assertEqual(com_nome.returncode, 0, com_nome.stderr)
        self.assertIn("Acme Web · F0 a F4", com_nome.stdout)
        sem_nome = self._rodar("--formato", "markdown", "--data", "2026-10-05")
        # o markdown escapa `_` e afins no nome da pasta: compara com o nome já escapado
        self.assertIn(f"## Panorama das fases · {gp._md(self.raiz.name)}", sem_nome.stdout)

    def test_exemplo_do_painel_e_renderizavel_sem_layout_do_projeto(self) -> None:
        texto = (SCRIPT.parents[1] / "references/painel.md").read_text(encoding="utf-8")
        dados = json.loads(re.search(r"```json\n(.*?)\n```", texto, re.DOTALL).group(1))
        fases, avisos, projeto = gp.normalizar_dados(dados)
        self.assertIn("T01", gp.renderizar_html(fases, None, avisos, "2026-10-05", projeto))
        self.assertIn("T03", gp.renderizar_markdown(fases, None, avisos, "2026-10-05", projeto))


class PanoramaDinamicoTests(unittest.TestCase):
    def setUp(self) -> None:
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.raiz = Path(pasta.name)

    def dados_atia(self) -> dict:
        # Cenário baseado no relato: implementado não equivale a aceite visual.
        return {
            "projeto": "ATIA",
            "fases": [{"id": "Documentos", "titulo": "Documentação", "estado": "Não iniciada"}],
            "tickets": [
                {"id": "T01", "fase": "Documentos", "titulo": "Primeiro documento",
                 "estado": "implementado", "dependencias": [],
                 "evidencia": "Implementação local registrada",
                 "pendencias": ["Renderizar e inspecionar DOCX"],
                 "fontes": ["docs/tickets/rascunhos/T01.md", "Conversa com o mantenedor"]},
                {"id": "T02", "fase": "Documentos", "titulo": "Segundo documento",
                 "estado": "concluido", "dependencias": [],
                 "evidencia": "Commit e313780; checklist completo",
                 "pendencias": ["Inspeção visual do DOCX"],
                 "fontes": ["Registro T02", "Commit e313780"]},
                *[{"id": f"T{n:02}", "fase": "Documentos", "titulo": f"Entrega {n}",
                   "estado": "planejado", "dependencias": ["T01"] if n in (3, 12) else [],
                   "fontes": ["docs/plano-tickets-atia.md"]} for n in range(3, 19)],
            ],
            "avisos": [{"titulo": "Próximo passo", "texto": "Concluir a validação visual; fonte: registros T01 e T02."}],
        }

    def rodar(self, dados: object, formato: str = "markdown") -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--dados", "-", "--formato", formato, "--data", "2026-10-05"],
            input=json.dumps(dados, ensure_ascii=False).encode("utf-8"),
            cwd=self.raiz, capture_output=True, check=False,
            env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        )

    def test_atia_sem_layout_exigido_preserva_ids_validacao_e_dependencias(self) -> None:
        fases, avisos, projeto = gp.normalizar_dados(self.dados_atia())
        tickets = {t["numero"]: t for f in fases for t in f["tickets"]}
        self.assertEqual(projeto, "ATIA")
        self.assertEqual(gp.totais(fases)["total"], 18)
        self.assertEqual(gp.totais(fases)["entregues"], 0)
        self.assertEqual(fases[0]["calculado"], "andamento")
        self.assertTrue(fases[0]["diverge"])
        for tid in ("T01", "T02"):
            self.assertEqual(tickets[tid]["estado"], "validacao")
        for tid in ("T03", "T12"):
            self.assertEqual(tickets[tid]["estado"], "travado")
            self.assertEqual(gp._espera(tickets[tid]), "T01")
        self.assertEqual(tickets["T04"]["estado"], "planejado")
        md = gp.renderizar_markdown(fases, None, avisos, "2026-10-05", projeto)
        self.assertIn("Commit e313780", md)
        self.assertIn("Renderizar e inspecionar DOCX", md)
        self.assertIn("docs/plano-tickets-atia.md", md)
        self.assertIn("Próximo passo", md)

    def test_cli_todos_formatos_sem_arquivos_do_projeto_e_sem_escritas(self) -> None:
        for formato in ("html", "markdown", "marca"):
            with self.subTest(formato=formato):
                resultado = self.rodar(self.dados_atia(), formato)
                self.assertEqual(resultado.returncode, 0, resultado.stderr.decode("utf-8"))
                saida = resultado.stdout.decode("utf-8")
                self.assertIn("0 de 18", saida)
                if formato != "marca":
                    self.assertIn("T01", saida)
                    self.assertNotIn("MT01", saida)
                    self.assertIn("Inspeção visual do DOCX", saida)
                self.assertEqual(list(self.raiz.iterdir()), [])

    def test_json_em_arquivo_arbitrario_sem_consultar_git_ou_layout(self) -> None:
        arquivo = self.raiz / "entrada.json"
        arquivo.write_text(json.dumps(self.dados_atia()), encoding="utf-8")
        with patch.object(gp, "_git", side_effect=AssertionError("não deve consultar Git")), patch.object(gp, "montar", side_effect=AssertionError("não deve abrir o projeto")), patch("sys.stdout"):
            self.assertEqual(gp.main(["--dados", str(arquivo), "--raiz", str(self.raiz / "inexistente"), "--formato", "html"]), 0)

    def test_conversa_sem_plano_formal_e_dependencia_nao_confirmada(self) -> None:
        dados = {"tickets": [
            {"id": "APP-7", "titulo": "Entrega discutida", "estado": "pronto", "fontes": ["Mensagem do mantenedor"]},
            {"id": "APP-8", "titulo": "Frente independente", "estado": "pronto", "dependencias": [], "fontes": ["Decisão na conversa"]},
        ]}
        fases, _, _ = gp.normalizar_dados(dados)
        self.assertEqual(fases[0]["fase"], "Entregas")
        self.assertEqual([t["estado"] for t in fases[0]["tickets"]], ["indefinido", "pronto"])
        self.assertIn("Dependências não confirmadas", str(gp.avisos_automaticos(fases, None)))

    def test_dependencia_entre_grupos_e_bloqueador_ausente(self) -> None:
        dados = {"tickets": [
            {"id": "base", "fase": "B", "titulo": "Base", "estado": "concluido", "dependencias": [], "fontes": ["Aceite"]},
            {"id": "app", "fase": "A", "titulo": "App", "estado": "pronto", "dependencias": ["base"], "fontes": ["Plano"]},
            {"id": "infra", "fase": "A", "titulo": "Infra", "estado": "pronto", "dependencias": ["externo"], "fontes": ["Plano"]},
        ]}
        fases, _, _ = gp.normalizar_dados(dados)
        self.assertEqual([f["fase"] for f in fases], ["B", "A"])
        self.assertEqual([t["estado"] for t in fases[1]["tickets"]], ["pronto", "travado"])
        self.assertIn("externo (sem ticket)", gp._espera(fases[1]["tickets"][1]))

    def test_fontes_e_identificadores_escapados_em_html_e_markdown(self) -> None:
        dados = {"tickets": [{"id": "T|01", "titulo": "<script>alert(1)</script>",
            "fase": "F|ase", "estado": "concluido", "dependencias": [],
            "fontes": ["<img src=x onerror=alert(1)>"], "evidencia": "[falso](link)"}]}
        fases, _, _ = gp.normalizar_dados(dados)
        html_ = gp.renderizar_html(fases, None, [], "2026-10-05")
        md = gp.renderizar_markdown(fases, None, [], "2026-10-05")
        self.assertNotIn("<script>", html_)
        self.assertNotIn("<img src", html_)
        self.assertIn("&lt;img", html_)
        self.assertIn(r"F\|ase", md)
        self.assertIn(r"T\|01", md)
        self.assertNotIn("[falso](link)", md)

    def test_entradas_ambiguas_ou_sem_evidencia_recusadas(self) -> None:
        base = {"id": "T01", "titulo": "Documento", "estado": "planejado", "fontes": ["Plano"]}
        casos = [
            {"tickets": [base, base]},
            {"tickets": [{**base, "fontes": []}]},
            {"tickets": [{**base, "estado": "qualquer"}]},
            {"tickets": [{**base, "dependencias": "T02"}]},
            {"tickets": [{**base, "fontes": "Plano"}]},
            {"fases": [{"id": "Fase", "titulo": "Fase"}], "tickets": [{**base, "fase": "Outra"}]},
            {},
        ]
        for dados in casos:
            with self.subTest(dados=dados), self.assertRaises(gp.ErroDados):
                gp.normalizar_dados(dados)

    def test_cli_recusa_json_quebrado_e_entrada_acima_do_limite(self) -> None:
        for entrada in (b"{", b" " * (gp.MAX_BYTES + 1)):
            resultado = subprocess.run([sys.executable, str(SCRIPT), "--dados", "-", "--formato", "html"], input=entrada, cwd=self.raiz, capture_output=True, check=False)
            self.assertEqual(resultado.returncode, 1)
            self.assertEqual(resultado.stdout, b"")
            self.assertNotIn(b"Traceback", resultado.stderr)


if __name__ == "__main__":
    unittest.main()
