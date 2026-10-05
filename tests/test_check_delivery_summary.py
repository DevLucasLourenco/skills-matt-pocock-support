"""Testes do hook `Stop` que exige o fechamento de entrega."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "hooks/check_delivery_summary.py").is_file()
            or (p / "tools/governance/check_delivery_summary.py").is_file())
HOOK = ROOT / "hooks/check_delivery_summary.py"
if not HOOK.is_file():
    HOOK = ROOT / "tools/governance/check_delivery_summary.py"
_spec = importlib.util.spec_from_file_location("check_delivery_summary", HOOK)
cds = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cds)

SCRIPT = Path(cds.__file__).resolve()

FECHAMENTO = "**Fechamento da entrega**\n\n**Resultado:** `Concluído`\n\n**Decisões humanas pendentes:** Nenhuma."
SEM_FECHAMENTO = "Pronto, editei os arquivos."


def _prompt(texto: str = "faça a mudança") -> dict:
    return {"type": "user", "message": {"role": "user", "content": texto}}


def _edicao(ferramenta: str = "Edit", caminho: str | None = None, **extra: object) -> dict:
    parametros = {} if caminho is None else {"file_path": caminho}
    bloco = {"type": "tool_use", "id": "t1", "name": ferramenta, "input": parametros}
    return {"type": "assistant", "message": {"role": "assistant", "content": [bloco]}, **extra}


def _leitura() -> dict:
    bloco = {"type": "tool_use", "id": "t2", "name": "Read", "input": {}}
    return {"type": "assistant", "message": {"role": "assistant", "content": [bloco]}}


def _resultado_de_ferramenta() -> dict:
    bloco = {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}
    return {"type": "user", "message": {"role": "user", "content": [bloco]}}


def _linhas(*entradas: dict) -> list[str]:
    return [json.dumps(entrada, ensure_ascii=False) + "\n" for entrada in entradas]


class TemSecaoTests(unittest.TestCase):
    def test_reconhece_rotulo_em_negrito(self) -> None:
        self.assertTrue(cds.tem_secao(FECHAMENTO))

    def test_ignora_acento_caixa_e_quebra_de_linha(self) -> None:
        self.assertTrue(cds.tem_secao("FECHAMENTO DA\nentrega\nDECISOES HUMANAS\npendentes: nenhuma"))

    def test_resposta_sem_a_secao(self) -> None:
        self.assertFalse(cds.tem_secao(SEM_FECHAMENTO))

    def test_secao_escrita_a_mao_sem_o_cabecalho_do_gerador_nao_basta(self) -> None:
        self.assertFalse(cds.tem_secao("**Decisões humanas pendentes:** Nenhuma."))

    def test_cabecalho_sem_a_secao_de_pendencias_nao_basta(self) -> None:
        self.assertFalse(cds.tem_secao("**Fechamento da entrega**\n\nTudo certo."))

    def test_mencao_em_qualquer_ponto_conta_por_desenho(self) -> None:
        # limite aceito: o hook checa presença, não estrutura; conteúdo é julgado na revisão
        self.assertTrue(cds.tem_secao("falta o fechamento da entrega e as decisões humanas pendentes"))


class EditouNoTurnoTests(unittest.TestCase):
    def test_edicao_depois_do_ultimo_prompt(self) -> None:
        self.assertTrue(cds.editou_no_turno(_linhas(_prompt(), _edicao(), _resultado_de_ferramenta())))

    def test_cada_ferramenta_de_edicao_conta(self) -> None:
        for ferramenta in ("Edit", "MultiEdit", "Write", "NotebookEdit"):
            with self.subTest(ferramenta=ferramenta):
                self.assertTrue(cds.editou_no_turno(_linhas(_prompt(), _edicao(ferramenta))))

    def test_edicao_de_turno_anterior_nao_conta(self) -> None:
        self.assertFalse(cds.editou_no_turno(_linhas(_prompt(), _edicao(), _prompt("e agora?"), _leitura())))

    def test_resultado_de_ferramenta_nao_encerra_o_turno(self) -> None:
        linhas = _linhas(_prompt(), _edicao(), _resultado_de_ferramenta(), _leitura(), _resultado_de_ferramenta())
        self.assertTrue(cds.editou_no_turno(linhas))

    def test_mensagem_injetada_pelo_sistema_nao_encerra_o_turno(self) -> None:
        injetada = {**_prompt("<system-reminder>"), "isMeta": True}
        self.assertTrue(cds.editou_no_turno(_linhas(_prompt(), _edicao(), injetada)))

    def test_prompt_em_lista_de_blocos_de_texto_encerra_o_turno(self) -> None:
        prompt = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "e agora?"}]}}
        self.assertFalse(cds.editou_no_turno(_linhas(_prompt(), _edicao(), prompt, _leitura())))

    def test_delegacao_a_subagente_conta_como_edicao(self) -> None:
        # o subagente grava o próprio histórico em arquivo separado, que o hook não lê
        # nomes fixos, não a constante: com a constante vazia o laço passaria sem testar nada
        for ferramenta in ("Agent", "Task"):
            with self.subTest(ferramenta=ferramenta):
                self.assertTrue(cds.editou_no_turno(_linhas(_prompt(), _edicao(ferramenta), _resultado_de_ferramenta())))

    def test_edicao_marcada_como_sidechain_conta(self) -> None:
        self.assertTrue(cds.editou_no_turno(_linhas(_prompt(), _edicao(isSidechain=True))))

    def test_edicao_conta_qualquer_que_seja_o_caminho(self) -> None:
        # por desenho: separar por caminho abriu evasões (relativo, junção, unidade mapeada) e foi removido
        for caminho in ("docs/nota.md", str(Path(tempfile.gettempdir()) / "memoria" / "nota.md"), "D:\\fora\\x.md"):
            with self.subTest(caminho=caminho):
                self.assertTrue(cds.editou_no_turno(_linhas(_prompt(), _edicao("Write", caminho))))

    def test_linhas_invalidas_sao_ignoradas(self) -> None:
        linhas = _linhas(_prompt(), _edicao()) + ["{truncad", "[]\n", "\n"]
        self.assertTrue(cds.editou_no_turno(linhas))

    def test_transcript_vazio(self) -> None:
        self.assertFalse(cds.editou_no_turno([]))


class DecidirTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.transcript = Path(self.tempdir.name) / "transcript.jsonl"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _payload(self, mensagem: object, *entradas: dict, **extra: object) -> dict:
        self.transcript.write_text("".join(_linhas(*entradas)), encoding="utf-8")
        return {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "transcript_path": str(self.transcript),
            "last_assistant_message": mensagem,
            **extra,
        }

    def test_bloqueia_entrega_sem_fechamento(self) -> None:
        self.assertEqual(cds.decidir(self._payload(SEM_FECHAMENTO, _prompt(), _edicao())), cds.MOTIVO)

    def test_libera_entrega_com_fechamento(self) -> None:
        self.assertIsNone(cds.decidir(self._payload(FECHAMENTO, _prompt(), _edicao())))

    def test_libera_turno_sem_edicao(self) -> None:
        self.assertIsNone(cds.decidir(self._payload(SEM_FECHAMENTO, _prompt(), _leitura())))

    def test_libera_segunda_tentativa_para_nao_criar_laco(self) -> None:
        payload = self._payload(SEM_FECHAMENTO, _prompt(), _edicao(), stop_hook_active=True)
        self.assertIsNone(cds.decidir(payload))

    def test_falha_aberta_sem_ultima_mensagem(self) -> None:
        self.assertIsNone(cds.decidir(self._payload(None, _prompt(), _edicao())))

    def test_falha_aberta_sem_transcript(self) -> None:
        payload = self._payload(SEM_FECHAMENTO, _prompt(), _edicao())
        payload["transcript_path"] = ""
        self.assertIsNone(cds.decidir(payload))


def _painel(codigo: str = "<p>Fechamento da entrega</p>") -> dict:
    bloco = {
        "type": "tool_use",
        "id": "w1",
        "name": "mcp__visualize__show_widget",
        "input": {"title": "fechamento", "widget_code": codigo},
    }
    return {"type": "assistant", "message": {"role": "assistant", "content": [bloco]}}


MARCA_DO_GERADOR = FECHAMENTO + " — detalhes no painel acima"


class PainelObrigatorioTests(unittest.TestCase):
    setUp = DecidirTests.setUp
    tearDown = DecidirTests.tearDown
    _payload = DecidirTests._payload

    def test_marca_sem_chamada_de_painel_bloqueia(self) -> None:
        payload = self._payload(MARCA_DO_GERADOR, _prompt(), _edicao())
        self.assertEqual(cds.decidir(payload), cds.MOTIVO_PAINEL)

    def test_marca_com_painel_no_turno_libera(self) -> None:
        payload = self._payload(MARCA_DO_GERADOR, _prompt(), _edicao(), _painel())
        self.assertIsNone(cds.decidir(payload))

    def test_markdown_colado_em_sessao_que_ja_usou_painel_bloqueia(self) -> None:
        payload = self._payload(FECHAMENTO, _prompt("a"), _painel(), _prompt("b"), _edicao())
        self.assertEqual(cds.decidir(payload), cds.MOTIVO_PAINEL)

    def test_painel_de_turno_anterior_nao_vale(self) -> None:
        payload = self._payload(MARCA_DO_GERADOR, _prompt("a"), _painel(), _prompt("b"), _edicao())
        self.assertEqual(cds.decidir(payload), cds.MOTIVO_PAINEL)

    def test_painel_sem_o_cabecalho_do_fechamento_nao_vale(self) -> None:
        payload = self._payload(MARCA_DO_GERADOR, _prompt(), _edicao(), _painel("<p>outra coisa</p>"))
        self.assertEqual(cds.decidir(payload), cds.MOTIVO_PAINEL)

    def test_painel_seguido_de_resultado_de_ferramenta_libera(self) -> None:
        payload = self._payload(
            MARCA_DO_GERADOR, _prompt(), _edicao(), _painel(), _resultado_de_ferramenta()
        )
        self.assertIsNone(cds.decidir(payload))

    def test_ferramenta_com_sufixo_diferente_nao_conta_como_painel(self) -> None:
        legado = _painel()
        legado["message"]["content"][0]["name"] = "mcp__x__show_widget_legado"
        payload = self._payload(MARCA_DO_GERADOR, _prompt(), _edicao(), legado)
        self.assertEqual(cds.decidir(payload), cds.MOTIVO_PAINEL)

    def test_sem_fechamento_a_ausencia_do_fechamento_vem_antes_da_do_painel(self) -> None:
        payload = self._payload(SEM_FECHAMENTO, _prompt("a"), _painel(), _prompt("b"), _edicao())
        self.assertEqual(cds.decidir(payload), cds.MOTIVO)

    def test_sessao_sem_painel_e_sem_marca_segue_livre_com_markdown(self) -> None:
        self.assertIsNone(cds.decidir(self._payload(FECHAMENTO, _prompt(), _edicao())))

    def test_turno_sem_edicao_nao_exige_painel(self) -> None:
        self.assertIsNone(cds.decidir(self._payload(MARCA_DO_GERADOR, _prompt(), _leitura())))


class MainTests(unittest.TestCase):
    """Executa o script como o Claude Code executa: payload em stdin, código de saída."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.transcript = Path(self.tempdir.name) / "transcript.jsonl"
        self.transcript.write_text("".join(_linhas(_prompt("ajuste a acentuação"), _edicao())), encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _executar(self, entrada: bytes) -> subprocess.CompletedProcess[bytes]:
        # stdin em cp1252 em qualquer sistema: uma leitura que dependa da codificação
        # padrão corromperia "Decisões" também no CI Linux, não só no Windows
        ambiente = {**os.environ, "PYTHONIOENCODING": "cp1252"}
        return subprocess.run(
            [sys.executable, str(SCRIPT)], input=entrada, capture_output=True, check=False, env=ambiente
        )

    def _payload(self, mensagem: str) -> bytes:
        payload = {"stop_hook_active": False, "transcript_path": str(self.transcript), "last_assistant_message": mensagem}
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def test_bloqueia_com_codigo_2_e_motivo_em_utf8(self) -> None:
        resultado = self._executar(self._payload(SEM_FECHAMENTO))
        self.assertEqual(resultado.returncode, 2)
        self.assertIn("Decisões humanas pendentes", resultado.stderr.decode("utf-8"))

    def test_libera_fechamento_acentuado_mesmo_com_stdin_em_cp1252(self) -> None:
        resultado = self._executar(self._payload(FECHAMENTO))
        self.assertEqual(resultado.returncode, 0, resultado.stderr.decode("utf-8", "replace"))

    def test_falha_aberta_com_payload_invalido(self) -> None:
        self.assertEqual(self._executar(b"{nao e json").returncode, 0)

    def test_falha_aberta_com_transcript_inexistente(self) -> None:
        self.transcript.unlink()
        self.assertEqual(self._executar(self._payload(SEM_FECHAMENTO)).returncode, 0)


if __name__ == "__main__":
    unittest.main()
