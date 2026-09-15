"""
Testes Automatizados para o Script PowerShell RoboCopy.ps1 (Padrão Win11Debloat).
Valida a integridade da sintaxe PowerShell e a execução headless/scripting.
"""

import unittest
import subprocess
import os
import tempfile


class TestPowerShellScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "RoboCopy.ps1"))
        if not os.path.exists(cls.script_path):
            raise FileNotFoundError(f"Script RoboCopy.ps1 não encontrado em: {cls.script_path}")

    def test_powershell_syntax_no_parse_errors(self):
        """Valida que o analisador léxico/sintático do PowerShell não detecta erros no script."""
        ps_code = f"""
        $err = @()
        [System.Management.Automation.Language.Parser]::ParseFile('{self.script_path}', [ref]$null, [ref]$err)
        if ($err.Count -gt 0) {{
            $err | ForEach-Object {{ Write-Error $_ }}
            exit 1
        }}
        exit 0
        """
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", ps_code],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"Erros de sintaxe encontrados no RoboCopy.ps1:\n{res.stderr}")

    def test_powershell_backup_dry_run(self):
        """Valida a execução de simulação (/L) do modo backup em pasta temporária."""
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            test_file = os.path.join(src, "documento.txt")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("Teste de integridade PowerShell.")

            cmd = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", self.script_path,
                "-Source", src,
                "-Destination", dst,
                "-Mode", "backup",
                "-DryRun",
                "-NonInteractive",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertIn(res.returncode, [0, 1, 2, 3], f"Falha na execução do PowerShell. Saída:\n{res.stdout}\n{res.stderr}")
            self.assertIn("Comando RoboCopy preparado:", res.stdout)
            self.assertIn("/XO", res.stdout)
            # Como foi DryRun, o arquivo não deve existir fisicamente no destino
            self.assertFalse(os.path.exists(os.path.join(dst, "documento.txt")))

    def test_powershell_goodsync_mirror_dry_run(self):
        """Valida a execução do modo GoodSync Mirror pelo script PowerShell."""
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            cmd = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", self.script_path,
                "-Source", src,
                "-Destination", dst,
                "-Mode", "goodsync_mirror",
                "-DryRun",
                "-NonInteractive",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertIn(res.returncode, [0, 1, 2, 3], f"Falha na simulação GoodSync Mirror:\n{res.stdout}")
            self.assertIn("/MIR", res.stdout)

    def test_powershell_goodsync_two_way_sync(self):
        """Valida o modo de 2 vias (fusão bidirecional em 2 etapas) no script PowerShell."""
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            cmd = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", self.script_path,
                "-Source", src,
                "-Destination", dst,
                "-Mode", "goodsync_two_way",
                "-DryRun",
                "-NonInteractive",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.assertIn(res.returncode, [0, 1, 2, 3], f"Falha na simulação GoodSync Two-Way:\n{res.stdout}")
            self.assertIn("ETAPA 1 DE 2", res.stdout)
            self.assertIn("ETAPA 2 DE 2", res.stdout)

    def test_powershell_gui_bootstrap_detection(self):
        """Valida os parâmetros -GUI, -CLI, -Update e as funções do bootstrap."""
        with open(self.script_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("[switch]$GUI", content)
        self.assertIn("[switch]$CLI", content)
        self.assertIn("[switch]$Update", content)
        self.assertIn("function Launch-GUIApp", content)
        self.assertIn("function Get-AppSource", content)
        self.assertIn("function Find-Python", content)

    def test_powershell_bootstrap_uses_source_not_executable(self):
        """
        O aplicativo é aberto a partir do código-fonte baixado do GitHub
        (padrão Win11Debloat), e não de um executável compilado que ficaria
        desatualizado em relação à branch main.
        """
        with open(self.script_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("RoboCopyManager.exe", content,
                         "O bootstrap não deve mais depender de executável compilado.")

        # Todos os módulos da aplicação precisam constar na lista de download.
        for module in ("robocopy_gui.py", "robocopy_engine.py", "sync_analyzer.py",
                       "presets.py", "robocopy_cli.py"):
            self.assertIn(module, content, f"O módulo {module} não é baixado pelo bootstrap.")

        self.assertIn("raw.githubusercontent.com/pedropaivaf/RoboCopyManager/main", content)
        self.assertIn("pythonw.exe", content, "A GUI deve abrir sem console preto atrás dela.")

    def test_powershell_dist_copy_is_synchronized(self):
        """A cópia em dist/ precisa acompanhar o script da raiz."""
        dist_path = os.path.join(os.path.dirname(self.script_path), "dist", "RoboCopy.ps1")
        if not os.path.exists(dist_path):
            self.skipTest("dist/RoboCopy.ps1 não está presente neste checkout.")

        with open(self.script_path, "r", encoding="utf-8") as f:
            root_content = f.read()
        with open(dist_path, "r", encoding="utf-8") as f:
            dist_content = f.read()

        self.assertEqual(root_content, dist_content,
                         "dist/RoboCopy.ps1 está diferente do script da raiz.")


if __name__ == "__main__":
    unittest.main()
