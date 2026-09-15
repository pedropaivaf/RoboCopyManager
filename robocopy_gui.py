"""
RoboCopy Manager - Utilitário Profissional de Cópia, Backup e Sincronização.
Compatível com Windows 10 e Windows 11.
Interface minimalista, tela cheia nativa, modo simplificado por padrão e opções avançadas sob demanda.
"""

import csv
import os
import subprocess
import sys
import ctypes
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk

from robocopy_engine import (
    OCCURRENCE_CATEGORIES,
    RobocopyConfig,
    RobocopyEngine,
    analyze_extra_args,
    classify_log_line,
    DESTRUCTIVE_FLAGS,
    explain_exit_code,
    format_size,
    interpret_exit_code,
    parse_log_entry,
)
from presets import PRESETS, apply_preset_to_config, export_profile_to_json, import_profile_from_json
from sync_analyzer import (
    ACTION_COPY_TO_DEST,
    ACTION_COPY_TO_SOURCE,
    ACTION_DELETE_DEST,
    ACTION_LABELS,
    ACTION_SKIP,
    SyncAnalyzer,
    SyncPlanExecutor,
    build_execution_plan,
    suggest_action,
)

# Cor de cada tipo de linha do log, no formato (tema claro, tema escuro).
LOG_TAG_COLORS = {
    "new_file": ("#15803d", "#4ade80"),
    "new_dir": ("#0f766e", "#5eead4"),
    "extra_file": ("#b45309", "#facc15"),
    "extra_dir": ("#b45309", "#facc15"),
    "lonely": ("#b45309", "#facc15"),
    "mismatch": ("#c2410c", "#fb923c"),
    "newer": ("#0369a1", "#38bdf8"),
    "older": ("#7c3aed", "#c4b5fd"),
    "changed": ("#0369a1", "#38bdf8"),
    "tweaked": ("#0f766e", "#5eead4"),
    "same": ("#94a3b8", "#64748b"),
    "deleted": ("#be123c", "#fb7185"),
    "error": ("#dc2626", "#f87171"),
    "warning": ("#b45309", "#facc15"),
    "step": ("#1d4ed8", "#93c5fd"),
    "summary": ("#334155", "#cbd5e1"),
    "banner": ("#94a3b8", "#64748b"),
    "progress": ("#94a3b8", "#64748b"),
}

# Identidade da aplicacao no Windows: sem isso a barra de tarefas mostra o icone
# do pythonw.exe em vez da logo do RoboCopy Manager.
APP_MODEL_ID = "PedroPaiva.RoboCopyManager.GUI.1"

# Abas do monitor (o nome e usado para alternar automaticamente entre elas).
TAB_CONSOLE = "Console ao Vivo"
TAB_OCCURRENCES = "Ocorrências"
TAB_DIFFERENCES = "Divergências"

# Filtros do painel de ocorrências.
OCCURRENCE_FILTERS = ["Todas", "Arquivos EXTRA", "Falhas", "Incompatibilidades"]

# Filtros da tabela de divergências da Central de Sincronização.
DIFFERENCE_FILTERS = [
    "Todas",
    "Só na Origem",
    "Só no Destino",
    "Atualizações",
    "Marcadas para excluir",
]

# Atalhos de flags avançadas oferecidos ao lado do campo de parâmetros livres.
EXTRA_FLAG_SHORTCUTS = [
    ("/PURGE", "Apaga do destino os arquivos que não existem mais na origem, sem espelhar o resto."),
    ("/MIR", "Espelhamento completo: copia tudo e apaga do destino o que não está na origem."),
    ("/FFT", "Usa tolerância de 2 segundos nos horários. Essencial para pendrives, NAS, Linux e discos FAT32."),
    ("/Z", "Modo reiniciável: continua a transferência de onde parou se a rede cair."),
    ("/XX", "Ignora completamente os arquivos extras do destino (nem lista, nem apaga)."),
    ("/SL", "Copia os links simbólicos como links, em vez de copiar o conteúdo apontado."),
    ("/NOSD", "Não exibe o diretório de origem no relatório."),
    ("/256", "Desativa o suporte a caminhos com mais de 256 caracteres."),
]

# Limites de memória da interface para logs muito longos.
MAX_OCCURRENCE_ROWS = 5000
MAX_LOG_LINES = 8000
LOG_TRIM_BLOCK = 2000

# Suporte opcional a Drag & Drop
try:
    import windnd
    HAS_WINDND = True
except ImportError:
    HAS_WINDND = False


class ToolTip:
    """
    Dica de contexto que sempre cabe na tela: o texto longo quebra em várias
    linhas e a janela é reposicionada quando encostaria em qualquer borda.
    """

    # Largura máxima da dica antes de quebrar a linha.
    DEFAULT_WRAPLENGTH = 460

    # Folga mínima entre a dica e a borda da tela.
    SCREEN_MARGIN = 10

    def __init__(self, widget, text: str, wraplength: int = 0):
        self.widget = widget
        self.text = text
        self.wraplength = wraplength or self.DEFAULT_WRAPLENGTH
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def set_text(self, text: str):
        """Troca o conteúdo da dica (usado para explicar o resultado da última execução)."""
        self.text = text
        if self.tip_window:
            self.hide_tip()

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return

        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.attributes("-topmost", True)
        # Posiciona só depois de medir, para a dica não piscar no lugar errado.
        tw.wm_geometry("+-1000+-1000")

        is_light = ctk.get_appearance_mode() == "Light"
        bg_col = "#ffffff" if is_light else "#1e293b"
        fg_col = "#0f172a" if is_light else "#f8fafc"

        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background=bg_col,
            foreground=fg_col,
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9),
            padx=10,
            pady=6,
            wraplength=self.wraplength
        )
        label.pack()

        self._place_within_screen(tw)

    def _place_within_screen(self, tw):
        """Mantém a dica inteira dentro da área visível do monitor."""
        try:
            tw.update_idletasks()
            tip_width = tw.winfo_reqwidth()
            tip_height = tw.winfo_reqheight()
            screen_width = tw.winfo_screenwidth()
            screen_height = tw.winfo_screenheight()

            widget_x = self.widget.winfo_rootx()
            widget_y = self.widget.winfo_rooty()
            widget_height = self.widget.winfo_height()

            x = widget_x + 20
            y = widget_y + widget_height + 6

            # Encostou na direita: alinha pela borda em vez de sair da tela.
            if x + tip_width > screen_width - self.SCREEN_MARGIN:
                x = screen_width - tip_width - self.SCREEN_MARGIN
            if x < self.SCREEN_MARGIN:
                x = self.SCREEN_MARGIN

            # Não cabe embaixo: mostra acima do item apontado.
            if y + tip_height > screen_height - self.SCREEN_MARGIN:
                above = widget_y - tip_height - 6
                y = above if above >= self.SCREEN_MARGIN else max(
                    self.SCREEN_MARGIN, screen_height - tip_height - self.SCREEN_MARGIN
                )

            tw.wm_geometry(f"+{int(x)}+{int(y)}")
        except Exception:
            # Em qualquer imprevisto, volta ao posicionamento simples ao lado do cursor.
            try:
                tw.wm_geometry(f"+{self.widget.winfo_rootx() + 20}+{self.widget.winfo_rooty() + 20}")
            except Exception:
                pass

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


