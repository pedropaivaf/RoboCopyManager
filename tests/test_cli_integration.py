"""
Testes de Integração e Validação da Interface de Terminal (CLI/TUI) do RoboCopy Manager.
"""

import unittest
import os
import sys
import tempfile
from robocopy_cli import clean_path, is_admin
from robocopy_engine import RobocopyConfig, RobocopyEngine
from presets import apply_preset_to_config


class TestCLIIntegration(unittest.TestCase):
    def test_clean_path(self):
        """Valida a limpeza e normalização de caminhos com e sem aspas."""
        self.assertEqual(clean_path(r'"C:\Pastas\Com Espaco"'), os.path.normpath(r"C:\Pastas\Com Espaco"))
        self.assertEqual(clean_path(r"'D:\Backup\Dados'"), os.path.normpath(r"D:\Backup\Dados"))
        self.assertEqual(clean_path("  E:\\Arquivos  "), os.path.normpath(r"E:\Arquivos"))
        self.assertEqual(clean_path(""), "")

    def test_is_admin_check(self):
        """Garante que a checagem de privilégios de Administrador retorna bool sem exceções."""
        res = is_admin()
        self.assertIsInstance(res, bool)

    def test_cli_preset_mappings(self):
        """Valida que todos os modos disponíveis no CLI configuram o RobocopyConfig corretamente."""
        cfg = RobocopyConfig(source=r"C:\Origem", destination=r"D:\Destino")

        # 1. Backup
        c1 = apply_preset_to_config(cfg, "backup_incremental")
        self.assertTrue(c1.copy_subdirs_empty)
        self.assertTrue(c1.exclude_older)
        self.assertFalse(c1.mirror)

        # 2. Fast
        c2 = apply_preset_to_config(cfg, "copia_rapida")
        self.assertTrue(c2.copy_subdirs)
        self.assertFalse(c2.copy_subdirs_empty)
        self.assertEqual(c2.multi_threaded, 16)

        # 3. Mirror
        c3 = apply_preset_to_config(cfg, "espelhamento")
        self.assertTrue(c3.mirror)

        # 4. Move
        c4 = apply_preset_to_config(cfg, "mover")
        self.assertTrue(c4.move_all)

        # 5. GoodSync Mirror
        c5 = apply_preset_to_config(cfg, "goodsync_mirror")
        self.assertTrue(c5.mirror)
        self.assertTrue(c5.verbose_timestamps)

        # 6. GoodSync Update
        c6 = apply_preset_to_config(cfg, "goodsync_update")
        self.assertTrue(c6.exclude_older)
        self.assertFalse(c6.mirror)

        # 7. GoodSync Two Way
        c7 = apply_preset_to_config(cfg, "goodsync_two_way")
        self.assertTrue(c7.is_two_way_sync)

    def test_cli_run_sync_simulation(self):
        """Valida a execução síncrona (run_sync) usada pelo terminal em pasta temporária."""
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            test_file = os.path.join(src, "arquivo_teste.txt")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("Conteúdo para validação CLI.")

            engine = RobocopyEngine()
            cfg = RobocopyConfig(source=src, destination=dst, dry_run=True)

            output_lines = []
            exit_code, title, desc, summary = engine.run_sync(cfg, on_line=output_lines.append)

            # Em simulação (/L), o arquivo deve ser listado mas NÃO copiado fisicamente
            self.assertLess(exit_code, 8)
            self.assertFalse(os.path.exists(os.path.join(dst, "arquivo_teste.txt")))
            self.assertIn("dirs_total", summary)
            self.assertIn("files_total", summary)
            self.assertGreater(len(output_lines), 0)


if __name__ == "__main__":
    unittest.main()
