"""
RoboCopy Engine - Gerenciador, construtor de comandos e executor do RoboCopy para Windows.
Compatível com Windows 10 (todas as compilações) e Windows 11.
"""

import os
import subprocess
import threading
import re
import shlex
import unicodedata
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


# =============================================================================
# INTERPRETAÇÃO DETALHADA DOS CÓDIGOS DE SAÍDA (BITS DO ROBOCOPY)
# =============================================================================
# O código de saída do RoboCopy é um conjunto de bits somados. Ex.: 3 = 1 + 2.
EXIT_CODE_BITS = {
    1: (
        "Arquivos copiados",
        "Pelo menos um arquivo novo ou atualizado foi gravado no destino.",
        "success",
    ),
    2: (
        "Arquivos extras no destino",
        "Existem arquivos ou pastas no destino que não estão na origem. "
        "Nada foi perdido: o RoboCopy apenas avisa que os dois lados estão diferentes.",
        "warning",
    ),
    4: (
        "Itens incompatíveis",
        "Um mesmo nome existe como arquivo de um lado e como pasta do outro. "
        "Esses itens precisam de decisão manual: o RoboCopy não consegue resolver sozinho.",
        "warning",
    ),
    8: (
        "Falha ao copiar arquivos",
        "Alguns arquivos não puderam ser copiados (bloqueados por outro programa, "
        "sem permissão de leitura ou caminho longo demais).",
        "error",
    ),
    16: (
        "Erro fatal",
        "O RoboCopy não conseguiu iniciar: caminho inválido, unidade inacessível, "
        "acesso negado ou parâmetro incorreto. Nenhuma cópia foi realizada.",
        "error",
    ),
}

# Sugestão prática para o usuário, por bit acionado.
EXIT_CODE_ACTIONS = {
    2: "Use a Central de Sincronização para listar os arquivos extras e escolher o que fazer com cada um.",
    4: "Abra o painel de Ocorrências e renomeie manualmente os itens incompatíveis antes de sincronizar novamente.",
    8: "Feche os programas que estejam usando os arquivos e reexecute. Se persistir, execute como Administrador.",
    16: "Confira se os caminhos de origem e destino existem e se você tem permissão de acesso.",
}


def decompose_exit_code(code: int) -> List[int]:
    """Decompõe o código de saída do RoboCopy nos bits que o formam (ex.: 3 -> [1, 2])."""
    if code is None or code <= 0:
        return []
    return [bit for bit in (1, 2, 4, 8, 16) if code & bit]


def explain_exit_code(code: int, step_results: Optional[List[Dict[str, Any]]] = None) -> str:
    """Texto didático explicando o código de saída, o impacto real e o que fazer."""
    title, desc, _category = interpret_exit_code(code)

    lines = [f"Código de saída do RoboCopy: {code} ({title})", desc, ""]

    bits = decompose_exit_code(code)
    if bits:
        lines.append("O que esse número significa (a soma dos sinalizadores):")
        for bit in bits:
            bit_title, bit_desc, _cat = EXIT_CODE_BITS[bit]
            lines.append(f"  [{bit}] {bit_title}: {bit_desc}")
    else:
        lines.append("Nenhum sinalizador acionado: origem e destino já estavam sincronizados.")

    actions = [EXIT_CODE_ACTIONS[bit] for bit in bits if bit in EXIT_CODE_ACTIONS]
    if actions:
        lines.append("")
        lines.append("Como resolver:")
        for action in actions:
            lines.append(f"  - {action}")

    if step_results:
        lines.append("")
        lines.append("Resultado de cada etapa executada:")
        for step in step_results:
            lines.append(
                f"  - {step.get('label', 'Etapa')}: [{step.get('code')}] {step.get('title', '')}"
            )
        if len(step_results) > 1:
            lines.append("")
            lines.append(
                "O status acima já é o resultado consolidado: divergências apontadas em uma "
                "etapa e resolvidas pela etapa seguinte não contam como pendência."
            )

    lines.append("")
    lines.append("Referência: 0 a 7 indicam sucesso (com ou sem avisos). 8 ou mais indicam falha real.")
    return "\n".join(lines)


