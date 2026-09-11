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


if __name__ == "__main__":
    unittest.main()