def is_admin() -> bool:
    """Verifica se o processo possui privilégios de Administrador no Windows."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def restart_as_admin():
    """Reinicia a aplicação solicitando elevação de privilégios pelo UAC do Windows."""
    try:
        script = os.path.abspath(sys.argv[0])
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
        sys.exit(0)
    except Exception as ex:
        messagebox.showerror("Acesso Negado", f"Não foi possível reiniciar como Administrador:\n{ex}")


class RobocopyApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.engine = RobocopyEngine()
        self.analyzer = SyncAnalyzer()
        self.plan_executor = SyncPlanExecutor()
        self.config = RobocopyConfig()
        self.advanced_visible = False
        self.sync_visible = False

        # Estado do painel de ocorrências e da análise de divergências
        self.occurrences = []
        self.sync_differences = []
        self.sync_analysis = None
        self._analyze_buttons = []
        self.last_summary = {}
        self.last_exit_code = None
        self.is_busy = False

        # Flags livres do RoboCopy digitadas pelo usuário (compartilhadas entre painéis)
        self.var_extra_args = tk.StringVar(value="")
        self.var_two_way = tk.BooleanVar(value=False)
        self.extra_args_warning_labels = []

        # Configuração da Janela
        self.title("RoboCopy Manager - Transferência e Backup de Arquivos")
        self.minsize(1020, 720)

        # Inicia automaticamente em tela cheia (maximizado no Windows)
        try:
            self.state("zoomed")
        except Exception:
            # Ambientes nao-Windows (ou sessoes de teste) nao suportam o estado "zoomed"
            try:
                self.attributes("-zoomed", True)
            except Exception:
                pass

        # Configuração de Tema Profissional
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Ícone da Janela e da Barra de Tarefas
        self._apply_app_icon()

        # Criação da Interface
        self._build_header()
        self._build_main_container()
        self._build_footer()

        # Aparência das tabelas (ocorrências e divergências)
        self._configure_tree_style()

        # Inicializa valores e modo simplificado padrão
        self._sync_ui_from_config(self.config)
        self.update_command_preview()

        # A partir daqui qualquer mudança nas flags livres atualiza a prévia do comando
        self.var_extra_args.trace_add("write", lambda *_args: self._on_extra_args_change())

        if HAS_WINDND:
            self._setup_drag_and_drop()

    def _find_icon_file(self) -> str:
        """Localiza o ícone do aplicativo, funcione ele a partir do código ou empacotado."""
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        for name in ("desktop_icon.ico", "app_icon.ico"):
            candidate = os.path.join(base_dir, "assets", name)
            if os.path.exists(candidate):
                return candidate
        return ""

    def _apply_app_icon(self):
        """
        Aplica a logo do RoboCopy Manager na janela e na barra de tarefas.

        Ao rodar pelo interpretador (é o caso do atalho do PowerShell, que executa
        pythonw.exe), o Windows agrupa a janela pelo ícone do próprio Python. Definir
        um AppUserModelID próprio faz o sistema usar o ícone da aplicação.
        """
        if os.name == "nt":
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_MODEL_ID)
            except Exception:
                pass

        icon_path = self._find_icon_file()
        if not icon_path:
            return

        self._icon_path = icon_path
        try:
            # 'default' propaga o ícone para as janelas secundárias (diálogos).
            self.iconbitmap(default=icon_path)
        except Exception:
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # Alguns gerenciadores de janela só aceitam o ícone depois que a janela existe.
        self.after(200, self._reapply_app_icon)

    def _reapply_app_icon(self):
        icon_path = getattr(self, "_icon_path", "")
        if not icon_path or not os.path.exists(icon_path):
            return
        try:
            self.iconbitmap(default=icon_path)
        except Exception:
            pass

    def _create_info_badge(self, parent, tip_text: str):
        """Cria um indicador minimalista '(i)' que exibe dica ao passar o mouse."""
        badge = ctk.CTkLabel(
            parent,
            text="(i)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#475569", "#94a3b8"),
            fg_color=("#e2e8f0", "#1e293b"),
            corner_radius=4,
            width=22,
            height=20,
            cursor="hand2"
        )
        ToolTip(badge, tip_text)
        return badge

    def _build_header(self):
        """Cabeçalho minimalista com status e opções de sistema."""
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(14, 6))

        # Título institucional
        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left")

        lbl_title = ctk.CTkLabel(
            title_box,
            text="RoboCopy Manager",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        )
        lbl_title.pack(anchor="w")

        lbl_sub = ctk.CTkLabel(
            title_box,
            text="Transferência rápida, backup seguro e sincronização bidirecional no Windows",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("#64748b", "#9e9e9e")
        )
        lbl_sub.pack(anchor="w")

        # Controles à direita
        right_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        right_box.pack(side="right")

        if is_admin():
            admin_indicator = ctk.CTkLabel(
                right_box,
                text="Modo Administrador Ativo",
                fg_color=("#dcfce7", "#14532d"),
                text_color=("#15803d", "#86efac"),
                corner_radius=4,
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                padx=10, pady=3
            )
            admin_indicator.pack(side="left", padx=10)
        else:
            btn_elevate = ctk.CTkButton(
                right_box,
                text="Executar como Administrador",
                command=restart_as_admin,
                fg_color=("#e2e8f0", "#2b2b2b"),
                hover_color=("#cbd5e1", "#3d3d3d"),
                text_color=("#0f172a", "#e0e0e0"),
                height=28,
                font=ctk.CTkFont(family="Segoe UI", size=11)
            )
            btn_elevate.pack(side="left", padx=10)
            ToolTip(btn_elevate, "Reinicia o sistema com privilégios elevados para permitir cópias de pastas protegidas do Windows.")

        ctk.CTkLabel(right_box, text="Tema:", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=("#64748b", "#9e9e9e")).pack(side="left", padx=(6, 4))
        
        self.theme_menu = ctk.CTkOptionMenu(
            right_box,
            values=["Escuro", "Claro", "Sistema"],
            command=self._change_theme,
            width=90,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        self.theme_menu.set("Escuro")
        self.theme_menu.pack(side="left")

    def _change_theme(self, choice: str):
        map_theme = {"Escuro": "Dark", "Claro": "Light", "Sistema": "System"}
        ctk.set_appearance_mode(map_theme.get(choice, "Dark"))
        # As cores do console e das tabelas não seguem o tema automaticamente
        self._apply_log_tag_colors()
        self._configure_tree_style()

    def _build_main_container(self):
        """
        Layout de altura fixa: a configuração fica compacta no topo e o monitor
        ocupa todo o resto da janela. Assim a saída do RoboCopy está sempre
        visível, sem que o usuário precise rolar a tela para acompanhá-la.
        """
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=24, pady=4)

        # Área de configuração (topo): ocupa apenas a altura de que precisa.
        self.config_area = ctk.CTkFrame(container, fg_color="transparent")
        self.config_area.pack(fill="x", side="top")

        # 1. Painel de Pastas (Origem / Destino)
        self._build_paths_card()

        # 2. Linha de Modo de Operação (compacta)
        self._build_modes_card()

        # 3. Barra de Botões Alternadores (Avançado e Sincronizar Pastas)
        self._build_toggle_bar()

        # 4 e 5. Painéis sob demanda. São quadros simples, sem rolagem própria:
        # rolagem dentro de rolagem é justamente o que fazia a tela travar.
        self.sync_container = ctk.CTkFrame(self.config_area, fg_color="transparent")
        self._build_sync_panel()

        self.advanced_container = ctk.CTkFrame(self.config_area, fg_color="transparent")
        self._build_advanced_tabs()

        # 6. Monitor: recebe todo o espaço restante da janela.
        self.monitor_parent = container
        self._build_live_monitor_card()

    def _build_paths_card(self):
        """Card para definir pasta de Origem e Destino com botões diretos."""
        card = ctk.CTkFrame(self.config_area, corner_radius=6, border_width=1, border_color=("#e2e8f0", "#333333"), fg_color=("#ffffff", "#181818"))
        card.pack(fill="x", pady=(0, 6))
        card.grid_columnconfigure(1, weight=1)

        # Origem
        lbl_src_box = ctk.CTkFrame(card, fg_color="transparent")
        lbl_src_box.grid(row=0, column=0, padx=(16, 6), pady=(14, 4), sticky="w")
        ctk.CTkLabel(lbl_src_box, text="Origem (De onde copiar):", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(side="left")
        self._create_info_badge(lbl_src_box, "Pasta original onde estão os arquivos que você deseja transferir ou salvar.").pack(side="left", padx=6)

        self.entry_source = ctk.CTkEntry(
            card,
            placeholder_text="Selecione, cole ou arraste a pasta aqui (ex: C:\\MeusArquivos ou \\\\servidor\\pasta)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=34
        )
        self.entry_source.grid(row=0, column=1, padx=6, pady=(14, 4), sticky="ew")
        self.entry_source.bind("<KeyRelease>", lambda e: self.update_command_preview())

        btn_paste_src = ctk.CTkButton(
            card, text="Colar", width=65, height=34,
            fg_color=("#e2e8f0", "#2f353a"), hover_color=("#cbd5e1", "#3e444a"),
            text_color=("#0f172a", "#ffffff"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=lambda: self._paste_to_entry(self.entry_source)
        )
        btn_paste_src.grid(row=0, column=2, padx=4, pady=(14, 4))

        btn_browse_src = ctk.CTkButton(
            card, text="Procurar...", width=95, height=34,
            fg_color="#0f6cbd", hover_color="#115ea3",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._browse_source
        )
        btn_browse_src.grid(row=0, column=3, padx=(4, 16), pady=(14, 4))

        # Botão Inverter no meio
        mid_box = ctk.CTkFrame(card, fg_color="transparent")
        mid_box.grid(row=1, column=0, columnspan=4, padx=16, pady=2, sticky="ew")

        btn_swap = ctk.CTkButton(
            mid_box, text="Inverter Origem / Destino", width=180, height=26,
            fg_color=("#e2e8f0", "#262626"), hover_color=("#cbd5e1", "#333333"),
            text_color=("#0f172a", "#d1d5db"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._swap_paths
        )
        btn_swap.pack(side="left")

        # Destino
        lbl_dst_box = ctk.CTkFrame(card, fg_color="transparent")
        lbl_dst_box.grid(row=2, column=0, padx=(16, 6), pady=(4, 14), sticky="w")
        ctk.CTkLabel(lbl_dst_box, text="Destino (Para onde enviar):", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(side="left")
        self._create_info_badge(lbl_dst_box, "Pasta de destino onde os arquivos serão copiados. Se ela ainda não existir, o sistema cria automaticamente.").pack(side="left", padx=6)

        self.entry_dest = ctk.CTkEntry(
            card,
            placeholder_text="Selecione, cole ou arraste a pasta de destino (ex: D:\\Backup ou Pendrive)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=34
        )
        self.entry_dest.grid(row=2, column=1, padx=6, pady=(4, 14), sticky="ew")
        self.entry_dest.bind("<KeyRelease>", lambda e: self.update_command_preview())

        btn_paste_dst = ctk.CTkButton(
            card, text="Colar", width=65, height=34,
            fg_color=("#e2e8f0", "#2f353a"), hover_color=("#cbd5e1", "#3e444a"),
            text_color=("#0f172a", "#ffffff"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=lambda: self._paste_to_entry(self.entry_dest)
        )
        btn_paste_dst.grid(row=2, column=2, padx=4, pady=(4, 14))

        btn_browse_dst = ctk.CTkButton(
            card, text="Procurar...", width=95, height=34,
            fg_color="#0f6cbd", hover_color="#115ea3",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._browse_destination
        )
        btn_browse_dst.grid(row=2, column=3, padx=(4, 16), pady=(4, 14))

    def _build_modes_card(self):
        """
        Seleção de modo em uma única linha. A descrição do modo escolhido aparece
        logo abaixo, então nenhuma informação se perde e a tela fica limpa.
        """
        card = ctk.CTkFrame(self.config_area, corner_radius=6, border_width=1, border_color=("#e2e8f0", "#333333"), fg_color=("#ffffff", "#181818"))
        card.pack(fill="x", pady=(0, 6))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(10, 2))

        ctk.CTkLabel(
            row,
            text="Operação:",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        ).pack(side="left", padx=(0, 10))

        self.selected_preset_key = tk.StringVar(value="backup_incremental")

        # (chave do preset, rótulo curto do seletor, descrição completa)
        self.preset_options = [
            (
                "backup_incremental",
                "Backup Seguro",
                "Backup Seguro (recomendado): copia arquivos novos ou alterados. "
                "NUNCA apaga nada que já exista na pasta de destino."
            ),
            (
                "copia_rapida",
                "Cópia Rápida",
                "Cópia Rápida: copia tudo com velocidade máxima multithread, "
                "ignorando subpastas que estejam vazias."
            ),
            (
                "espelhamento",
                "Espelhamento",
                "Espelhamento Idêntico: faz o destino ficar 100% igual à origem. "
                "ATENÇÃO: o que você apagou na origem será apagado no destino também."
            ),
            (
                "mover",
                "Mover",
                "Mover Arquivos (recortar): transfere tudo para o destino e apaga "
                "os arquivos da origem após a cópia com êxito."
            ),
            (
                "goodsync_two_way",
                "Sincronização Dupla",
                "Sincronização Dupla (2 vias, em um clique): Etapa 1 Origem ➔ Destino e "
                "Etapa 2 Destino ➔ Origem. Nada é apagado e as duas pastas terminam iguais."
            ),
        ]

        self.preset_label_by_key = {key: label for key, label, _desc in self.preset_options}
        self.preset_key_by_label = {label: key for key, label, _desc in self.preset_options}
        self.preset_description_by_key = {key: desc for key, _label, desc in self.preset_options}

        self.mode_selector = ctk.CTkSegmentedButton(
            row,
            values=[label for _key, label, _desc in self.preset_options],
            command=self._on_mode_segment_change,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=30
        )
        self.mode_selector.set(self.preset_label_by_key["backup_incremental"])
        self.mode_selector.pack(side="left")

        self.lbl_mode_description = ctk.CTkLabel(
            card,
            text=self.preset_description_by_key["backup_incremental"],
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#475569", "#94a3b8"),
            justify="left",
            anchor="w",
            wraplength=1200
        )
        self.lbl_mode_description.pack(fill="x", padx=16, pady=(2, 10))

    def _on_mode_segment_change(self, label: str):
        """Traduz o rótulo curto do seletor para a predefinição correspondente."""
        key = self.preset_key_by_label.get(label)
        if not key:
            return
        self.selected_preset_key.set(key)
        self._on_preset_selected()

    def _build_toggle_bar(self):
        """Barra de alternância com botões para Opções Avançadas e Central GoodSync."""
        toggle_bar = ctk.CTkFrame(self.config_area, fg_color="transparent")
        toggle_bar.pack(fill="x", pady=(2, 6))

        self.btn_toggle_adv = ctk.CTkButton(
            toggle_bar,
            text="Mostrar Opções Avançadas",
            height=30,
            fg_color=("#e2e8f0", "#1e293b"),
            hover_color=("#cbd5e1", "#334155"),
            text_color=("#0f172a", "#94a3b8"),
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._toggle_advanced_panel
        )
        self.btn_toggle_adv.pack(side="left")

        self._create_info_badge(
            toggle_bar,
            "Clique para exibir filtros de exclusão de arquivos, ajuste de velocidade de threads, permissões NTFS e visualização do comando."
        ).pack(side="left", padx=(6, 16))

        # Botão dedicado para Sincronizar Pastas (Modo GoodSync)
        self.btn_toggle_sync = ctk.CTkButton(
            toggle_bar,
            text="Sincronizar Pastas (Modo GoodSync)",
            height=30,
            fg_color=("#0284c7", "#0369a1"),
            hover_color=("#0369a1", "#0284c7"),
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._toggle_sync_panel
        )
        self.btn_toggle_sync.pack(side="left")

        self._create_info_badge(
            toggle_bar,
            "Abre a central dedicada para sincronização de diretórios no padrão GoodSync (Espelhamento Rígido, Atualização, Sincronização Bidirecional de 2 Vias, Mover e Filtros)."
        ).pack(side="left", padx=6)

    def _toggle_advanced_panel(self):
        """Alterna a exibição das abas avançadas de forma exclusiva."""
        if self.advanced_visible:
            self.advanced_container.pack_forget()
            self.btn_toggle_adv.configure(text="Mostrar Opções Avançadas")
            self.advanced_visible = False
            self.update_command_preview()
        else:
            # Se a central GoodSync estiver aberta, fecha-a para evitar conflito de opções
            if self.sync_visible:
                self.sync_container.pack_forget()
                self.btn_toggle_sync.configure(text="Sincronizar Pastas (Modo GoodSync)")
                self.sync_visible = False

            self.advanced_container.pack(fill="x", pady=(4, 8))
            self.btn_toggle_adv.configure(text="Ocultar Opções Avançadas")
            self.advanced_visible = True
            self.update_command_preview()

    def _toggle_sync_panel(self):
        """Alterna a exibição do painel dedicado GoodSync de forma exclusiva."""
        if self.sync_visible:
            self.sync_container.pack_forget()
            self.btn_toggle_sync.configure(text="Sincronizar Pastas (Modo GoodSync)")
            self.sync_visible = False
            self.update_command_preview()
        else:
            # Se as opções avançadas estiverem abertas, fecha-as para que a central GoodSync assuma o controle
            if self.advanced_visible:
                self.advanced_container.pack_forget()
                self.btn_toggle_adv.configure(text="Mostrar Opções Avançadas")
                self.advanced_visible = False

            self.sync_container.pack(fill="x", pady=(4, 8))
            self.btn_toggle_sync.configure(text="Ocultar Sincronização GoodSync")
            self.sync_visible = True
            self._on_goodsync_mode_change()

    def _build_sync_panel(self):
        """Central dedicada de Sincronização de Pastas no padrão GoodSync."""
        sync_card = ctk.CTkFrame(self.sync_container, corner_radius=6, border_width=1, border_color=("#38bdf8", "#0284c7"), fg_color=("#f0f9ff", "#101827"))
        sync_card.pack(fill="x", pady=(2, 6))

        # Barra de título do card GoodSync
        top_bar = ctk.CTkFrame(sync_card, fg_color="transparent")
        top_bar.pack(fill="x", padx=16, pady=(12, 6))

        lbl_sync_title = ctk.CTkLabel(
            top_bar,
            text="Central de Sincronização de Pastas (Padrão GoodSync)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=("#0369a1", "#38bdf8")
        )
        lbl_sync_title.pack(side="left")

        self._create_info_badge(
            top_bar,
            "Modos profissionais para sincronizar duas pastas com precisão. Escolha a direção e as regras de atualização ideais para o seu fluxo."
        ).pack(side="left", padx=8)

        # Indicador visual de direção
        self.lbl_sync_direction = ctk.CTkLabel(
            top_bar,
            text="Direção: Origem -> Destino (Espelhamento Rígido)",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=("#bae6fd", "#0c4a6e"),
            text_color=("#0369a1", "#7dd3fc"),
            corner_radius=4,
            padx=10,
            pady=3
        )
        self.lbl_sync_direction.pack(side="right")

        # Modos GoodSync
        modes_box = ctk.CTkFrame(sync_card, fg_color="transparent")
        modes_box.pack(fill="x", padx=16, pady=4)

        self.var_goodsync_mode = tk.StringVar(value="goodsync_mirror")

        goodsync_modes = [
            (
                "goodsync_mirror",
                "1. Espelhamento Rígido (Mirror / 1-Way Sync)",
                "Cria uma cópia exata da origem no destino. Se um arquivo for deletado na origem, ele é deletado no destino. Se houver arquivos extras no destino que não existem na origem, eles são apagados.\nComando: /MIR /R:3 /W:5 /V /TS /FP"
            ),
            (
                "goodsync_update",
                "2. Atualização Sem Exclusão (Contribute / Update)",
                "Copia arquivos novos e modificados da origem para o destino. Arquivos deletados na origem NUNCA são apagados no destino.\nComando: /E /XO /R:3 /W:5"
            ),
            (
                "goodsync_two_way",
                "3. Sincronização Bidirecional (2-Way Sync / Fusão)",
                "Mescla o conteúdo de duas pastas em duas etapas invertidas com /XO: Etapa 1 (Origem -> Destino) e Etapa 2 (Destino -> Origem). O que for novo em A vai para B e o que for novo em B vai para A sem deletar nada."
            ),
            (
                "goodsync_move",
                "4. Mover Arquivos (Move / Cut & Paste)",
                "Transfere os arquivos para o destino e os apaga completamente da pasta de origem após o sucesso da cópia.\nComando: /E /MOVE /R:3 /W:5"
            ),
            (
                "goodsync_filter",
                "5. Sincronização com Filtro de Extensão ou Tamanho",
                "Permite incluir ou excluir arquivos baseado em formato (ex: ignorar .tmp, .bak) ou tamanho máximo (ex: não copiar arquivos maiores que 50MB).\nComando: /E /MAX:n /XF ... /R:3 /W:5"
            ),
        ]

        modes_box.grid_columnconfigure((0, 1), weight=1)

        for position, (m_key, m_title, m_desc) in enumerate(goodsync_modes):
            m_row = ctk.CTkFrame(modes_box, fg_color="transparent")
            m_row.grid(row=position // 2, column=position % 2, sticky="w", pady=2, padx=(0, 12))

            r = ctk.CTkRadioButton(
                m_row,
                text=m_title,
                value=m_key,
                variable=self.var_goodsync_mode,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                command=self._on_goodsync_mode_change
            )
            r.pack(side="left")

            self._create_info_badge(m_row, m_desc).pack(side="left", padx=8)

        # Filtros rápidos para o Modo 5
        self.sync_filter_box = ctk.CTkFrame(sync_card, fg_color=("#e0f2fe", "#182026"), corner_radius=4)

        f_inner = ctk.CTkFrame(self.sync_filter_box, fg_color="transparent")
        f_inner.pack(fill="x", padx=12, pady=6)

        ctk.CTkLabel(f_inner, text="Excluir Extensões (/XF):", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=("#475569", "#94a3b8")).pack(side="left")
        self.entry_sync_xf = ctk.CTkEntry(f_inner, width=160, height=26, font=ctk.CTkFont(family="Consolas", size=11), placeholder_text="*.tmp *.bak")
        self.entry_sync_xf.insert(0, "*.tmp *.bak")
        self.entry_sync_xf.pack(side="left", padx=(6, 16))
        self.entry_sync_xf.bind("<KeyRelease>", lambda e: self.update_command_preview())

        ctk.CTkLabel(f_inner, text="Tamanho Máximo (/MAX em bytes):", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=("#475569", "#94a3b8")).pack(side="left")
        self.entry_sync_max = ctk.CTkEntry(f_inner, width=120, height=26, font=ctk.CTkFont(family="Consolas", size=11), placeholder_text="52428800")
        self.entry_sync_max.insert(0, "52428800")
        self.entry_sync_max.pack(side="left", padx=(6, 16))
        self.entry_sync_max.bind("<KeyRelease>", lambda e: self.update_command_preview())

        # Parâmetros Avançados Corporativos GoodSync
        corp_box = ctk.CTkFrame(sync_card, fg_color="transparent")
        corp_box.pack(fill="x", padx=16, pady=(4, 0))
        self.sync_corp_box = corp_box

        corp_checks = ctk.CTkFrame(corp_box, fg_color="transparent")
        corp_checks.pack(fill="x")

        ctk.CTkLabel(
            corp_checks,
            text="Avançado:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#475569", "#94a3b8")
        ).pack(side="left", padx=(0, 10))

        self.var_sync_mt32 = tk.BooleanVar(value=True)
        r_mt = ctk.CTkFrame(corp_checks, fg_color="transparent")
        r_mt.pack(side="left", padx=(0, 16))
        ctk.CTkCheckBox(r_mt, text="Velocidade 32x (/MT:32)", font=ctk.CTkFont(family="Segoe UI", size=11), variable=self.var_sync_mt32, command=self.update_command_preview).pack(side="left")
        self._create_info_badge(r_mt, "Multi-Threading: copia até 32 arquivos simultaneamente, acelerando a sincronização de milhares de arquivos pequenos.").pack(side="left", padx=4)

        self.var_sync_copyall = tk.BooleanVar(value=False)
        r_ca = ctk.CTkFrame(corp_checks, fg_color="transparent")
        r_ca.pack(side="left", padx=16)
        ctk.CTkCheckBox(r_ca, text="Copiar Informações Totais NTFS (/COPYALL)", font=ctk.CTkFont(family="Segoe UI", size=11), variable=self.var_sync_copyall, command=self.update_command_preview).pack(side="left")
        self._create_info_badge(r_ca, "Copia Dados, Atributos, Carimbos de data/hora, NTFS ACLs (permissões de segurança), Dono e Auditoria corporativa.").pack(side="left", padx=4)

        self.var_sync_zb = tk.BooleanVar(value=is_admin())
        r_zb = ctk.CTkFrame(corp_checks, fg_color="transparent")
        r_zb.pack(side="left", padx=16)
        ctk.CTkCheckBox(r_zb, text="Modo Reinicialização Backup (/ZB)", font=ctk.CTkFont(family="Segoe UI", size=11), variable=self.var_sync_zb, command=self.update_command_preview).pack(side="left")
        self._create_info_badge(r_zb, "Se o acesso for negado por permissões de usuário, usa privilégios de Administrador de Backup para copiar à força.").pack(side="left", padx=4)

        # Flags livres continuam acessíveis com a Central de Sincronização aberta
        self._build_extra_args_section(sync_card, compact=True)

        # Disparo da análise: o resultado aparece na aba "Divergências" do monitor
        self._build_sync_actions_row(sync_card)

    # -------------------------------------------------------------
    # CENTRAL GOODSYNC: ANÁLISE E RESOLUÇÃO DE DIVERGÊNCIAS
    # -------------------------------------------------------------
    def _build_sync_actions_row(self, parent):
        """Linha enxuta dentro da Central: dispara a análise e explica o fluxo."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(6, 12))

        button = ctk.CTkButton(
            row,
            text="Analisar Diferenças",
            height=32,
            fg_color="#0284c7",
            hover_color="#0369a1",
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._analyze_differences
        )
        button.pack(side="left")
        self._analyze_buttons.append(button)

        ctk.CTkLabel(
            row,
            text="Compara as duas pastas sem alterar nada e abre a aba Divergências com o resultado.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#475569", "#94a3b8")
        ).pack(side="left", padx=10)

    def _build_differences_tab(self, parent):
        """Aba do monitor com a lista de divergências e as ações de cada item."""
        # --- Barra de comandos ---
        actions_bar = ctk.CTkFrame(parent, fg_color="transparent")
        actions_bar.pack(fill="x", padx=4, pady=(4, 2))

        button = ctk.CTkButton(
            actions_bar,
            text="Analisar Diferenças",
            height=30,
            fg_color="#0284c7",
            hover_color="#0369a1",
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._analyze_differences
        )
        button.pack(side="left")
        self._analyze_buttons.append(button)
        self.btn_analyze = button

        self._create_info_badge(
            actions_bar,
            "A análise usa o RoboCopy em modo somente-leitura (/L): nada é copiado nem apagado\n"
            "até você clicar em 'Aplicar Ações'.\n\n"
            "Fluxo: 1. Analisar  ➔  2. Revisar e ajustar as ações  ➔  3. Aplicar."
        ).pack(side="left", padx=6)

        self.btn_apply_plan = ctk.CTkButton(
            actions_bar,
            text="Aplicar Ações",
            height=30,
            fg_color=("#dcfce7", "#14532d"),
            hover_color=("#bbf7d0", "#166534"),
            text_color=("#15803d", "#86efac"),
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            state="disabled",
            command=self._apply_sync_plan
        )
        self.btn_apply_plan.pack(side="left", padx=6)

        self.btn_stop_sync = ctk.CTkButton(
            actions_bar,
            text="Interromper",
            height=30,
            width=100,
            fg_color=("#fee2e2", "#7f1d1d"),
            hover_color=("#fecaca", "#991b1b"),
            text_color=("#991b1b", "#fecaca"),
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            state="disabled",
            command=self._stop_sync_operation
        )
        self.btn_stop_sync.pack(side="left")

        self.btn_export_diff = ctk.CTkButton(
            actions_bar,
            text="Exportar CSV",
            height=30,
            width=110,
            fg_color=("#e2e8f0", "#2b2b2b"),
            hover_color=("#cbd5e1", "#3d3d3d"),
            text_color=("#0f172a", "#ffffff"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._export_differences_csv
        )
        self.btn_export_diff.pack(side="right", padx=3)

        self.btn_open_diff = ctk.CTkButton(
            actions_bar,
            text="Abrir no Explorer",
            height=30,
            width=130,
            fg_color=("#e2e8f0", "#2b2b2b"),
            hover_color=("#cbd5e1", "#3d3d3d"),
            text_color=("#0f172a", "#ffffff"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._open_selected_difference
        )
        self.btn_open_diff.pack(side="right", padx=3)

        # --- Resumo e filtros ---
        self.lbl_diff_summary = ctk.CTkLabel(
            parent,
            text="Clique em 'Analisar Diferenças' para comparar as duas pastas item a item.",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#334155", "#cbd5e1"),
            justify="left",
            anchor="w"
        )
        self.lbl_diff_summary.pack(fill="x", padx=8, pady=(4, 2))

        filter_bar = ctk.CTkFrame(parent, fg_color="transparent")
        filter_bar.pack(fill="x", padx=4, pady=(0, 4))

        self.difference_filter = ctk.CTkSegmentedButton(
            filter_bar,
            values=DIFFERENCE_FILTERS,
            command=self._on_difference_filter_change,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            height=26
        )
        self.difference_filter.set(DIFFERENCE_FILTERS[0])
        self.difference_filter.pack(side="left")

        self.lbl_plan_preview = ctk.CTkLabel(
            filter_bar,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#0369a1", "#38bdf8")
        )
        self.lbl_plan_preview.pack(side="right", padx=4)

        # --- Tabela de divergências ---
        table_box = ctk.CTkFrame(parent, fg_color="transparent")
        table_box.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        self.tree_differences = ttk.Treeview(
            table_box,
            columns=("acao", "situacao", "lado", "tamanho", "caminho"),
            show="headings",
            style="RCM.Treeview",
            selectmode="extended"
        )
        self.tree_differences.heading("acao", text="Ação a executar")
        self.tree_differences.heading("situacao", text="Situação encontrada")
        self.tree_differences.heading("lado", text="Existe em")
        self.tree_differences.heading("tamanho", text="Tamanho")
        self.tree_differences.heading("caminho", text="Caminho (relativo às pastas comparadas)")
        self.tree_differences.column("acao", width=200, minwidth=150, stretch=False)
        self.tree_differences.column("situacao", width=190, minwidth=150, stretch=False)
        self.tree_differences.column("lado", width=90, minwidth=70, stretch=False)
        self.tree_differences.column("tamanho", width=90, minwidth=70, anchor="e", stretch=False)
        self.tree_differences.column("caminho", width=520, minwidth=240, stretch=True)

        diff_scroll = ctk.CTkScrollbar(table_box, command=self.tree_differences.yview)
        self.tree_differences.configure(yscrollcommand=diff_scroll.set)
        diff_scroll.pack(side="right", fill="y", padx=(2, 0))
        self.tree_differences.pack(side="left", fill="both", expand=True)

        self.tree_differences.bind("<<TreeviewSelect>>", self._on_difference_select)
        self.tree_differences.bind("<Double-1>", self._cycle_difference_action)

        # --- Ações em lote sobre a seleção ---
        bulk = ctk.CTkFrame(parent, fg_color="transparent")
        bulk.pack(fill="x", padx=4, pady=(2, 2))

        ctk.CTkLabel(
            bulk,
            text="Itens selecionados:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#334155", "#cbd5e1")
        ).pack(side="left", padx=(4, 8))

        bulk_buttons = [
            (ACTION_COPY_TO_DEST, "Copiar para o Destino", ("#dbeafe", "#1e3a5f"), ("#1d4ed8", "#93c5fd")),
            (ACTION_COPY_TO_SOURCE, "Copiar para a Origem", ("#dbeafe", "#1e3a5f"), ("#1d4ed8", "#93c5fd")),
            (ACTION_DELETE_DEST, "Excluir do Destino", ("#fee2e2", "#7f1d1d"), ("#991b1b", "#fecaca")),
            (ACTION_SKIP, "Ignorar", ("#e2e8f0", "#1e293b"), ("#334155", "#cbd5e1")),
        ]
        for action, caption, fg, text_color in bulk_buttons:
            ctk.CTkButton(
                bulk,
                text=caption,
                height=26,
                fg_color=fg,
                hover_color=fg,
                text_color=text_color,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                command=lambda a=action: self._set_action_for_selected(a)
            ).pack(side="left", padx=3)

        ctk.CTkButton(
            bulk,
            text="Restaurar sugestão do modo",
            height=26,
            width=190,
            fg_color=("#e2e8f0", "#2b2b2b"),
            hover_color=("#cbd5e1", "#3d3d3d"),
            text_color=("#0f172a", "#ffffff"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._restore_suggested_actions
        ).pack(side="right", padx=3)

        ctk.CTkButton(
            bulk,
            text="Selecionar tudo",
            height=26,
            width=120,
            fg_color=("#e2e8f0", "#2b2b2b"),
            hover_color=("#cbd5e1", "#3d3d3d"),
            text_color=("#0f172a", "#ffffff"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._select_all_differences
        ).pack(side="right", padx=3)

        self.lbl_diff_detail = ctk.CTkLabel(
            parent,
            text="Selecione uma linha para ver a explicação e os caminhos completos dos dois lados. "
                 "Dois cliques alternam a ação daquele item.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#64748b", "#94a3b8"),
            justify="left",
            anchor="w",
            wraplength=1100
        )
        self.lbl_diff_detail.pack(fill="x", padx=8, pady=(2, 6))

    def _analyze_differences(self):
        """Compara origem e destino em modo somente-leitura e preenche a tabela."""
        if self.is_busy:
            messagebox.showinfo("Aguarde", "Já existe uma operação em andamento.")
            return

        cfg = self._gather_config_from_ui()
        if not cfg.source or not cfg.destination:
            messagebox.showwarning(
                "Caminhos Incompletos",
                "Informe a pasta de Origem e a pasta de Destino antes de analisar as diferenças."
            )
            return

        if not os.path.exists(cfg.source):
            messagebox.showerror("Origem Inexistente", f"A pasta de origem não foi encontrada:\n{cfg.source}")
            return

        if not os.path.exists(cfg.destination):
            messagebox.showwarning(
                "Destino Inexistente",
                f"A pasta de destino ainda não existe:\n{cfg.destination}\n\n"
                "Todos os itens da origem serão listados como novos."
            )

        mode = self.var_goodsync_mode.get() if hasattr(self, "var_goodsync_mode") else "goodsync_two_way"

        self._set_sync_busy(True)
        self._clear_differences()
        self.lbl_diff_summary.configure(
            text="Analisando as duas pastas... (somente leitura, nada está sendo alterado)",
            text_color=("#d97706", "#facc15")
        )
        self.lbl_status.configure(text="Status: Analisando diferenças...", text_color=("#d97706", "#facc15"))
        self._show_tab(TAB_DIFFERENCES)
        self._append_log_line("\n>>> [ANÁLISE] Comparando origem e destino em modo somente-leitura...\n\n")

        self.analyzer.analyze_async(
            config=cfg,
            mode=mode,
            on_line=self._handle_output_line,
            on_finish=lambda analysis: self.after(0, self._on_analysis_completed, analysis),
        )

    def _on_analysis_completed(self, analysis):
        """Recebe o resultado da análise e monta a tabela de divergências."""
        self._set_sync_busy(False)
        self.sync_analysis = analysis
        self.sync_differences = list(analysis.differences)

        self._populate_difference_tree()

        if analysis.cancelled:
            self.lbl_diff_summary.configure(
                text="Análise interrompida pelo usuário.",
                text_color=("#d97706", "#facc15")
            )
            self.lbl_status.configure(text="Status: Análise interrompida", text_color=("#d97706", "#facc15"))
            return

        if analysis.exit_code >= 16 and not analysis.differences:
            self.lbl_diff_summary.configure(
                text="Não foi possível concluir a análise. Verifique os caminhos e as permissões de acesso.",
                text_color=("#dc2626", "#f87171")
            )
            self.lbl_status.configure(text="Status: Falha na análise", text_color=("#dc2626", "#f87171"))
            return

        summary = analysis.summary_text()
        if analysis.differences:
            color = ("#b45309", "#facc15")
            status_text = f"Status: {len(analysis.differences)} divergência(s) encontrada(s) - escolha a ação de cada item"
            status_color = ("#d97706", "#facc15")
        else:
            color = ("#15803d", "#4ade80")
            status_text = "Status: Origem e destino já estão sincronizados"
            status_color = ("#16a34a", "#4ade80")

        self.lbl_diff_summary.configure(text=summary, text_color=color)
        self.lbl_status.configure(text=status_text, text_color=status_color)
        self.btn_apply_plan.configure(state="normal" if analysis.differences else "disabled")

        if analysis.differences:
            self._show_tab(TAB_DIFFERENCES)

    def _clear_differences(self):
        self.sync_differences = []
        self.sync_analysis = None
        for item in self.tree_differences.get_children():
            self.tree_differences.delete(item)
        self.btn_apply_plan.configure(state="disabled")
        self.lbl_plan_preview.configure(text="")

    def _difference_matches_filter(self, diff) -> bool:
        selected = self.difference_filter.get() if hasattr(self, "difference_filter") else DIFFERENCE_FILTERS[0]
        if selected == DIFFERENCE_FILTERS[1]:
            return diff.category in ("new_file", "new_dir")
        if selected == DIFFERENCE_FILTERS[2]:
            return diff.category in ("extra_file", "extra_dir", "lonely")
        if selected == DIFFERENCE_FILTERS[3]:
            return diff.category in ("newer", "older", "changed", "mismatch")
        if selected == DIFFERENCE_FILTERS[4]:
            return diff.action == ACTION_DELETE_DEST
        return True

    def _populate_difference_tree(self):
        """Redesenha a tabela de divergências respeitando o filtro atual."""
        for item in self.tree_differences.get_children():
            self.tree_differences.delete(item)

        for index, diff in enumerate(self.sync_differences):
            if not self._difference_matches_filter(diff):
                continue
            self.tree_differences.insert(
                "", "end", iid=str(index),
                values=(
                    diff.action_label,
                    diff.label,
                    diff.side_label,
                    diff.size_text,
                    diff.relative_path + ("\\" if diff.is_dir else ""),
                ),
                tags=(f"cat_{diff.category}",),
            )

        self._update_plan_preview()

    def _update_plan_preview(self):
        """Mostra quantas cópias e exclusões o plano atual vai executar."""
        to_dest = sum(1 for d in self.sync_differences if d.action == ACTION_COPY_TO_DEST)
        to_source = sum(1 for d in self.sync_differences if d.action == ACTION_COPY_TO_SOURCE)
        to_delete = sum(1 for d in self.sync_differences if d.action == ACTION_DELETE_DEST)
        ignored = sum(1 for d in self.sync_differences if d.action == ACTION_SKIP)

        if not self.sync_differences:
            self.lbl_plan_preview.configure(text="")
            return

        self.lbl_plan_preview.configure(
            text=(
                f"Plano atual: {to_dest} ➔ destino | {to_source} ➔ origem | "
                f"{to_delete} exclusão(ões) | {ignored} ignorado(s)"
            )
        )

    def _on_difference_filter_change(self, _value=None):
        self._populate_difference_tree()

    def _selected_differences(self):
        selected = []
        for item_id in self.tree_differences.selection():
            try:
                selected.append((int(item_id), self.sync_differences[int(item_id)]))
            except (ValueError, IndexError):
                continue
        return selected

    def _on_difference_select(self, _event=None):
        """Mostra a explicação e os caminhos completos do item selecionado."""
        selected = self._selected_differences()
        if not selected:
            return

        _index, diff = selected[0]
        available = " | ".join(ACTION_LABELS[a] for a in diff.available_actions())
        self.lbl_diff_detail.configure(
            text=(
                f"{diff.label}: {diff.explanation}\n"
                f"{diff.location_text()}\n"
                f"Ações possíveis para este item: {available}"
            )
        )

    def _set_action_for_selected(self, action: str):
        """Aplica a ação escolhida a todos os itens selecionados na tabela."""
        selected = self._selected_differences()
        if not selected:
            messagebox.showinfo(
                "Nenhum item selecionado",
                "Selecione na tabela as linhas que deseja alterar.\n"
                "Use Ctrl+clique ou Shift+clique para escolher vários de uma vez."
            )
            return

        rejected = 0
        for index, diff in selected:
            if action not in diff.available_actions():
                rejected += 1
                continue
            diff.action = action
            if self.tree_differences.exists(str(index)):
                values = list(self.tree_differences.item(str(index), "values"))
                values[0] = diff.action_label
                self.tree_differences.item(str(index), values=values)

        if self.difference_filter.get() == DIFFERENCE_FILTERS[4]:
            self._populate_difference_tree()
        else:
            self._update_plan_preview()

        if rejected:
            messagebox.showinfo(
                "Ação não aplicável",
                f"{rejected} item(ns) não aceitam a ação '{ACTION_LABELS.get(action, action)}' "
                "e permaneceram como estavam.\n\n"
                "Exemplo: um arquivo que só existe na origem não pode ser excluído do destino, "
                "e itens incompatíveis precisam ser resolvidos manualmente."
            )

    def _cycle_difference_action(self, _event=None):
        """Dois cliques em uma linha alternam entre as ações possíveis daquele item."""
        selected = self._selected_differences()
        if not selected:
            return
        _index, diff = selected[0]
        options = diff.available_actions()
        try:
            position = options.index(diff.action)
        except ValueError:
            position = -1
        self._set_action_for_selected(options[(position + 1) % len(options)])

    def _select_all_differences(self):
        children = self.tree_differences.get_children()
        if children:
            self.tree_differences.selection_set(children)

    def _restore_suggested_actions(self):
        """Volta todas as ações para a sugestão automática do modo selecionado."""
        mode = self.var_goodsync_mode.get() if hasattr(self, "var_goodsync_mode") else "goodsync_two_way"
        for diff in self.sync_differences:
            diff.action = suggest_action(diff.category, mode)
        self._populate_difference_tree()

    def _apply_sync_plan(self):
        """Executa exatamente as ações escolhidas na tabela."""
        if self.is_busy:
            messagebox.showinfo("Aguarde", "Já existe uma operação em andamento.")
            return

        if not self.sync_differences:
            messagebox.showinfo("Nada a fazer", "Analise as diferenças antes de aplicar as ações.")
            return

        cfg = self._gather_config_from_ui()
        plan = build_execution_plan(self.sync_differences)

        if not plan:
            messagebox.showinfo(
                "Nada a fazer",
                "Todos os itens estão marcados como 'Ignorar'.\n"
                "Escolha pelo menos uma ação de cópia ou exclusão."
            )
            return

        to_dest = sum(1 for d in self.sync_differences if d.action == ACTION_COPY_TO_DEST)
        to_source = sum(1 for d in self.sync_differences if d.action == ACTION_COPY_TO_SOURCE)
        deletions = [d for d in self.sync_differences if d.action == ACTION_DELETE_DEST]

        message = [
            "As seguintes ações serão executadas agora:",
            "",
            f"  Copiar para o destino: {to_dest} item(ns)",
            f"  Copiar para a origem:  {to_source} item(ns)",
            f"  Excluir do destino:    {len(deletions)} item(ns)",
        ]

        if deletions:
            preview = "\n".join(f"    - {d.relative_path}" for d in deletions[:8])
            if len(deletions) > 8:
                preview += f"\n    ... e mais {len(deletions) - 8} item(ns)."
            message += [
                "",
                "ATENÇÃO: as exclusões abaixo são permanentes e não passam pela Lixeira:",
                preview,
            ]

        message += ["", "Deseja prosseguir?"]

        if not messagebox.askyesno("Confirmar Aplicação das Ações", "\n".join(message)):
            return

        self._set_sync_busy(True)
        self.lbl_status.configure(text="Status: Aplicando ações escolhidas...", text_color=("#d97706", "#facc15"))
        self._show_tab(TAB_CONSOLE)
        self.var_autoscroll.set(True)
        self._append_log_line(f"\n>>> [APLICANDO PLANO] {len(plan)} operação(ões) a executar...\n")

        self.plan_executor.execute_async(
            plan=plan,
            config=cfg,
            on_line=self._handle_output_line,
            on_finish=lambda result: self.after(0, self._on_plan_completed, result),
        )

    def _on_plan_completed(self, result: dict):
        """Atualiza a interface após a execução do plano de ações."""
        self._set_sync_busy(False)

        exit_code = result.get("exit_code", 0)
        title, desc, _category = interpret_exit_code(exit_code)
        steps = [{"label": s["label"], "code": s["code"], "title": interpret_exit_code(s["code"])[0]}
                 for s in result.get("steps", [])]

        summary = {
            "steps": steps,
            "explanation": explain_exit_code(exit_code, steps),
        }
        self._update_status_result(exit_code, title, desc, summary)

        self.lbl_diff_summary.configure(
            text=(
                f"Ações aplicadas: {result.get('copied', 0)} cópia(s), "
                f"{result.get('deleted', 0)} exclusão(ões), {result.get('failed', 0)} falha(s). "
                "Analise novamente para confirmar que as pastas ficaram sincronizadas."
            ),
            text_color=("#15803d", "#4ade80") if exit_code < 8 else ("#dc2626", "#f87171")
        )

        if exit_code < 8 and not result.get("cancelled"):
            if messagebox.askyesno(
                "Ações Concluídas",
                f"{result.get('copied', 0)} cópia(s) e {result.get('deleted', 0)} exclusão(ões) aplicadas.\n\n"
                "Deseja analisar novamente para confirmar que não sobrou nenhuma divergência?"
            ):
                self._analyze_differences()
        elif exit_code >= 8:
            messagebox.showerror(
                "Algumas Ações Falharam",
                f"{result.get('failed', 0)} operação(ões) não puderam ser concluídas.\n\n"
                "Consulte o painel de Ocorrências para ver o motivo de cada falha."
            )

    def _set_sync_busy(self, busy: bool):
        """Bloqueia ou libera os controles durante a análise e a aplicação do plano."""
        self.is_busy = busy
        state = "disabled" if busy else "normal"
        for button in self._analyze_buttons:
            button.configure(state=state)
        self.btn_run.configure(state=state)
        self.btn_simulate.configure(state=state)
        self.btn_stop_sync.configure(state="normal" if busy else "disabled")
        # O botão "Interromper" do rodapé também cancela a análise e o plano
        self.btn_cancel.configure(state="normal" if busy else "disabled")
        if busy:
            self.btn_apply_plan.configure(state="disabled")
        elif self.sync_differences:
            self.btn_apply_plan.configure(state="normal")

    def _stop_sync_operation(self):
        """Interrompe a análise ou a aplicação do plano em andamento."""
        stopped = self.analyzer.stop() or self.plan_executor.stop()
        if stopped:
            self._append_log_line("\n[OPERAÇÃO CANCELADA PELO USUÁRIO]\n")

    def _open_selected_difference(self):
        """Abre no Explorer a pasta do item divergente selecionado."""
        selected = self._selected_differences()
        if not selected:
            messagebox.showinfo("Abrir no Explorer", "Selecione na tabela o item que deseja localizar.")
            return
        _index, diff = selected[0]
        self._reveal_in_explorer(diff.path_on_side)

    def _export_differences_csv(self):
        """Exporta a lista de divergências e as ações escolhidas para um arquivo CSV."""
        if not self.sync_differences:
            messagebox.showinfo("Exportar Lista", "Analise as diferenças antes de exportar a lista.")
            return

        filepath = filedialog.asksaveasfilename(
            title="Exportar Lista de Divergências",
            defaultextension=".csv",
            filetypes=[("Planilha CSV", "*.csv"), ("Todos os Arquivos", "*.*")]
        )
        if not filepath:
            return

        try:
            with open(filepath, "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow([
                    "Acao", "Situacao", "Existe em", "Tamanho (bytes)",
                    "Caminho relativo", "Caminho na origem", "Caminho no destino", "Explicacao",
                ])
                for diff in self.sync_differences:
                    writer.writerow([
                        diff.action_label, diff.label, diff.side_label,
                        diff.size if diff.size is not None else "",
                        diff.relative_path, diff.source_path, diff.dest_path, diff.explanation,
                    ])
            messagebox.showinfo("Exportado", f"Lista de divergências salva em:\n{filepath}")
        except Exception as ex:
            messagebox.showerror("Erro ao Exportar", f"Não foi possível salvar o arquivo:\n{ex}")

    def _on_goodsync_mode_change(self):
        mode = self.var_goodsync_mode.get()
        if mode == "goodsync_mirror":
            self.lbl_sync_direction.configure(text="Direção: Origem -> Destino (Espelhamento Rígido)")
        elif mode == "goodsync_update":
            self.lbl_sync_direction.configure(text="Direção: Origem -> Destino (Atualização Sem Exclusão)")
        elif mode == "goodsync_two_way":
            self.lbl_sync_direction.configure(text="Direção: Origem <-> Destino (Bidirecional Mútuo)")
        elif mode == "goodsync_move":
            self.lbl_sync_direction.configure(text="Direção: Origem -> Destino [Mover e Apagar Origem]")
        elif mode == "goodsync_filter":
            self.lbl_sync_direction.configure(text="Direção: Origem -> Destino (Com Filtros Ativos)")

        # Os campos de filtro só fazem sentido no modo 5: ficam ocultos nos demais.
        if mode == "goodsync_filter":
            if not self.sync_filter_box.winfo_manager():
                self.sync_filter_box.pack(fill="x", padx=16, pady=4, before=self.sync_corp_box)
        else:
            self.sync_filter_box.pack_forget()

        # As ações sugeridas dependem do modo: atualiza a tabela já analisada
        if getattr(self, "sync_differences", None):
            for diff in self.sync_differences:
                diff.action = suggest_action(diff.category, mode)
            self._populate_difference_tree()

        self.update_command_preview()

    def _build_advanced_tabs(self):
        """Abas avançadas detalhadas com nomes explicativos e botões (i)."""
        self.tabview = ctk.CTkTabview(self.advanced_container, corner_radius=6)
        self.tabview.pack(fill="x", pady=2)

        tab_copy = self.tabview.add("Estrutura e Modos")
        tab_filters = self.tabview.add("Filtros e Exclusões")
        tab_perf = self.tabview.add("Velocidade e Rede")
        tab_attrs = self.tabview.add("Segurança e Registro")
        tab_cmd = self.tabview.add("Comando Interno")

        self._build_advanced_copy_tab(tab_copy)
        self._build_advanced_filters_tab(tab_filters)
        self._build_advanced_perf_tab(tab_perf)
        self._build_advanced_attrs_tab(tab_attrs)
        self._build_advanced_cmd_tab(tab_cmd)

    def _build_advanced_copy_tab(self, parent):
        parent.grid_columnconfigure((0, 1), weight=1)

        f1 = ctk.CTkFrame(parent, border_width=1, border_color=("#cbd5e1", "#2d2d2d"), fg_color=("#f8fafc", "#1a1a1a"))
        f1.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(f1, text="Tratamento de Subpastas", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(anchor="w", padx=12, pady=(10, 6))

        # Checkbox E
        r_e = ctk.CTkFrame(f1, fg_color="transparent")
        r_e.pack(anchor="w", padx=12, pady=4)
        self.var_copy_e = tk.BooleanVar(value=True)
        self.chk_e = ctk.CTkCheckBox(r_e, text="Incluir todas as subpastas, mesmo as vazias (/E)", font=ctk.CTkFont(family="Segoe UI", size=12), variable=self.var_copy_e, command=self._on_chk_e_change)
        self.chk_e.pack(side="left")
        self._create_info_badge(r_e, "Garante que a estrutura completa de diretórios da origem seja recriada no destino.").pack(side="left", padx=6)

        # Checkbox S
        r_s = ctk.CTkFrame(f1, fg_color="transparent")
        r_s.pack(anchor="w", padx=12, pady=4)
        self.var_copy_s = tk.BooleanVar(value=False)
        self.chk_s = ctk.CTkCheckBox(r_s, text="Copiar apenas subpastas que tenham arquivos dentro (/S)", font=ctk.CTkFont(family="Segoe UI", size=12), variable=self.var_copy_s, command=self._on_chk_s_change)
        self.chk_s.pack(side="left")
        self._create_info_badge(r_s, "Subpastas que estiverem vazias não serão criadas no destino.").pack(side="left", padx=6)

        # Checkbox MIR
        r_mir = ctk.CTkFrame(f1, fg_color="transparent")
        r_mir.pack(anchor="w", padx=12, pady=4)
        self.var_mirror = tk.BooleanVar(value=False)
        self.chk_mir = ctk.CTkCheckBox(r_mir, text="Espelhar destino com exclusão de arquivos órfãos (/MIR)", font=ctk.CTkFont(family="Segoe UI", size=12), variable=self.var_mirror, command=self._on_chk_mir_change)
        self.chk_mir.pack(side="left")
        self._create_info_badge(r_mir, "Apaga no destino qualquer item que foi deletado da origem.").pack(side="left", padx=6)

        # Profundidade
        r_lev = ctk.CTkFrame(f1, fg_color="transparent")
        r_lev.pack(anchor="w", padx=12, pady=(8, 10))
        ctk.CTkLabel(r_lev, text="Limite de níveis de subpastas (/LEV:n):", font=ctk.CTkFont(family="Segoe UI", size=12)).pack(side="left")
        self.entry_lev = ctk.CTkEntry(r_lev, width=50, height=26, font=ctk.CTkFont(family="Consolas", size=11))
        self.entry_lev.insert(0, "0")
        self.entry_lev.pack(side="left", padx=6)
        ctk.CTkLabel(r_lev, text="(0 = sem limite)", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=("#64748b", "#757575")).pack(side="left")
        self._create_info_badge(r_lev, "Permite limitar a cópia até um nível máximo de pastas filhas.").pack(side="left", padx=6)
        self.entry_lev.bind("<KeyRelease>", lambda e: self.update_command_preview())

        # Coluna 2: Modos especiais
        f2 = ctk.CTkFrame(parent, border_width=1, border_color=("#cbd5e1", "#2d2d2d"), fg_color=("#f8fafc", "#1a1a1a"))
        f2.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(f2, text="Modos Especiais de Desempenho", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(anchor="w", padx=12, pady=(10, 6))

        r_j = ctk.CTkFrame(f2, fg_color="transparent")
        r_j.pack(anchor="w", padx=12, pady=4)
        self.var_mode_j = tk.BooleanVar(value=False)
        self.chk_j = ctk.CTkCheckBox(r_j, text="E/S direta sem sobrecarregar memória para arquivos gigantes (/J)", font=ctk.CTkFont(family="Segoe UI", size=12), variable=self.var_mode_j, command=self.update_command_preview)
        self.chk_j.pack(side="left")
        self._create_info_badge(r_j, "Recomendado para cópia de filmes, imagens ISO, máquinas virtuais ou bancos de dados pesados.").pack(side="left", padx=6)

        r_z = ctk.CTkFrame(f2, fg_color="transparent")
        r_z.pack(anchor="w", padx=12, pady=4)
        self.var_mode_z = tk.BooleanVar(value=False)
        self.chk_z = ctk.CTkCheckBox(r_z, text="Modo reiniciável em caso de oscilação de rede (/Z)", font=ctk.CTkFont(family="Segoe UI", size=12), variable=self.var_mode_z, command=self._on_mode_change)
        self.chk_z.pack(side="left")
        self._create_info_badge(r_z, "Se uma transferência pela rede cair no meio de um arquivo, ela continua de onde parou.").pack(side="left", padx=6)

        r_mov = ctk.CTkFrame(f2, fg_color="transparent")
        r_mov.pack(anchor="w", padx=12, pady=4)
        self.var_move_files = tk.BooleanVar(value=False)
        self.chk_mov = ctk.CTkCheckBox(r_mov, text="Recortar apenas arquivos da origem após copiar (/MOV)", font=ctk.CTkFont(family="Segoe UI", size=12), variable=self.var_move_files, command=self._on_chk_mov_change)
        self.chk_mov.pack(side="left")
        self._create_info_badge(r_mov, "Remove os arquivos copiados da pasta de origem, mantendo as pastas vazias.").pack(side="left", padx=6)

        r_move = ctk.CTkFrame(f2, fg_color="transparent")
        r_move.pack(anchor="w", padx=12, pady=4)
        self.var_move_all = tk.BooleanVar(value=False)
        self.chk_move = ctk.CTkCheckBox(r_move, text="Recortar arquivos e remover pastas de origem (/MOVE)", font=ctk.CTkFont(family="Segoe UI", size=12), variable=self.var_move_all, command=self._on_chk_move_change)
        self.chk_move.pack(side="left")
        self._create_info_badge(r_move, "Remove tanto os arquivos quanto as pastas da origem após a conclusão.").pack(side="left", padx=6)

        r_2way = ctk.CTkFrame(f2, fg_color="transparent")
        r_2way.pack(anchor="w", padx=12, pady=(10, 10))
        self.chk_two_way = ctk.CTkCheckBox(
            r_2way,
            text="Sincronização Dupla: executar as duas direções em sequência",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            variable=self.var_two_way,
            command=self._on_two_way_change
        )
        self.chk_two_way.pack(side="left")
        self._create_info_badge(
            r_2way,
            "Com um único clique o sistema roda duas etapas seguidas:\n"
            "1) Origem ➔ Destino e 2) Destino ➔ Origem, ambas com /XO (só o que é mais novo).\n"
            "O status final considera as duas etapas juntas, e não cada uma isolada."
        ).pack(side="left", padx=6)

    def _build_advanced_filters_tab(self, parent):
        parent.grid_columnconfigure((0, 1), weight=1)

        f1 = ctk.CTkFrame(parent, border_width=1, border_color=("#cbd5e1", "#2d2d2d"), fg_color=("#f8fafc", "#1a1a1a"))
        f1.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(f1, text="Exclusão por Nome de Arquivo ou Pasta", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))

        # XF
        xf_box = ctk.CTkFrame(f1, fg_color="transparent")
        xf_box.pack(anchor="w", padx=12, pady=(4, 1))
        ctk.CTkLabel(xf_box, text="Excluir arquivos por nome ou extensão (/XF):", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=("#64748b", "#9e9e9e")).pack(side="left")
        self._create_info_badge(xf_box, "Exemplo: *.tmp *.bak thumbs.db (separe múltiplos itens por espaço)").pack(side="left", padx=6)

        self.entry_xf = ctk.CTkEntry(f1, placeholder_text="Ex: *.tmp *.bak desktop.ini", font=ctk.CTkFont(family="Consolas", size=11), height=28)
        self.entry_xf.pack(fill="x", padx=12, pady=(0, 6))
        self.entry_xf.bind("<KeyRelease>", lambda e: self.update_command_preview())

        # XD
        xd_box = ctk.CTkFrame(f1, fg_color="transparent")
        xd_box.pack(anchor="w", padx=12, pady=(4, 1))
        ctk.CTkLabel(xd_box, text="Excluir pastas específicas (/XD):", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=("#64748b", "#9e9e9e")).pack(side="left")
        self._create_info_badge(xd_box, "Pastas que você não quer que sejam copiadas. Ex: .git node_modules $RECYCLE.BIN").pack(side="left", padx=6)

        self.entry_xd = ctk.CTkEntry(f1, placeholder_text='Ex: .git node_modules "$RECYCLE.BIN"', font=ctk.CTkFont(family="Consolas", size=11), height=28)
        self.entry_xd.pack(fill="x", padx=12, pady=(0, 8))
        self.entry_xd.bind("<KeyRelease>", lambda e: self.update_command_preview())

        # XJ
        r_xj = ctk.CTkFrame(f1, fg_color="transparent")
        r_xj.pack(anchor="w", padx=12, pady=4)
        self.var_xj = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(r_xj, text="Pular atalhos e junções de sistema do Windows (/XJ)", font=ctk.CTkFont(family="Segoe UI", size=12), variable=self.var_xj, command=self.update_command_preview).pack(side="left")
        self._create_info_badge(r_xj, "Evita loops infinitos e travamentos causados por links internos do sistema do Windows.").pack(side="left", padx=6)

        # XO
        r_xo = ctk.CTkFrame(f1, fg_color="transparent")
        r_xo.pack(anchor="w", padx=12, pady=4)
        self.var_xo = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(r_xo, text="Pular arquivos que não mudaram ou mais novos no destino (/XO)", font=ctk.CTkFont(family="Segoe UI", size=12), variable=self.var_xo, command=self.update_command_preview).pack(side="left")
        self._create_info_badge(r_xo, "Impede que um arquivo antigo da origem sobrescreva um arquivo recente no destino.").pack(side="left", padx=6)

        # Coluna 2: Tamanhos e Idade
        f2 = ctk.CTkFrame(parent, border_width=1, border_color=("#cbd5e1", "#2d2d2d"), fg_color=("#f8fafc", "#1a1a1a"))
        f2.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(f2, text="Filtros de Tamanho de Arquivo", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))

        max_box = ctk.CTkFrame(f2, fg_color="transparent")
        max_box.pack(anchor="w", padx=12, pady=(4, 1))
        ctk.CTkLabel(max_box, text="Ignorar arquivos maiores que (/MAX em bytes):", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=("#64748b", "#9e9e9e")).pack(side="left")
        self._create_info_badge(max_box, "Exemplo: 52428800 para ignorar qualquer arquivo com mais de 50MB.").pack(side="left", padx=6)

        self.entry_max_size = ctk.CTkEntry(f2, placeholder_text="Ex: 52428800 (para 50MB)", font=ctk.CTkFont(family="Consolas", size=11), height=28)
        self.entry_max_size.pack(fill="x", padx=12, pady=(0, 6))
        self.entry_max_size.bind("<KeyRelease>", lambda e: self.update_command_preview())

        min_box = ctk.CTkFrame(f2, fg_color="transparent")
        min_box.pack(anchor="w", padx=12, pady=(4, 1))
        ctk.CTkLabel(min_box, text="Ignorar arquivos menores que (/MIN em bytes):", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=("#64748b", "#9e9e9e")).pack(side="left")
        self._create_info_badge(min_box, "Exemplo: 1024 para ignorar arquivos vazios ou menores que 1KB.").pack(side="left", padx=6)

        self.entry_min_size = ctk.CTkEntry(f2, placeholder_text="Ex: 1024 (para 1KB)", font=ctk.CTkFont(family="Consolas", size=11), height=28)
        self.entry_min_size.pack(fill="x", padx=12, pady=(0, 6))
        self.entry_min_size.bind("<KeyRelease>", lambda e: self.update_command_preview())

        pat_box = ctk.CTkFrame(f2, fg_color="transparent")
        pat_box.pack(anchor="w", padx=12, pady=(6, 1))
        ctk.CTkLabel(pat_box, text="Padrão de nome de arquivo (Filtro):", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=("#64748b", "#9e9e9e")).pack(side="left")
        self._create_info_badge(pat_box, "Padrão *.* copia todos. Se quiser apenas fotos, digite: *.jpg *.png").pack(side="left", padx=6)

        self.entry_pattern = ctk.CTkEntry(f2, width=120, height=28, font=ctk.CTkFont(family="Consolas", size=11))
        self.entry_pattern.insert(0, "*.*")
        self.entry_pattern.pack(anchor="w", padx=12, pady=(0, 8))
        self.entry_pattern.bind("<KeyRelease>", lambda e: self.update_command_preview())

    def _build_advanced_perf_tab(self, parent):
        parent.grid_columnconfigure((0, 1), weight=1)

        f1 = ctk.CTkFrame(parent, border_width=1, border_color=("#cbd5e1", "#2d2d2d"), fg_color=("#f8fafc", "#1a1a1a"))
        f1.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(f1, text="Processamento Paralelo (Velocidade)", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))

        mt_box = ctk.CTkFrame(f1, fg_color="transparent")
        mt_box.pack(anchor="w", padx=12, pady=(6, 2))
        self.lbl_mt = ctk.CTkLabel(mt_box, text="Arquivos copiados simultaneamente (/MT:8):", font=ctk.CTkFont(family="Segoe UI", size=12))
        self.lbl_mt.pack(side="left")
        self._create_info_badge(mt_box, "Aumenta drasticamente a velocidade ao copiar milhares de fotos, músicas ou documentos em SSDs e redes locais.").pack(side="left", padx=6)

        self.slider_mt = ctk.CTkSlider(f1, from_=1, to=64, number_of_steps=63, command=self._on_mt_change)
        self.slider_mt.set(8)
        self.slider_mt.pack(fill="x", padx=12, pady=4)

        f2 = ctk.CTkFrame(parent, border_width=1, border_color=("#cbd5e1", "#2d2d2d"), fg_color=("#f8fafc", "#1a1a1a"))
        f2.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(f2, text="Proteção contra Travamentos", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))

        r_box = ctk.CTkFrame(f2, fg_color="transparent")
        r_box.pack(anchor="w", padx=12, pady=(6, 2))
        self.lbl_r = ctk.CTkLabel(r_box, text="Tentativas em caso de arquivo bloqueado (/R:1):", font=ctk.CTkFont(family="Segoe UI", size=12))
        self.lbl_r.pack(side="left")
        self._create_info_badge(r_box, "Se um arquivo estiver em uso por outro programa, quantas vezes tentar de novo antes de prosseguir. O padrão de 1 evita travamentos.").pack(side="left", padx=6)

        self.slider_r = ctk.CTkSlider(f2, from_=0, to=10, number_of_steps=10, command=self._on_r_change)
        self.slider_r.set(1)
        self.slider_r.pack(fill="x", padx=12, pady=4)

        w_box = ctk.CTkFrame(f2, fg_color="transparent")
        w_box.pack(anchor="w", padx=12, pady=(6, 2))
        self.lbl_w = ctk.CTkLabel(w_box, text="Tempo de espera entre tentativas (/W:3 seg):", font=ctk.CTkFont(family="Segoe UI", size=12))
        self.lbl_w.pack(side="left")
        self._create_info_badge(w_box, "Quantos segundos aguardar antes de tentar novamente o arquivo bloqueado.").pack(side="left", padx=6)

        self.slider_w = ctk.CTkSlider(f2, from_=0, to=30, number_of_steps=30, command=self._on_w_change)
        self.slider_w.set(3)
        self.slider_w.pack(fill="x", padx=12, pady=4)

    def _build_advanced_attrs_tab(self, parent):
        parent.grid_columnconfigure((0, 1), weight=1)

        f1 = ctk.CTkFrame(parent, border_width=1, border_color=("#cbd5e1", "#2d2d2d"), fg_color=("#f8fafc", "#1a1a1a"))
        f1.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(f1, text="Propriedades dos Arquivos", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))

        self.var_cp_d = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(f1, text="Conteúdo e dados do arquivo (/COPY:D)", font=ctk.CTkFont(family="Segoe UI", size=12), variable=self.var_cp_d, command=self.update_command_preview).pack(anchor="w", padx=12, pady=3)

        self.var_cp_a = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(f1, text="Atributos (Somente leitura, Oculto) (/COPY:A)", font=ctk.CTkFont(family="Segoe UI", size=12), variable=self.var_cp_a, command=self.update_command_preview).pack(anchor="w", padx=12, pady=3)

        self.var_cp_t = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(f1, text="Carimbos de data e horário originais (/COPY:T)", font=ctk.CTkFont(family="Segoe UI", size=12), variable=self.var_cp_t, command=self.update_command_preview).pack(anchor="w", padx=12, pady=3)

        r_sec = ctk.CTkFrame(f1, fg_color="transparent")
        r_sec.pack(anchor="w", padx=12, pady=3)
        self.var_cp_s = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(r_sec, text="Permissões de segurança do Windows NTFS (/COPY:S)", font=ctk.CTkFont(family="Segoe UI", size=12), variable=self.var_cp_s, command=self.update_command_preview).pack(side="left")
        self._create_info_badge(r_sec, "Copia as ACLs de controle de acesso de usuários corporativos.").pack(side="left", padx=6)

        f2 = ctk.CTkFrame(parent, border_width=1, border_color=("#cbd5e1", "#2d2d2d"), fg_color=("#f8fafc", "#1a1a1a"))
        f2.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")

        ctk.CTkLabel(f2, text="Gravar Arquivo de Relatório (Log)", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))

        self.var_log_np = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(f2, text="Ocultar porcentagens repetitivas no log (/NP)", font=ctk.CTkFont(family="Segoe UI", size=12), variable=self.var_log_np, command=self.update_command_preview).pack(anchor="w", padx=12, pady=3)

        ctk.CTkLabel(f2, text="Salvar relatório completo em arquivo externo:", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=("#64748b", "#9e9e9e")).pack(anchor="w", padx=12, pady=(6, 2))
        log_box = ctk.CTkFrame(f2, fg_color="transparent")
        log_box.pack(fill="x", padx=12, pady=2)

        self.entry_log_file = ctk.CTkEntry(log_box, placeholder_text="Ex: C:\\Logs\\backup.log", font=ctk.CTkFont(family="Consolas", size=11), height=28)
        self.entry_log_file.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_log_file.bind("<KeyRelease>", lambda e: self.update_command_preview())

        btn_log = ctk.CTkButton(log_box, text="Definir...", width=75, height=28, fg_color=("#e2e8f0", "#2b2b2b"), hover_color=("#cbd5e1", "#3d3d3d"), text_color=("#0f172a", "#ffffff"), command=self._browse_log_file)
        btn_log.pack(side="left")

    def _build_advanced_cmd_tab(self, parent):
        """Exibição do comando RoboCopy apenas para quem quiser inspecionar."""
        ctk.CTkLabel(
            parent,
            text="Linha de Comando RoboCopy que o sistema executa automaticamente nos bastidores:",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#64748b", "#9e9e9e")
        ).pack(anchor="w", padx=12, pady=(8, 4))

        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(fill="x", padx=12, pady=4)

        self.cmd_display = ctk.CTkEntry(
            box,
            height=30,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=("#ffffff", "#121212"),
            border_color=("#cbd5e1", "#2a2a2a"),
            text_color=("#0f172a", "#38bdf8")
        )
        self.cmd_display.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_copy = ctk.CTkButton(
            box, text="Copiar", width=70, height=30,
            fg_color=("#e2e8f0", "#2b2b2b"), hover_color=("#cbd5e1", "#3d3d3d"),
            text_color=("#0f172a", "#ffffff"),
            command=self._copy_command_to_clipboard
        )
        btn_copy.pack(side="right")

        self._build_extra_args_section(parent)

    def _build_extra_args_compact(self, parent):
        """
        Mesma funcionalidade do campo completo, em uma linha só. Usado na Central
        de Sincronização, onde o espaço vertical é disputado com a tabela.
        """
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(2, 0))

        ctk.CTkLabel(
            row,
            text="Flags personalizadas:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        ).pack(side="left")

        self._create_info_badge(
            row,
            "Qualquer argumento do RoboCopy que não tenha caixa própria na tela.\n"
            "Exemplos: /PURGE  /MIR  /FFT  /Z  /XX  /SL  /NOSD  /256  /IPG:20\n"
            "Os atalhos de um clique estão em Opções Avançadas ➔ Comando Interno."
        ).pack(side="left", padx=6)

        ctk.CTkEntry(
            row,
            textvariable=self.var_extra_args,
            placeholder_text="Ex: /FFT /Z",
            font=ctk.CTkFont(family="Consolas", size=11),
            height=26,
            width=220
        ).pack(side="left", padx=6)

        warning = ctk.CTkLabel(
            row,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#b45309", "#facc15"),
            anchor="w"
        )
        warning.pack(side="left", fill="x", expand=True, padx=6)
        self.extra_args_warning_labels.append(warning)

    def _build_extra_args_section(self, parent, compact: bool = False):
        """Campo livre para parâmetros avançados do RoboCopy que não têm caixa própria."""
        if compact:
            self._build_extra_args_compact(parent)
            return

        frame = ctk.CTkFrame(
            parent,
            fg_color=("#f8fafc", "#141a24"),
            corner_radius=4,
            border_width=1,
            border_color=("#e2e8f0", "#1e293b")
        )
        frame.pack(fill="x", padx=12, pady=(10, 8))

        title_row = ctk.CTkFrame(frame, fg_color="transparent")
        title_row.pack(fill="x", padx=10, pady=(8, 2))

        ctk.CTkLabel(
            title_row,
            text="Flags Personalizadas (parâmetros livres do RoboCopy):",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        ).pack(side="left")

        self._create_info_badge(
            title_row,
            "Digite aqui qualquer argumento do RoboCopy que não tenha uma caixa própria na tela.\n"
            "Eles são acrescentados ao final do comando, exatamente como você escrever.\n"
            "Exemplos: /PURGE  /MIR  /FFT  /Z  /XX  /SL  /NOSD  /256  /IPG:20\n"
            "Separe vários parâmetros por espaço. Use aspas em caminhos com espaço."
        ).pack(side="left", padx=6)

        entry = ctk.CTkEntry(
            frame,
            textvariable=self.var_extra_args,
            placeholder_text="Ex: /FFT /Z /XX  (deixe em branco para não usar nenhum parâmetro extra)",
            font=ctk.CTkFont(family="Consolas", size=11),
            height=30
        )
        entry.pack(fill="x", padx=10, pady=(2, 6))
        if not compact:
            self.entry_extra_args = entry

        chips = ctk.CTkFrame(frame, fg_color="transparent")
        if not compact:
            chips.pack(fill="x", padx=10, pady=(0, 4))

        ctk.CTkLabel(
            chips,
            text="Atalhos:",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#64748b", "#94a3b8")
        ).pack(side="left", padx=(0, 6))

        for flag, tip in EXTRA_FLAG_SHORTCUTS:
            chip = ctk.CTkButton(
                chips,
                text=flag,
                width=58,
                height=24,
                fg_color=("#e2e8f0", "#1e293b"),
                hover_color=("#cbd5e1", "#334155"),
                text_color=("#0f172a", "#e2e8f0"),
                font=ctk.CTkFont(family="Consolas", size=11),
                command=lambda f=flag: self._toggle_extra_flag(f)
            )
            chip.pack(side="left", padx=2)
            ToolTip(chip, tip, wraplength=380)

        ctk.CTkButton(
            chips,
            text="Limpar",
            width=60,
            height=24,
            fg_color=("#fee2e2", "#7f1d1d"),
            hover_color=("#fecaca", "#991b1b"),
            text_color=("#991b1b", "#fecaca"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=lambda: self.var_extra_args.set("")
        ).pack(side="left", padx=(10, 2))

        warning = ctk.CTkLabel(
            frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#b45309", "#facc15"),
            justify="left",
            anchor="w"
        )
        warning.pack(fill="x", padx=10, pady=(0, 8))
        self.extra_args_warning_labels.append(warning)

    def _build_live_monitor_card(self):
        """Card com métricas, Console ao Vivo colorido e Painel de Ocorrências."""
        self.monitor_card = ctk.CTkFrame(self.monitor_parent, corner_radius=6, border_width=1, border_color=("#e2e8f0", "#333333"), fg_color=("#ffffff", "#181818"))
        self.monitor_card.pack(fill="both", expand=True, pady=(4, 0))

        # Barra de métricas compacta (uma linha)
        stats_bar = ctk.CTkFrame(self.monitor_card, fg_color=("#f1f5f9", "#181818"), corner_radius=4)
        stats_bar.pack(fill="x", padx=10, pady=(8, 4))
        stats_bar.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.card_dirs = self._create_stat_card(stats_bar, 0, "Diretórios", "-")
        self.card_files = self._create_stat_card(stats_bar, 1, "Arquivos", "-")
        self.card_bytes = self._create_stat_card(stats_bar, 2, "Volume", "-")
        self.card_speed = self._create_stat_card(stats_bar, 3, "Velocidade", "-")

        # Barra de controle do console
        console_tools = ctk.CTkFrame(self.monitor_card, fg_color="transparent")
        console_tools.pack(fill="x", padx=10, pady=2)

        ctk.CTkLabel(
            console_tools,
            text="Registro de Execução ao Vivo:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#334155", "#94a3b8")
        ).pack(side="left")

        self._create_info_badge(
            console_tools,
            "A aba 'Console ao Vivo' mostra tudo o que o RoboCopy está fazendo, com cores por tipo de evento.\n"
            "A aba 'Ocorrências' isola automaticamente apenas o que exige a sua atenção."
        ).pack(side="left", padx=6)

        self.lbl_occurrence_badge = ctk.CTkLabel(
            console_tools,
            text="Ocorrências: 0",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=("#e2e8f0", "#1e293b"),
            text_color=("#334155", "#94a3b8"),
            corner_radius=4,
            padx=10, pady=2
        )
        self.lbl_occurrence_badge.pack(side="left", padx=8)

        btn_clear = ctk.CTkButton(
            console_tools, text="Limpar", width=65, height=24,
            fg_color=("#e2e8f0", "#2b2b2b"), hover_color=("#cbd5e1", "#3d3d3d"),
            text_color=("#0f172a", "#ffffff"), command=self._clear_log
        )
        btn_clear.pack(side="right", padx=3)

        btn_copy = ctk.CTkButton(
            console_tools, text="Copiar Log", width=75, height=24,
            fg_color=("#e2e8f0", "#2b2b2b"), hover_color=("#cbd5e1", "#3d3d3d"),
            text_color=("#0f172a", "#ffffff"), command=self._copy_log_to_clipboard
        )
        btn_copy.pack(side="right", padx=3)

        btn_save = ctk.CTkButton(
            console_tools, text="Exportar...", width=75, height=24,
            fg_color=("#e2e8f0", "#2b2b2b"), hover_color=("#cbd5e1", "#3d3d3d"),
            text_color=("#0f172a", "#ffffff"), command=self._save_log_as
        )
        btn_save.pack(side="right", padx=3)

        # Abas do monitor: saída completa, ocorrências e divergências
        self.monitor_tabs = ctk.CTkTabview(self.monitor_card, corner_radius=6)
        self.monitor_tabs.pack(fill="both", expand=True, padx=10, pady=(2, 10))

        self._build_console_tab(self.monitor_tabs.add(TAB_CONSOLE))
        self._build_occurrences_tab(self.monitor_tabs.add(TAB_OCCURRENCES))
        self._build_differences_tab(self.monitor_tabs.add(TAB_DIFFERENCES))

    def _show_tab(self, name: str):
        """
        Traz uma aba do monitor para a frente.

        O CTkTabview agenda uma limpeza 100 ms depois de cada troca, que esconde
        todas as abas menos a que estava selecionada naquele instante. Com duas
        trocas em sequência, a limpeza da primeira apaga a aba escolhida pela
        segunda e a área fica em branco (a interface parece travada). Por isso a
        aba é conferida e reaplicada depois que essas limpezas já rodaram.
        """
        self._pending_tab = name
        try:
            self.monitor_tabs.set(name)
        except Exception:
            return

        self.after(160, self._ensure_tab_visible)

    def _ensure_tab_visible(self):
        """Reaplica a aba pedida caso a limpeza atrasada do CTkTabview a tenha escondido."""
        name = getattr(self, "_pending_tab", "")
        if not name:
            return
        try:
            # winfo_manager() diz se o quadro continua no grid; ao contrário de
            # winfo_ismapped(), funciona mesmo com a janela minimizada ou oculta.
            if not self.monitor_tabs.tab(name).winfo_manager():
                self.monitor_tabs.set(name)
        except Exception:
            pass

    def _build_console_tab(self, parent):
        """Terminal com destaque de sintaxe por tipo de linha."""
        legend = ctk.CTkFrame(parent, fg_color="transparent")
        legend.pack(fill="x", padx=4, pady=(2, 2))

        ctk.CTkLabel(
            legend,
            text="Legenda:",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=("#64748b", "#94a3b8")
        ).pack(side="left", padx=(2, 6))

        for category, caption in (
            ("new_file", "Novo arquivo"),
            ("newer", "Atualizado"),
            ("extra_file", "Arquivo EXTRA"),
            ("mismatch", "Incompatibilidade"),
            ("error", "Falha / Acesso negado"),
        ):
            ctk.CTkLabel(
                legend,
                text=caption,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color=LOG_TAG_COLORS[category]
            ).pack(side="left", padx=6)

        # Controles de rolagem: por padrão o console acompanha a última linha.
        self.var_autoscroll = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            legend,
            text="Acompanhar a última linha",
            variable=self.var_autoscroll,
            command=self._on_autoscroll_toggle,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            checkbox_width=16,
            checkbox_height=16
        ).pack(side="right", padx=4)

        ctk.CTkButton(
            legend, text="Fim", width=46, height=22,
            fg_color=("#e2e8f0", "#2b2b2b"), hover_color=("#cbd5e1", "#3d3d3d"),
            text_color=("#0f172a", "#ffffff"),
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self._scroll_log_to_end
        ).pack(side="right", padx=2)

        ctk.CTkButton(
            legend, text="Início", width=52, height=22,
            fg_color=("#e2e8f0", "#2b2b2b"), hover_color=("#cbd5e1", "#3d3d3d"),
            text_color=("#0f172a", "#ffffff"),
            font=ctk.CTkFont(family="Segoe UI", size=10),
            command=self._scroll_log_to_start
        ).pack(side="right", padx=2)

        self.log_textbox = ctk.CTkTextbox(
            parent,
            wrap="none",
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=("#f8fafc", "#0b0f19"),
            text_color=("#0f172a", "#cbd5e1"),
            corner_radius=4,
            border_width=1,
            border_color=("#e2e8f0", "#1e293b")
        )
        self.log_textbox.pack(fill="both", expand=True, padx=4, pady=(2, 6))
        self._apply_log_tag_colors()

        # Rolar com a roda do mouse pausa o acompanhamento automático, para que a
        # linha que o usuário está lendo não fuja da tela.
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            try:
                self.log_textbox.bind(sequence, self._on_log_mouse_wheel, add=True)
            except Exception:
                pass

    def _on_log_mouse_wheel(self, _event=None):
        """Desliga o acompanhamento automático quando o usuário rola para trás."""
        def _check():
            try:
                if self.log_textbox.yview()[1] < 0.999:
                    self.var_autoscroll.set(False)
            except Exception:
                pass
        self.after(10, _check)

    def _on_autoscroll_toggle(self):
        if self.var_autoscroll.get():
            self._scroll_log_to_end()

    def _scroll_log_to_end(self):
        """Vai para o fim do log e volta a acompanhar as novas linhas."""
        self.var_autoscroll.set(True)
        self._show_tab(TAB_CONSOLE)
        try:
            self.log_textbox.see("end")
        except Exception:
            pass

    def _scroll_log_to_start(self):
        """Vai para o começo do log e pausa o acompanhamento automático."""
        self.var_autoscroll.set(False)
        self._show_tab(TAB_CONSOLE)
        try:
            self.log_textbox.see("1.0")
        except Exception:
            pass

    def _apply_log_tag_colors(self):
        """(Re)aplica as cores do destaque de sintaxe conforme o tema atual."""
        if not hasattr(self, "log_textbox"):
            return

        index = 0 if ctk.get_appearance_mode() == "Light" else 1
        for category, colors in LOG_TAG_COLORS.items():
            try:
                self.log_textbox.tag_config(f"cat_{category}", foreground=colors[index])
            except Exception:
                pass

    def _build_occurrences_tab(self, parent):
        """Tabela que isola apenas arquivos EXTRA, falhas e incompatibilidades."""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=4, pady=(4, 2))

        ctk.CTkLabel(
            header,
            text="Somente o que exige atenção:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#334155", "#94a3b8")
        ).pack(side="left")

        self._create_info_badge(
            header,
            "Esta lista é preenchida automaticamente enquanto o RoboCopy roda.\n"
            "Ela recolhe do log apenas as linhas de Arquivo EXTRA, Pasta EXTRA,\n"
            "Incompatibilidade e Falha/Acesso negado, com o caminho completo de cada item."
        ).pack(side="left", padx=6)

        self.occurrence_filter = ctk.CTkSegmentedButton(
            header,
            values=OCCURRENCE_FILTERS,
            command=self._on_occurrence_filter_change,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            height=26
        )
        self.occurrence_filter.set(OCCURRENCE_FILTERS[0])
        self.occurrence_filter.pack(side="left", padx=12)

        btn_open = ctk.CTkButton(
            header, text="Abrir Pasta", width=90, height=26,
            fg_color=("#e2e8f0", "#2b2b2b"), hover_color=("#cbd5e1", "#3d3d3d"),
            text_color=("#0f172a", "#ffffff"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._open_selected_occurrence
        )
        btn_open.pack(side="right", padx=3)

        btn_export = ctk.CTkButton(
            header, text="Exportar CSV", width=100, height=26,
            fg_color=("#e2e8f0", "#2b2b2b"), hover_color=("#cbd5e1", "#3d3d3d"),
            text_color=("#0f172a", "#ffffff"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._export_occurrences_csv
        )
        btn_export.pack(side="right", padx=3)

        self.lbl_occurrence_counts = ctk.CTkLabel(
            parent,
            text="Nenhuma ocorrência registrada até agora.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#64748b", "#94a3b8")
        )
        self.lbl_occurrence_counts.pack(anchor="w", padx=8, pady=(0, 4))

        table_box = ctk.CTkFrame(parent, fg_color="transparent")
        table_box.pack(fill="both", expand=True, padx=4, pady=(0, 6))

        self.tree_occurrences = ttk.Treeview(
            table_box,
            columns=("tipo", "tamanho", "caminho"),
            show="headings",
            style="RCM.Treeview",
            height=9,
            selectmode="extended"
        )
        self.tree_occurrences.heading("tipo", text="Tipo de Ocorrência")
        self.tree_occurrences.heading("tamanho", text="Tamanho")
        self.tree_occurrences.heading("caminho", text="Caminho completo do item")
        self.tree_occurrences.column("tipo", width=180, minwidth=140, stretch=False)
        self.tree_occurrences.column("tamanho", width=90, minwidth=70, anchor="e", stretch=False)
        self.tree_occurrences.column("caminho", width=620, minwidth=260, stretch=True)

        scroll_y = ctk.CTkScrollbar(table_box, command=self.tree_occurrences.yview)
        self.tree_occurrences.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side="right", fill="y", padx=(2, 0))
        self.tree_occurrences.pack(side="left", fill="both", expand=True)
        self.tree_occurrences.bind("<Double-1>", lambda e: self._open_selected_occurrence())

        self._apply_tree_tag_colors(self.tree_occurrences)

    def _create_stat_card(self, parent, col: int, title: str, initial_text: str):
        """Métrica em uma única linha: rótulo e valor lado a lado."""
        card = ctk.CTkFrame(parent, fg_color=("#ffffff", "#202020"), corner_radius=4, border_width=1, border_color=("#e2e8f0", "#2a2a2a"))
        card.grid(row=0, column=col, padx=4, pady=3, sticky="ew")
        ctk.CTkLabel(
            card, text=f"{title}:",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#334155", "#cbd5e1")
        ).pack(side="left", padx=(8, 4), pady=3)
        lbl_val = ctk.CTkLabel(
            card, text=initial_text,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("#0f172a", "#94a3b8")
        )
        lbl_val.pack(side="left", padx=(0, 8), pady=3)
        return lbl_val

    # -------------------------------------------------------------
    # TABELAS (ttk) - ESTILO COMPATÍVEL COM TEMA CLARO E ESCURO
    # -------------------------------------------------------------
    def _configure_tree_style(self):
        """Ajusta a aparência das tabelas ttk para acompanhar o tema do aplicativo."""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        is_light = ctk.get_appearance_mode() == "Light"
        background = "#ffffff" if is_light else "#0b0f19"
        foreground = "#0f172a" if is_light else "#cbd5e1"
        heading_bg = "#e2e8f0" if is_light else "#1e293b"
        heading_fg = "#0f172a" if is_light else "#e2e8f0"

        style.configure(
            "RCM.Treeview",
            background=background,
            fieldbackground=background,
            foreground=foreground,
            rowheight=24,
            borderwidth=1,
            font=("Segoe UI", 10),
        )
        style.map(
            "RCM.Treeview",
            background=[("selected", "#0f6cbd")],
            foreground=[("selected", "#ffffff")],
        )
        style.configure(
            "RCM.Treeview.Heading",
            background=heading_bg,
            foreground=heading_fg,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
        )
        style.map("RCM.Treeview.Heading", background=[("active", heading_bg)])

        for tree in (getattr(self, "tree_occurrences", None), getattr(self, "tree_differences", None)):
            if tree is not None:
                self._apply_tree_tag_colors(tree)

    def _apply_tree_tag_colors(self, tree):
        """Aplica a cor de cada categoria nas linhas da tabela."""
        index = 0 if ctk.get_appearance_mode() == "Light" else 1
        for category, colors in LOG_TAG_COLORS.items():
            try:
                tree.tag_configure(f"cat_{category}", foreground=colors[index])
            except Exception:
                pass

    # -------------------------------------------------------------
    # PAINEL DE OCORRÊNCIAS
    # -------------------------------------------------------------
    def _register_occurrence(self, entry):
        """Adiciona uma ocorrência detectada no log à tabela dedicada."""
        # Mensagens de detalhe de um erro ("Acesso negado.") complementam o erro anterior.
        if entry.category == "error" and not entry.path and self.occurrences:
            previous = self.occurrences[-1]
            if previous.category == "error":
                previous.message = f"{previous.message} {entry.message}".strip()
                self._refresh_occurrence_row(len(self.occurrences) - 1)
                return

        if len(self.occurrences) >= MAX_OCCURRENCE_ROWS:
            return

        self.occurrences.append(entry)
        self._insert_occurrence_row(len(self.occurrences) - 1)
        self._update_occurrence_counters()

    def _occurrence_matches_filter(self, entry) -> bool:
        selected = self.occurrence_filter.get() if hasattr(self, "occurrence_filter") else OCCURRENCE_FILTERS[0]
        if selected == OCCURRENCE_FILTERS[1]:
            return entry.category in ("extra_file", "extra_dir", "lonely")
        if selected == OCCURRENCE_FILTERS[2]:
            return entry.category == "error"
        if selected == OCCURRENCE_FILTERS[3]:
            return entry.category == "mismatch"
        return True

    def _insert_occurrence_row(self, index: int):
        entry = self.occurrences[index]
        if not self._occurrence_matches_filter(entry):
            return
        try:
            self.tree_occurrences.insert(
                "", "end", iid=str(index),
                values=(entry.label, format_size(entry.size), entry.display_path),
                tags=(f"cat_{entry.category}",),
            )
        except Exception:
            pass

    def _refresh_occurrence_row(self, index: int):
        entry = self.occurrences[index]
        if self.tree_occurrences.exists(str(index)):
            self.tree_occurrences.item(
                str(index),
                values=(entry.label, format_size(entry.size), entry.display_path),
            )

    def _on_occurrence_filter_change(self, _value=None):
        self._repopulate_occurrences()

    def _repopulate_occurrences(self):
        """Redesenha a tabela de ocorrências respeitando o filtro selecionado."""
        for item in self.tree_occurrences.get_children():
            self.tree_occurrences.delete(item)
        for index in range(len(self.occurrences)):
            self._insert_occurrence_row(index)
        self._update_occurrence_counters()

    def _update_occurrence_counters(self):
        total = len(self.occurrences)
        extras = sum(1 for o in self.occurrences if o.category in ("extra_file", "extra_dir", "lonely"))
        failures = sum(1 for o in self.occurrences if o.category == "error")
        mismatches = sum(1 for o in self.occurrences if o.category == "mismatch")

        self.lbl_occurrence_badge.configure(text=f"Ocorrências: {total}")
        if total == 0:
            self.lbl_occurrence_counts.configure(text="Nenhuma ocorrência registrada até agora.")
        else:
            self.lbl_occurrence_counts.configure(
                text=(
                    f"Total: {total}  |  Arquivos/Pastas EXTRA: {extras}  |  "
                    f"Falhas e acessos negados: {failures}  |  Incompatibilidades: {mismatches}"
                )
            )

    def _clear_occurrences(self):
        self.occurrences = []
        for item in self.tree_occurrences.get_children():
            self.tree_occurrences.delete(item)
        self._update_occurrence_counters()

    def _selected_occurrence_paths(self):
        paths = []
        for item_id in self.tree_occurrences.selection():
            try:
                entry = self.occurrences[int(item_id)]
            except (ValueError, IndexError):
                continue
            if entry.path:
                paths.append(entry.path)
        return paths

    def _open_selected_occurrence(self):
        """Abre no Explorer a pasta do item selecionado."""
        paths = self._selected_occurrence_paths()
        if not paths:
            messagebox.showinfo("Abrir Pasta", "Selecione na lista a ocorrência que deseja localizar no Explorer.")
            return
        self._reveal_in_explorer(paths[0])

    def _reveal_in_explorer(self, path: str):
        """Mostra o item no Explorer do Windows (ou abre a pasta que o contém)."""
        if os.name != "nt":
            messagebox.showinfo("Abrir Pasta", f"Caminho do item:\n{path}")
            return
        try:
            if os.path.exists(path):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            else:
                parent = os.path.dirname(os.path.normpath(path))
                if os.path.isdir(parent):
                    subprocess.Popen(["explorer", parent])
                else:
                    messagebox.showwarning("Abrir Pasta", f"O caminho não existe mais:\n{path}")
        except Exception as ex:
            messagebox.showerror("Abrir Pasta", f"Não foi possível abrir o Explorer:\n{ex}")

    def _export_occurrences_csv(self):
        """Exporta a lista de ocorrências para um arquivo CSV."""
        if not self.occurrences:
            messagebox.showinfo("Exportar Ocorrências", "Não há ocorrências registradas para exportar.")
            return

        filepath = filedialog.asksaveasfilename(
            title="Exportar Lista de Ocorrências",
            defaultextension=".csv",
            filetypes=[("Planilha CSV", "*.csv"), ("Todos os Arquivos", "*.*")]
        )
        if not filepath:
            return

        try:
            with open(filepath, "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle, delimiter=";")
                writer.writerow(["Tipo", "Tamanho (bytes)", "Caminho", "Linha original do RoboCopy"])
                for entry in self.occurrences:
                    writer.writerow([entry.label, entry.size if entry.size is not None else "", entry.display_path, entry.raw.strip()])
            messagebox.showinfo("Exportado", f"Lista de ocorrências salva em:\n{filepath}")
        except Exception as ex:
            messagebox.showerror("Erro ao Exportar", f"Não foi possível salvar o arquivo:\n{ex}")

    def _build_footer(self):
        """Rodapé fixo de ação com status e os grandes botões de Iniciar Cópia e Simular."""
        footer = ctk.CTkFrame(self, fg_color=("#f8fafc", "#181818"), corner_radius=0, border_width=1, border_color=("#e2e8f0", "#2d2d2d"))
        footer.pack(fill="x", side="bottom")

        inner = ctk.CTkFrame(footer, fg_color="transparent")
        inner.pack(fill="x", padx=24, pady=12)

        # Status à esquerda
        self.lbl_status = ctk.CTkLabel(
            inner,
            text="Status: Pronto para iniciar",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=("#16a34a", "#4ade80")
        )
        self.lbl_status.pack(side="left")

        # Botão de ajuda que explica o código de saída exibido no status
        self.btn_status_help = ctk.CTkButton(
            inner,
            text="?",
            width=26,
            height=26,
            corner_radius=13,
            fg_color=("#e2e8f0", "#1e293b"),
            hover_color=("#cbd5e1", "#334155"),
            text_color=("#0f172a", "#e2e8f0"),
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._show_status_details
        )
        self.btn_status_help.pack(side="left", padx=8)
        self.tip_status = ToolTip(
            self.btn_status_help,
            "Execute uma cópia para ver aqui a explicação completa do código de saída do RoboCopy.",
            wraplength=430
        )

        # Aparece apenas quando a execução termina com divergências entre as pastas
        self.btn_resolve = ctk.CTkButton(
            inner,
            text="Resolver Divergências",
            height=30,
            fg_color=("#fef3c7", "#78350f"),
            hover_color=("#fde68a", "#92400e"),
            text_color=("#92400e", "#fde68a"),
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._open_sync_center_for_resolution
        )
        ToolTip(
            self.btn_resolve,
            "Abre a Central de Sincronização e lista arquivo por arquivo o que está diferente,\n"
            "com o caminho completo e a ação que você pode aplicar em cada um.",
            wraplength=400
        )

        # Botões de ação à direita
        self.btn_cancel = ctk.CTkButton(
            inner,
            text="Interromper",
            fg_color=("#fee2e2", "#7f1d1d"),
            hover_color=("#fecaca", "#991b1b"),
            text_color=("#991b1b", "#fecaca"),
            width=110,
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            state="disabled",
            command=self._cancel_robocopy
        )
        self.btn_cancel.pack(side="right", padx=(6, 0))

        self.btn_simulate = ctk.CTkButton(
            inner,
            text="Simular (Testar sem risco)",
            fg_color=("#e2e8f0", "#334155"),
            hover_color=("#cbd5e1", "#475569"),
            text_color=("#0f172a", "#f1f5f9"),
            width=175,
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._start_dry_run
        )
        self.btn_simulate.pack(side="right", padx=6)

        self.btn_run = ctk.CTkButton(
            inner,
            text="Iniciar Cópia",
            fg_color="#0f6cbd",
            hover_color="#115ea3",
            text_color="#ffffff",
            width=175,
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self._start_robocopy
        )
        self.btn_run.pack(side="right", padx=6)

    # -------------------------------------------------------------
    # EVENTOS E SINCRONIZAÇÃO
    # -------------------------------------------------------------
    def _on_preset_selected(self):
        # Se o painel GoodSync estiver aberto, fecha-o para que o preset padrão tenha prioridade imediata
        if self.sync_visible:
            self.sync_container.pack_forget()
            self.btn_toggle_sync.configure(text="Sincronizar Pastas (Modo GoodSync)")
            self.sync_visible = False

        key = self.selected_preset_key.get()

        # Mantém o seletor e o texto explicativo alinhados, inclusive quando a
        # predefinição é trocada por código em vez de por clique.
        label = self.preset_label_by_key.get(key)
        if label and self.mode_selector.get() != label:
            self.mode_selector.set(label)
        self.lbl_mode_description.configure(text=self.preset_description_by_key.get(key, ""))

        cfg = self._gather_config_from_ui()
        cfg = apply_preset_to_config(cfg, key)
        self._sync_ui_from_config(cfg)
        self.update_command_preview()

    def _on_chk_e_change(self):
        if self.var_copy_e.get():
            self.var_mirror.set(False)
            self.var_copy_s.set(False)
        self.update_command_preview()

    def _on_chk_s_change(self):
        if self.var_copy_s.get():
            self.var_mirror.set(False)
            self.var_copy_e.set(False)
        self.update_command_preview()

    def _on_chk_mir_change(self):
        if self.var_mirror.get():
            self.var_copy_e.set(False)
            self.var_copy_s.set(False)
            self.var_two_way.set(False)
        self.update_command_preview()

    def _on_mode_change(self):
        self.update_command_preview()

    def _on_two_way_change(self):
        """Sincronização dupla é incompatível com espelhamento e com mover arquivos."""
        if self.var_two_way.get():
            self.var_mirror.set(False)
            self.var_move_all.set(False)
            self.var_move_files.set(False)
            self.var_copy_e.set(True)
            self.var_copy_s.set(False)
            self.var_xo.set(True)
        self.update_command_preview()

    def _toggle_extra_flag(self, flag: str):
        """Adiciona ou remove uma flag pelos botões de atalho."""
        current = self.var_extra_args.get().strip()
        tokens = current.split()
        upper = flag.upper()

        remaining = [t for t in tokens if t.split(":", 1)[0].upper() != upper]
        if len(remaining) != len(tokens):
            self.var_extra_args.set(" ".join(remaining))
        else:
            tokens.append(flag)
            self.var_extra_args.set(" ".join(tokens))

    def _on_extra_args_change(self):
        """Valida as flags livres e avisa quando alguma delas apaga arquivos."""
        diagnosis = analyze_extra_args(self.var_extra_args.get())
        for label in self.extra_args_warning_labels:
            try:
                label.configure(text=diagnosis["warning"])
            except Exception:
                pass
        self.update_command_preview()

    def _on_chk_mov_change(self):
        if self.var_move_files.get():
            self.var_move_all.set(False)
            self.var_two_way.set(False)
        self.update_command_preview()

    def _on_chk_move_change(self):
        if self.var_move_all.get():
            self.var_move_files.set(False)
            self.var_two_way.set(False)
        self.update_command_preview()

    def _on_mt_change(self, val):
        self.lbl_mt.configure(text=f"Arquivos copiados simultaneamente (/MT:{int(val)}):")
        self.update_command_preview()

    def _on_r_change(self, val):
        self.lbl_r.configure(text=f"Tentativas em caso de arquivo bloqueado (/R:{int(val)}):")
        self.update_command_preview()

    def _on_w_change(self, val):
        self.lbl_w.configure(text=f"Tempo de espera entre tentativas (/W:{int(val)} seg):")
        self.update_command_preview()

    def _gather_config_from_ui(self) -> RobocopyConfig:
        cfg = RobocopyConfig()
        cfg.source = self.entry_source.get().strip()
        cfg.destination = self.entry_dest.get().strip()
        cfg.file_pattern = self.entry_pattern.get().strip() or "*.*"

        cfg.copy_subdirs_empty = self.var_copy_e.get()
        cfg.copy_subdirs = self.var_copy_s.get()
        cfg.mirror = self.var_mirror.get()
        try:
            cfg.subfolder_level = int(self.entry_lev.get().strip() or 0)
        except ValueError:
            cfg.subfolder_level = 0

        cfg.restartable = self.var_mode_z.get()
        cfg.unbuffered_io = self.var_mode_j.get()
        cfg.move_files = self.var_move_files.get()
        cfg.move_all = self.var_move_all.get()

        cfg.exclude_files = self.entry_xf.get().strip()
        cfg.exclude_dirs = self.entry_xd.get().strip()
        cfg.exclude_junctions = self.var_xj.get()
        cfg.exclude_older = self.var_xo.get()
        cfg.max_size = self.entry_max_size.get().strip()
        cfg.min_size = self.entry_min_size.get().strip()

        cfg.multi_threaded = int(self.slider_mt.get())
        cfg.retries = int(self.slider_r.get())
        cfg.wait_time = int(self.slider_w.get())

        cfg.copy_data = self.var_cp_d.get()
        cfg.copy_attrs = self.var_cp_a.get()
        cfg.copy_timestamps = self.var_cp_t.get()
        cfg.copy_security = self.var_cp_s.get()

        cfg.no_progress = self.var_log_np.get()
        cfg.log_file = self.entry_log_file.get().strip()

        cfg.is_two_way_sync = self.var_two_way.get()
        cfg.extra_args = self.var_extra_args.get().strip()

        # Sobrescrita inteligente e isolada se o painel GoodSync estiver ativo
        if self.sync_visible:
            mode = self.var_goodsync_mode.get()
            if mode == "goodsync_mirror":
                cfg.mirror = True
                cfg.copy_subdirs_empty = False
                cfg.copy_subdirs = False
                cfg.purge = False
                cfg.move_all = False
                cfg.move_files = False
                cfg.is_two_way_sync = False
                cfg.verbose_timestamps = True
                cfg.retries = 3
                cfg.wait_time = 5
            elif mode == "goodsync_update":
                cfg.mirror = False
                cfg.copy_subdirs_empty = True
                cfg.copy_subdirs = False
                cfg.purge = False
                cfg.move_all = False
                cfg.move_files = False
                cfg.exclude_older = True
                cfg.is_two_way_sync = False
                cfg.verbose_timestamps = False
                cfg.retries = 3
                cfg.wait_time = 5
            elif mode == "goodsync_two_way":
                cfg.mirror = False
                cfg.copy_subdirs_empty = True
                cfg.copy_subdirs = False
                cfg.purge = False
                cfg.move_all = False
                cfg.move_files = False
                cfg.exclude_older = True
                cfg.is_two_way_sync = True
                cfg.verbose_timestamps = False
                cfg.retries = 3
                cfg.wait_time = 5
            elif mode == "goodsync_move":
                cfg.mirror = False
                cfg.copy_subdirs_empty = True
                cfg.copy_subdirs = False
                cfg.purge = False
                cfg.move_all = True
                cfg.move_files = False
                cfg.is_two_way_sync = False
                cfg.verbose_timestamps = False
                cfg.retries = 3
                cfg.wait_time = 5
            elif mode == "goodsync_filter":
                cfg.mirror = False
                cfg.copy_subdirs_empty = True
                cfg.copy_subdirs = False
                cfg.purge = False
                cfg.move_all = False
                cfg.move_files = False
                cfg.is_two_way_sync = False
                cfg.verbose_timestamps = False
                cfg.exclude_files = self.entry_sync_xf.get().strip()
                cfg.max_size = self.entry_sync_max.get().strip()
                cfg.retries = 3
                cfg.wait_time = 5

            if hasattr(self, "var_sync_mt32") and self.var_sync_mt32.get():
                cfg.multi_threaded = 32
            else:
                cfg.multi_threaded = int(self.slider_mt.get())

            if hasattr(self, "var_sync_copyall"):
                cfg.copyall = self.var_sync_copyall.get()
            if hasattr(self, "var_sync_zb"):
                cfg.restartable_backup = self.var_sync_zb.get()

        return cfg

    def _sync_ui_from_config(self, cfg: RobocopyConfig):
        self.entry_source.delete(0, "end")
        self.entry_source.insert(0, cfg.source or "")

        self.entry_dest.delete(0, "end")
        self.entry_dest.insert(0, cfg.destination or "")

        self.entry_pattern.delete(0, "end")
        self.entry_pattern.insert(0, cfg.file_pattern or "*.*")

        self.var_copy_e.set(cfg.copy_subdirs_empty)
        self.var_copy_s.set(cfg.copy_subdirs)
        self.var_mirror.set(cfg.mirror)
        self.entry_lev.delete(0, "end")
        self.entry_lev.insert(0, str(cfg.subfolder_level))

        self.var_mode_z.set(cfg.restartable)
        self.var_mode_j.set(cfg.unbuffered_io)
        self.var_move_files.set(cfg.move_files)
        self.var_move_all.set(cfg.move_all)

        self.entry_xf.delete(0, "end")
        self.entry_xf.insert(0, cfg.exclude_files)
        self.entry_xd.delete(0, "end")
        self.entry_xd.insert(0, cfg.exclude_dirs)
        self.var_xj.set(cfg.exclude_junctions)
        self.var_xo.set(cfg.exclude_older)

        self.entry_max_size.delete(0, "end")
        self.entry_max_size.insert(0, cfg.max_size)
        self.entry_min_size.delete(0, "end")
        self.entry_min_size.insert(0, cfg.min_size)

        self.slider_mt.set(cfg.multi_threaded)
        self.lbl_mt.configure(text=f"Arquivos copiados simultaneamente (/MT:{cfg.multi_threaded}):")

        self.slider_r.set(cfg.retries)
        self.lbl_r.configure(text=f"Tentativas em caso de arquivo bloqueado (/R:{cfg.retries}):")

        self.slider_w.set(cfg.wait_time)
        self.lbl_w.configure(text=f"Tempo de espera entre tentativas (/W:{cfg.wait_time} seg):")

        self.var_cp_d.set(cfg.copy_data)
        self.var_cp_a.set(cfg.copy_attrs)
        self.var_cp_t.set(cfg.copy_timestamps)
        self.var_cp_s.set(cfg.copy_security)

        self.var_log_np.set(cfg.no_progress)
        self.entry_log_file.delete(0, "end")
        self.entry_log_file.insert(0, cfg.log_file)

        self.var_two_way.set(cfg.is_two_way_sync)
        if cfg.extra_args != self.var_extra_args.get():
            self.var_extra_args.set(cfg.extra_args)

        # Sincroniza widgets do painel GoodSync caso existam
        if hasattr(self, "var_sync_mt32"):
            self.var_sync_mt32.set(cfg.multi_threaded >= 32)
        if hasattr(self, "var_sync_copyall"):
            self.var_sync_copyall.set(cfg.copyall)
        if hasattr(self, "var_sync_zb"):
            self.var_sync_zb.set(cfg.restartable_backup)
        if hasattr(self, "entry_sync_xf") and cfg.exclude_files:
            self.entry_sync_xf.delete(0, "end")
            self.entry_sync_xf.insert(0, cfg.exclude_files)
        if hasattr(self, "entry_sync_max") and cfg.max_size:
            self.entry_sync_max.delete(0, "end")
            self.entry_sync_max.insert(0, cfg.max_size)

    def update_command_preview(self):
        cfg = self._gather_config_from_ui()
        cmd_str = self.engine.build_command_string(cfg)
        self.cmd_display.configure(state="normal")
        self.cmd_display.delete(0, "end")
        self.cmd_display.insert(0, cmd_str)
        self.cmd_display.configure(state="readonly")

    def _copy_command_to_clipboard(self):
        cmd = self.cmd_display.get()
        if cmd:
            self.clipboard_clear()
            self.clipboard_append(cmd)
            messagebox.showinfo("Copiado", "Comando copiado para a área de transferência.")

    # -------------------------------------------------------------
    # DRAG & DROP E PASTAS
    # -------------------------------------------------------------
    def _setup_drag_and_drop(self):
        try:
            windnd.hook_dropfiles(self.entry_source, func=lambda files: self._on_drop(files, self.entry_source))
            windnd.hook_dropfiles(self.entry_dest, func=lambda files: self._on_drop(files, self.entry_dest))
        except Exception:
            pass

    def _on_drop(self, files, target_entry):
        if files:
            path = files[0]
            if isinstance(path, bytes):
                path = path.decode("utf-8", errors="ignore")
            target_entry.delete(0, "end")
            target_entry.insert(0, path)
            self.update_command_preview()

    def _paste_to_entry(self, entry):
        try:
            content = self.clipboard_get().strip()
            if (content.startswith('"') and content.endswith('"')) or (content.startswith("'") and content.endswith("'")):
                content = content[1:-1]
            entry.delete(0, "end")
            entry.insert(0, content)
            self.update_command_preview()
        except Exception:
            pass

    def _browse_source(self):
        chosen = filedialog.askdirectory(title="Selecione a Pasta de Origem")
        if chosen:
            path = os.path.normpath(chosen)
            self.entry_source.delete(0, "end")
            self.entry_source.insert(0, path)
            self.update_command_preview()

    def _browse_destination(self):
        chosen = filedialog.askdirectory(title="Selecione a Pasta de Destino")
        if chosen:
            path = os.path.normpath(chosen)
            self.entry_dest.delete(0, "end")
            self.entry_dest.insert(0, path)
            self.update_command_preview()

    def _browse_log_file(self):
        chosen = filedialog.asksaveasfilename(
            title="Definir Arquivo de Relatório",
            defaultextension=".log",
            filetypes=[("Arquivos de Log", "*.log"), ("Todos os Arquivos", "*.*")]
        )
        if chosen:
            self.entry_log_file.delete(0, "end")
            self.entry_log_file.insert(0, os.path.normpath(chosen))
            self.update_command_preview()

    def _swap_paths(self):
        src = self.entry_source.get()
        dst = self.entry_dest.get()
        self.entry_source.delete(0, "end")
        self.entry_source.insert(0, dst)
        self.entry_dest.delete(0, "end")
        self.entry_dest.insert(0, src)
        self.update_command_preview()

    # -------------------------------------------------------------
    # EXECUÇÃO DO ROBOCOPY
    # -------------------------------------------------------------
    def _start_dry_run(self):
        self._execute(is_dry_run=True)

    def _start_robocopy(self):
        cfg = self._gather_config_from_ui()

        diagnosis = analyze_extra_args(cfg.extra_args)
        if diagnosis["is_destructive"]:
            details = "\n".join(
                f"  {flag} — {DESTRUCTIVE_FLAGS[flag]}" for flag in diagnosis["destructive"]
            )
            confirm = messagebox.askyesno(
                "Atenção - Flags Personalizadas que Apagam Arquivos",
                "As flags personalizadas que você digitou incluem parâmetros que apagam arquivos:\n\n"
                f"{details}\n\nDeseja realmente executar com esses parâmetros?"
            )
            if not confirm:
                return

        if cfg.is_two_way_sync:
            confirm = messagebox.askyesno(
                "Sincronização Dupla (2 vias)",
                "A operação será executada em duas etapas automáticas:\n\n"
                f"  Etapa 1: {cfg.source or '(origem)'}  ➔  {cfg.destination or '(destino)'}\n"
                f"  Etapa 2: {cfg.destination or '(destino)'}  ➔  {cfg.source or '(origem)'}\n\n"
                "Somente arquivos mais novos são copiados em cada direção (/XO) e nada é apagado.\n"
                "No final, o status mostra o resultado consolidado das duas etapas.\n\n"
                "Deseja iniciar?"
            )
            if not confirm:
                return
        elif cfg.mirror:
            confirm = messagebox.askyesno(
                "Atenção - Modo Espelhamento",
                "O modo de espelhamento excluirá do destino arquivos que não estejam na origem.\n\n"
                "Dica: use 'Analisar Diferenças' na Central de Sincronização para ver antes, "
                "arquivo por arquivo, o que seria apagado.\n\n"
                "Deseja realmente prosseguir com a cópia?"
            )
            if not confirm:
                return
        elif cfg.move_all or cfg.move_files:
            confirm = messagebox.askyesno(
                "Atenção - Mover Arquivos",
                "Os arquivos transferidos serão apagados da pasta de origem após a conclusão da cópia.\n\n"
                "Deseja realmente mover os arquivos?"
            )
            if not confirm:
                return

        self._execute(is_dry_run=False)

    def _execute(self, is_dry_run: bool):
        cfg = self._gather_config_from_ui()
        cfg.dry_run = is_dry_run

        if not cfg.source:
            messagebox.showwarning("Caminho Inválido", "Por favor, selecione a pasta de Origem.")
            self.entry_source.focus()
            return

        if not os.path.exists(cfg.source):
            messagebox.showerror("Origem Inexistente", f"A pasta de origem não foi encontrada:\n{cfg.source}")
            return

        if not cfg.destination:
            messagebox.showwarning("Caminho Inválido", "Por favor, selecione a pasta de Destino.")
            self.entry_dest.focus()
            return

        # Bloqueio de controles
        self.is_busy = True
        self.btn_run.configure(state="disabled")
        self.btn_simulate.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        for button in self._analyze_buttons:
            button.configure(state="disabled")
        self.btn_apply_plan.configure(state="disabled")
        self.btn_resolve.pack_forget()

        # As ocorrências sempre refletem a execução atual
        self._clear_occurrences()

        # Leva o usuário direto para a saída ao vivo, já acompanhando a última linha
        self._show_tab(TAB_CONSOLE)
        self.var_autoscroll.set(True)

        if cfg.is_two_way_sync:
            mode_label = "Sincronização dupla em andamento (2 etapas)"
        elif is_dry_run:
            mode_label = "Simulação (Testando sem risco)"
        else:
            mode_label = "Copiando arquivos"
        self.lbl_status.configure(text=f"Status: {mode_label}...", text_color=("#d97706", "#facc15"))

        self.engine.run(
            config=cfg,
            on_line=self._handle_output_line,
            on_finish=self._handle_finish
        )

    def _handle_output_line(self, line: str):
        self.after(0, self._append_log_line, line)

    def _append_log_line(self, line: str):
        """Escreve a linha no console aplicando a cor da categoria e alimenta as ocorrências."""
        category = classify_log_line(line)

        try:
            self.log_textbox.insert("end", line, f"cat_{category}")
        except Exception:
            self.log_textbox.insert("end", line)

        self._trim_log_if_needed()
        if self.var_autoscroll.get():
            self.log_textbox.see("end")

        if category in OCCURRENCE_CATEGORIES:
            entry = parse_log_entry(line)
            if entry is not None:
                self._register_occurrence(entry)

    def _trim_log_if_needed(self):
        """Evita travamentos descartando o início do log quando ele fica gigante."""
        try:
            total_lines = int(self.log_textbox.index("end-1c").split(".")[0])
        except Exception:
            return
        if total_lines > MAX_LOG_LINES:
            self.log_textbox.delete("1.0", f"{LOG_TRIM_BLOCK}.0")

    def _handle_finish(self, exit_code: int, title: str, desc: str, summary: dict):
        self.after(0, self._on_process_completed, exit_code, title, desc, summary)

    def _on_process_completed(self, exit_code: int, title: str, desc: str, summary: dict):
        self.is_busy = False
        self.btn_run.configure(state="normal")
        self.btn_simulate.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        for button in self._analyze_buttons:
            button.configure(state="normal")
        if self.sync_differences:
            self.btn_apply_plan.configure(state="normal")

        self.last_summary = summary or {}
        self.last_exit_code = exit_code

        self.card_dirs.configure(
            text=f"{summary.get('dirs_total', '-')} ({summary.get('dirs_copied', '-')} copiados)"
        )
        self.card_files.configure(
            text=f"{summary.get('files_total', '-')} ({summary.get('files_copied', '-')} copiados, "
                 f"{summary.get('files_failed', '0')} falhas)"
        )
        self.card_bytes.configure(
            text=f"{summary.get('bytes_copied', '-')} de {summary.get('bytes_total', '-')}"
        )
        self.card_speed.configure(text=f"{summary.get('speed', '-')}")

        self._update_status_result(exit_code, title, desc, summary)

    def _update_status_result(self, exit_code: int, title: str, desc: str, summary: dict):
        """Atualiza o rodapé com o resultado consolidado, a explicação e os atalhos de ação."""
        steps = (summary or {}).get("steps") or []

        if exit_code >= 8:
            status_color = ("#dc2626", "#f87171")
        elif exit_code >= 2:
            status_color = ("#d97706", "#facc15")
        else:
            status_color = ("#16a34a", "#4ade80")

        suffix = f" (resultado consolidado de {len(steps)} etapas)" if len(steps) > 1 else ""
        self.lbl_status.configure(
            text=f"Status: [{exit_code}] {title} - {desc}{suffix}",
            text_color=status_color
        )

        explanation = (summary or {}).get("explanation") or explain_exit_code(exit_code, steps)
        self.status_explanation = explanation
        self.tip_status.set_text(explanation)

        # O atalho de resolução só faz sentido quando há divergência entre as pastas
        has_divergence = bool(exit_code & 2 or exit_code & 4) or any(
            o.category in ("extra_file", "extra_dir", "lonely", "mismatch") for o in self.occurrences
        )
        if has_divergence:
            if not self.btn_resolve.winfo_manager():
                self.btn_resolve.pack(side="left", padx=(4, 0))
        else:
            self.btn_resolve.pack_forget()

        # Terminou com algo para o usuário revisar: mostra a lista em vez de
        # deixá-lo procurar no meio do log.
        if self.occurrences:
            self._show_tab(TAB_OCCURRENCES)

    def _show_status_details(self):
        """Janela explicando em detalhes o código de saída da última execução."""
        explanation = getattr(self, "status_explanation", "") or (
            "Nenhuma execução foi concluída ainda nesta sessão.\n\n"
            "Assim que uma cópia ou sincronização terminar, este botão mostra:\n"
            "  - o que o código de saída do RoboCopy significa;\n"
            "  - o impacto real daquele resultado nos seus arquivos;\n"
            "  - o que fazer para resolver cada pendência;\n"
            "  - o resultado de cada etapa, quando a operação tem mais de uma."
        )

        window = ctk.CTkToplevel(self)
        window.title("Entenda o resultado da operação")
        window.geometry("640x460")
        window.transient(self)

        ctk.CTkLabel(
            window,
            text="Explicação do resultado do RoboCopy",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        ).pack(anchor="w", padx=16, pady=(16, 4))

        textbox = ctk.CTkTextbox(
            window,
            wrap="word",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=("#f8fafc", "#0b0f19"),
            text_color=("#0f172a", "#cbd5e1")
        )
        textbox.pack(fill="both", expand=True, padx=16, pady=6)
        textbox.insert("1.0", explanation)
        textbox.configure(state="disabled")

        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.pack(fill="x", padx=16, pady=(4, 16))

        ctk.CTkButton(
            buttons, text="Fechar", width=100, command=window.destroy
        ).pack(side="right")

        ctk.CTkButton(
            buttons, text="Copiar Explicação", width=150,
            fg_color=("#e2e8f0", "#2b2b2b"), hover_color=("#cbd5e1", "#3d3d3d"),
            text_color=("#0f172a", "#ffffff"),
            command=lambda: (self.clipboard_clear(), self.clipboard_append(explanation))
        ).pack(side="right", padx=8)

        try:
            window.after(150, window.grab_set)
        except Exception:
            pass

    def _open_sync_center_for_resolution(self):
        """Abre a aba de divergências já analisando o que ficou diferente."""
        self._show_tab(TAB_DIFFERENCES)
        self._analyze_differences()

    def _cancel_robocopy(self):
        confirm = messagebox.askyesno("Interromper", "Deseja realmente cancelar a operação em andamento?")
        if confirm:
            self.lbl_status.configure(text="Status: Cancelando processo...", text_color=("#dc2626", "#f87171"))
            stopped = self.engine.stop() or self.analyzer.stop() or self.plan_executor.stop()
            if stopped:
                self._append_log_line("\n[OPERAÇÃO CANCELADA PELO USUÁRIO]\n")

    # -------------------------------------------------------------
    # LOG
    # -------------------------------------------------------------
    def _clear_log(self):
        self.log_textbox.delete("1.0", "end")
        self._clear_occurrences()

    def _copy_log_to_clipboard(self):
        content = self.log_textbox.get("1.0", "end")
        if content.strip():
            self.clipboard_clear()
            self.clipboard_append(content)
            messagebox.showinfo("Copiado", "Log copiado para a área de transferência.")

    def _save_log_as(self):
        filepath = filedialog.asksaveasfilename(
            title="Exportar Registro de Execução",
            defaultextension=".txt",
            filetypes=[("Arquivos de Texto", "*.txt"), ("Arquivos de Log", "*.log")]
        )
        if filepath:
            content = self.log_textbox.get("1.0", "end")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Exportado", f"Arquivo salvo com sucesso em:\n{filepath}")


if __name__ == "__main__":
    app = RobocopyApp()
    app.mainloop()
