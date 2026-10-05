"""Verifica a instalação das skills em um projeto vazio."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstalacaoTests(unittest.TestCase):
    def setUp(self) -> None:
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.projeto = Path(pasta.name)

    def instalar(self, *opcoes: str) -> None:
        resultado = subprocess.run(
            [sys.executable, str(ROOT / "instalar.py"), str(self.projeto), *opcoes],
            capture_output=True, encoding="utf-8", check=False,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)

    def test_exemplo_gera_panorama_e_preserva_arquivos_existentes(self) -> None:
        self.instalar("--dry-run", "--exemplo")
        self.assertEqual(list(self.projeto.iterdir()), [])
        self.instalar("--exemplo")
        script = self.projeto / ".claude/skills/phase-overview/scripts/gerar_panorama.py"
        resultado = subprocess.run(
            [sys.executable, str(script), "--raiz", str(self.projeto), "--formato", "marca"],
            capture_output=True, encoding="utf-8", check=False,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn("0 de 1 tickets entregues", resultado.stdout)

        skill = self.projeto / ".claude/skills/delivery-summary/SKILL.md"
        exemplo = self.projeto / "docs/panorama-das-fases.md"
        extra = skill.parent / "nota.md"
        skill.write_text("Conteúdo do projeto", encoding="utf-8")
        exemplo.write_text("Fases do projeto", encoding="utf-8")
        extra.write_text("Nota do projeto", encoding="utf-8")
        self.instalar("--exemplo")
        self.assertEqual(skill.read_text(encoding="utf-8"), "Conteúdo do projeto")
        self.instalar("--exemplo", "--force")
        self.assertEqual(skill.read_bytes(), (ROOT / "skills/delivery-summary/SKILL.md").read_bytes())
        self.assertEqual(exemplo.read_text(encoding="utf-8"), "Fases do projeto")
        self.assertEqual(extra.read_text(encoding="utf-8"), "Nota do projeto")

    def test_testes_instalados_funcionam_sem_dados_de_exemplo(self) -> None:
        self.instalar()
        resultado = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests/governance", "-p", "test_*.py"],
            cwd=self.projeto, capture_output=True, encoding="utf-8", check=False,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr)


if __name__ == "__main__":
    unittest.main()
