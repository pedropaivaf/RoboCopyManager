"""
RoboCopy Engine - Gerenciador, construtor de comandos e executor do RoboCopy para Windows.
Compatível com Windows 10 (todas as compilações) e Windows 11.
"""

import os
import subprocess
import threading
import re
import shlex
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Any

ROBOCOPY_EXIT_CODES = {
    0: ("Sucesso", "Nenhum arquivo precisou ser copiado. Origem e destino já sincronizados.", "success"),
    1: ("Sucesso", "Todos os arquivos foram copiados com sucesso.", "success"),
    2: ("Aviso", "Existem arquivos extras no destino que não existem na origem.", "warning"),
    3: ("Sucesso Parcial", "Arquivos copiados com sucesso e arquivos extras detectados.", "success"),
    4: ("Aviso", "Arquivos incompatíveis ou com discrepâncias detectados.", "warning"),
    5: ("Sucesso Parcial", "Alguns arquivos copiados e discrepâncias encontradas.", "warning"),
    6: ("Aviso", "Arquivos extras e incompatíveis presentes.", "warning"),
    7: ("Sucesso Parcial", "Arquivos copiados, arquivos extras e discrepâncias detectados.", "warning"),
    8: ("Falha de Cópia", "Alguns arquivos não puderam ser copiados (falha de leitura ou bloqueio).", "error"),
    16: ("Erro Crítico", "Acesso negado, privilégios insuficientes ou caminho inválido.", "error"),
}

def interpret_exit_code(code: int) -> tuple[str, str, str]:
    """Retorna (título, descrição, categoria) do exit code do RoboCopy."""
    if code in ROBOCOPY_EXIT_CODES:
        return ROBOCOPY_EXIT_CODES[code]
    elif code < 8:
        return ("Concluído com avisos", f"Operação concluída sem erros fatais (código {code}).", "warning")
    else:
        return ("Falha na Cópia", f"Robocopy finalizado com código de erro {code}.", "error")


@dataclass
class RobocopyConfig:
    source: str = ""
    destination: str = ""
    file_pattern: str = "*.*"

    # Modos de subpasta e espelhamento
    copy_subdirs: bool = False       # /S
    copy_subdirs_empty: bool = True   # /E
    mirror: bool = False             # /MIR
    purge: bool = False              # /PURGE
    subfolder_level: int = 0         # /LEV:n (0 = sem limite)

    # Modos especiais (/ZB e /B requerem privilégio SeBackupPrivilege / Administrador)
    restartable: bool = False        # /Z
    backup_mode: bool = False        # /B
    restartable_backup: bool = False # /ZB (desativado por padrão para compatibilidade com usuário padrão)
    unbuffered_io: bool = False      # /J (arquivos grandes)
    move_files: bool = False         # /MOV
    move_all: bool = False           # /MOVE

    # Atributos e Segurança NTFS (/COPY:flags)
    copy_data: bool = True           # D
    copy_attrs: bool = True          # A
    copy_timestamps: bool = True     # T
    copy_security: bool = False      # S (requer admin para certas ACLs)
    copy_owner: bool = False         # O
    copy_audit: bool = False         # U
    copy_dir_attrs: bool = True      # /DCOPY:DAT
    copyall: bool = False            # /COPYALL (Dados, Atributos, Timestamps, Segurança ACL, Dono, Auditoria)
    secfix: bool = False             # /SECFIX
    timfix: bool = False             # /TIMFIX

    # Exclusões e Filtros
    exclude_files: str = ""          # /XF
    exclude_dirs: str = ""           # /XD
    exclude_older: bool = False      # /XO
    exclude_newer: bool = False      # /XN
    exclude_changed: bool = False    # /XC
    exclude_junctions: bool = True   # /XJ
    max_size: str = ""               # /MAX:n
    min_size: str = ""               # /MIN:n
    max_age: str = ""                # /MAXAGE:n
    min_age: str = ""                # /MINAGE:n

    # Desempenho e Rede
    multi_threaded: int = 8          # /MT:n
    retries: int = 1                 # /R:n (1 tentativa para não congelar processo)
    wait_time: int = 3               # /W:n (segundos)
    inter_packet_gap: int = 0        # /IPG:n

    # Logs e Interface
    dry_run: bool = False            # /L
    tee: bool = True                 # /TEE
    no_progress: bool = True         # /NP
    no_file_list: bool = False       # /NFL
    no_dir_list: bool = False        # /NDL
    show_bytes: bool = False         # /BYTES
    show_eta: bool = False           # /ETA
    verbose_timestamps: bool = False # /V /TS /FP (Modo detalhado com timestamps e caminhos completos)
    log_file: str = ""               # /LOG:
    log_append: bool = False         # /LOG+:

    # Modo GoodSync Especial
    is_two_way_sync: bool = False    # Sincronização Bidirecional (Passo 1: A->B + Passo 2: B->A)

    # Argumentos adicionais livres
    extra_args: str = ""


