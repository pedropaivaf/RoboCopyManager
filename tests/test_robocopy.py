"""
Bateria de Testes Automatizados para o RoboCopy Manager.
Validação completa de:
- Montagem de comandos e tratamento de caminhos (aspas, barras)
- Predefinições e exportação/importação de perfis JSON
- Interpretação de Exit Codes e parser de estatísticas
- Execução real com arquivos de teste (Cópia, Simulação, Interrupção)
"""

import os
import shutil
import tempfile
import time
import unittest
import json

from robocopy_engine import RobocopyEngine, RobocopyConfig, interpret_exit_code
from presets import PRESETS, apply_preset_to_config, export_profile_to_json, import_profile_from_json


class TestRobocopyCommandBuilder(unittest.TestCase):
    def setUp(self):
        self.engine = RobocopyEngine()

    def test_default_command(self):
        cfg = RobocopyConfig(source=r"C:\Fonte", destination=r"D:\Destino")
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("robocopy", cmd)
        self.assertIn(r"C:\Fonte", cmd)
        self.assertIn(r"D:\Destino", cmd)
        self.assertIn("/E", cmd)
        self.assertIn("/MT:8", cmd)
        self.assertIn("/R:1", cmd)
        self.assertIn("/W:3", cmd)
        self.assertIn("/XJ", cmd)

    def test_spaces_in_paths(self):
        cfg = RobocopyConfig(source=r"C:\Minha Pasta de Arquivos", destination=r"D:\Meu Backup 2026")
        cmd = self.engine.build_command_string(cfg)
        self.assertIn(r'"C:\Minha Pasta de Arquivos"', cmd)
        self.assertIn(r'"D:\Meu Backup 2026"', cmd)

    def test_trailing_slashes_removal(self):
        # Evita que "C:\pasta\" escape a aspa final no Windows
        cfg = RobocopyConfig(source=r"C:\Origem\\", destination=r"D:\Destino/")
        cmd = self.engine.build_command_string(cfg)
        self.assertIn(r"C:\Origem", cmd)
        self.assertIn(r"D:\Destino", cmd)
        self.assertNotIn(r"C:\Origem\\", cmd)

    def test_mirror_mode(self):
        cfg = RobocopyConfig(source=r"C:\Origem", destination=r"D:\Destino", mirror=True, copy_subdirs_empty=False)
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("/MIR", cmd)
        self.assertNotIn("/E", cmd)
        self.assertNotIn("/S", cmd)

    def test_filters_and_exclusions(self):
        cfg = RobocopyConfig(
            source=r"C:\Origem",
            destination=r"D:\Destino",
            file_pattern="*.docx *.xlsx",
            exclude_files="*.tmp *.bak thumbs.db",
            exclude_dirs=r'node_modules .git "$RECYCLE.BIN"',
            exclude_older=True,
            exclude_newer=True,
            max_size="10485760",
            min_size="1024"
        )
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("*.docx", cmd)
        self.assertIn("*.xlsx", cmd)
        self.assertIn("/XF", cmd)
        self.assertIn("*.tmp", cmd)
        self.assertIn("/XD", cmd)
        self.assertIn("node_modules", cmd)
        self.assertIn("/XO", cmd)
        self.assertIn("/XN", cmd)
        self.assertIn("/MAX:10485760", cmd)
        self.assertIn("/MIN:1024", cmd)

    def test_performance_flags(self):
        cfg = RobocopyConfig(
            source=r"C:\Origem",
            destination=r"D:\Destino",
            multi_threaded=32,
            retries=2,
            wait_time=5,
            inter_packet_gap=50
        )
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("/MT:32", cmd)
        self.assertIn("/R:2", cmd)
        self.assertIn("/W:5", cmd)
        self.assertIn("/IPG:50", cmd)

    def test_ntfs_attributes(self):
        cfg = RobocopyConfig(
            source=r"C:\Origem",
            destination=r"D:\Destino",
            copy_data=True,
            copy_attrs=True,
            copy_timestamps=True,
            copy_security=True,
            copy_owner=True,
            copy_audit=True,
            copy_dir_attrs=True
        )
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("/COPY:DATSOU", cmd)
        self.assertIn("/DCOPY:DAT", cmd)

    def test_move_flags(self):
        cfg_files = RobocopyConfig(source=r"C:\Origem", destination=r"D:\Destino", move_files=True)
        self.assertIn("/MOV", self.engine.build_command_string(cfg_files))

        cfg_all = RobocopyConfig(source=r"C:\Origem", destination=r"D:\Destino", move_all=True)
        self.assertIn("/MOVE", self.engine.build_command_string(cfg_all))


