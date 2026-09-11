"""
RoboCopy Manager - Interface de Terminal (CLI / TUI)
Permite executar todas as funções de cópia e sincronização diretamente no CMD ou PowerShell,
com interface de texto interativa, cores ANSI, suporte a elevação de Administrador e modo script.
"""

import os
import sys
import ctypes
import argparse
from typing import Optional

from robocopy_engine import (
    RobocopyConfig,
    RobocopyEngine,
    interpret_exit_code,
)
from presets import (
    PRESETS,
    apply_preset_to_config,
)


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Cores de primeiro plano
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Cores brilhantes
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Fundos
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


def init_terminal():
    """Habilita suporte a sequências de escape ANSI (VT100) no console Windows."""
    if os.name == "nt":
        try:
            kernel32 = ctypes.windll.kernel32
            h_stdout = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(h_stdout, ctypes.byref(mode)):
                mode.value |= 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
                kernel32.SetConsoleMode(h_stdout, mode)
        except Exception:
            pass


def is_admin() -> bool:
    """Verifica se o processo atual está executando como Administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def restart_as_admin():
    """Reinicia a aplicação em uma nova janela de terminal com privilégios de Administrador."""
    if is_admin():
        return

    script = os.path.abspath(sys.argv[0])
    params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
    if getattr(sys, "frozen", False):
        target = sys.executable
        args = params
    else:
        target = sys.executable
        args = f'"{script}" {params}'

    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", target, args, None, 1)
    if ret > 32:
        sys.exit(0)
    else:
        print(f"\n{Colors.BRIGHT_RED}[AVISO] Permissão de administrador negada ou cancelada pelo usuário.{Colors.RESET}\n")


def clean_path(path_str: str) -> str:
    """Remove aspas iniciais/finais e normaliza o caminho informado pelo usuário."""
    if not path_str:
        return ""
    p = path_str.strip()
    if (p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")):
        p = p[1:-1].strip()
    return os.path.normpath(p)


def print_banner():
    """Exibe o cabeçalho oficial do RoboCopy Terminal."""
    admin_str = (
        f"{Colors.BRIGHT_GREEN}[ADMINISTRADOR ATIVO]{Colors.RESET}"
        if is_admin()
        else f"{Colors.BRIGHT_YELLOW}[USUÁRIO PADRÃO - Algumas pastas protegidas podem requerer Admin]{Colors.RESET}"
    )

    print(f"{Colors.BRIGHT_CYAN}=" * 72)
    print(f"{Colors.BOLD}   ROBOCOPY MANAGER - INTERFACE DE TERMINAL (CLI / TUI){Colors.RESET}")
    print(f"   Transferência rápida, backup e sincronização GoodSync no Windows")
    print(f"   Status: {admin_str}")
    print(f"{Colors.BRIGHT_CYAN}=" * 72 + f"{Colors.RESET}\n")


def prompt_path(prompt_text: str, check_exists: bool = False) -> str:
    """Solicita e valida um caminho de diretório."""
    while True:
        try:
            val = input(f"{Colors.BOLD}{prompt_text}:{Colors.RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.YELLOW}Operação cancelada pelo usuário.{Colors.RESET}")
            sys.exit(0)

        cleaned = clean_path(val)
        if not cleaned:
            print(f"{Colors.BRIGHT_RED}O caminho não pode ficar vazio. Tente novamente.{Colors.RESET}")
            continue

        if check_exists and not os.path.exists(cleaned):
            print(f"{Colors.BRIGHT_RED}A pasta de origem informada não existe: '{cleaned}'{Colors.RESET}")
            continue

        return cleaned


def interactive_main():
    """Interface interativa completa de terminal (TUI)."""
    init_terminal()
    print_banner()

    # 1. Obtenção de Origem e Destino
    print(f"{Colors.BOLD}--- 1. Definição de Pastas ---{Colors.RESET}")
    source = prompt_path("Digite ou arraste a pasta de Origem (De onde copiar)", check_exists=True)
    destination = prompt_path("Digite ou arraste a pasta de Destino (Para onde enviar)", check_exists=False)

    cfg = RobocopyConfig(source=source, destination=destination)

    # 2. Menu de Seleção de Modo
    while True:
        print(f"\n{Colors.BOLD}--- 2. Escolha o Modo de Operação ---{Colors.RESET}")
        print(f"  {Colors.BRIGHT_CYAN}[1]{Colors.RESET} Backup Seguro (Recomendado)     - Copia novos/modificados sem apagar destino")
        print(f"  {Colors.BRIGHT_CYAN}[2]{Colors.RESET} Cópia Rápida                   - Velocidade máxima (/MT:16), ignora subpastas vazias")
        print(f"  {Colors.BRIGHT_CYAN}[3]{Colors.RESET} Espelhamento Idêntico          - Destino 100% igual à origem (apaga órfãos /MIR)")
        print(f"  {Colors.BRIGHT_CYAN}[4]{Colors.RESET} Mover Arquivos (Recortar)      - Apaga da pasta de origem após copiar (/MOVE)")
        print(f"  {Colors.BRIGHT_CYAN}[5]{Colors.RESET} Central GoodSync               - Espelhamento, Atualização, 2-Way Sync (Fusão) e Filtros")
        print(f"  {Colors.BRIGHT_CYAN}[6]{Colors.RESET} Opções Avançadas Customizadas  - Definir threads, tentativas e exclusões manuais")
        if not is_admin():
            print(f"  {Colors.BRIGHT_YELLOW}[7]{Colors.RESET} Reiniciar como Administrador   - Eleva o terminal para permissões totais")
        print(f"  {Colors.WHITE}[0]{Colors.RESET} Sair")

        try:
            choice = input(f"\n{Colors.BOLD}Opção desejada [1-7]:{Colors.RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.YELLOW}Operação cancelada.{Colors.RESET}")
            sys.exit(0)

        if choice == "1":
            cfg = apply_preset_to_config(cfg, "backup_incremental")
            break
        elif choice == "2":
            cfg = apply_preset_to_config(cfg, "copia_rapida")
            break
        elif choice == "3":
            cfg = apply_preset_to_config(cfg, "espelhamento")
            break
        elif choice == "4":
            cfg = apply_preset_to_config(cfg, "mover")
            break
        elif choice == "5":
            cfg = goodsync_submenu(cfg)
            if cfg:
                break
        elif choice == "6":
            cfg = advanced_submenu(cfg)
            if cfg:
                break
        elif choice == "7" and not is_admin():
            restart_as_admin()
        elif choice == "0":
            print(f"\n{Colors.CYAN}Encerrando RoboCopy Terminal. Até logo!{Colors.RESET}")
            sys.exit(0)
        else:
            print(f"{Colors.BRIGHT_RED}Opção inválida. Digite um número correspondente.{Colors.RESET}")

    # 3. Confirmação e Execução
    engine = RobocopyEngine()
    cmd_preview = engine.build_command_string(cfg)

    print(f"\n{Colors.BRIGHT_CYAN}=" * 72)
    print(f"{Colors.BOLD}Comando RoboCopy preparado:{Colors.RESET}")
    print(f"  {Colors.BRIGHT_WHITE}{cmd_preview}{Colors.RESET}")
    print(f"{Colors.BRIGHT_CYAN}=" * 72)

    while True:
        print(f"\n{Colors.BOLD}Como deseja prosseguir?{Colors.RESET}")
        print(f"  {Colors.BRIGHT_GREEN}[1] Iniciar Execução Imediata{Colors.RESET}")
        print(f"  {Colors.BRIGHT_YELLOW}[2] Simular Primeiro (Dry-Run /L - Sem alterar arquivos){Colors.RESET}")
        print(f"  {Colors.WHITE}[0] Cancelar{Colors.RESET}")

        try:
            exec_choice = input(f"\n{Colors.BOLD}Escolha [1-2, 0]:{Colors.RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.YELLOW}Operação cancelada.{Colors.RESET}")
            sys.exit(0)

        if exec_choice == "1":
            cfg.dry_run = False
            break
        elif exec_choice == "2":
            cfg.dry_run = True
            break
        elif exec_choice == "0":
            print(f"\n{Colors.YELLOW}Operação cancelada pelo usuário.{Colors.RESET}")
            sys.exit(0)

    # 4. Execução com Saída ao Vivo
    run_with_live_terminal(cfg, engine)


def goodsync_submenu(cfg: RobocopyConfig) -> Optional[RobocopyConfig]:
    """Submenu dedicado para os modos da Central GoodSync."""
    while True:
        print(f"\n{Colors.BOLD}--- Central de Sincronização GoodSync ---{Colors.RESET}")
        print(f"  {Colors.BRIGHT_CYAN}[1]{Colors.RESET} 1. Espelhamento Rígido (Mirror / 1-Way Sync)     - /MIR /R:3 /W:5 /V /TS /FP")
        print(f"  {Colors.BRIGHT_CYAN}[2]{Colors.RESET} 2. Atualização Sem Exclusão (Contribute / Update) - /E /XO /R:3 /W:5")
        print(f"  {Colors.BRIGHT_CYAN}[3]{Colors.RESET} 3. Sincronização Bidirecional (2-Way Sync / Fusão) - Executa em 2 etapas A->B e B->A")
        print(f"  {Colors.BRIGHT_CYAN}[4]{Colors.RESET} 4. Mover Arquivos (Move / Cut & Paste)           - /E /MOVE /R:3 /W:5")
        print(f"  {Colors.BRIGHT_CYAN}[5]{Colors.RESET} 5. Sincronização com Filtro de Extensão/Tamanho    - /E /MAX:n /XF ...")
        print(f"  {Colors.WHITE}[0]{Colors.RESET} Voltar ao Menu Principal")

        try:
            g_choice = input(f"\n{Colors.BOLD}Selecione o modo GoodSync [1-5, 0]:{Colors.RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            return None

        if g_choice == "1":
            return apply_preset_to_config(cfg, "goodsync_mirror")
        elif g_choice == "2":
            return apply_preset_to_config(cfg, "goodsync_update")
        elif g_choice == "3":
            return apply_preset_to_config(cfg, "goodsync_two_way")
        elif g_choice == "4":
            return apply_preset_to_config(cfg, "goodsync_move")
        elif g_choice == "5":
            c = apply_preset_to_config(cfg, "goodsync_filter")
            xf = input(f"{Colors.BOLD}Extensões para excluir (Enter para padrão '*.tmp *.bak'):{Colors.RESET} ").strip()
            if xf:
                c.exclude_files = xf
            max_b = input(f"{Colors.BOLD}Tamanho máximo em bytes (Enter para padrão '52428800' = 50MB):{Colors.RESET} ").strip()
            if max_b:
                c.max_size = max_b
            return c
        elif g_choice == "0":
            return None


def advanced_submenu(cfg: RobocopyConfig) -> Optional[RobocopyConfig]:
    """Submenu para ajuste manual de opções avançadas."""
    print(f"\n{Colors.BOLD}--- Opções Avançadas Customizadas ---{Colors.RESET}")
    threads_in = input(f"{Colors.BOLD}Número de Threads paralelas (/MT: 1 a 64, padrão 8):{Colors.RESET} ").strip()
    if threads_in.isdigit() and 1 <= int(threads_in) <= 64:
        cfg.multi_threaded = int(threads_in)

    retries_in = input(f"{Colors.BOLD}Tentativas para arquivos bloqueados (/R: 0 a 10, padrão 1):{Colors.RESET} ").strip()
    if retries_in.isdigit() and 0 <= int(retries_in) <= 10:
        cfg.retries = int(retries_in)

    xf_in = input(f"{Colors.BOLD}Arquivos para excluir (/XF ex: *.log *.tmp, Enter para nenhum):{Colors.RESET} ").strip()
    if xf_in:
        cfg.exclude_files = xf_in

    xd_in = input(f"{Colors.BOLD}Pastas para excluir (/XD ex: node_modules .git, Enter para nenhuma):{Colors.RESET} ").strip()
    if xd_in:
        cfg.exclude_dirs = xd_in

    return cfg


def run_with_live_terminal(cfg: RobocopyConfig, engine: RobocopyEngine):
    """Executa o RoboCopy transmitindo a saída em tempo real no terminal com estatísticas."""
    is_sim = cfg.dry_run
    mode_text = "SIMULAÇÃO (DRY-RUN /L)" if is_sim else "CÓPIA REAL EM ANDAMENTO"
    color_hdr = Colors.BRIGHT_YELLOW if is_sim else Colors.BRIGHT_GREEN

    print(f"\n{color_hdr}{'=' * 72}")
    print(f"   INICIANDO: {mode_text}")
    print(f"{'=' * 72}{Colors.RESET}\n")

    def on_line(line: str):
        # Transmite cada linha recebida do processo
        print(line, end="")

    exit_code, title, desc, summary = engine.run_sync(cfg, on_line=on_line)

    # Exibição de Resumo Técnico Formatado
    print(f"\n{Colors.BRIGHT_CYAN}{'=' * 72}")
    if exit_code < 8:
        status_color = Colors.BRIGHT_GREEN
    else:
        status_color = Colors.BRIGHT_RED

    print(f"{status_color}{Colors.BOLD}   STATUS FINAL: [{exit_code}] {title}{Colors.RESET}")
    print(f"   {desc}")
    print(f"{Colors.BRIGHT_CYAN}{'-' * 72}{Colors.RESET}")
    print(f"   Diretórios: Total: {summary.get('dirs_total', '-')} | Copiados: {summary.get('dirs_copied', '-')} | Falhas: {summary.get('dirs_failed', '0')}")
    print(f"   Arquivos:   Total: {summary.get('files_total', '-')} | Copiados: {summary.get('files_copied', '-')} | Falhas: {summary.get('files_failed', '0')}")
    print(f"   Volume:     Total: {summary.get('bytes_total', '-')} | Copiado: {summary.get('bytes_copied', '-')}")
    print(f"   Velocidade: {summary.get('speed', '-')}")
    print(f"{Colors.BRIGHT_CYAN}{'=' * 72}{Colors.RESET}\n")

    return exit_code


def cli_main():
    """Ponto de entrada CLI: suporta argumentos diretos ou modo interativo TUI."""
    parser = argparse.ArgumentParser(
        description="RoboCopy Manager CLI - Gerenciador e Sincronizador de Pastas no Terminal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exemplos:\n"
               "  Modo Interativo (TUI):      python robocopy_cli.py\n"
               "  Backup Seguro:              python robocopy_cli.py C:\\Origem D:\\Destino --mode backup\n"
               "  GoodSync Espelhamento:      python robocopy_cli.py C:\\Origem D:\\Destino --mode goodsync_mirror\n"
               "  Simulação Rápida:           python robocopy_cli.py C:\\Origem D:\\Destino --dry-run\n"
    )

    parser.add_argument("source", nargs="?", help="Pasta de Origem")
    parser.add_argument("destination", nargs="?", help="Pasta de Destino")
    parser.add_argument("--mode", choices=["backup", "fast", "mirror", "move", "goodsync_mirror", "goodsync_update", "goodsync_two_way", "goodsync_move", "goodsync_filter"],
                        help="Modo de operação predefinido")
    parser.add_argument("--threads", type=int, default=None, help="Número de threads simultâneas (/MT)")
    parser.add_argument("--dry-run", "-L", action="store_true", help="Apenas simular sem modificar arquivos")
    parser.add_argument("--exclude-files", "-xf", help="Arquivos/extensões para excluir (/XF)")
    parser.add_argument("--exclude-dirs", "-xd", help="Diretórios para excluir (/XD)")
    parser.add_argument("--admin", action="store_true", help="Solicita elevação de Administrador imediatamente")

    args = parser.parse_args()

    init_terminal()

    if args.admin and not is_admin():
        restart_as_admin()

    # Se origem ou destino não foram fornecidos via parâmetros de linha de comando, entra no modo interativo TUI
    if not args.source or not args.destination:
        interactive_main()
        return

    # Modo de Linha de Comando Direta (Headless / Scripting)
    src = clean_path(args.source)
    dst = clean_path(args.destination)

    if not os.path.exists(src):
        print(f"{Colors.BRIGHT_RED}Erro: A pasta de origem informada não existe: '{src}'{Colors.RESET}", file=sys.stderr)
        sys.exit(1)

    cfg = RobocopyConfig(source=src, destination=dst)

    mode_map = {
        "backup": "backup_incremental",
        "fast": "copia_rapida",
        "mirror": "espelhamento",
        "move": "mover",
        "goodsync_mirror": "goodsync_mirror",
        "goodsync_update": "goodsync_update",
        "goodsync_two_way": "goodsync_two_way",
        "goodsync_move": "goodsync_move",
        "goodsync_filter": "goodsync_filter",
    }

    if args.mode:
        key = mode_map.get(args.mode, "backup_incremental")
        cfg = apply_preset_to_config(cfg, key)

    if args.threads:
        cfg.multi_threaded = max(1, min(64, args.threads))

    if args.dry_run:
        cfg.dry_run = True

    if args.exclude_files:
        cfg.exclude_files = args.exclude_files

    if args.exclude_dirs:
        cfg.exclude_dirs = args.exclude_dirs

    engine = RobocopyEngine()
    exit_code = run_with_live_terminal(cfg, engine)
    sys.exit(0 if exit_code < 8 else exit_code)


if __name__ == "__main__":
    cli_main()
