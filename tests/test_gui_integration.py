"""
Teste de Integração da Interface Gráfica (GUI) do RoboCopy Manager.
Instancia a janela, verifica a integridade de todas as abas, cartões,
e confirma que a alteração de cada variável da interface atualiza a configuração
e a linha de comando do RoboCopy.
"""

import unittest
import tkinter as tk
from robocopy_gui import RobocopyApp
from robocopy_engine import RobocopyConfig


class TestGUIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Instancia a aplicação CTk sem exibir na tela (withdrawn para ambiente de teste)
        cls.app = RobocopyApp()
        cls.app.withdraw()
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except Exception:
            pass

    def test_gui_components_exist(self):
        """Verifica se todos os componentes visuais principais e abas foram instanciados."""
        self.assertIsNotNone(self.app.entry_source)
        self.assertIsNotNone(self.app.entry_dest)
        self.assertIsNotNone(self.app.btn_run)
        self.assertIsNotNone(self.app.btn_simulate)
        self.assertIsNotNone(self.app.btn_cancel)
        self.assertIsNotNone(self.app.log_textbox)
        self.assertIsNotNone(self.app.cmd_display)

    def test_gui_source_dest_sync(self):
        """Testa digitação nos campos de origem e destino e reflexo no comando."""
        self.app.entry_source.delete(0, "end")
        self.app.entry_source.insert(0, r"C:\TesteOrigem")
        self.app.entry_dest.delete(0, "end")
        self.app.entry_dest.insert(0, r"D:\TesteDestino")

        self.app.update_command_preview()
        cmd = self.app.cmd_display.get()
        self.assertIn(r"C:\TesteOrigem", cmd)
        self.assertIn(r"D:\TesteDestino", cmd)

    def test_gui_tab1_structure_toggles(self):
        """Testa alternância de checkboxes na Aba 1: Estrutura."""
        # Marca E
        self.app.var_copy_e.set(True)
        self.app._on_chk_e_change()
        self.assertFalse(self.app.var_mirror.get())
        self.assertFalse(self.app.var_copy_s.get())
        self.assertIn("/E", self.app.cmd_display.get())

        # Marca S
        self.app.var_copy_s.set(True)
        self.app._on_chk_s_change()
        self.assertFalse(self.app.var_mirror.get())
        self.assertFalse(self.app.var_copy_e.get())
        self.assertIn("/S", self.app.cmd_display.get())

        # Marca MIR
        self.app.var_mirror.set(True)
        self.app._on_chk_mir_change()
        self.assertFalse(self.app.var_copy_e.get())
        self.assertFalse(self.app.var_copy_s.get())
        self.assertIn("/MIR", self.app.cmd_display.get())

        # Desmarca MIR e volta para E
        self.app.var_mirror.set(False)
        self.app.var_copy_e.set(True)
        self.app._on_chk_e_change()

    def test_gui_tab1_move_toggles(self):
        """Testa exclusividade entre /MOV e /MOVE na interface."""
        # Marca MOV
        self.app.var_move_files.set(True)
        self.app._on_chk_mov_change()
        self.assertFalse(self.app.var_move_all.get())
        self.assertIn("/MOV", self.app.cmd_display.get())

        # Marca MOVE
        self.app.var_move_all.set(True)
        self.app._on_chk_move_change()
        self.assertFalse(self.app.var_move_files.get())
        self.assertIn("/MOVE", self.app.cmd_display.get())

        # Desmarca MOVE
        self.app.var_move_all.set(False)
        self.app.update_command_preview()
        self.assertNotIn("/MOVE", self.app.cmd_display.get())

    def test_gui_tab2_filter_inputs(self):
        """Testa campos de exclusão de arquivos e pastas na Aba 2."""
        self.app.entry_xf.delete(0, "end")
        self.app.entry_xf.insert(0, "*.iso *.vmdk")
        self.app.entry_xd.delete(0, "end")
        self.app.entry_xd.insert(0, r".git $RECYCLE.BIN")
        self.app.update_command_preview()

        cmd = self.app.cmd_display.get()
        self.assertIn("/XF", cmd)
        self.assertIn("*.iso", cmd)
        self.assertIn("/XD", cmd)
        self.assertIn(".git", cmd)

    def test_gui_tab3_sliders(self):
        """Testa sliders de multithread, tentativas e tempo de espera."""
        self.app.slider_mt.set(16)
        self.app._on_mt_change(16)
        self.assertIn("16", self.app.lbl_mt.cget("text"))
        self.assertIn("/MT:16", self.app.cmd_display.get())

        self.app.slider_r.set(4)
        self.app._on_r_change(4)
        self.assertIn("/R:4", self.app.cmd_display.get())

        self.app.slider_w.set(8)
        self.app._on_w_change(8)
        self.assertIn("/W:8", self.app.cmd_display.get())

    def test_gui_tab4_security_checks(self):
        """Testa checkboxes de propriedades e log na Aba 4."""
        self.app.var_cp_s.set(True)
        self.app.update_command_preview()
        self.assertIn("/COPY:DATS", self.app.cmd_display.get())

        self.app.var_cp_s.set(False)
        self.app.update_command_preview()
        self.assertIn("/COPY:DAT", self.app.cmd_display.get())

    def test_gui_goodsync_panel_toggle(self):
        """Testa exibição e recolhimento do painel GoodSync."""
        # Abre painel GoodSync
        self.app._toggle_sync_panel()
        self.assertTrue(self.app.sync_visible)
        self.assertEqual(self.app.btn_toggle_sync.cget("text"), "Ocultar Sincronização GoodSync")

        # Seleciona modo Atualização
        self.app.var_goodsync_mode.set("goodsync_update")
        self.app._on_goodsync_mode_change()
        cmd_update = self.app.cmd_display.get()
        self.assertIn("/XO", cmd_update)
        self.assertIn("/E", cmd_update)

        # Fecha painel GoodSync
        self.app._toggle_sync_panel()
        self.assertFalse(self.app.sync_visible)
        self.assertEqual(self.app.btn_toggle_sync.cget("text"), "Sincronizar Pastas (Modo GoodSync)")

    def test_gui_seamless_transition_goodsync_and_advanced(self):
        """
        Valida a resolução do bug relatado pelo usuário:
        Abrir o Sincronizador GoodSync e em seguida clicar em Opções Avançadas
        deve alternar imediatamente sem exigir clique manual para sair e
        as opções avançadas devem alterar o comando instantaneamente.
        """
        # 1. Abre o painel GoodSync
        self.app._toggle_sync_panel()
        self.assertTrue(self.app.sync_visible)
        self.assertFalse(self.app.advanced_visible)

        # 2. Usuário clica diretamente em "Mostrar Opções Avançadas" SEM fechar o GoodSync manualmente
        self.app._toggle_advanced_panel()
        
        # 3. Deve fechar GoodSync e abrir Opções Avançadas automaticamente
        self.assertFalse(self.app.sync_visible, "Painel GoodSync deve ter sido fechado automaticamente")
        self.assertTrue(self.app.advanced_visible, "Opções Avançadas devem estar visíveis")
        self.assertEqual(self.app.btn_toggle_sync.cget("text"), "Sincronizar Pastas (Modo GoodSync)")
        self.assertEqual(self.app.btn_toggle_adv.cget("text"), "Ocultar Opções Avançadas")

        # 4. Modifica uma opção avançada (ex: marca /J e /MIR)
        self.app.var_mode_j.set(True)
        self.app.var_mirror.set(True)
        self.app._on_chk_mir_change()

        # 5. O comando preview DEVE atualizar instantaneamente com as opções avançadas
        cmd = self.app.cmd_display.get()
        self.assertIn("/J", cmd, "Opção /J deve aparecer imediatamente no comando sem exigir saída manual")
        self.assertIn("/MIR", cmd, "Opção /MIR deve aparecer imediatamente no comando")

        # 6. Usuário clica de volta em Sincronizar Pastas
        self.app._toggle_sync_panel()
        self.assertTrue(self.app.sync_visible)
        self.assertFalse(self.app.advanced_visible)

        # 7. Usuário seleciona um preset básico no topo
        self.app.selected_preset_key.set("copia_rapida")
        self.app._on_preset_selected()
        self.assertFalse(self.app.sync_visible, "Painel GoodSync deve fechar ao selecionar preset da tela inicial")
        self.assertIn("/S", self.app.cmd_display.get())

    def test_gui_light_and_dark_mode_switching(self):
        """Valida a alternância dinâmica entre modo Claro e Escuro sem erros visuais."""
        import customtkinter as ctk
        from robocopy_gui import ToolTip

        # 1. Muda para Modo Claro
        self.app._change_theme("Claro")
        self.app.update_idletasks()
        self.assertEqual(ctk.get_appearance_mode(), "Light")

        # 2. Testa ToolTip em modo Claro
        tip = ToolTip(self.app.btn_simulate, "Dica de teste modo claro")
        tip.show_tip()
        self.assertIsNotNone(tip.tip_window)
        tip.hide_tip()
        self.assertIsNone(tip.tip_window)

        # 3. Retorna para Modo Escuro
        self.app._change_theme("Escuro")
        self.app.update_idletasks()
        self.assertEqual(ctk.get_appearance_mode(), "Dark")

        # 4. Testa ToolTip em modo Escuro
        tip.show_tip()
        self.assertIsNotNone(tip.tip_window)
        tip.hide_tip()
        self.assertIsNone(tip.tip_window)


if __name__ == "__main__":
    unittest.main()

