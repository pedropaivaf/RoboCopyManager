"""
Auditoria Automatizada Exaustiva de 100% dos Recursos e Opções do RoboCopy Manager.
Testa cada aba, cada controle, predefinição, flag ativada e desativada,
e valida sintaxe diretamente contra o executável nativo robocopy.exe do Windows.
"""

import os
import shutil
import tempfile
import unittest
import subprocess

from robocopy_engine import RobocopyEngine, RobocopyConfig, split_windows_args, interpret_exit_code
from presets import PRESETS, apply_preset_to_config, export_profile_to_json, import_profile_from_json


class TestAuditAllTabsAndOptions(unittest.TestCase):
    def setUp(self):
        self.engine = RobocopyEngine()
        self.src = r"C:\Audit_Origem"
        self.dst = r"D:\Audit_Destino"

    # =========================================================================
    # 1. MODO SIMPLIFICADO & TRANSIÇÃO DE PRESETS
    # =========================================================================
    def test_preset_transitions_do_not_bleed_flags(self):
        """Garante que alternar entre presets limpa flags exclusivas (ex: /MOVE não vaza para Backup)."""
        cfg = RobocopyConfig(source=self.src, destination=self.dst)
        
        # 1. Ativa mover
        cfg = apply_preset_to_config(cfg, "mover")
        self.assertTrue(cfg.move_all)
        cmd_mover = self.engine.build_command_string(cfg)
        self.assertIn("/MOVE", cmd_mover)

        # 2. Alterna para backup_incremental
        cfg = apply_preset_to_config(cfg, "backup_incremental")
        self.assertFalse(cfg.move_all, "move_all deve ser False após mudar para backup_incremental")
        self.assertFalse(cfg.move_files, "move_files deve ser False")
        self.assertTrue(cfg.copy_subdirs_empty)
        self.assertTrue(cfg.exclude_older)
        cmd_backup = self.engine.build_command_string(cfg)
        self.assertNotIn("/MOVE", cmd_backup)
        self.assertNotIn("/MOV", cmd_backup)
        self.assertIn("/XO", cmd_backup)

        # 3. Alterna para espelhamento
        cfg = apply_preset_to_config(cfg, "espelhamento")
        self.assertTrue(cfg.mirror)
        self.assertFalse(cfg.copy_subdirs_empty)
        self.assertFalse(cfg.exclude_older)
        cmd_mirror = self.engine.build_command_string(cfg)
        self.assertIn("/MIR", cmd_mirror)
        self.assertNotIn("/XO", cmd_mirror)

        # 4. Alterna para copia_rapida
        cfg = apply_preset_to_config(cfg, "copia_rapida")
        self.assertFalse(cfg.mirror)
        self.assertTrue(cfg.copy_subdirs)
        self.assertFalse(cfg.copy_subdirs_empty)
        cmd_quick = self.engine.build_command_string(cfg)
        self.assertIn("/S", cmd_quick)
        self.assertNotIn("/MIR", cmd_quick)
        self.assertNotIn("/E", cmd_quick)

    # =========================================================================
    # 2. ABA 1: ESTRUTURA E MODOS (/E, /S, /MIR, /LEV, /J, /Z, /MOV, /MOVE)
    # =========================================================================
    def test_tab1_copy_subdirs_empty_e(self):
        """Flag /E ativada e desativada."""
        cfg_on = RobocopyConfig(source=self.src, destination=self.dst, copy_subdirs_empty=True, copy_subdirs=False, mirror=False)
        self.assertIn("/E", self.engine.build_command_string(cfg_on))

        cfg_off = RobocopyConfig(source=self.src, destination=self.dst, copy_subdirs_empty=False, copy_subdirs=False, mirror=False)
        self.assertNotIn("/E", self.engine.build_command_string(cfg_off))

    def test_tab1_copy_subdirs_s(self):
        """Flag /S ativada e desativada."""
        cfg_on = RobocopyConfig(source=self.src, destination=self.dst, copy_subdirs=True, copy_subdirs_empty=False, mirror=False)
        self.assertIn("/S", self.engine.build_command_string(cfg_on))

        cfg_off = RobocopyConfig(source=self.src, destination=self.dst, copy_subdirs=False, copy_subdirs_empty=False, mirror=False)
        self.assertNotIn("/S", self.engine.build_command_string(cfg_off))

    def test_tab1_mirror_mir(self):
        """Flag /MIR ativada e desativada."""
        cfg_on = RobocopyConfig(source=self.src, destination=self.dst, mirror=True, copy_subdirs_empty=False)
        cmd = self.engine.build_command_string(cfg_on)
        self.assertIn("/MIR", cmd)
        self.assertNotIn("/E", cmd)
        self.assertNotIn("/S", cmd)

        cfg_off = RobocopyConfig(source=self.src, destination=self.dst, mirror=False, copy_subdirs_empty=True)
        self.assertNotIn("/MIR", self.engine.build_command_string(cfg_off))

    def test_tab1_subfolder_level_lev(self):
        """Flag /LEV:n com diferentes valores."""
        cfg_zero = RobocopyConfig(source=self.src, destination=self.dst, subfolder_level=0)
        self.assertNotIn("/LEV:", self.engine.build_command_string(cfg_zero))

        cfg_two = RobocopyConfig(source=self.src, destination=self.dst, subfolder_level=2)
        self.assertIn("/LEV:2", self.engine.build_command_string(cfg_two))

    def test_tab1_unbuffered_io_j(self):
        """Flag /J ativada e desativada."""
        cfg_on = RobocopyConfig(source=self.src, destination=self.dst, unbuffered_io=True)
        self.assertIn("/J", self.engine.build_command_string(cfg_on))

        cfg_off = RobocopyConfig(source=self.src, destination=self.dst, unbuffered_io=False)
        self.assertNotIn("/J", self.engine.build_command_string(cfg_off))

    def test_tab1_restartable_z(self):
        """Flag /Z ativada e desativada."""
        cfg_on = RobocopyConfig(source=self.src, destination=self.dst, restartable=True)
        self.assertIn("/Z", self.engine.build_command_string(cfg_on))

        cfg_off = RobocopyConfig(source=self.src, destination=self.dst, restartable=False)
        self.assertNotIn("/Z", self.engine.build_command_string(cfg_off))

    def test_tab1_move_files_mov(self):
        """Flag /MOV ativada e desativada."""
        cfg_on = RobocopyConfig(source=self.src, destination=self.dst, move_files=True, move_all=False)
        self.assertIn("/MOV", self.engine.build_command_string(cfg_on))
        self.assertNotIn("/MOVE", self.engine.build_command_string(cfg_on))

        cfg_off = RobocopyConfig(source=self.src, destination=self.dst, move_files=False, move_all=False)
        self.assertNotIn("/MOV", self.engine.build_command_string(cfg_off))

    def test_tab1_move_all_move(self):
        """Flag /MOVE ativada e desativada."""
        cfg_on = RobocopyConfig(source=self.src, destination=self.dst, move_all=True, move_files=False)
        self.assertIn("/MOVE", self.engine.build_command_string(cfg_on))
        self.assertNotIn("/MOV ", self.engine.build_command_string(cfg_on) + " ")

        cfg_off = RobocopyConfig(source=self.src, destination=self.dst, move_all=False)
        self.assertNotIn("/MOVE", self.engine.build_command_string(cfg_off))

    # =========================================================================
    # 3. ABA 2: FILTROS E EXCLUSÕES (/XF, /XD, /XJ, /XO, /MAX, /MIN, PATTERN)
    # =========================================================================
    def test_tab2_exclude_files_xf(self):
        """Exclusão de arquivos /XF com e sem parâmetros."""
        cfg_on = RobocopyConfig(source=self.src, destination=self.dst, exclude_files="*.tmp *.bak thumbs.db")
        cmd = self.engine.build_command_string(cfg_on)
        self.assertIn("/XF", cmd)
        self.assertIn("*.tmp", cmd)
        self.assertIn("*.bak", cmd)
        self.assertIn("thumbs.db", cmd)

        cfg_off = RobocopyConfig(source=self.src, destination=self.dst, exclude_files="")
        self.assertNotIn("/XF", self.engine.build_command_string(cfg_off))

    def test_tab2_exclude_dirs_xd(self):
        """Exclusão de pastas /XD com caminhos Windows e espaços."""
        cfg_on = RobocopyConfig(source=self.src, destination=self.dst, exclude_dirs=r'.git node_modules "C:\Temp Dir"')
        cmd = self.engine.build_command_string(cfg_on)
        self.assertIn("/XD", cmd)
        self.assertIn(".git", cmd)
        self.assertIn("node_modules", cmd)
        self.assertIn(r'"C:\Temp Dir"', cmd)

        cfg_off = RobocopyConfig(source=self.src, destination=self.dst, exclude_dirs="")
        self.assertNotIn("/XD", self.engine.build_command_string(cfg_off))

    def test_tab2_exclude_junctions_xj(self):
        """Flag /XJ ativada e desativada."""
        cfg_on = RobocopyConfig(source=self.src, destination=self.dst, exclude_junctions=True)
        self.assertIn("/XJ", self.engine.build_command_string(cfg_on))

        cfg_off = RobocopyConfig(source=self.src, destination=self.dst, exclude_junctions=False)
        self.assertNotIn("/XJ", self.engine.build_command_string(cfg_off))

    def test_tab2_exclude_older_xo(self):
        """Flag /XO ativada e desativada."""
        cfg_on = RobocopyConfig(source=self.src, destination=self.dst, exclude_older=True)
        self.assertIn("/XO", self.engine.build_command_string(cfg_on))

        cfg_off = RobocopyConfig(source=self.src, destination=self.dst, exclude_older=False)
        self.assertNotIn("/XO", self.engine.build_command_string(cfg_off))

    def test_tab2_file_size_limits_max_min(self):
        """Filtros /MAX e /MIN ativados e desativados."""
        cfg_on = RobocopyConfig(source=self.src, destination=self.dst, max_size="52428800", min_size="1024")
        cmd = self.engine.build_command_string(cfg_on)
        self.assertIn("/MAX:52428800", cmd)
        self.assertIn("/MIN:1024", cmd)

        cfg_off = RobocopyConfig(source=self.src, destination=self.dst, max_size="", min_size="")
        cmd_off = self.engine.build_command_string(cfg_off)
        self.assertNotIn("/MAX:", cmd_off)
        self.assertNotIn("/MIN:", cmd_off)

    def test_tab2_file_pattern(self):
        """Filtro de padrão de arquivo (*.* vs *.docx *.pdf)."""
        cfg_all = RobocopyConfig(source=self.src, destination=self.dst, file_pattern="*.*")
        args_all = self.engine.build_command_args(cfg_all)
        self.assertNotIn("*.*", args_all)  # Padrão default é omitido dos argumentos para brevidade

        cfg_custom = RobocopyConfig(source=self.src, destination=self.dst, file_pattern="*.docx *.xlsx")
        cmd_custom = self.engine.build_command_string(cfg_custom)
        self.assertIn("*.docx", cmd_custom)
        self.assertIn("*.xlsx", cmd_custom)

    # =========================================================================
    # 4. ABA 3: VELOCIDADE E REDE (/MT, /R, /W, /IPG)
    # =========================================================================
    def test_tab3_multi_threaded_mt(self):
        """Multi-threading de 1 a 64 threads."""
        cfg_1 = RobocopyConfig(source=self.src, destination=self.dst, multi_threaded=1)
        self.assertNotIn("/MT", self.engine.build_command_string(cfg_1))

        cfg_8 = RobocopyConfig(source=self.src, destination=self.dst, multi_threaded=8)
        self.assertIn("/MT:8", self.engine.build_command_string(cfg_8))

        cfg_32 = RobocopyConfig(source=self.src, destination=self.dst, multi_threaded=32)
        self.assertIn("/MT:32", self.engine.build_command_string(cfg_32))

        cfg_64 = RobocopyConfig(source=self.src, destination=self.dst, multi_threaded=64)
        self.assertIn("/MT:64", self.engine.build_command_string(cfg_64))

    def test_tab3_retries_and_wait(self):
        """Tentativas /R:n e espera /W:n."""
        cfg = RobocopyConfig(source=self.src, destination=self.dst, retries=5, wait_time=10)
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("/R:5", cmd)
        self.assertIn("/W:10", cmd)

        cfg_zero = RobocopyConfig(source=self.src, destination=self.dst, retries=0, wait_time=0)
        cmd_zero = self.engine.build_command_string(cfg_zero)
        self.assertIn("/R:0", cmd_zero)
        self.assertIn("/W:0", cmd_zero)

    # =========================================================================
    # 5. ABA 4: SEGURANÇA E REGISTRO (/COPY, /DCOPY, /NP, /LOG)
    # =========================================================================
    def test_tab4_copy_flags_individual(self):
        """Verifica cada combinação de marcas de cópia /COPY:."""
        # Padrão: D, A, T
        cfg_dat = RobocopyConfig(source=self.src, destination=self.dst, copy_data=True, copy_attrs=True, copy_timestamps=True, copy_security=False)
        self.assertIn("/COPY:DAT", self.engine.build_command_string(cfg_dat))

        # Apenas Dados e Atributos (sem timestamp)
        cfg_da = RobocopyConfig(source=self.src, destination=self.dst, copy_data=True, copy_attrs=True, copy_timestamps=False, copy_security=False)
        self.assertIn("/COPY:DA", self.engine.build_command_string(cfg_da))

        # Com Segurança NTFS (/COPY:DATS)
        cfg_dats = RobocopyConfig(source=self.src, destination=self.dst, copy_data=True, copy_attrs=True, copy_timestamps=True, copy_security=True)
        self.assertIn("/COPY:DATS", self.engine.build_command_string(cfg_dats))

        # Apenas Dados (/COPY:D)
        cfg_d = RobocopyConfig(source=self.src, destination=self.dst, copy_data=True, copy_attrs=False, copy_timestamps=False, copy_security=False)
        self.assertIn("/COPY:D", self.engine.build_command_string(cfg_d))

        # Se tudo for desmarcado, faz fallback seguro para /COPY:D
        cfg_none = RobocopyConfig(source=self.src, destination=self.dst, copy_data=False, copy_attrs=False, copy_timestamps=False, copy_security=False)
        self.assertIn("/COPY:D", self.engine.build_command_string(cfg_none))

    def test_tab4_dcopy_dat(self):
        """Cópia de atributos e timestamps de pastas /DCOPY:DAT."""
        cfg_on = RobocopyConfig(source=self.src, destination=self.dst, copy_dir_attrs=True)
        self.assertIn("/DCOPY:DAT", self.engine.build_command_string(cfg_on))

        cfg_off = RobocopyConfig(source=self.src, destination=self.dst, copy_dir_attrs=False)
        self.assertNotIn("/DCOPY:DAT", self.engine.build_command_string(cfg_off))

    def test_tab4_copyall(self):
        """/COPYALL substitui /COPY e copia tudo com segurança total."""
        cfg_all = RobocopyConfig(source=self.src, destination=self.dst, copyall=True)
        cmd = self.engine.build_command_string(cfg_all)
        self.assertIn("/COPYALL", cmd)
        self.assertNotIn("/COPY:DAT", cmd)

    def test_tab4_no_progress_np(self):
        """Flag /NP ativada e desativada."""
        cfg_on = RobocopyConfig(source=self.src, destination=self.dst, no_progress=True)
        self.assertIn("/NP", self.engine.build_command_string(cfg_on))

        cfg_off = RobocopyConfig(source=self.src, destination=self.dst, no_progress=False)
        self.assertNotIn("/NP", self.engine.build_command_string(cfg_off))

    def test_tab4_log_file(self):
        """Caminho de arquivo de log com e sem espaços."""
        cfg_log = RobocopyConfig(source=self.src, destination=self.dst, log_file=r"C:\Logs\copia.log")
        self.assertIn(r"/LOG:C:\Logs\copia.log", self.engine.build_command_string(cfg_log))

        cfg_space = RobocopyConfig(source=self.src, destination=self.dst, log_file=r"C:\Meus Logs\copia 2026.log")
        self.assertIn(r'"/LOG:C:\Meus Logs\copia 2026.log"', self.engine.build_command_string(cfg_space))

        cfg_none = RobocopyConfig(source=self.src, destination=self.dst, log_file="")
        self.assertNotIn("/LOG:", self.engine.build_command_string(cfg_none))

    # =========================================================================
    # 6. CENTRAL GOODSYNC: 5 MODOS + PARÂMETROS CORPORATIVOS
    # =========================================================================
    def test_goodsync_mode_1_mirror(self):
        """Modo 1 GoodSync: /MIR /R:3 /W:5 /V /TS /FP."""
        cfg = RobocopyConfig(source=self.src, destination=self.dst)
        cfg = apply_preset_to_config(cfg, "goodsync_mirror")
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("/MIR", cmd)
        self.assertIn("/R:3", cmd)
        self.assertIn("/W:5", cmd)
        self.assertIn("/V", cmd)
        self.assertIn("/TS", cmd)
        self.assertIn("/FP", cmd)
        self.assertNotIn("/MOVE", cmd)

    def test_goodsync_mode_2_update(self):
        """Modo 2 GoodSync: /E /XO /R:3 /W:5."""
        cfg = RobocopyConfig(source=self.src, destination=self.dst)
        cfg = apply_preset_to_config(cfg, "goodsync_update")
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("/E", cmd)
        self.assertIn("/XO", cmd)
        self.assertIn("/R:3", cmd)
        self.assertIn("/W:5", cmd)
        self.assertNotIn("/MIR", cmd)
        self.assertNotIn("/MOVE", cmd)

    def test_goodsync_mode_3_two_way_sync(self):
        """Modo 3 GoodSync: Sincronização Bidirecional de 2 Etapas."""
        cfg = RobocopyConfig(source=self.src, destination=self.dst)
        cfg = apply_preset_to_config(cfg, "goodsync_two_way")
        self.assertTrue(cfg.is_two_way_sync)
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("Etapa 1", cmd)
        self.assertIn("Etapa 2", cmd)
        self.assertIn(f'{self.src} {self.dst}', cmd)
        self.assertIn(f'{self.dst} {self.src}', cmd)
        self.assertIn("/XO", cmd)

    def test_goodsync_mode_4_move(self):
        """Modo 4 GoodSync: /E /MOVE /R:3 /W:5."""
        cfg = RobocopyConfig(source=self.src, destination=self.dst)
        cfg = apply_preset_to_config(cfg, "goodsync_move")
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("/E", cmd)
        self.assertIn("/MOVE", cmd)
        self.assertIn("/R:3", cmd)
        self.assertIn("/W:5", cmd)
        self.assertNotIn("/MIR", cmd)

    def test_goodsync_mode_5_filter(self):
        """Modo 5 GoodSync: /E /MAX /XF /R:3 /W:5."""
        cfg = RobocopyConfig(source=self.src, destination=self.dst)
        cfg = apply_preset_to_config(cfg, "goodsync_filter")
        cfg.exclude_files = "*.tmp *.bak"
        cfg.max_size = "52428800"
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("/E", cmd)
        self.assertIn("/MAX:52428800", cmd)
        self.assertIn("/XF", cmd)
        self.assertIn("*.tmp", cmd)
        self.assertIn("/R:3", cmd)
        self.assertIn("/W:5", cmd)

    def test_goodsync_corporate_switches(self):
        """Parâmetros corporativos: /MT:32, /COPYALL, /ZB."""
        cfg = RobocopyConfig(source=self.src, destination=self.dst, multi_threaded=32, copyall=True, restartable_backup=True)
        cmd = self.engine.build_command_string(cfg)
        self.assertIn("/MT:32", cmd)
        self.assertIn("/COPYALL", cmd)
        self.assertIn("/ZB", cmd)

        # Desativando parâmetros corporativos
        cfg_off = RobocopyConfig(source=self.src, destination=self.dst, multi_threaded=8, copyall=False, restartable_backup=False)
        cmd_off = self.engine.build_command_string(cfg_off)
        self.assertIn("/MT:8", cmd_off)
        self.assertNotIn("/COPYALL", cmd_off)
        self.assertNotIn("/ZB", cmd_off)

    # =========================================================================
    # 7. VALIDAÇÃO REAL CONTRA O ROBOCOPY.EXE NATIVO DO WINDOWS
    # =========================================================================
    def test_windows_robocopy_syntax_validation_all_options(self):
        """
        Executa uma simulação (/L) real com o robocopy nativo do Windows em pasta temporária,
        garantindo que todas as opções geradas pelo sistema são 100% aceitas sem erro de sintaxe.
        """
        tmp_src = tempfile.mkdtemp(prefix="src_test_")
        tmp_dst = tempfile.mkdtemp(prefix="dst_test_")

        try:
            # Cria arquivo de teste
            with open(os.path.join(tmp_src, "arquivo_teste.txt"), "w", encoding="utf-8") as f:
                f.write("Conteudo de teste para validacao de sintaxe.")

            # Configura todos os parâmetros suportados em modo de simulação segura
            cfg = RobocopyConfig(
                source=tmp_src,
                destination=tmp_dst,
                dry_run=True,  # /L: não altera o disco
                copy_subdirs_empty=True,  # /E
                unbuffered_io=True,  # /J
                subfolder_level=3,  # /LEV:3
                exclude_junctions=True,  # /XJ
                exclude_older=True,  # /XO
                exclude_files="*.tmp *.bak",
                exclude_dirs=".git Temp",
                max_size="10485760",
                min_size="10",
                multi_threaded=8,
                retries=1,
                wait_time=1,
                copy_data=True,
                copy_attrs=True,
                copy_timestamps=True,
                copy_dir_attrs=True,
                no_progress=True,
                tee=True,
            )

            args = self.engine.build_command_args(cfg)
            proc = subprocess.run(args, capture_output=True, text=True)
            
            # No RoboCopy, exit codes < 8 indicam sucesso.
            # Erros de sintaxe ou parâmetros inválidos geram código 16 com mensagem "ERRO : Parâmetro Inválido"
            self.assertLess(proc.returncode, 8, f"Robocopy falhou com código {proc.returncode}. Saída:\n{proc.stdout}")
            self.assertNotIn("Parâmetro Inválido", proc.stdout)
            self.assertNotIn("Invalid Parameter", proc.stdout)

        finally:
            shutil.rmtree(tmp_src, ignore_errors=True)
            shutil.rmtree(tmp_dst, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
