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

    # =========================================================================
    # CONSOLE COLORIDO E PAINEL DE OCORRÊNCIAS
    # =========================================================================
    def test_gui_log_colorization(self):
        """Cada tipo de linha do log recebe a tag de cor correspondente."""
        self.app._clear_log()
        self.app._append_log_line("\t  Novo Arquivo  \t\t      1024\tC:\\Origem\\a.docx\n")
        self.app._append_log_line("\t*Arquivo EXTRA \t\t       512\tD:\\Destino\\b.bak\n")
        self.app._append_log_line("2025/09/03 10:12:35 ERRO 5 (0x00000005) Copiando Arquivo C:\\Origem\\c.dat\n")
        self.app.update_idletasks()

        conteudo = self.app.log_textbox.get("1.0", "end")
        self.assertIn("a.docx", conteudo)
        # As três categorias precisam estar efetivamente aplicadas no texto.
        for tag in ("cat_new_file", "cat_extra_file", "cat_error"):
            self.assertTrue(self.app.log_textbox.tag_ranges(tag), f"Tag {tag} não foi aplicada.")

    def test_gui_occurrences_panel_filters_the_log(self):
        """O painel de ocorrências isola apenas EXTRA, falhas e incompatibilidades."""
        self.app._clear_log()
        self.app._append_log_line("\t  Novo Arquivo  \t\t      1024\tC:\\Origem\\a.docx\n")
        self.app._append_log_line("\t*Arquivo EXTRA \t\t       512\tD:\\Destino\\b.bak\n")
        self.app._append_log_line("\t*INCOMPATÍVEL  \t\t          \tD:\\Destino\\config\n")
        self.app._append_log_line("2025/09/03 10:12:35 ERRO 5 (0x00000005) Copiando Arquivo C:\\Origem\\c.dat\n")
        self.app._append_log_line("Acesso negado.\n")
        self.app.update_idletasks()

        # O arquivo novo não é ocorrência; os outros três são.
        self.assertEqual(len(self.app.occurrences), 3)
        self.assertEqual(len(self.app.tree_occurrences.get_children()), 3)
        self.assertIn("Ocorrências: 3", self.app.lbl_occurrence_badge.cget("text"))

        # O caminho completo precisa aparecer na tabela.
        valores = [self.app.tree_occurrences.item(i, "values") for i in self.app.tree_occurrences.get_children()]
        caminhos = [v[2] for v in valores]
        self.assertIn(r"D:\Destino\b.bak", caminhos)
        self.assertIn(r"C:\Origem\c.dat", caminhos)

        # Filtros
        self.app.occurrence_filter.set("Arquivos EXTRA")
        self.app._on_occurrence_filter_change()
        self.assertEqual(len(self.app.tree_occurrences.get_children()), 1)

        self.app.occurrence_filter.set("Falhas")
        self.app._on_occurrence_filter_change()
        self.assertEqual(len(self.app.tree_occurrences.get_children()), 1)

        self.app.occurrence_filter.set("Todas")
        self.app._on_occurrence_filter_change()
        self.assertEqual(len(self.app.tree_occurrences.get_children()), 3)

        self.app._clear_log()
        self.assertEqual(len(self.app.occurrences), 0)

    def test_gui_status_explains_exit_code(self):
        """O rodapé mostra o resultado consolidado e a ajuda traz a explicação completa."""
        resumo = {
            "steps": [
                {"label": "Etapa 1 de 2 (Origem -> Destino)", "code": 2, "title": "Aviso", "desc": "x"},
                {"label": "Etapa 2 de 2 (Destino -> Origem)", "code": 1, "title": "Sucesso", "desc": "y"},
            ]
        }
        self.app._on_process_completed(1, "Sucesso", "Todos os arquivos foram copiados.", resumo)
        self.app.update_idletasks()

        status = self.app.lbl_status.cget("text")
        self.assertIn("[1]", status)
        self.assertIn("consolidado de 2 etapas", status)
        self.assertIn("Etapa 1 de 2", self.app.tip_status.text)
        self.assertIn("Etapa 2 de 2", self.app.tip_status.text)

    def test_gui_resolve_button_appears_only_with_divergences(self):
        """O atalho 'Resolver Divergências' só aparece quando há o que resolver."""
        self.app._clear_log()
        self.app._on_process_completed(1, "Sucesso", "Tudo copiado.", {"steps": []})
        self.app.update_idletasks()
        self.assertFalse(self.app.btn_resolve.winfo_manager())

        self.app._on_process_completed(2, "Aviso", "Existem arquivos extras.", {"steps": []})
        self.app.update_idletasks()
        self.assertTrue(self.app.btn_resolve.winfo_manager())

    # =========================================================================
    # FLAGS PERSONALIZADAS E SINCRONIZAÇÃO DUPLA
    # =========================================================================
    def test_gui_custom_flags_reach_the_command(self):
        """O campo de flags livres entra no comando e avisa sobre parâmetros perigosos."""
        self.app.var_extra_args.set("/FFT /Z")
        self.app.update_idletasks()
        comando = self.app.cmd_display.get()
        self.assertIn("/FFT", comando)
        self.assertIn("/Z", comando)
        self.assertEqual(self.app.extra_args_warning_labels[0].cget("text"), "")

        # Atalho adiciona e remove a mesma flag
        self.app._toggle_extra_flag("/PURGE")
        self.assertIn("/PURGE", self.app.var_extra_args.get())
        self.assertIn("APAGA", self.app.extra_args_warning_labels[0].cget("text"))
        self.app._toggle_extra_flag("/PURGE")
        self.assertNotIn("/PURGE", self.app.var_extra_args.get())

        self.app.var_extra_args.set("")
        self.app.update_idletasks()

    def test_gui_two_way_sync_preset(self):
        """O modo Sincronização Dupla gera as duas etapas no comando."""
        self.app.entry_source.delete(0, "end")
        self.app.entry_source.insert(0, r"C:\Origem")
        self.app.entry_dest.delete(0, "end")
        self.app.entry_dest.insert(0, r"D:\Destino")

        self.app.selected_preset_key.set("goodsync_two_way")
        self.app._on_preset_selected()
        self.app.update_idletasks()

        self.assertTrue(self.app.var_two_way.get())
        cfg = self.app._gather_config_from_ui()
        self.assertTrue(cfg.is_two_way_sync)

        comando = self.app.cmd_display.get()
        self.assertIn("Etapa 1", comando)
        self.assertIn("Etapa 2", comando)
        self.assertIn(r"robocopy C:\Origem D:\Destino", comando)
        self.assertIn(r"robocopy D:\Destino C:\Origem", comando)

        # Ativar espelhamento desliga a sincronização dupla (são incompatíveis)
        self.app.var_mirror.set(True)
        self.app._on_chk_mir_change()
        self.assertFalse(self.app.var_two_way.get())

        self.app.selected_preset_key.set("backup_incremental")
        self.app._on_preset_selected()

    # =========================================================================
    # CENTRAL DE SINCRONIZAÇÃO: TABELA DE DIVERGÊNCIAS E AÇÕES
    # =========================================================================
    def _carregar_analise(self, modo="goodsync_two_way"):
        from sync_analyzer import parse_analysis_output

        linhas = [
            "\t  Novo Arquivo  \t\t      1024\tC:\\Origem\\relatorio.docx",
            "\t  Mais Antigo   \t\t      4096\tC:\\Origem\\notas.txt",
            "\t*Arquivo EXTRA \t\t       512\tD:\\Destino\\antigo.bak",
            "\t*Pasta EXTRA   \t\t          \tD:\\Destino\\lixo\\",
            "\t*INCOMPATÍVEL  \t\t          \tD:\\Destino\\config",
        ]
        analise = parse_analysis_output(linhas, r"C:\Origem", r"D:\Destino", modo)
        self.app.var_goodsync_mode.set(modo)
        self.app._on_analysis_completed(analise)
        self.app.update_idletasks()
        return analise

    def test_gui_difference_table_shows_paths_and_actions(self):
        """A tabela informa qual arquivo, em que caminho, de que lado e com qual ação."""
        self._carregar_analise()

        self.assertEqual(len(self.app.tree_differences.get_children()), 5)
        self.assertEqual(self.app.btn_apply_plan.cget("state"), "normal")

        valores = {
            self.app.tree_differences.item(i, "values")[4]: self.app.tree_differences.item(i, "values")
            for i in self.app.tree_differences.get_children()
        }
        self.assertIn("relatorio.docx", valores)
        self.assertEqual(valores["relatorio.docx"][0], "Copiar para o Destino")
        self.assertEqual(valores["relatorio.docx"][1], "Novo Arquivo")
        self.assertEqual(valores["relatorio.docx"][2], "Origem")
        self.assertEqual(valores["antigo.bak"][2], "Destino")

        self.assertIn("divergência", self.app.lbl_diff_summary.cget("text"))
        self.assertIn("Plano atual", self.app.lbl_plan_preview.cget("text"))

    def test_gui_difference_actions_can_be_changed(self):
        """O usuário escolhe a ação de cada item, com bloqueio do que não faz sentido."""
        from sync_analyzer import ACTION_DELETE_DEST

        self._carregar_analise()
        indice = next(
            i for i in self.app.tree_differences.get_children()
            if self.app.tree_differences.item(i, "values")[4] == "antigo.bak"
        )
        self.app.tree_differences.selection_set((indice,))
        self.app._on_difference_select()
        self.assertIn("Existe hoje no destino", self.app.lbl_diff_detail.cget("text"))

        self.app._set_action_for_selected(ACTION_DELETE_DEST)
        self.assertEqual(self.app.tree_differences.item(indice, "values")[0], "Excluir do Destino")
        self.assertIn("1 exclusão", self.app.lbl_plan_preview.cget("text"))

        # Dois cliques alternam para a próxima ação possível
        self.app._cycle_difference_action()
        self.assertNotEqual(self.app.tree_differences.item(indice, "values")[0], "Excluir do Destino")

    def test_gui_difference_filters(self):
        """Os filtros da tabela separam origem, destino, atualizações e exclusões."""
        self._carregar_analise()

        self.app.difference_filter.set("Só na Origem")
        self.app._on_difference_filter_change()
        self.assertEqual(len(self.app.tree_differences.get_children()), 1)

        self.app.difference_filter.set("Só no Destino")
        self.app._on_difference_filter_change()
        self.assertEqual(len(self.app.tree_differences.get_children()), 2)

        self.app.difference_filter.set("Todas")
        self.app._on_difference_filter_change()
        self.assertEqual(len(self.app.tree_differences.get_children()), 5)

    def test_gui_mode_change_updates_suggested_actions(self):
        """Trocar o modo GoodSync re-sugere a ação de cada divergência já listada."""
        self._carregar_analise("goodsync_two_way")
        acoes_2vias = [self.app.tree_differences.item(i, "values")[0] for i in self.app.tree_differences.get_children()]
        self.assertIn("Copiar para a Origem", acoes_2vias)

        self.app.var_goodsync_mode.set("goodsync_mirror")
        self.app._on_goodsync_mode_change()
        self.app.update_idletasks()
        acoes_espelho = [self.app.tree_differences.item(i, "values")[0] for i in self.app.tree_differences.get_children()]
        self.assertIn("Excluir do Destino", acoes_espelho)
        self.assertNotIn("Copiar para a Origem", acoes_espelho)

        self.app.var_goodsync_mode.set("goodsync_two_way")
        self.app._on_goodsync_mode_change()

    def test_gui_analysis_clears_between_runs(self):
        """Uma nova análise sem divergências limpa a tabela e libera o estado anterior."""
        from sync_analyzer import parse_analysis_output

        self._carregar_analise()
        self.assertTrue(self.app.sync_differences)

        vazia = parse_analysis_output([], r"C:\Origem", r"D:\Destino", "goodsync_two_way")
        self.app._on_analysis_completed(vazia)
        self.app.update_idletasks()

        self.assertEqual(len(self.app.tree_differences.get_children()), 0)
        self.assertEqual(self.app.btn_apply_plan.cget("state"), "disabled")
        self.assertIn("idênticos", self.app.lbl_diff_summary.cget("text"))

    # =========================================================================
    # LAYOUT, ROLAGEM E CORREÇÕES VISUAIS
    # =========================================================================
    def _pump(self, milliseconds: int):
        """Roda o laço de eventos por um tempo, para os 'after' agendados dispararem."""
        import time
        limite = time.time() + (milliseconds / 1000.0)
        while time.time() < limite:
            self.app.update()
            time.sleep(0.01)

    def test_gui_monitor_is_always_visible(self):
        """O monitor não fica abaixo da dobra: a tela não tem rolagem de página."""
        self.assertFalse(hasattr(self.app, "main_scroll"),
                         "A rolagem da página inteira foi removida do layout.")
        self.app.update()
        # A janela está oculta durante os testes, então a verificação é pelo
        # gerenciador de geometria em vez da visibilidade efetiva na tela.
        self.assertEqual(self.app.monitor_card.winfo_manager(), "pack")
        self.assertTrue(self.app.monitor_card.pack_info().get("expand"),
                        "O monitor precisa receber todo o espaço restante da janela.")

    def test_gui_rapid_tab_switching_keeps_content_visible(self):
        """
        Duas trocas de aba seguidas não podem deixar a área em branco.

        O CTkTabview agenda uma limpeza 100 ms após cada troca, que esconde as
        abas que não estavam selecionadas naquele instante. Sem tratamento, a
        limpeza da primeira troca apaga a aba escolhida pela segunda.
        """
        from robocopy_gui import TAB_CONSOLE, TAB_DIFFERENCES, TAB_OCCURRENCES

        self.app._show_tab(TAB_OCCURRENCES)
        self.app._show_tab(TAB_DIFFERENCES)
        self.app._show_tab(TAB_CONSOLE)
        self._pump(400)

        self.assertEqual(self.app.monitor_tabs.get(), TAB_CONSOLE)
        self.assertTrue(
            self.app.monitor_tabs.tab(TAB_CONSOLE).winfo_manager(),
            "A aba escolhida ficou escondida após trocas em sequência."
        )
        # E as abas que não foram escolhidas continuam recolhidas.
        for outra in (TAB_OCCURRENCES, TAB_DIFFERENCES):
            self.assertFalse(self.app.monitor_tabs.tab(outra).winfo_manager())

    def test_gui_tooltip_never_leaves_the_screen(self):
        """A dica é reposicionada e quebrada em linhas para caber na tela."""
        from robocopy_gui import ToolTip

        self.app.update()
        texto_longo = ("Texto bem longo de propósito, repetido para forçar a quebra de linha "
                       "e garantir que a janela da dica não ultrapasse a borda do monitor. ") * 3

        # Elemento colado na borda direita da janela
        alvo = self.app.theme_menu
        dica = ToolTip(alvo, texto_longo)
        dica.show_tip()
        self.app.update()

        janela = dica.tip_window
        self.assertIsNotNone(janela)
        x, y = janela.winfo_rootx(), janela.winfo_rooty()
        largura, altura = janela.winfo_reqwidth(), janela.winfo_reqheight()
        tela_w, tela_h = janela.winfo_screenwidth(), janela.winfo_screenheight()

        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x + largura, tela_w, "A dica saiu pela borda direita da tela.")
        self.assertLessEqual(y + altura, tela_h, "A dica saiu pela borda inferior da tela.")
        self.assertLessEqual(largura, ToolTip.DEFAULT_WRAPLENGTH + 40,
                             "A dica não quebrou o texto em várias linhas.")
        dica.hide_tip()

    def test_gui_autoscroll_controls(self):
        """O console acompanha a última linha e o usuário pode pausar esse comportamento."""
        self.app._clear_log()
        self.assertTrue(self.app.var_autoscroll.get())

        for i in range(200):
            self.app._append_log_line(f"linha {i}\n")
        self.app.update()
        self.assertAlmostEqual(self.app.log_textbox.yview()[1], 1.0, places=2)

        # Ir para o início pausa o acompanhamento
        self.app._scroll_log_to_start()
        self.app.update()
        self.assertFalse(self.app.var_autoscroll.get())
        self.assertLess(self.app.log_textbox.yview()[0], 0.05)

        # Com o acompanhamento pausado, novas linhas não arrastam a visualização
        posicao = self.app.log_textbox.yview()[0]
        self.app._append_log_line("nova linha enquanto o usuário lê o começo\n")
        self.app.update()
        self.assertAlmostEqual(self.app.log_textbox.yview()[0], posicao, places=2)

        # Voltar ao fim religa o acompanhamento
        self.app._scroll_log_to_end()
        self.app.update()
        self.assertTrue(self.app.var_autoscroll.get())
        self.app._clear_log()

    def test_gui_mode_selector_and_preset_stay_in_sync(self):
        """O seletor compacto de operação e a predefinição apontam sempre para o mesmo modo."""
        self.app.selected_preset_key.set("espelhamento")
        self.app._on_preset_selected()
        self.app.update()
        self.assertEqual(self.app.mode_selector.get(), "Espelhamento")
        self.assertIn("Espelhamento", self.app.lbl_mode_description.cget("text"))

        # Clicar no seletor também troca a predefinição
        self.app._on_mode_segment_change("Sincronização Dupla")
        self.app.update()
        self.assertEqual(self.app.selected_preset_key.get(), "goodsync_two_way")
        self.assertTrue(self.app.var_two_way.get())

        self.app._on_mode_segment_change("Backup Seguro")
        self.assertEqual(self.app.selected_preset_key.get(), "backup_incremental")

    def test_gui_panels_open_in_their_own_window(self):
        """
        Os painéis de opções abrem em janela própria com rolagem: encaixados na
        tela principal, eles empurravam o monitor (e o rodapé) para fora em
        telas de menor altura, sem deixar o usuário rolar até o resto.
        """
        # As janelas existem desde o início, para que todos os controles que a
        # configuração lê estejam disponíveis mesmo com os painéis fechados.
        self.assertIsNotNone(self.app.advanced_window)
        self.assertIsNotNone(self.app.sync_window)
        self.assertEqual(self.app.advanced_window.state(), "withdrawn")
        self.assertEqual(self.app.sync_window.state(), "withdrawn")

        # O conteúdo fica em um quadro rolável dentro da janela.
        self.assertTrue(hasattr(self.app.advanced_window, "body"))
        self.assertIs(self.app.advanced_container, self.app.advanced_window.body)
        self.assertIs(self.app.sync_container, self.app.sync_window.body)

        self.app._toggle_advanced_panel()
        self.app.update()
        self.assertTrue(self.app.advanced_visible)
        self.assertEqual(self.app.advanced_window.state(), "normal")

        # Abrir a Central fecha as opções avançadas (as duas disputam a config).
        self.app._toggle_sync_panel()
        self.app.update()
        self.assertFalse(self.app.advanced_visible)
        self.assertEqual(self.app.advanced_window.state(), "withdrawn")
        self.assertEqual(self.app.sync_window.state(), "normal")

        self.app._toggle_sync_panel()
        self.app.update()
        self.assertFalse(self.app.sync_visible)
        self.assertEqual(self.app.sync_window.state(), "withdrawn")

    def test_gui_action_buttons_stay_inside_the_window(self):
        """O rodapé de ações é montado antes do miolo e nunca é empurrado para fora."""
        self.app.update_idletasks()
        ordem = list(self.app.pack_slaves())

        self.assertIn(self.app.footer_frame, ordem)
        self.assertIn(self.app.main_container, ordem)
        self.assertLess(
            ordem.index(self.app.footer_frame),
            ordem.index(self.app.main_container),
            "O rodapé precisa ser empacotado antes do container expansível, "
            "senão ele é empurrado para fora da janela em telas de menor altura."
        )
        self.assertTrue(self.app.main_container.pack_info().get("expand"))
        self.assertEqual(self.app.footer_frame.pack_info().get("side"), "bottom")

    def test_gui_sync_filters_only_show_in_filter_mode(self):
        """Os campos de filtro só aparecem no modo que realmente os utiliza."""
        if not self.app.sync_visible:
            self.app._toggle_sync_panel()

        self.app.var_goodsync_mode.set("goodsync_mirror")
        self.app._on_goodsync_mode_change()
        self.app.update()
        self.assertFalse(self.app.sync_filter_box.winfo_manager())

        self.app.var_goodsync_mode.set("goodsync_filter")
        self.app._on_goodsync_mode_change()
        self.app.update()
        self.assertTrue(self.app.sync_filter_box.winfo_manager())

        self.app.var_goodsync_mode.set("goodsync_two_way")
        self.app._on_goodsync_mode_change()
        if self.app.sync_visible:
            self.app._toggle_sync_panel()


if __name__ == "__main__":
    unittest.main()