def consolidate_exit_codes(codes: List[Optional[int]], two_way: bool = False) -> int:
    """
    Consolida os códigos de saída de uma operação de várias etapas em um único resultado.

    Os códigos do RoboCopy são bits somados, portanto a união (OR) preserva todos os
    sinalizadores. Em sincronização bidirecional concluída sem falhas, o sinalizador de
    "arquivos extras" (bit 2) apontado por uma etapa é resolvido pela etapa inversa,
    que copia esses arquivos de volta, e por isso deixa de ser reportado.
    """
    valid = [c for c in codes if c is not None]
    if not valid:
        return 0

    combined = 0
    for code in valid:
        if code < 0:
            return 16
        combined |= code

    if two_way and len(valid) >= 2 and all(c < 8 for c in valid):
        combined &= ~2

    return combined


# =============================================================================
# CLASSIFICAÇÃO E LEITURA DAS LINHAS DE SAÍDA DO ROBOCOPY
# =============================================================================
# Rótulos legíveis de cada categoria reconhecida no log.
LOG_CATEGORY_LABELS = {
    "new_file": "Novo Arquivo",
    "new_dir": "Nova Pasta",
    "extra_file": "Arquivo EXTRA",
    "extra_dir": "Pasta EXTRA",
    "lonely": "Somente no destino",
    "mismatch": "Incompatibilidade",
    "newer": "Mais recente na origem",
    "older": "Mais antigo na origem",
    "changed": "Conteúdo alterado",
    "tweaked": "Ajustado",
    "same": "Idêntico",
    "deleted": "Excluído",
    "error": "FALHA",
    "warning": "Aviso",
    "step": "Etapa",
    "summary": "Resumo",
    "banner": "Cabeçalho",
    "progress": "Progresso",
    "plain": "",
}

# Categorias que representam uma ocorrência que o usuário precisa revisar.
OCCURRENCE_CATEGORIES = ("extra_file", "extra_dir", "lonely", "mismatch", "error")

# Categorias que representam divergência real entre origem e destino.
DIFFERENCE_CATEGORIES = (
    "new_file", "new_dir", "newer", "older", "changed",
    "extra_file", "extra_dir", "lonely", "mismatch",
)


