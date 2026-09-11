"""
RoboCopy Manager - Utilitário Profissional de Cópia, Backup e Sincronização.
Compatível com Windows 10 e Windows 11.
Interface minimalista, tela cheia nativa, modo simplificado por padrão e opções avançadas sob demanda.
"""

import os
import sys
import ctypes
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from robocopy_engine import RobocopyEngine, RobocopyConfig, interpret_exit_code
from presets import PRESETS, apply_preset_to_config, export_profile_to_json, import_profile_from_json

# Suporte opcional a Drag & Drop
try:
    import windnd
    HAS_WINDND = True
except ImportError:
    HAS_WINDND = False


class ToolTip:
    """Tooltip minimalista e leve para exibir dicas rápidas ao passar o mouse."""
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
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
            pady=6
        )
        label.pack()

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
        self.config = RobocopyConfig()
        self.advanced_visible = False
        self.sync_visible = False

        # Configuração da Janela
        self.title("RoboCopy Manager - Transferência e Backup de Arquivos")
        self.minsize(1020, 720)

        # Inicia automaticamente em tela cheia (maximizado no Windows)
        self.state("zoomed")

        # Configuração de Tema Profissional
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Ícone da Janela
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, "assets", "desktop_icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(base_dir, "assets", "app_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # Criação da Interface
        self._build_header()
        self._build_main_container()
        self._build_footer()

        # Inicializa valores e modo simplificado padrão
        self._sync_ui_from_config(self.config)
        self.update_command_preview()

        if HAS_WINDND:
            self._setup_drag_and_drop()

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

    def _build_main_container(self):
        """Estrutura principal: Seção Básica, Alternador de Avançado, GoodSync e Console ao vivo."""
        self.main_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_scroll.pack(fill="both", expand=True, padx=24, pady=4)

        # 1. Painel de Pastas (Origem / Destino)
        self._build_paths_card()

        # 2. Painel de Modo de Operação (Básico e intuitivo)
        self._build_modes_card()

        # 3. Barra de Botões Alternadores (Avançado e Sincronizar Pastas)
        self._build_toggle_bar()

        # 4. Painel de Sincronização GoodSync (Inicialmente oculto)
        self.sync_container = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        self._build_sync_panel()

        # 5. Painel Avançado (Inicialmente oculto)
        self.advanced_container = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        self._build_advanced_tabs()

        # 6. Painel de Monitoramento e Console ao Vivo
        self._build_live_monitor_card()

    def _build_paths_card(self):
        """Card para definir pasta de Origem e Destino com botões diretos."""
        card = ctk.CTkFrame(self.main_scroll, corner_radius=6, border_width=1, border_color=("#e2e8f0", "#333333"), fg_color=("#ffffff", "#181818"))
        card.pack(fill="x", pady=(0, 8))
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
        self._create_info_badge(mid_box, "Troca a pasta de origem pela de destino instantaneamente.").pack(side="left", padx=6)

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
        """Card para seleção do modo de transferência com títulos autoexplicativos e botões (i)."""
        card = ctk.CTkFrame(self.main_scroll, corner_radius=6, border_width=1, border_color=("#e2e8f0", "#333333"), fg_color=("#ffffff", "#181818"))
        card.pack(fill="x", pady=(0, 8))

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=16, pady=(10, 4))

        ctk.CTkLabel(
            top_row,
            text="Qual operação você deseja realizar?",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        ).pack(side="left")

        self._create_info_badge(
            top_row,
            "Escolha como o RoboCopy deve agir. Para uso diário, o 'Backup Seguro' é a opção recomendada."
        ).pack(side="left", padx=8)

        # Modos principais
        modes_frame = ctk.CTkFrame(card, fg_color="transparent")
        modes_frame.pack(fill="x", padx=16, pady=(4, 12))

        self.selected_preset_key = tk.StringVar(value="backup_incremental")

        presets_list = [
            (
                "backup_incremental",
                "Backup Seguro (Recomendado)",
                "Copia arquivos novos ou que sofreram alterações. NUNCA apaga nada que já exista na pasta de destino."
            ),
            (
                "copia_rapida",
                "Cópia Rápida de Pastas e Arquivos",
                "Copia tudo com velocidade máxima multithread, ignorando subpastas que estejam vazias."
            ),
            (
                "espelhamento",
                "Espelhamento Idêntico de Pasta",
                "Faz o destino ficar 100% igual à origem. ATENÇÃO: se você apagou um arquivo na origem, ele será apagado no destino também."
            ),
            (
                "mover",
                "Mover Arquivos (Recortar)",
                "Transfere tudo para o destino e apaga os arquivos da pasta de origem após a cópia com êxito."
            ),
        ]

        for p_key, p_title, p_desc in presets_list:
            row = ctk.CTkFrame(modes_frame, fg_color="transparent")
            row.pack(anchor="w", pady=3)

            rbtn = ctk.CTkRadioButton(
                row,
                text=p_title,
                value=p_key,
                variable=self.selected_preset_key,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                command=self._on_preset_selected
            )
            rbtn.pack(side="left")

            self._create_info_badge(row, p_desc).pack(side="left", padx=8)

    def _build_toggle_bar(self):
        """Barra de alternância com botões para Opções Avançadas e Central GoodSync."""
        toggle_bar = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
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

            self.advanced_container.pack(fill="x", pady=(4, 8), before=self.monitor_card)
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

            self.sync_container.pack(fill="x", pady=(4, 8), before=self.monitor_card)
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

        for m_key, m_title, m_desc in goodsync_modes:
            m_row = ctk.CTkFrame(modes_box, fg_color="transparent")
            m_row.pack(anchor="w", pady=3)

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
        self.sync_filter_box.pack(fill="x", padx=16, pady=4)

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
        corp_box.pack(fill="x", padx=16, pady=(6, 12))

        ctk.CTkLabel(corp_box, text="Parâmetros Avançados Essenciais (Equivalentes ao Modo Avançado GoodSync):", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=("#475569", "#94a3b8")).pack(anchor="w", pady=(0, 4))

        corp_checks = ctk.CTkFrame(corp_box, fg_color="transparent")
        corp_checks.pack(fill="x")

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

    def _build_live_monitor_card(self):
        """Card do Console de Saída ao Vivo e Resultados Técnicos."""
        self.monitor_card = ctk.CTkFrame(self.main_scroll, corner_radius=6, border_width=1, border_color=("#e2e8f0", "#333333"), fg_color=("#ffffff", "#181818"))
        self.monitor_card.pack(fill="both", expand=True, pady=(4, 0))

        # Barra de métricas
        stats_bar = ctk.CTkFrame(self.monitor_card, fg_color=("#f1f5f9", "#181818"), corner_radius=4)
        stats_bar.pack(fill="x", padx=10, pady=(10, 6))
        stats_bar.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.card_dirs = self._create_stat_card(stats_bar, 0, "Diretórios", "Total: -\nCopiados: -")
        self.card_files = self._create_stat_card(stats_bar, 1, "Arquivos", "Total: -\nCopiados: -")
        self.card_bytes = self._create_stat_card(stats_bar, 2, "Volume de Dados", "Total: -\nCopiado: -")
        self.card_speed = self._create_stat_card(stats_bar, 3, "Velocidade", "Média: -\nFalhas: 0")

        # Barra de controle do console
        console_tools = ctk.CTkFrame(self.monitor_card, fg_color="transparent")
        console_tools.pack(fill="x", padx=10, pady=2)

        ctk.CTkLabel(
            console_tools,
            text="Registro de Execução ao Vivo (Console):",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#334155", "#94a3b8")
        ).pack(side="left")

        self._create_info_badge(
            console_tools,
            "Exibe os arquivos sendo copiados em tempo real diretamente do motor RoboCopy."
        ).pack(side="left", padx=6)

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

        # Terminal
        self.log_textbox = ctk.CTkTextbox(
            self.monitor_card,
            wrap="none",
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=("#f8fafc", "#0b0f19"),
            text_color=("#0f172a", "#cbd5e1"),
            corner_radius=4,
            border_width=1,
            border_color=("#e2e8f0", "#1e293b"),
            height=260
        )
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(2, 10))

    def _create_stat_card(self, parent, col: int, title: str, initial_text: str):
        card = ctk.CTkFrame(parent, fg_color=("#ffffff", "#202020"), corner_radius=4, border_width=1, border_color=("#e2e8f0", "#2a2a2a"))
        card.grid(row=0, column=col, padx=4, pady=4, sticky="ew")
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=("#334155", "#cbd5e1")).pack(anchor="w", padx=8, pady=(4, 1))
        lbl_val = ctk.CTkLabel(card, text=initial_text, font=ctk.CTkFont(family="Segoe UI", size=11), text_color=("#0f172a", "#94a3b8"), justify="left")
        lbl_val.pack(anchor="w", padx=8, pady=(1, 4))
        return lbl_val

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
        ToolTip(self.btn_simulate, "Executa uma simulação no console. Mostra exatamente o que seria copiado sem alterar nada.")

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
        ToolTip(self.btn_run, "Inicia o RoboCopy diretamente pelo próprio sistema em segundo plano com log ao vivo.")

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
        self.update_command_preview()

    def _on_mode_change(self):
        self.update_command_preview()

    def _on_chk_mov_change(self):
        if self.var_move_files.get():
            self.var_move_all.set(False)
        self.update_command_preview()

    def _on_chk_move_change(self):
        if self.var_move_all.get():
            self.var_move_files.set(False)
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
        if cfg.mirror:
            confirm = messagebox.askyesno(
                "Atenção - Modo Espelhamento",
                "O modo de espelhamento excluirá do destino arquivos que não estejam na origem.\n\n"
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
        self.btn_run.configure(state="disabled")
        self.btn_simulate.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        
        mode_label = "Simulação (Testando sem risco)" if is_dry_run else "Copiando arquivos"
        self.lbl_status.configure(text=f"Status: {mode_label}...", text_color=("#d97706", "#facc15"))

        self.engine.run(
            config=cfg,
            on_line=self._handle_output_line,
            on_finish=self._handle_finish
        )

    def _handle_output_line(self, line: str):
        self.after(0, self._append_log_line, line)

    def _append_log_line(self, line: str):
        self.log_textbox.insert("end", line)
        self.log_textbox.see("end")

    def _handle_finish(self, exit_code: int, title: str, desc: str, summary: dict):
        self.after(0, self._on_process_completed, exit_code, title, desc, summary)

    def _on_process_completed(self, exit_code: int, title: str, desc: str, summary: dict):
        self.btn_run.configure(state="normal")
        self.btn_simulate.configure(state="normal")
        self.btn_cancel.configure(state="disabled")

        self.card_dirs.configure(
            text=f"Total: {summary.get('dirs_total', '-')}\nCopiados: {summary.get('dirs_copied', '-')}"
        )
        self.card_files.configure(
            text=f"Total: {summary.get('files_total', '-')}\nCopiados: {summary.get('files_copied', '-')}"
        )
        self.card_bytes.configure(
            text=f"Total: {summary.get('bytes_total', '-')}\nCopiado: {summary.get('bytes_copied', '-')}"
        )
        self.card_speed.configure(
            text=f"Média: {summary.get('speed', '-')}\nFalhas: {summary.get('files_failed', '0')}"
        )

        if exit_code < 8:
            status_color = ("#16a34a", "#4ade80")
        else:
            status_color = ("#dc2626", "#f87171")

        self.lbl_status.configure(
            text=f"Status: [{exit_code}] {title} - {desc}",
            text_color=status_color
        )

    def _cancel_robocopy(self):
        confirm = messagebox.askyesno("Interromper", "Deseja realmente cancelar a cópia em andamento?")
        if confirm:
            self.lbl_status.configure(text="Status: Cancelando processo...", text_color=("#dc2626", "#f87171"))
            stopped = self.engine.stop()
            if stopped:
                self._append_log_line("\n[OPERAÇÃO CANCELADA PELO USUÁRIO]\n")

    # -------------------------------------------------------------
    # LOG
    # -------------------------------------------------------------
    def _clear_log(self):
        self.log_textbox.delete("1.0", "end")

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