class TestPresetsAndProfiles(unittest.TestCase):
    def test_apply_mirror_preset(self):
        cfg = RobocopyConfig(source=r"C:\A", destination=r"D:\B")
        cfg = apply_preset_to_config(cfg, "espelhamento")
        self.assertTrue(cfg.mirror)
        self.assertFalse(cfg.copy_subdirs_empty)
        self.assertEqual(cfg.source, r"C:\A")

    def test_apply_backup_preset(self):
        cfg = RobocopyConfig(source=r"C:\A", destination=r"D:\B")
        cfg = apply_preset_to_config(cfg, "backup_incremental")
        self.assertFalse(cfg.mirror)
        self.assertTrue(cfg.copy_subdirs_empty)
        self.assertTrue(cfg.exclude_older)

    def test_export_import_json(self):
        temp_dir = tempfile.mkdtemp()
        try:
            profile_path = os.path.join(temp_dir, "perfil_teste.json")
            original_cfg = RobocopyConfig(
                source=r"C:\Dados",
                destination=r"E:\Backup",
                multi_threaded=16,
                exclude_files="*.iso *.vmdk"
            )
            export_profile_to_json(original_cfg, profile_path)
            self.assertTrue(os.path.exists(profile_path))

            loaded_cfg = import_profile_from_json(profile_path)
            self.assertEqual(loaded_cfg.source, r"C:\Dados")
            self.assertEqual(loaded_cfg.destination, r"E:\Backup")
            self.assertEqual(loaded_cfg.multi_threaded, 16)
            self.assertEqual(loaded_cfg.exclude_files, "*.iso *.vmdk")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestExitCodeInterpreter(unittest.TestCase):
    def test_exit_codes(self):
        self.assertEqual(interpret_exit_code(0)[2], "success")
        self.assertEqual(interpret_exit_code(1)[2], "success")
        self.assertEqual(interpret_exit_code(3)[2], "success")
        self.assertEqual(interpret_exit_code(4)[2], "warning")
        self.assertEqual(interpret_exit_code(8)[2], "error")
        self.assertEqual(interpret_exit_code(16)[2], "error")


class TestSummaryParser(unittest.TestCase):
    def setUp(self):
        self.engine = RobocopyEngine()

    def test_parse_portuguese_summary(self):
        sample_output = [
            "-------------------------------------------------------------------------------\n",
            "   ROBOCOPY     ::     Robust File Copy para Windows                           \n",
            "-------------------------------------------------------------------------------\n",
            "   Arquivos: *.*\n",
            "  Opções: *.* /TEE /S /E /DCOPY:DAT /COPY:DAT /NP /XJ /MT:8 /R:1 /W:3\n",
            "               Total   Copiada  IgnoradaIncompatibilidade     FALHA    Extras\n",
            "Diretórios:         3         2         1         0         0         0\n",
            " Arquivos:        150        50       100         0         0         0\n",
            "    Bytes:     4.50 m    1.50 m    3.00 m         0         0         0\n",
            "N.º de Vezes:   0:00:02   0:00:01                       0:00:00   0:00:01\n",
            " Velocidade:             750000 Bytes/s.\n"
        ]
        res = self.engine._parse_summary(sample_output)
        self.assertEqual(res["dirs_total"], "3")
        self.assertEqual(res["dirs_copied"], "2")
        self.assertEqual(res["files_total"], "150")
        self.assertEqual(res["files_copied"], "50")
        self.assertEqual(res["bytes_total"], "4.50 m")
        self.assertEqual(res["bytes_copied"], "1.50 m")
        self.assertEqual(res["speed"], "750000 Bytes/s.")

    def test_parse_english_summary(self):
        sample_output = [
            "               Total    Copied   Skipped  Mismatch    FAILED    Extras\n",
            "    Dirs :        10         5         5         0         0         0\n",
            "   Files :        80        40        40         0         0         0\n",
            "   Bytes :    2.10 m    1.05 m    1.05 m         0         0         0\n",
            "   Speed :            1200000 Bytes/sec.\n"
        ]
        res = self.engine._parse_summary(sample_output)
        self.assertEqual(res["dirs_total"], "10")
        self.assertEqual(res["dirs_copied"], "5")
        self.assertEqual(res["files_total"], "80")
        self.assertEqual(res["files_copied"], "40")
        self.assertEqual(res["bytes_total"], "2.10 m")
        self.assertEqual(res["bytes_copied"], "1.05 m")
        self.assertEqual(res["speed"], "1200000 Bytes/sec.")