def normalize_text(text: str) -> str:
    """Remove acentuação e converte para maiúsculas para comparações independentes de idioma."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).upper()


# Linhas emitidas pelo próprio RoboCopy Manager (não pelo robocopy.exe).
_RE_ENGINE_STEP = re.compile(r"^\s*>>>")
_RE_ENGINE_ERROR = re.compile(r"^\s*\[(?:ERRO|ERROR|FALHA)")
_RE_ENGINE_WARNING = re.compile(r"^\s*\[(?:AVISO|ATEN|OPERACAO|WARNING)")
_RE_ENGINE_BANNER = re.compile(r"^\s*(?:={3,}|-{3,})\s*$")
_RE_ENGINE_LABEL = re.compile(r"^\s*(?:INICIO|COMANDO|HORARIO|CONCLUSAO|ETAPA|RESULTADO)\s*:")

# Cabeçalho e rodapé do próprio robocopy.exe.
_RE_SUMMARY_HEADER = re.compile(r"^\s*TOTAL\s+(?:COPIAD|COPIED)")
_RE_SUMMARY_ROW = re.compile(
    r"^\s*(?:DIRET\w*|DIRS|ARQUIVOS|FILES|BYTES|TEMPOS|TIMES|VELOCIDADE|SPEED|"
    r"TERMINADO|ENDED|INICIADO|STARTED|ORIGEM|SOURCE|DESTINO|DEST|OPCOES|OPTIONS|ROBOCOPY)\s*:"
)

# Erros e avisos do robocopy.exe.
_RE_ERROR = re.compile(
    r"(?:^|\s)(?:ERROR|ERRO)\s+\d+|ACESSO NEGADO|ACCESS IS DENIED|"
    r"(?:^|\s)FALHOU(?:\s|$)|(?:^|\s)FAILED(?:\s|$)"
)
_RE_RETRY = re.compile(r"AGUARDANDO\s+\d+|WAITING\s+\d+|REPETINDO|RETRYING")
_RE_PROGRESS = re.compile(r"^\s*[\d.,]+%\s*$")

# Classes de arquivo/pasta. Sempre no início da linha, antes do tamanho e do caminho.
_CLASS_PATTERNS = [
    ("extra_file", re.compile(r"^[\s\t]*\*\s*(?:EXTRA\s+FILE|ARQUIVO\s+EXTRA)\b")),
    ("extra_dir", re.compile(r"^[\s\t]*\*\s*(?:EXTRA\s+DIR\w*|DIRETORIO\s+EXTRA|PASTA\s+EXTRA)\b")),
    ("mismatch", re.compile(r"^[\s\t]*\*\s*(?:MISMATCH\w*|INCOMPAT\w*)\b")),
    ("lonely", re.compile(r"^[\s\t]*\*\s*(?:LONELY|SOZINH\w*)\b")),
    ("new_dir", re.compile(r"^[\s\t]*(?:NEW\s+DIR\w*|NOVO\s+DIR\w*|NOVA\s+PASTA)\b")),
    ("new_file", re.compile(r"^[\s\t]*(?:NEW\s+FILE|NOVO\s+ARQUIVO|ARQUIVO\s+NOVO)\b")),
    ("newer", re.compile(r"^[\s\t]*(?:NEWER|MAIS\s+RECENTE|MAIS\s+NOVO)\b")),
    ("older", re.compile(r"^[\s\t]*(?:OLDER|MAIS\s+ANTIGO)\b")),
    ("changed", re.compile(r"^[\s\t]*(?:CHANGED|ALTERAD\w*|MODIFICAD\w*)\b")),
    ("tweaked", re.compile(r"^[\s\t]*(?:TWEAKED|AJUSTAD\w*)\b")),
    ("same", re.compile(r"^[\s\t]*(?:SAME|IGUAL|MESMO)\b")),
    ("deleted", re.compile(r"^[\s\t]*(?:DELETING|DELETED|EXCLUINDO|EXCLUID\w*|APAGANDO)\b")),
]

# Tamanho opcional seguido do caminho (campos separados por tabulação ou 2+ espaços).
_RE_SIZE_PATH = re.compile(
    r"^[\s\t]*(?:(?P<size>[\d.,]+\s*[kmgtb]?)(?:\t+|\s{2,}))?(?P<path>\S.*?)\s*$",
    re.IGNORECASE,
)

_SIZE_MULTIPLIERS = {"k": 1024, "m": 1024 ** 2, "g": 1024 ** 3, "t": 1024 ** 4}


def parse_size(size_text: str) -> Optional[int]:
    """Converte o tamanho impresso pelo RoboCopy ('1024', '1.2 m', '24,5 k') em bytes."""
    if not size_text:
        return None

    cleaned = size_text.strip().lower().replace(" ", "")
    if not cleaned:
        return None

    multiplier = 1
    if cleaned[-1] in _SIZE_MULTIPLIERS:
        multiplier = _SIZE_MULTIPLIERS[cleaned[-1]]
        cleaned = cleaned[:-1]
    elif cleaned.endswith("b"):
        cleaned = cleaned[:-1]

    if not cleaned:
        return None

    try:
        if multiplier > 1:
            # Com sufixo o separador é decimal (1.2 m / 1,2 m).
            return int(float(cleaned.replace(",", ".")) * multiplier)
        # Sem sufixo os separadores são de milhar.
        digits = cleaned.replace(".", "").replace(",", "")
        return int(digits) if digits.isdigit() else None
    except (ValueError, OverflowError):
        return None


def format_size(size_bytes: Optional[int]) -> str:
    """Formata um tamanho em bytes de forma legível (para a tabela de ocorrências)."""
    if size_bytes is None:
        return "-"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    value = float(size_bytes)
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1024.0
        if value < 1024.0:
            return f"{value:.1f} {unit}".replace(".", ",")
    return f"{value:.1f} PB".replace(".", ",")


def classify_log_line(line: str) -> str:
    """
    Identifica a natureza de uma linha do log (categoria usada no destaque colorido
    e no painel de ocorrências). Reconhece a saída do RoboCopy em português e inglês.
    """
    if not line or not line.strip():
        return "plain"

    if _RE_ENGINE_STEP.match(line):
        return "step"

    normalized = normalize_text(line)

    if _RE_ENGINE_ERROR.match(normalized):
        return "error"
    if _RE_ENGINE_WARNING.match(normalized):
        return "warning"
    if _RE_ENGINE_BANNER.match(normalized) or _RE_ENGINE_LABEL.match(normalized):
        return "banner"
    if _RE_PROGRESS.match(normalized):
        return "progress"
    if _RE_SUMMARY_HEADER.match(normalized) or _RE_SUMMARY_ROW.match(normalized):
        return "summary"

    for category, pattern in _CLASS_PATTERNS:
        if pattern.match(normalized):
            return category

    if _RE_ERROR.search(normalized):
        return "error"
    if _RE_RETRY.search(normalized):
        return "warning"

    return "plain"


@dataclass
class LogEntry:
    """Uma linha de log já interpretada: categoria, tamanho e caminho do item."""
    category: str
    label: str
    path: str
    size: Optional[int] = None
    size_text: str = ""
    raw: str = ""
    message: str = ""

    @property
    def display_path(self) -> str:
        """Caminho do item ou, quando o RoboCopy não informa um caminho, a mensagem original."""
        return self.path or self.message or self.raw.strip()

    @property
    def is_occurrence(self) -> bool:
        return self.category in OCCURRENCE_CATEGORIES


def parse_log_entry(line: str) -> Optional[LogEntry]:
    """
    Converte uma linha do RoboCopy em um registro estruturado (categoria, tamanho, caminho).
    Retorna None para linhas sem conteúdo aproveitável (banners, resumos, progresso).
    """
    if not line or not line.strip():
        return None

    category = classify_log_line(line)
    if category in ("banner", "summary", "progress", "plain", "step"):
        return None

    raw = line.rstrip("\r\n")
    label = LOG_CATEGORY_LABELS.get(category, category)

    if category in ("error", "warning"):
        return LogEntry(
            category=category,
            label=label,
            path=_extract_error_path(raw),
            raw=raw,
            message=raw.strip(),
        )

    normalized = normalize_text(raw)
    remainder = raw
    for cat, pattern in _CLASS_PATTERNS:
        if cat != category:
            continue
        match = pattern.match(normalized)
        if match:
            remainder = raw[match.end():]
        break

    parsed = _RE_SIZE_PATH.match(remainder)
    if not parsed:
        return LogEntry(category=category, label=label, path=remainder.strip(), raw=raw)

    size_text = (parsed.group("size") or "").strip()
    path = (parsed.group("path") or "").strip()

    return LogEntry(
        category=category,
        label=label,
        path=path,
        size=parse_size(size_text),
        size_text=size_text,
        raw=raw,
    )


def _extract_error_path(line: str) -> str:
    """Isola o caminho citado em uma linha de erro do RoboCopy (vazio quando não há)."""
    match = re.search(r"([A-Za-z]:\\[^\r\n\"]+|\\\\[^\r\n\"]+)", line)
    if match:
        return match.group(1).strip()
    return ""


# =============================================================================
# FLAGS PERSONALIZADAS (PARÂMETROS LIVRES DIGITADOS PELO USUÁRIO)
# =============================================================================
# Parâmetros que apagam arquivos e por isso exigem confirmação explícita.
DESTRUCTIVE_FLAGS = {
    "/MIR": "espelha o destino e APAGA tudo o que não existir na origem",
    "/PURGE": "APAGA do destino os arquivos que não existem mais na origem",
    "/MOVE": "APAGA da origem os arquivos e as pastas depois de copiar",
    "/MOV": "APAGA da origem os arquivos depois de copiar",
}

# Parâmetros controlados pela própria interface: repeti-los aqui gera conflito.
_MANAGED_FLAGS = ("/L", "/TEE", "/NP", "/LOG", "/LOG+", "/COPY", "/DCOPY", "/MT", "/R", "/W")


def analyze_extra_args(text: str) -> Dict[str, Any]:
    """
    Verifica as flags livres digitadas pelo usuário e devolve um diagnóstico:
    quais apagam arquivos, quais duplicam opções da interface e quais não parecem flags.
    """
    tokens = split_windows_args(text or "")
    destructive: List[str] = []
    duplicated: List[str] = []
    suspicious: List[str] = []

    for token in tokens:
        if not token.startswith("/"):
            suspicious.append(token)
            continue

        base = token.split(":", 1)[0].upper()
        if base in DESTRUCTIVE_FLAGS:
            destructive.append(base)
        elif base in _MANAGED_FLAGS:
            duplicated.append(base)

    messages: List[str] = []
    if destructive:
        details = "; ".join(f"{flag} {DESTRUCTIVE_FLAGS[flag]}" for flag in destructive)
        messages.append(f"ATENÇÃO - parâmetro que apaga arquivos: {details}.")
    if duplicated:
        messages.append(
            "Já controlado pela interface (o valor daqui pode entrar em conflito): "
            + ", ".join(sorted(set(duplicated)))
            + "."
        )
    if suspicious:
        messages.append(
            "Não parece um parâmetro do RoboCopy (flags começam com '/'): "
            + ", ".join(suspicious)
            + "."
        )

    return {
        "tokens": tokens,
        "destructive": destructive,
        "duplicated": duplicated,
        "suspicious": suspicious,
        "warning": " ".join(messages),
        "is_destructive": bool(destructive),
    }


def extract_occurrences(lines: List[str]) -> List["LogEntry"]:
    """
    Filtra de um log completo apenas as ocorrências que exigem atenção do usuário.
    Linhas de detalhe de um erro (ex.: "Acesso negado.") são anexadas ao erro anterior
    em vez de virarem uma ocorrência solta.
    """
    occurrences: List[LogEntry] = []
    for line in lines:
        entry = parse_log_entry(line)
        if not entry or not entry.is_occurrence:
            continue

        if entry.category == "error" and not entry.path and occurrences:
            previous = occurrences[-1]
            if previous.category == "error":
                detail = entry.message.strip()
                if detail:
                    previous.message = f"{previous.message} {detail}".strip()
                continue

        occurrences.append(entry)
    return occurrences


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
        step_results: List[Dict[str, Any]] = []
        exit_code = 0
        is_two_way = bool(config.is_two_way_sync)

        def _register_step(label: str, code: int):
            title, desc, _cat = interpret_exit_code(code)
            step_results.append({"label": label, "code": code, "title": title, "desc": desc})
            on_line(f"\n>>> {label} concluída: [{code}] {title} - {desc}\n")

        try:
            if is_two_way:
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
                _register_step("Etapa 1 de 2 (Origem -> Destino)", code1)

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
                    _register_step("Etapa 2 de 2 (Destino -> Origem)", code2)
                else:
                    on_line(
                        "\n[AVISO] A Etapa 2 (Destino -> Origem) não foi executada porque a "
                        "Etapa 1 não pôde ser concluída.\n"
                    )

                exit_code = consolidate_exit_codes([s["code"] for s in step_results], two_way=True)
            else:
                cmd_args = self.build_command_args(config)
                exit_code = self._execute_single_step(cmd_args, full_output_lines, on_line)
                title, desc, _cat = interpret_exit_code(exit_code)
                step_results.append({
                    "label": "Etapa única (Origem -> Destino)",
                    "code": exit_code, "title": title, "desc": desc,
                })

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
        summary["occurrences"] = extract_occurrences(full_output_lines)
        summary["steps"] = step_results
        summary["step_codes"] = [s["code"] for s in step_results]
        summary["is_two_way"] = is_two_way
        summary["raw_exit_code"] = exit_code

        if self._cancel_requested:
            exit_code = 16
            title = "Interrompido"
            desc = "Operação cancelada pelo usuário."
        else:
            title, desc, status_cat = interpret_exit_code(exit_code)

        summary["exit_code"] = exit_code
        summary["explanation"] = explain_exit_code(exit_code, step_results)

        on_line("\n" + "-" * 60 + "\n")
        if len(step_results) > 1:
            for step in step_results:
                on_line(f"{step['label']}: [{step['code']}] {step['title']}\n")
            on_line(f"Resultado consolidado: [{exit_code}] {title} - {desc}\n")
        else:
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