def split_windows_args(s: str) -> List[str]:
    r"""Divide argumentos no padrao Windows preservando barras invertidas (\) e respeitando aspas."""
    if not s or not s.strip():
        return []
    try:
        raw_tokens = shlex.split(s.strip(), posix=False)
        tokens = []
        for t in raw_tokens:
            cleaned = t.strip()
            if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
                cleaned = cleaned[1:-1]
            if cleaned:
                tokens.append(cleaned)
        return tokens
    except Exception:
        return s.strip().split()


class RobocopyEngine:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self._cancel_requested = False
        self._lock = threading.Lock()

    def build_command_args(self, config: RobocopyConfig) -> List[str]:
        """Gera a lista de argumentos para o processo robocopy."""
        src = config.source.strip()
        dst = config.destination.strip()

        if (src.startswith('"') and src.endswith('"')) or (src.startswith("'") and src.endswith("'")):
            src = src[1:-1]
        if (dst.startswith('"') and dst.endswith('"')) or (dst.startswith("'") and dst.endswith("'")):
            dst = dst[1:-1]

        if len(src) > 3 and src.endswith(("\\", "/")):
            src = src.rstrip("\\/")
        if len(dst) > 3 and dst.endswith(("\\", "/")):
            dst = dst.rstrip("\\/")

        args = ["robocopy", src, dst]

        pattern = config.file_pattern.strip()
        if pattern and pattern != "*.*":
            args.extend(split_windows_args(pattern))

        if config.mirror:
            args.append("/MIR")
        else:
            if config.copy_subdirs_empty:
                args.append("/E")
            elif config.copy_subdirs:
                args.append("/S")
            if config.purge:
                args.append("/PURGE")

        if config.subfolder_level > 0:
            args.append(f"/LEV:{config.subfolder_level}")

        if config.restartable_backup:
            args.append("/ZB")
        elif config.backup_mode:
            args.append("/B")
        elif config.restartable:
            args.append("/Z")

        if config.unbuffered_io:
            args.append("/J")

        if config.move_all:
            args.append("/MOVE")
        elif config.move_files:
            args.append("/MOV")

        if config.copyall:
            args.append("/COPYALL")
        else:
            copy_flags = ""
            if config.copy_data: copy_flags += "D"
            if config.copy_attrs: copy_flags += "A"
            if config.copy_timestamps: copy_flags += "T"
            if config.copy_security: copy_flags += "S"
            if config.copy_owner: copy_flags += "O"
            if config.copy_audit: copy_flags += "U"
            
            if not copy_flags:
                # Robocopy não aceita /COPY: vazio; o padrão de dados é preservado
                copy_flags = "D"

            args.append(f"/COPY:{copy_flags}")

            if config.copy_dir_attrs:
                args.append("/DCOPY:DAT")

        if config.secfix:
            args.append("/SECFIX")
        if config.timfix:
            args.append("/TIMFIX")

        if config.exclude_junctions:
            args.append("/XJ")
        if config.exclude_older:
            args.append("/XO")
        if config.exclude_newer:
            args.append("/XN")
        if config.exclude_changed:
            args.append("/XC")

        if config.exclude_files.strip():
            xf_list = split_windows_args(config.exclude_files.strip())
            if xf_list:
                args.append("/XF")
                args.extend(xf_list)

        if config.exclude_dirs.strip():
            xd_list = split_windows_args(config.exclude_dirs.strip())
            if xd_list:
                args.append("/XD")
                args.extend(xd_list)

        if config.max_size.strip():
            args.append(f"/MAX:{config.max_size.strip()}")
        if config.min_size.strip():
            args.append(f"/MIN:{config.min_size.strip()}")
        if config.max_age.strip():
            args.append(f"/MAXAGE:{config.max_age.strip()}")
        if config.min_age.strip():
            args.append(f"/MINAGE:{config.min_age.strip()}")

        if config.multi_threaded > 1:
            args.append(f"/MT:{min(max(config.multi_threaded, 1), 128)}")
        args.append(f"/R:{config.retries}")
        args.append(f"/W:{config.wait_time}")
        if config.inter_packet_gap > 0:
            args.append(f"/IPG:{config.inter_packet_gap}")

        if config.dry_run:
            args.append("/L")
        if config.tee:
            args.append("/TEE")
        if config.no_progress:
            args.append("/NP")
        if config.no_file_list:
            args.append("/NFL")
        if config.no_dir_list:
            args.append("/NDL")
        if config.show_bytes:
            args.append("/BYTES")
        if config.show_eta:
            args.append("/ETA")
        if config.verbose_timestamps:
            args.extend(["/V", "/TS", "/FP"])

        if config.log_file.strip():
            flag = "/LOG+:" if config.log_append else "/LOG:"
            args.append(f"{flag}{config.log_file.strip()}")

        if config.extra_args.strip():
            args.extend(split_windows_args(config.extra_args.strip()))

        return args

    def build_command_string(self, config: RobocopyConfig) -> str:
        """Gera a representação em texto limpa do comando."""
        if config.is_two_way_sync:
            # Passo 1: A -> B
            import copy
            cfg1 = copy.copy(config)
            cfg1.is_two_way_sync = False
            cmd1 = self._format_args(self.build_command_args(cfg1))

            # Passo 2: B -> A
            cfg2 = copy.copy(config)
            cfg2.is_two_way_sync = False
            cfg2.source = config.destination
            cfg2.destination = config.source
            cmd2 = self._format_args(self.build_command_args(cfg2))

            return f"# Etapa 1: Copiar novidades da Origem para o Destino\n{cmd1}\n\n# Etapa 2: Copiar novidades do Destino para a Origem\n{cmd2}"

        raw_args = self.build_command_args(config)
        return self._format_args(raw_args)

    def _format_args(self, raw_args: List[str]) -> str:
        formatted_args = []
        for a in raw_args:
            if " " in a and not a.startswith('"'):
                formatted_args.append(f'"{a}"')
            else:
                formatted_args.append(a)
        return " ".join(formatted_args)

    def run(
        self,
        config: RobocopyConfig,
        on_line: Callable[[str], None],
        on_finish: Callable[[int, str, str, Dict[str, Any]], None],
    ):
        """Executa o RoboCopy em thread dedicada."""
        thread = threading.Thread(
            target=self._run_process,
            args=(config, on_line, on_finish),
            daemon=True,
        )
        thread.start()

    def run_sync(
        self,
        config: RobocopyConfig,
        on_line: Optional[Callable[[str], None]] = None,
    ) -> tuple[int, str, str, Dict[str, Any]]:
        """Executa o RoboCopy de forma síncrona/bloqueante e retorna (exit_code, title, desc, summary)."""
        result: Dict[str, Any] = {}
        event = threading.Event()

        def _on_finish(code: int, title: str, desc: str, summary: Dict[str, Any]):
            result["exit_code"] = code
            result["title"] = title
            result["desc"] = desc
            result["summary"] = summary
            event.set()

        self.run(config, on_line=on_line or (lambda l: None), on_finish=_on_finish)
        try:
            while not event.is_set():
                event.wait(timeout=0.1)
        except KeyboardInterrupt:
            self.stop()
            event.wait(timeout=2.0)

        return (
            result.get("exit_code", 16),
            result.get("title", "Interrompido"),
            result.get("desc", "Operação interrompida."),
            result.get("summary", {}),
        )

    def _run_process(
        self,
        config: RobocopyConfig,
        on_line: Callable[[str], None],
        on_finish: Callable[[int, str, str, Dict[str, Any]], None],
    ):
        with self._lock:
            if self.is_running:
                on_line("\n[AVISO] Uma tarefa do RoboCopy já está em execução.\n")
                return
            self.is_running = True
            self._cancel_requested = False

        on_line("=" * 60 + "\n")
        on_line(f"Início: {self._get_now_str()}\n")
        on_line(f"Comando:\n{self.build_command_string(config)}\n")
        on_line("=" * 60 + "\n\n")

        full_output_lines = []
        exit_code = 0

        try:
            if config.is_two_way_sync:
                import copy
                # ETAPA 1: Origem -> Destino
                on_line(">>> [ETAPA 1 DE 2]: Copiando novidades da Origem para o Destino...\n\n")
                cfg1 = copy.copy(config)
                cfg1.is_two_way_sync = False
                cfg1.copy_subdirs_empty = True
                cfg1.exclude_older = True
                cfg1.mirror = False
                cmd_args_1 = self.build_command_args(cfg1)
                code1 = self._execute_single_step(cmd_args_1, full_output_lines, on_line)

                if not self._cancel_requested and self.is_running and code1 < 8:
                    on_line("\n>>> [ETAPA 2 DE 2]: Copiando novidades do Destino para a Origem...\n\n")
                    cfg2 = copy.copy(config)
                    cfg2.is_two_way_sync = False
                    cfg2.source = config.destination
                    cfg2.destination = config.source
                    cfg2.copy_subdirs_empty = True
                    cfg2.exclude_older = True
                    cfg2.mirror = False
                    cmd_args_2 = self.build_command_args(cfg2)
                    code2 = self._execute_single_step(cmd_args_2, full_output_lines, on_line)
                    exit_code = max(code1, code2)
                else:
                    exit_code = code1
            else:
                cmd_args = self.build_command_args(config)
                exit_code = self._execute_single_step(cmd_args, full_output_lines, on_line)

        except Exception as ex:
            on_line(f"\n[ERRO NA EXECUÇÃO]: {str(ex)}\n")
            exit_code = 16
        finally:
            with self._lock:
                self.is_running = False
                if self.process and self.process.stdout:
                    try:
                        self.process.stdout.close()
                    except Exception:
                        pass
                self.process = None

        summary = self._parse_summary(full_output_lines)
        if self._cancel_requested:
            exit_code = 16
            title = "Interrompido"
            desc = "Operação cancelada pelo usuário."
        else:
            title, desc, status_cat = interpret_exit_code(exit_code)

        on_line("\n" + "-" * 60 + "\n")
        on_line(f"Conclusão: [{exit_code}] {title} - {desc}\n")
        on_line(f"Horário: {self._get_now_str()}\n")
        on_line("-" * 60 + "\n")

        on_finish(exit_code, title, desc, summary)

    def _execute_single_step(self, cmd_args: List[str], full_output_lines: List[str], on_line: Callable[[str], None]) -> int:
        """Executa uma chamada individual do robocopy e transmite a saída."""
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW

        self.process = subprocess.Popen(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )

        while True:
            raw_line = self.process.stdout.readline()
            if not raw_line and self.process.poll() is not None:
                break
            if raw_line:
                line = self._decode_line(raw_line)
                full_output_lines.append(line)
                on_line(line)

        code = self.process.poll()
        if self.process and self.process.stdout:
            try:
                self.process.stdout.close()
            except Exception:
                pass
        return 0 if code is None else code

    def stop(self) -> bool:
        """Interrompe a árvore de processos do RoboCopy."""
        with self._lock:
            if not self.is_running or not self.process:
                return False

            self._cancel_requested = True
            try:
                pid = self.process.pid
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                else:
                    self.process.terminate()
                return True
            except Exception:
                return False

    def _decode_line(self, raw_bytes: bytes) -> str:
        """Decodificação precisa do console Windows (CP850 / CP1252 / UTF-8)."""
        for enc in ("cp850", "cp1252", "utf-8"):
            try:
                return raw_bytes.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return raw_bytes.decode("latin-1", errors="replace")

    def _parse_summary(self, lines: List[str]) -> Dict[str, Any]:
        """Extrai as métricas de resumo da saída do RoboCopy."""
        summary = {
            "dirs_total": "-", "dirs_copied": "-", "dirs_skipped": "-", "dirs_failed": "-",
            "files_total": "-", "files_copied": "-", "files_skipped": "-", "files_failed": "-",
            "bytes_total": "-", "bytes_copied": "-", "speed": "-", "times": "-"
        }
        
        full_text = "".join(lines)
        
        dir_matches = re.findall(r'(?:Diret[oó\xa2]rios|Dirs)\s*:\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', full_text, re.IGNORECASE)
        if dir_matches:
            last = dir_matches[-1]
            summary["dirs_total"] = last[0]
            summary["dirs_copied"] = last[1]
            summary["dirs_skipped"] = last[2]
            summary["dirs_failed"] = last[3]

        file_matches = re.findall(r'(?:Arquivos|Files)\s*:\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', full_text, re.IGNORECASE)
        if file_matches:
            last = file_matches[-1]
            summary["files_total"] = last[0]
            summary["files_copied"] = last[1]
            summary["files_skipped"] = last[2]
            summary["files_failed"] = last[3]

        bytes_matches = re.findall(r'Bytes\s*:\s*([0-9\.]+\s*[kmgtb]?)\s+([0-9\.]+\s*[kmgtb]?)', full_text, re.IGNORECASE)
        if bytes_matches:
            last = bytes_matches[-1]
            summary["bytes_total"] = last[0].strip()
            summary["bytes_copied"] = last[1].strip()

        speed_match = re.search(r'(?:Velocidade|Speed)\s*:\s*([^\r\n]+)', full_text, re.IGNORECASE)
        if speed_match:
            summary["speed"] = speed_match.group(1).strip()

        return summary

    def _get_now_str(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%d/%m/%Y %H:%M:%S")