class TestRealExecution(unittest.TestCase):
    def setUp(self):
        self.temp_base = tempfile.mkdtemp()
        self.src = os.path.join(self.temp_base, "origem")
        self.dst = os.path.join(self.temp_base, "destino")
        os.makedirs(self.src, exist_ok=True)
        os.makedirs(self.dst, exist_ok=True)

        # Cria arquivos e subpastas na origem
        sub = os.path.join(self.src, "subpasta")
        os.makedirs(sub, exist_ok=True)
        with open(os.path.join(self.src, "arq1.txt"), "w", encoding="utf-8") as f:
            f.write("Conteudo arquivo 1")
        with open(os.path.join(sub, "arq2.txt"), "w", encoding="utf-8") as f:
            f.write("Conteudo arquivo 2 dentro da subpasta")

        self.engine = RobocopyEngine()

    def tearDown(self):
        shutil.rmtree(self.temp_base, ignore_errors=True)

    def test_real_dry_run_simulation(self):
        """Valida que simulação (/L) não cria arquivos no destino."""
        cfg = RobocopyConfig(source=self.src, destination=self.dst, dry_run=True)
        output = []
        done = [False]
        res = [{}]

        def on_finish(c, t, d, s):
            done[0] = True
            res[0] = {"code": c, "summary": s}

        self.engine.run(cfg, lambda l: output.append(l), on_finish)

        for _ in range(50):
            if done[0]: break
            time.sleep(0.1)

        self.assertTrue(done[0], "A simulação não finalizou a tempo.")
        self.assertIn(res[0]["code"], (0, 1))
        # Destino NÃO deve conter os arquivos copiados
        self.assertFalse(os.path.exists(os.path.join(self.dst, "arq1.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.dst, "subpasta", "arq2.txt")))

    def test_real_copy_execution(self):
        """Valida cópia real de arquivos e subdiretórios com integridade de dados."""
        cfg = RobocopyConfig(source=self.src, destination=self.dst)
        output = []
        done = [False]
        res = [{}]

        def on_finish(c, t, d, s):
            done[0] = True
            res[0] = {"code": c, "summary": s}

        self.engine.run(cfg, lambda l: output.append(l), on_finish)

        for _ in range(50):
            if done[0]: break
            time.sleep(0.1)

        self.assertTrue(done[0], "A cópia não finalizou a tempo.")
        self.assertIn(res[0]["code"], (0, 1))
        # Verifica existência e conteúdo
        dst_f1 = os.path.join(self.dst, "arq1.txt")
        dst_f2 = os.path.join(self.dst, "subpasta", "arq2.txt")
        self.assertTrue(os.path.exists(dst_f1))
        self.assertTrue(os.path.exists(dst_f2))

        with open(dst_f1, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Conteudo arquivo 1")
        with open(dst_f2, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Conteudo arquivo 2 dentro da subpasta")

        # Verifica estatísticas
        self.assertEqual(res[0]["summary"]["files_copied"], "2")
        self.assertEqual(res[0]["summary"]["files_failed"], "0")

    def test_real_goodsync_two_way_sync_execution(self):
        """Valida fusão de pastas no modo GoodSync Bidirecional (2-Way Sync) com 2 etapas."""
        pasta_a = os.path.join(self.temp_base, "PastaA")
        pasta_b = os.path.join(self.temp_base, "PastaB")
        os.makedirs(pasta_a, exist_ok=True)
        os.makedirs(pasta_b, exist_ok=True)

        with open(os.path.join(pasta_a, "item_origem.txt"), "w", encoding="utf-8") as f:
            f.write("Arquivo exclusivo da Pasta A")
        with open(os.path.join(pasta_b, "item_destino.txt"), "w", encoding="utf-8") as f:
            f.write("Arquivo exclusivo da Pasta B")

        cfg = RobocopyConfig(
            source=pasta_a,
            destination=pasta_b,
            is_two_way_sync=True,
            retries=1,
            wait_time=1
        )

        output = []
        done = [False]
        res = [{}]

        def on_finish(c, t, d, s):
            done[0] = True
            res[0] = {"code": c, "summary": s}

        self.engine.run(cfg, lambda l: output.append(l), on_finish)

        for _ in range(50):
            if done[0]: break
            time.sleep(0.1)

        self.assertTrue(done[0], "A sincronização bidirecional não concluiu no tempo esperado.")
        self.assertLess(res[0]["code"], 8, "Código de erro fatal no Robocopy.")

        # Ambas as pastas devem conter os dois arquivos após a sincronização!
        arquivos_a = os.listdir(pasta_a)
        arquivos_b = os.listdir(pasta_b)
        self.assertIn("item_origem.txt", arquivos_a)
        self.assertIn("item_destino.txt", arquivos_a)
        self.assertIn("item_origem.txt", arquivos_b)
        self.assertIn("item_destino.txt", arquivos_b)


class TestGoodSyncFeatures(unittest.TestCase):
    def setUp(self):
        self.engine = RobocopyEngine()

    def test_goodsync_mirror_preset(self):
        cfg = RobocopyConfig(source=r"C:\PastaOrigem", destination=r"D:\PastaDestino")
        cfg = apply_preset_to_config(cfg, "goodsync_mirror")
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("/MIR", cmd)
        self.assertIn("/R:3", cmd)
        self.assertIn("/W:5", cmd)
        self.assertIn("/V", cmd)
        self.assertIn("/TS", cmd)
        self.assertIn("/FP", cmd)
        self.assertIn("/MT:32", cmd)

    def test_goodsync_update_preset(self):
        cfg = RobocopyConfig(source=r"C:\PastaOrigem", destination=r"D:\PastaDestino")
        cfg = apply_preset_to_config(cfg, "goodsync_update")
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("/E", cmd)
        self.assertIn("/XO", cmd)
        self.assertIn("/R:3", cmd)
        self.assertIn("/W:5", cmd)
        self.assertNotIn("/MIR", cmd)

    def test_goodsync_move_preset(self):
        cfg = RobocopyConfig(source=r"C:\PastaOrigem", destination=r"D:\PastaDestino")
        cfg = apply_preset_to_config(cfg, "goodsync_move")
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("/MOVE", cmd)
        self.assertIn("/E", cmd)
        self.assertIn("/R:3", cmd)
        self.assertIn("/W:5", cmd)

    def test_goodsync_filter_preset(self):
        cfg = RobocopyConfig(
            source=r"C:\PastaOrigem",
            destination=r"D:\PastaDestino",
            exclude_files="*.tmp *.bak",
            max_size="52428800",
            retries=3,
            wait_time=5
        )
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("/XF", cmd)
        self.assertIn("*.tmp", cmd)
        self.assertIn("/MAX:52428800", cmd)
        self.assertIn("/R:3", cmd)
        self.assertIn("/W:5", cmd)

    def test_goodsync_copyall_flag(self):
        cfg = RobocopyConfig(source=r"C:\A", destination=r"D:\B", copyall=True)
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("/COPYALL", cmd)
        self.assertNotIn("/COPY:DAT", cmd)

    def test_goodsync_two_way_sync_command(self):
        cfg = RobocopyConfig(
            source=r"C:\PastaA",
            destination=r"D:\PastaB",
            is_two_way_sync=True,
            exclude_older=True,
            retries=3,
            wait_time=5
        )
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("Etapa 1", cmd)
        self.assertIn("Etapa 2", cmd)
        self.assertIn(r"C:\PastaA D:\PastaB", cmd)
        self.assertIn(r"D:\PastaB C:\PastaA", cmd)
        self.assertIn("/XO", cmd)


if __name__ == "__main__":
    unittest.main()
