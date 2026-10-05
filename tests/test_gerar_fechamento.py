"""Testes do gerador do fechamento de entrega da Skill delivery-summary."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "hooks/check_delivery_summary.py").is_file()
            or (p / "tools/governance/check_delivery_summary.py").is_file())
HOOK = ROOT / "hooks/check_delivery_summary.py"
if not HOOK.is_file():
    HOOK = ROOT / "tools/governance/check_delivery_summary.py"
_hook_spec = importlib.util.spec_from_file_location("check_delivery_summary", HOOK)
hook = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(hook)
SCRIPT = ROOT / "skills/delivery-summary/scripts/gerar_fechamento.py"
if not SCRIPT.is_file():
    SCRIPT = ROOT / ".claude/skills/delivery-summary/scripts/gerar_fechamento.py"
_spec = importlib.util.spec_from_file_location("gerar_fechamento", SCRIPT)
gf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gf)

BASE = {
    "titulo": "Entrega de exemplo em `abc1234`",
    "trabalho": "commitado",
    "commit": "abc1234",
    "resultado": "concluido",
    "pendencias": [
        {
            "id": "adr18",
            "tipo": "decisao",
            "urgencia": "proximo",
            "pergunta": "Confirmar o ADR-0018?",
            "contexto": "O ADR ainda está Proposto.",
            "enquanto": "M3 a M12 seguem pela proposta.",
            "premissa": "ADR redigido como Proposto.",
            "recomendacao": {"opcao": "confirmar", "base": "fecha vazamento entre tenants.", "custo": "reajusta oito tickets."},
            "livre": "alteração",
        },
        {
            "id": "rls",
            "tipo": "aceite-de-risco",
            "urgencia": "agora",
            "pergunta": "Aceitar a RLS como segunda barreira?",
            "contexto": "A troca de tenant não é barrada pelo banco.",
            "enquanto": "A integração aguarda a decisão.",
            "recomendacao": {"opcao": "aceitar", "base": "ADR-0009 R2.", "custo": "role nova sem consumidor."},
            "alternativas": ["reforçar agora"],
        },
    ],
    "comportamentos": ["Primeira mudança", "Segunda mudança"],
    "arquivos": ["docs/adr/0018.md"],
    "verificacoes": ["QA na 2ª rodada"],
    "riscos": ["Sem teste executado"],
    "proximo_passo": "M10",
}


def _dados(**mudancas: object) -> dict:
    dados = copy.deepcopy(BASE)
    dados.update(mudancas)
    return dados


def _problemas(dados: object) -> list[str]:
    with unittest.TestCase().assertRaises(gf.DadosInvalidos) as contexto:
        gf.validar(dados)
    return contexto.exception.problemas


class ResultadoTests(unittest.TestCase):
    def test_resultado_da_tarefa_e_preservado(self) -> None:
        for resultado, esperado in gf.RESULTADOS.items():
            with self.subTest(resultado=resultado):
                f = gf.validar(_dados(resultado=resultado, motivo="Estado da tarefa"))
                self.assertEqual(f["estado"], esperado)

    def test_entrega_parcial_explica_o_que_falta(self) -> None:
        f = gf.validar(_dados(resultado="parcial", motivo="Falta validar a integração"))
        for renderizar in (gf.renderizar_texto, gf.renderizar_markdown, gf.renderizar_html):
            self.assertIn("Falta validar a integração", renderizar(f))


class ValidacaoTests(unittest.TestCase):
    def test_dados_de_exemplo_sao_validos(self) -> None:
        self.assertEqual(gf.validar(_dados())["estado"], "Concluído")

    def test_recusa_dados_incompletos(self) -> None:
        casos = [
            (_dados(resultado="desconhecido"), "resultado deve ser"),
            (_dados(resultado="bloqueado"), "motivo é obrigatório"),
            (_dados(resultado="parcial", motivo="Falta teste", proximo_passo=""), "proximo_passo é obrigatório"),
            (_dados(trabalho="talvez"), "trabalho deve ser"),
            (_dados(trabalho="local"), "trabalho local não tem commit"),
            (_dados(commit=None), "commit precisa do hash"),
            (_dados(comportamentos=[]), "comportamentos precisa"),
            (_dados(extra=True), "chave desconhecida"),
        ]
        campos = {
            "contexto": "contexto é obrigatório",
            "enquanto": "enquanto é obrigatório",
            "premissa": "decisão precisa da premissa",
            "recomendacao": "recomendacao precisa",
        }
        for campo, mensagem in campos.items():
            dados = _dados()
            del dados["pendencias"][0][campo]
            casos.append((dados, mensagem))
        repetido = _dados()
        repetido["pendencias"][1]["id"] = "adr18"
        casos.append((repetido, "identificador repetido"))
        sem_alternativa = _dados()
        del sem_alternativa["pendencias"][1]["alternativas"]
        casos.append((sem_alternativa, "precisa de alternativa"))
        for dados, mensagem in casos:
            with self.subTest(mensagem=mensagem):
                self.assertTrue(any(mensagem in p for p in _problemas(dados)))

    def test_bloqueio_exige_resultado_e_urgencia_compativeis(self) -> None:
        dados = _dados(resultado="bloqueado", motivo="Falta informação")
        dados["pendencias"][0].update(tipo="blocked", urgencia="agora")
        self.assertEqual(gf.validar(dados)["estado"], "Bloqueado")
        dados["resultado"] = "concluido"
        self.assertTrue(any("bloqueio exige resultado bloqueado" in p for p in _problemas(dados)))
        dados["resultado"] = "bloqueado"
        dados["pendencias"][0]["urgencia"] = "proximo"
        self.assertTrue(any("bloqueio tem urgência agora" in p for p in _problemas(dados)))

    def test_opcao_de_resposta_sem_crase(self) -> None:
        for campo, valor in (("alternativas", ["reforçar `agora`"]), ("livre", "`texto`")):
            with self.subTest(campo=campo):
                dados = _dados()
                dados["pendencias"][1][campo] = valor
                self.assertTrue(any("sem crase" in p for p in _problemas(dados)))
        dados = _dados()
        dados["pendencias"][1]["recomendacao"]["opcao"] = "`aceitar`"
        self.assertTrue(any("sem crase" in p for p in _problemas(dados)))

    def test_hash_de_commit_malformado_e_recusado(self) -> None:
        for invalido in ("ZZZ1234", "abc", "ABC1234"):
            with self.subTest(invalido=invalido):
                self.assertTrue(any("commit precisa do hash" in p for p in _problemas(_dados(commit=invalido))))

    def test_limites_validos_do_identificador(self) -> None:
        for valido in ("ab", "a" + "b" * 19):
            with self.subTest(valido=valido):
                dados = _dados()
                dados["pendencias"][0]["id"] = valido
                self.assertEqual(gf.validar(dados)["estado"], "Concluído")

    def test_identificador_precisa_ser_palavra_minuscula(self) -> None:
        for invalido in ("1", "A1", "adr 18", "x", "a" * 21):
            with self.subTest(invalido=invalido):
                dados = _dados()
                dados["pendencias"][0]["id"] = invalido
                self.assertTrue(any("id deve ser" in p for p in _problemas(dados)))

    def test_exemplo_da_skill_e_aceito_pelo_gerador(self) -> None:
        # a documentação da Skill e o gerador não podem divergir
        skill = (SCRIPT.parents[1] / "SKILL.md").read_text(encoding="utf-8")
        exemplo = re.search(r"```json\n(.*?)\n```", skill, re.S)
        self.assertIsNotNone(exemplo)
        self.assertEqual(gf.validar(json.loads(exemplo.group(1)))["estado"], "Concluído")

    def test_entrega_concluida_dispensa_proximo_passo(self) -> None:
        self.assertEqual(gf.validar(_dados(proximo_passo=""))["proximo_passo"], "")


class SaidasTests(unittest.TestCase):
    def test_toda_saida_passa_na_checagem_do_hook(self) -> None:
        for pendencias in (BASE["pendencias"], []):
            f = gf.validar(_dados(pendencias=pendencias))
            for nome, renderizar in gf.RENDERIZADORES.items():
                with self.subTest(formato=nome, pendencias=len(pendencias)):
                    self.assertTrue(hook.tem_secao(renderizar(f)))

    def test_marca_e_uma_linha_com_os_identificadores_sem_repetir_o_painel(self) -> None:
        marca = gf.renderizar_marca(gf.validar(_dados()))
        self.assertEqual(marca.count("\n"), 1)
        self.assertIn("**Fechamento da entrega** · resultado `Concluído`", marca)
        self.assertIn("Decisões humanas pendentes: 2 (`rls`, `adr18`)", marca)
        self.assertNotIn("Sem teste executado", marca)
        self.assertIn("pendentes: nenhuma", gf.renderizar_marca(gf.validar(_dados(pendencias=[]))))

    def test_ordem_fixa_das_secoes(self) -> None:
        saida = gf.renderizar_markdown(gf.validar(_dados()))
        secoes = ["Fechamento da entrega", "Decisões humanas pendentes", "Arquivos e comportamentos",
                  "Verificações e revisões", "Riscos e limitações", "Próximo passo"]
        posicoes = [saida.index(s) for s in secoes]
        self.assertEqual(posicoes, sorted(posicoes))

    def test_respostas_usam_o_identificador(self) -> None:
        f = gf.validar(_dados())
        texto = gf.renderizar_texto(f)
        self.assertIn("`adr18 confirmar`", texto)
        self.assertIn("ok todas", texto)
        painel = gf.renderizar_html(f)
        self.assertIn('data-id="rls" data-resposta="rls reforçar agora"', painel)
        self.assertIn('data-recomendada="1" aria-pressed="false" data-id="adr18" data-resposta="adr18 confirmar"', painel)

    def test_clique_seleciona_e_um_unico_envio_comeca_com_quebra_de_linha(self) -> None:
        painel = gf.renderizar_html(gf.validar(_dados()))
        self.assertIn('id="fx-enviar"', painel)
        self.assertIn('id="fx-texto"', painel)
        self.assertEqual(painel.count("sendPrompt("), 1)
        self.assertIn("sendPrompt('\\n'+t)", painel)

    def test_aceitar_todas_so_com_mais_de_uma_pendencia(self) -> None:
        self.assertIn('id="fx-todas"', gf.renderizar_html(gf.validar(_dados())))
        f = gf.validar(_dados(pendencias=BASE["pendencias"][:1]))
        self.assertNotIn('id="fx-todas"', gf.renderizar_html(f))
        self.assertNotIn("ok todas", gf.renderizar_texto(f))

    def test_pendencias_ordenadas_por_urgencia(self) -> None:
        f = gf.validar(_dados())
        self.assertEqual([p["id"] for p in f["pendencias"]], ["rls", "adr18"])
        texto = gf.renderizar_texto(f)
        self.assertLess(texto.index("`rls`"), texto.index("`adr18`"))

    def test_contexto_enquanto_e_urgencia_aparecem(self) -> None:
        f = gf.validar(_dados())
        for saida in (gf.renderizar_markdown(f), gf.renderizar_html(f)):
            self.assertIn("A troca de tenant não é barrada pelo banco.", saida)
            self.assertIn("Enquanto isso: A integração aguarda a decisão.", saida)
            self.assertIn("Bloqueia agora", saida)

    def test_estado_do_trabalho_no_cabecalho(self) -> None:
        self.assertIn("**Trabalho:** Commitado em `abc1234`", gf.renderizar_texto(gf.validar(_dados())))
        local = _dados(trabalho="local")
        del local["commit"]
        self.assertIn("Sem commit", gf.renderizar_html(gf.validar(local)))

    def test_sem_pendencia_declara_nenhuma(self) -> None:
        f = gf.validar(_dados(pendencias=[]))
        self.assertIn("**Decisões humanas pendentes:** Nenhuma.", gf.renderizar_texto(f))
        self.assertTrue(gf.renderizar_texto(f).startswith("**Fechamento da entrega**"))
        self.assertIn("Nenhuma.", gf.renderizar_markdown(f))

    def test_riscos_somem_quando_vazios_e_aparecem_no_texto_quando_existem(self) -> None:
        self.assertNotIn("Riscos e limitações", gf.renderizar_markdown(gf.validar(_dados(riscos=[]))))
        self.assertIn("- Sem teste executado", gf.renderizar_texto(gf.validar(_dados())))

    def test_bloqueio_aparece_em_todos_os_formatos(self) -> None:
        f = gf.validar(_dados(resultado="bloqueado", motivo="Ambiente indisponível"))
        for nome, renderizar in gf.RENDERIZADORES.items():
            with self.subTest(formato=nome):
                self.assertIn("Bloqueado", renderizar(f))
                if nome != "marca":
                    self.assertIn("Ambiente indisponível", renderizar(f))


    def test_invariantes_do_script_de_respostas(self) -> None:
        # o script não tem teste executável; fixa as peças de lógica que um refactor poderia quebrar em silêncio
        painel = gf.renderizar_html(gf.validar(_dados()))
        self.assertIn(".join('\\n')", painel)
        self.assertIn("button.fx-op[data-recomendada]", painel)
        self.assertIn("erro.textContent='Escolha ao menos uma resposta'", painel)
        self.assertIn("getElementById('fx-enviar').addEventListener('click',enviar)", painel)
        self.assertIn("texto.textContent=", painel)

    def test_mudancas_e_verificacoes_nao_sao_ocultadas(self) -> None:
        f = gf.validar(_dados())
        for renderizar in (gf.renderizar_markdown, gf.renderizar_html):
            saida = renderizar(f)
            for trecho in ("Primeira mudança", "Segunda mudança", "docs/adr/0018.md", "QA na 2ª rodada", "M10"):
                self.assertIn(trecho, saida)


    def test_barra_vertical_nao_quebra_tabela_markdown(self) -> None:
        f = gf.validar(_dados(titulo="a | b"))
        self.assertIn("| a \\| b |", gf.renderizar_markdown(f))


class HtmlSeguroTests(unittest.TestCase):
    def test_texto_dos_dados_e_escapado(self) -> None:
        dados = _dados()
        dados["pendencias"][0]["pergunta"] = '<script>alert(1)</script> "aspas"'
        dados["pendencias"][1]["alternativas"] = ['x" onclick="alert(1)']
        painel = gf.renderizar_html(gf.validar(dados))
        self.assertNotIn("<script>alert", painel)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", painel)
        self.assertNotIn('onclick="alert', painel)

    def test_um_unico_script_e_nenhum_javascript_inline(self) -> None:
        painel = gf.renderizar_html(gf.validar(_dados()))
        self.assertEqual(painel.count("<script>"), 1)
        self.assertIsNone(re.search(r"\son[a-z]+=", painel))

    def test_crase_vira_code_so_depois_do_escape(self) -> None:
        f = gf.validar(_dados(titulo="use `<b>` aqui"))
        self.assertIn("use <code>&lt;b&gt;</code> aqui", gf.renderizar_html(f))


class LinhaDeComandoTests(unittest.TestCase):
    """Executa o script como o modelo executa: arquivo ou entrada padrão, código de saída."""

    def _rodar(self, argv: list[str], entrada: bytes) -> tuple[int, str, str]:
        resultado = subprocess.run(
            [sys.executable, str(SCRIPT), *argv], input=entrada, capture_output=True, check=False
        )
        return resultado.returncode, resultado.stdout.decode("utf-8"), resultado.stderr.decode("utf-8")

    def test_gera_a_partir_da_entrada_padrao(self) -> None:
        codigo, saida, _ = self._rodar(["-", "--formato", "texto"], json.dumps(BASE).encode("utf-8"))
        self.assertEqual(codigo, 0)
        self.assertIn("Decisões humanas pendentes", saida)

    def test_dados_invalidos_saem_com_1_e_lista_de_problemas(self) -> None:
        codigo, saida, erro = self._rodar(["-", "--formato", "html"], b'{"resultado": "invalido"}')
        self.assertEqual(codigo, 1)
        self.assertEqual(saida, "")
        self.assertIn("resultado deve ser", erro)

    def test_json_malformado_sai_com_1(self) -> None:
        codigo, _, erro = self._rodar(["-", "--formato", "texto"], b"{quebrado")
        self.assertEqual(codigo, 1)
        self.assertIn("Não foi possível ler os dados", erro)


if __name__ == "__main__":
    unittest.main()
