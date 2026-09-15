"""
Analisador de Sincronização de Pastas (padrão GoodSync).

Responde às três perguntas que o RoboCopy sozinho não responde de forma direta:
  1. QUAIS arquivos estão diferentes entre origem e destino?
  2. EM QUE CAMINHO cada um deles está e de que lado ele existe?
  3. O QUE fazer com cada um (copiar para um lado, para o outro, excluir ou ignorar)?

A análise roda o RoboCopy em modo somente-listagem (/L), portanto NUNCA altera,
copia ou apaga arquivo algum. O resultado vira um plano de ações editável pelo
usuário, que só então é executado.
"""

import os
import re
import shutil
import stat
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from robocopy_engine import (
    DIFFERENCE_CATEGORIES,
    LOG_CATEGORY_LABELS,
    RobocopyConfig,
    RobocopyEngine,
    consolidate_exit_codes,
    format_size,
    interpret_exit_code,
    parse_log_entry,
    split_windows_args,
)

# -----------------------------------------------------------------------------
# AÇÕES POSSÍVEIS PARA CADA DIVERGÊNCIA
# -----------------------------------------------------------------------------
ACTION_COPY_TO_DEST = "copy_to_dest"
ACTION_COPY_TO_SOURCE = "copy_to_source"
ACTION_DELETE_DEST = "delete_dest"
ACTION_SKIP = "skip"

ACTION_LABELS = {
    ACTION_COPY_TO_DEST: "Copiar para o Destino",
    ACTION_COPY_TO_SOURCE: "Copiar para a Origem",
    ACTION_DELETE_DEST: "Excluir do Destino",
    ACTION_SKIP: "Ignorar",
}

ACTION_ORDER = [ACTION_COPY_TO_DEST, ACTION_COPY_TO_SOURCE, ACTION_DELETE_DEST, ACTION_SKIP]

SIDE_SOURCE = "source"
SIDE_DESTINATION = "destination"

SIDE_LABELS = {
    SIDE_SOURCE: "Origem",
    SIDE_DESTINATION: "Destino",
}

# De que lado o item detectado existe.
CATEGORY_SIDE = {
    "new_file": SIDE_SOURCE,
    "new_dir": SIDE_SOURCE,
    "newer": SIDE_SOURCE,
    "older": SIDE_SOURCE,
    "changed": SIDE_SOURCE,
    "extra_file": SIDE_DESTINATION,
    "extra_dir": SIDE_DESTINATION,
    "lonely": SIDE_DESTINATION,
    "mismatch": SIDE_DESTINATION,
}

# Explicação em linguagem comum do que cada situação significa.
CATEGORY_EXPLANATIONS = {
    "new_file": "Existe só na origem. Ainda não foi copiado para o destino.",
    "new_dir": "Pasta que existe só na origem e ainda não foi criada no destino.",
    "newer": "Existe dos dois lados, mas a versão da origem é mais recente.",
    "older": "Existe dos dois lados, mas a versão do DESTINO é mais recente que a da origem.",
    "changed": "Existe dos dois lados com o mesmo horário, porém com tamanho/conteúdo diferente.",
    "extra_file": "Existe só no destino. Foi apagado da origem ou criado direto no destino.",
    "extra_dir": "Pasta que existe só no destino, junto com todo o conteúdo dentro dela.",
    "lonely": "Existe só no destino e não tem correspondente na origem.",
    "mismatch": "O mesmo nome é arquivo de um lado e pasta do outro. Precisa de renomeação manual.",
}

# Modos de sincronização suportados pela Central (equivalentes aos do GoodSync).
MODE_MIRROR = "goodsync_mirror"
MODE_UPDATE = "goodsync_update"
MODE_TWO_WAY = "goodsync_two_way"
MODE_MOVE = "goodsync_move"
MODE_FILTER = "goodsync_filter"

# Ação sugerida automaticamente para cada situação, conforme o modo escolhido.
_SUGGESTIONS: Dict[str, Dict[str, str]] = {
    MODE_MIRROR: {
        "new_file": ACTION_COPY_TO_DEST,
        "new_dir": ACTION_COPY_TO_DEST,
        "newer": ACTION_COPY_TO_DEST,
        "older": ACTION_COPY_TO_DEST,
        "changed": ACTION_COPY_TO_DEST,
        "extra_file": ACTION_DELETE_DEST,
        "extra_dir": ACTION_DELETE_DEST,
        "lonely": ACTION_DELETE_DEST,
        "mismatch": ACTION_SKIP,
    },
    MODE_UPDATE: {
        "new_file": ACTION_COPY_TO_DEST,
        "new_dir": ACTION_COPY_TO_DEST,
        "newer": ACTION_COPY_TO_DEST,
        "older": ACTION_SKIP,
        "changed": ACTION_COPY_TO_DEST,
        "extra_file": ACTION_SKIP,
        "extra_dir": ACTION_SKIP,
        "lonely": ACTION_SKIP,
        "mismatch": ACTION_SKIP,
    },
    MODE_TWO_WAY: {
        "new_file": ACTION_COPY_TO_DEST,
        "new_dir": ACTION_COPY_TO_DEST,
        "newer": ACTION_COPY_TO_DEST,
        "older": ACTION_COPY_TO_SOURCE,
        "changed": ACTION_COPY_TO_DEST,
        "extra_file": ACTION_COPY_TO_SOURCE,
        "extra_dir": ACTION_COPY_TO_SOURCE,
        "lonely": ACTION_COPY_TO_SOURCE,
        "mismatch": ACTION_SKIP,
    },
    MODE_MOVE: {
        "new_file": ACTION_COPY_TO_DEST,
        "new_dir": ACTION_COPY_TO_DEST,
        "newer": ACTION_COPY_TO_DEST,
        "older": ACTION_COPY_TO_DEST,
        "changed": ACTION_COPY_TO_DEST,
        "extra_file": ACTION_SKIP,
        "extra_dir": ACTION_SKIP,
        "lonely": ACTION_SKIP,
        "mismatch": ACTION_SKIP,
    },
}
_SUGGESTIONS[MODE_FILTER] = dict(_SUGGESTIONS[MODE_UPDATE])


def suggest_action(category: str, mode: str = MODE_TWO_WAY) -> str:
    """Ação sugerida para uma divergência, de acordo com o modo de sincronização."""
    table = _SUGGESTIONS.get(mode, _SUGGESTIONS[MODE_UPDATE])
    return table.get(category, ACTION_SKIP)


# -----------------------------------------------------------------------------
# MANIPULAÇÃO DE CAMINHOS (independente do sistema onde o código roda)
# -----------------------------------------------------------------------------
def _to_backslash(path: str) -> str:
    return path.replace("/", "\\")


def _normalize_for_compare(path: str) -> str:
    return _to_backslash(path).rstrip("\\").lower()


def relative_to(path: str, base: str) -> Optional[str]:
    """Caminho relativo de 'path' dentro de 'base', ou None se não estiver dentro."""
    if not path or not base:
        return None

    norm_path = _normalize_for_compare(path)
    norm_base = _normalize_for_compare(base)
    if not norm_base:
        return None

    if norm_path == norm_base:
        return ""
    if norm_path.startswith(norm_base + "\\"):
        trailing = "\\" if _to_backslash(path).endswith("\\") else ""
        return _to_backslash(path).rstrip("\\")[len(norm_base) + 1:] + trailing
    return None


def join_path(base: str, relative: str) -> str:
    """Junta base e caminho relativo preservando o separador usado na base."""
    if not relative:
        return base
    separator = "\\" if "\\" in base else ("/" if "/" in base else os.sep)
    normalized = relative.replace("\\", separator).replace("/", separator)
    return base.rstrip("\\/") + separator + normalized.lstrip(separator)


def parent_of(relative_path: str) -> str:
    """Pasta pai de um caminho relativo ('sub\\a.txt' -> 'sub')."""
    cleaned = _to_backslash(relative_path).rstrip("\\")
    if "\\" not in cleaned:
        return ""
    return cleaned.rsplit("\\", 1)[0]


def name_of(relative_path: str) -> str:
    """Último componente de um caminho relativo."""
    cleaned = _to_backslash(relative_path).rstrip("\\")
    if "\\" not in cleaned:
        return cleaned
    return cleaned.rsplit("\\", 1)[1]


def _is_absolute_windows(path: str) -> bool:
    return bool(re.match(r"^(?:[A-Za-z]:[\\/]|\\\\)", path)) or os.path.isabs(path)


# Linha de cabeçalho de diretório do RoboCopy: "\t   12\tC:\Origem\sub\"
_RE_DIR_HEADER = re.compile(r"^[\s\t]*[\d.,]*[\s\t]*((?:[A-Za-z]:[\\/]|\\\\)[^\r\n]*[\\/])\s*$")


# -----------------------------------------------------------------------------
# ESTRUTURAS DE DADOS
# -----------------------------------------------------------------------------
@dataclass
class SyncDifference:
    """Uma divergência concreta entre origem e destino, com a ação escolhida."""
    category: str
    label: str
    relative_path: str
    source_path: str
    dest_path: str
    side: str
    action: str
    is_dir: bool = False
    size: Optional[int] = None
    raw: str = ""

    @property
    def size_text(self) -> str:
        return format_size(self.size)

    @property
    def side_label(self) -> str:
        return SIDE_LABELS.get(self.side, self.side)

    @property
    def action_label(self) -> str:
        return ACTION_LABELS.get(self.action, self.action)

    @property
    def explanation(self) -> str:
        return CATEGORY_EXPLANATIONS.get(self.category, "")

    @property
    def path_on_side(self) -> str:
        """Caminho completo real do item no lado em que ele existe hoje."""
        return self.dest_path if self.side == SIDE_DESTINATION else self.source_path

    @property
    def exists_on_both_sides(self) -> bool:
        """True quando o item existe nas duas pastas e apenas o conteúdo diverge."""
        return self.category in ("newer", "older", "changed", "tweaked", "mismatch")

    def location_text(self) -> str:
        """Descrição de onde o item está hoje e para onde ele iria."""
        if self.exists_on_both_sides:
            return f"Na origem:  {self.source_path}\nNo destino: {self.dest_path}"
        if self.side == SIDE_DESTINATION:
            return (
                f"Existe hoje no destino: {self.dest_path}\n"
                f"Caminho equivalente na origem (ainda não existe): {self.source_path}"
            )
        return (
            f"Existe hoje na origem: {self.source_path}\n"
            f"Caminho equivalente no destino (ainda não existe): {self.dest_path}"
        )

    def available_actions(self) -> List[str]:
        """Ações que fazem sentido para esta divergência."""
        if self.category == "mismatch":
            return [ACTION_SKIP]
        if self.side == SIDE_DESTINATION:
            return [ACTION_COPY_TO_SOURCE, ACTION_DELETE_DEST, ACTION_SKIP]
        return [ACTION_COPY_TO_DEST, ACTION_SKIP]


@dataclass
class SyncAnalysis:
    """Resultado completo de uma análise de diferenças."""
    source: str = ""
    destination: str = ""
    mode: str = MODE_TWO_WAY
    differences: List[SyncDifference] = field(default_factory=list)
    errors: List[Any] = field(default_factory=list)
    exit_code: int = 0
    raw_lines: List[str] = field(default_factory=list)
    cancelled: bool = False

    def counts(self) -> Dict[str, int]:
        """Quantidade de divergências por categoria, mais os totais por lado."""
        result: Dict[str, int] = {}
        for diff in self.differences:
            result[diff.category] = result.get(diff.category, 0) + 1
        result["total"] = len(self.differences)
        result["source_only"] = sum(1 for d in self.differences if d.side == SIDE_SOURCE)
        result["destination_only"] = sum(1 for d in self.differences if d.side == SIDE_DESTINATION)
        result["errors"] = len(self.errors)
        return result

    def summary_text(self) -> str:
        """Resumo curto para exibir acima da tabela de divergências."""
        if not self.differences and not self.errors:
            return "Origem e destino estão idênticos: nenhuma divergência encontrada."

        counts = self.counts()
        parts = []
        for category in ("new_file", "new_dir", "newer", "older", "changed",
                         "extra_file", "extra_dir", "lonely", "mismatch"):
            quantity = counts.get(category, 0)
            if quantity:
                parts.append(f"{LOG_CATEGORY_LABELS.get(category, category)}: {quantity}")
        if counts.get("errors"):
            parts.append(f"Erros de leitura: {counts['errors']}")
        return f"{counts['total']} divergência(s) — " + " | ".join(parts)


# -----------------------------------------------------------------------------
# LEITURA DA SAÍDA DA ANÁLISE
# -----------------------------------------------------------------------------
def build_analysis_args(config: RobocopyConfig, source: str = "", destination: str = "") -> List[str]:
    """
    Monta o comando de análise: somente listagem (/L), sem gravar nada.
    /MIR em conjunto com /L não apaga nada — apenas faz o RoboCopy relatar também
    os arquivos que existem apenas no destino (*Arquivo EXTRA).
    """
    src = (source or config.source).strip().strip('"')
    dst = (destination or config.destination).strip().strip('"')
    if len(src) > 3:
        src = src.rstrip("\\/")
    if len(dst) > 3:
        dst = dst.rstrip("\\/")

    args = ["robocopy", src, dst]

    pattern = (config.file_pattern or "").strip()
    if pattern and pattern != "*.*":
        args.extend(split_windows_args(pattern))

    # /L      = apenas listar (não copia, não apaga)
    # /MIR    = faz o RoboCopy enxergar e relatar os itens extras do destino
    # /FP     = caminho completo de cada arquivo listado
    # /BYTES  = tamanho exato em bytes
    # /NJH /NJS /NP = remove cabeçalho, rodapé e percentuais do relatório
    args.extend(["/L", "/MIR", "/FP", "/BYTES", "/NJH", "/NJS", "/NP", "/R:0", "/W:0"])

    if config.exclude_junctions:
        args.append("/XJ")

    if config.exclude_files.strip():
        excluded_files = split_windows_args(config.exclude_files.strip())
        if excluded_files:
            args.append("/XF")
            args.extend(excluded_files)

    if config.exclude_dirs.strip():
        excluded_dirs = split_windows_args(config.exclude_dirs.strip())
        if excluded_dirs:
            args.append("/XD")
            args.extend(excluded_dirs)

    if config.max_size.strip():
        args.append(f"/MAX:{config.max_size.strip()}")
    if config.min_size.strip():
        args.append(f"/MIN:{config.min_size.strip()}")

    if config.subfolder_level > 0:
        args.append(f"/LEV:{config.subfolder_level}")

    return args


def parse_analysis_output(
    lines: List[str],
    source: str,
    destination: str,
    mode: str = MODE_TWO_WAY,
) -> SyncAnalysis:
    """
    Converte a saída bruta da análise em uma lista de divergências com caminho,
    lado, tamanho e ação sugerida. Função pura: não toca em disco.
    """
    analysis = SyncAnalysis(source=source, destination=destination, mode=mode, raw_lines=list(lines))
    current_dir = ""
    seen = set()

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if not line.strip():
            continue

        entry = parse_log_entry(line)

        if entry is None:
            header = _RE_DIR_HEADER.match(line)
            if header:
                current_dir = header.group(1)
            continue

        if entry.category == "error":
            # "Acesso negado." e afins detalham o erro anterior, não são um novo erro.
            if not entry.path and analysis.errors:
                previous = analysis.errors[-1]
                previous.message = f"{previous.message} {entry.message}".strip()
            else:
                analysis.errors.append(entry)
            continue

        if entry.category not in DIFFERENCE_CATEGORIES:
            continue

        path = entry.path.strip()
        if not path:
            continue

        # Sem /FP o RoboCopy imprime apenas o nome do arquivo: completa com a pasta atual.
        if not _is_absolute_windows(path) and current_dir:
            path = join_path(current_dir, path)

        if entry.category == "new_dir":
            current_dir = path if path.endswith(("\\", "/")) else path + "\\"

        difference = _build_difference(entry, path, source, destination, mode)
        if difference is None:
            continue

        key = (difference.category, _normalize_for_compare(difference.relative_path))
        if key in seen:
            continue
        seen.add(key)
        analysis.differences.append(difference)

    return analysis


def _build_difference(entry, path: str, source: str, destination: str, mode: str) -> Optional[SyncDifference]:
    """Monta a divergência resolvendo de que lado o item está e seu caminho relativo."""
    side = CATEGORY_SIDE.get(entry.category, SIDE_SOURCE)
    base = destination if side == SIDE_DESTINATION else source
    relative = relative_to(path, base)

    if relative is None:
        # O caminho não está sob a base esperada: tenta o outro lado antes de desistir.
        other_side = SIDE_SOURCE if side == SIDE_DESTINATION else SIDE_DESTINATION
        other_base = source if other_side == SIDE_SOURCE else destination
        relative = relative_to(path, other_base)
        if relative is not None:
            side = other_side
        else:
            relative = name_of(path)

    if not relative:
        return None

    is_dir = entry.category in ("new_dir", "extra_dir") or path.endswith(("\\", "/"))
    clean_relative = _to_backslash(relative).strip("\\")

    # Em linhas de pasta o número impresso pelo RoboCopy é a contagem de itens,
    # e não um tamanho em bytes: exibi-lo como tamanho confundiria o usuário.
    size = None if is_dir else entry.size

    return SyncDifference(
        category=entry.category,
        label=LOG_CATEGORY_LABELS.get(entry.category, entry.category),
        relative_path=clean_relative,
        source_path=join_path(source, clean_relative),
        dest_path=join_path(destination, clean_relative),
        side=side,
        action=suggest_action(entry.category, mode),
        is_dir=is_dir,
        size=size,
        raw=entry.raw,
    )


# -----------------------------------------------------------------------------
# EXECUÇÃO DA ANÁLISE
# -----------------------------------------------------------------------------
class SyncAnalyzer:
    """Executa a análise de diferenças chamando o RoboCopy em modo somente-listagem."""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self._cancel_requested = False
        self._lock = threading.Lock()
        self._engine = RobocopyEngine()

    def analyze_sync(
        self,
        config: RobocopyConfig,
        mode: str = MODE_TWO_WAY,
        on_line: Optional[Callable[[str], None]] = None,
    ) -> SyncAnalysis:
        """Roda a análise de forma bloqueante e devolve o resultado já interpretado."""
        emit = on_line or (lambda _line: None)

        with self._lock:
            if self.is_running:
                emit("\n[AVISO] Uma análise já está em andamento.\n")
                return SyncAnalysis(source=config.source, destination=config.destination, mode=mode)
            self.is_running = True
            self._cancel_requested = False

        args = build_analysis_args(config)
        output_lines: List[str] = []
        exit_code = 0

        try:
            startupinfo = None
            creationflags = 0
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW

            self.process = subprocess.Popen(
                args,
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
                    line = self._engine._decode_line(raw_line)
                    output_lines.append(line)
                    emit(line)

            exit_code = self.process.poll() or 0
        except FileNotFoundError:
            emit("\n[ERRO NA ANÁLISE]: O comando robocopy não foi encontrado neste sistema.\n")
            exit_code = 16
        except Exception as ex:
            emit(f"\n[ERRO NA ANÁLISE]: {ex}\n")
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

        analysis = parse_analysis_output(output_lines, config.source, config.destination, mode)
        analysis.exit_code = exit_code
        analysis.cancelled = self._cancel_requested
        return analysis

    def analyze_async(
        self,
        config: RobocopyConfig,
        mode: str,
        on_line: Callable[[str], None],
        on_finish: Callable[[SyncAnalysis], None],
    ):
        """Versão em thread, para não travar a interface gráfica."""
        def _worker():
            result = self.analyze_sync(config, mode, on_line)
            on_finish(result)

        threading.Thread(target=_worker, daemon=True).start()

    def stop(self) -> bool:
        """Interrompe uma análise em andamento."""
        with self._lock:
            if not self.is_running or not self.process:
                return False
            self._cancel_requested = True
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                else:
                    self.process.terminate()
                return True
            except Exception:
                return False


# -----------------------------------------------------------------------------
# PLANO DE EXECUÇÃO DAS AÇÕES ESCOLHIDAS
# -----------------------------------------------------------------------------
PLAN_ROBOCOPY = "robocopy"
PLAN_MAKE_DIR = "make_dir"
PLAN_DELETE_FILE = "delete_file"
PLAN_DELETE_DIR = "delete_dir"

# Limite de nomes por chamada, para não estourar o tamanho máximo da linha de comando.
MAX_FILES_PER_CALL = 30


@dataclass
class PlanStep:
    """Uma operação concreta do plano (uma chamada do RoboCopy ou uma exclusão)."""
    kind: str
    label: str
    source_dir: str = ""
    dest_dir: str = ""
    files: List[str] = field(default_factory=list)
    path: str = ""
    recursive: bool = False
    items: List[SyncDifference] = field(default_factory=list)


def build_execution_plan(
    differences: List[SyncDifference],
    chunk_size: int = MAX_FILES_PER_CALL,
) -> List[PlanStep]:
    """
    Converte as divergências (com a ação escolhida pelo usuário) em passos executáveis.

    - Arquivos com a mesma ação e a mesma pasta são agrupados em uma única chamada.
    - Pastas que existem só na origem viram criação de pasta (os arquivos dentro delas
      são copiados individualmente, respeitando o que o usuário marcou).
    - Pastas que existem só no destino são tratadas como árvore inteira, porque o
      RoboCopy não lista o conteúdo delas.
    - As exclusões são sempre os últimos passos, depois de todas as cópias.
    """
    selected = [d for d in differences if d.action != ACTION_SKIP]

    tree_copies = [
        d for d in selected
        if d.is_dir and d.side == SIDE_DESTINATION and d.action == ACTION_COPY_TO_SOURCE
    ]
    delete_dirs = [d for d in selected if d.is_dir and d.action == ACTION_DELETE_DEST]

    def _inside_any(diff: SyncDifference, containers: List[SyncDifference]) -> bool:
        for container in containers:
            if container is diff:
                continue
            if relative_to(diff.relative_path, container.relative_path) is not None:
                return True
        return False

    copy_to_dest_files: Dict[str, List[SyncDifference]] = {}
    copy_to_source_files: Dict[str, List[SyncDifference]] = {}
    make_dirs: List[SyncDifference] = []
    delete_files: List[SyncDifference] = []

    for diff in selected:
        if diff.is_dir:
            if diff.action == ACTION_COPY_TO_DEST:
                make_dirs.append(diff)
            continue

        # Itens cobertos por uma pasta inteira já copiada/apagada não são repetidos.
        if diff.action == ACTION_COPY_TO_SOURCE and _inside_any(diff, tree_copies):
            continue
        if diff.action == ACTION_DELETE_DEST and _inside_any(diff, delete_dirs):
            continue

        if diff.action == ACTION_COPY_TO_DEST:
            copy_to_dest_files.setdefault(parent_of(diff.relative_path), []).append(diff)
        elif diff.action == ACTION_COPY_TO_SOURCE:
            copy_to_source_files.setdefault(parent_of(diff.relative_path), []).append(diff)
        elif diff.action == ACTION_DELETE_DEST:
            delete_files.append(diff)

    plan: List[PlanStep] = []

    # 1. Criação das pastas que faltam no destino.
    for diff in make_dirs:
        plan.append(PlanStep(
            kind=PLAN_MAKE_DIR,
            label=f"Criar pasta no destino: {diff.relative_path}",
            path=diff.dest_path,
            items=[diff],
        ))

    # 2. Cópias Origem -> Destino, agrupadas por pasta.
    for relative_dir in sorted(copy_to_dest_files):
        items = copy_to_dest_files[relative_dir]
        for chunk in _chunked(items, chunk_size):
            plan.append(PlanStep(
                kind=PLAN_ROBOCOPY,
                label=f"Copiar {len(chunk)} arquivo(s) para o destino em '{relative_dir or '.'}'",
                source_dir=_container_dir(items[0], SIDE_SOURCE),
                dest_dir=_container_dir(items[0], SIDE_DESTINATION),
                files=[name_of(item.relative_path) for item in chunk],
                items=list(chunk),
            ))

    # 3. Cópias Destino -> Origem, agrupadas por pasta.
    for relative_dir in sorted(copy_to_source_files):
        items = copy_to_source_files[relative_dir]
        for chunk in _chunked(items, chunk_size):
            plan.append(PlanStep(
                kind=PLAN_ROBOCOPY,
                label=f"Copiar {len(chunk)} arquivo(s) para a origem em '{relative_dir or '.'}'",
                source_dir=_container_dir(items[0], SIDE_DESTINATION),
                dest_dir=_container_dir(items[0], SIDE_SOURCE),
                files=[name_of(item.relative_path) for item in chunk],
                items=list(chunk),
            ))

    # 4. Pastas inteiras que existem apenas no destino e voltam para a origem.
    for diff in tree_copies:
        plan.append(PlanStep(
            kind=PLAN_ROBOCOPY,
            label=f"Copiar a pasta '{diff.relative_path}' do destino para a origem",
            source_dir=diff.dest_path,
            dest_dir=diff.source_path,
            recursive=True,
            items=[diff],
        ))

    # 5. Exclusões por último, já com tudo o que era para ser preservado copiado.
    for diff in delete_files:
        plan.append(PlanStep(
            kind=PLAN_DELETE_FILE,
            label=f"Excluir do destino: {diff.relative_path}",
            path=diff.dest_path,
            items=[diff],
        ))

    for diff in delete_dirs:
        if _inside_any(diff, delete_dirs):
            continue
        plan.append(PlanStep(
            kind=PLAN_DELETE_DIR,
            label=f"Excluir a pasta do destino: {diff.relative_path}",
            path=diff.dest_path,
            items=[diff],
        ))

    return plan


def _chunked(items: List[SyncDifference], size: int):
    size = max(1, size)
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _container_dir(item: SyncDifference, side: str) -> str:
    """
    Pasta que contém o item, do lado indicado (origem ou destino).
    O separador original do caminho é preservado: só o último trecho é removido.
    """
    base = item.source_path if side == SIDE_SOURCE else item.dest_path
    name = name_of(item.relative_path)
    cleaned = base.rstrip("\\/")
    if not name or len(cleaned) <= len(name):
        return cleaned

    tail = cleaned[-(len(name) + 1):]
    if _normalize_for_compare(tail) == _normalize_for_compare("\\" + name):
        trimmed = cleaned[: -(len(name) + 1)]
        return trimmed if trimmed else cleaned
    return cleaned


def build_step_command(step: PlanStep, config: Optional[RobocopyConfig] = None) -> List[str]:
    """Linha de comando do RoboCopy correspondente a um passo de cópia do plano."""
    if step.kind != PLAN_ROBOCOPY:
        return []

    config = config or RobocopyConfig()
    args = ["robocopy", step.source_dir, step.dest_dir]

    if step.recursive:
        args.append("/E")
    else:
        args.extend(step.files)

    if config.copyall:
        args.append("/COPYALL")
    else:
        copy_flags = ""
        if config.copy_data:
            copy_flags += "D"
        if config.copy_attrs:
            copy_flags += "A"
        if config.copy_timestamps:
            copy_flags += "T"
        if config.copy_security:
            copy_flags += "S"
        if config.copy_owner:
            copy_flags += "O"
        args.append(f"/COPY:{copy_flags or 'D'}")
        if config.copy_dir_attrs:
            args.append("/DCOPY:DAT")

    if config.restartable_backup:
        args.append("/ZB")
    elif config.backup_mode:
        args.append("/B")
    elif config.restartable:
        args.append("/Z")

    if config.exclude_junctions:
        args.append("/XJ")

    if step.recursive and config.multi_threaded > 1:
        args.append(f"/MT:{min(max(config.multi_threaded, 1), 128)}")

    args.append(f"/R:{config.retries}")
    args.append(f"/W:{config.wait_time}")
    args.extend(["/NP", "/NJH", "/NJS", "/FP"])

    if config.dry_run:
        args.append("/L")

    if config.extra_args.strip():
        args.extend(split_windows_args(config.extra_args.strip()))

    return args


class SyncPlanExecutor:
    """Executa o plano de ações escolhido pelo usuário na Central de Sincronização."""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self._cancel_requested = False
        self._lock = threading.Lock()
        self._engine = RobocopyEngine()

    def execute(
        self,
        plan: List[PlanStep],
        config: Optional[RobocopyConfig] = None,
        on_line: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Roda o plano passo a passo e devolve o resultado consolidado."""
        emit = on_line or (lambda _line: None)
        config = config or RobocopyConfig()

        with self._lock:
            if self.is_running:
                emit("\n[AVISO] Já existe uma execução em andamento.\n")
                return {"exit_code": 16, "steps": [], "copied": 0, "deleted": 0, "failed": 0}
            self.is_running = True
            self._cancel_requested = False

        results: List[Dict[str, Any]] = []
        copied = deleted = failed = 0
        codes: List[int] = []

        try:
            total = len(plan)
            for index, step in enumerate(plan, start=1):
                if self._cancel_requested:
                    emit("\n[OPERAÇÃO CANCELADA PELO USUÁRIO]\n")
                    break

                emit(f"\n>>> [{index}/{total}] {step.label}\n")

                if step.kind == PLAN_ROBOCOPY:
                    code = self._run_robocopy_step(step, config, emit)
                    codes.append(code)
                    if code < 8:
                        copied += len(step.items)
                    else:
                        failed += len(step.items)
                    results.append({"label": step.label, "code": code})
                elif step.kind == PLAN_MAKE_DIR:
                    ok = self._make_dir(step.path, emit, config.dry_run)
                    copied += 1 if ok else 0
                    failed += 0 if ok else 1
                    codes.append(0 if ok else 8)
                    results.append({"label": step.label, "code": 0 if ok else 8})
                elif step.kind in (PLAN_DELETE_FILE, PLAN_DELETE_DIR):
                    ok = self._delete(step.path, step.kind == PLAN_DELETE_DIR, emit, config.dry_run)
                    deleted += 1 if ok else 0
                    failed += 0 if ok else 1
                    codes.append(0 if ok else 8)
                    results.append({"label": step.label, "code": 0 if ok else 8})
        finally:
            with self._lock:
                self.is_running = False
                self.process = None

        exit_code = 16 if self._cancel_requested else consolidate_exit_codes(codes)
        title, desc, _category = interpret_exit_code(exit_code)

        emit("\n" + "-" * 60 + "\n")
        emit(f"Ações aplicadas: {copied} cópia(s), {deleted} exclusão(ões), {failed} falha(s).\n")
        emit(f"Resultado consolidado: [{exit_code}] {title} - {desc}\n")
        emit("-" * 60 + "\n")

        return {
            "exit_code": exit_code,
            "title": title,
            "desc": desc,
            "steps": results,
            "copied": copied,
            "deleted": deleted,
            "failed": failed,
            "cancelled": self._cancel_requested,
        }

    def execute_async(
        self,
        plan: List[PlanStep],
        config: RobocopyConfig,
        on_line: Callable[[str], None],
        on_finish: Callable[[Dict[str, Any]], None],
    ):
        """Versão em thread, para manter a interface responsiva."""
        def _worker():
            result = self.execute(plan, config, on_line)
            on_finish(result)

        threading.Thread(target=_worker, daemon=True).start()

    def stop(self) -> bool:
        """Interrompe o plano em execução."""
        with self._lock:
            self._cancel_requested = True
            if not self.process:
                return self.is_running
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                else:
                    self.process.terminate()
                return True
            except Exception:
                return False

    def _run_robocopy_step(self, step: PlanStep, config: RobocopyConfig, emit: Callable[[str], None]) -> int:
        args = build_step_command(step, config)
        try:
            startupinfo = None
            creationflags = 0
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW

            self.process = subprocess.Popen(
                args,
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
                    emit(self._engine._decode_line(raw_line))

            code = self.process.poll() or 0
        except FileNotFoundError:
            emit("[ERRO]: O comando robocopy não foi encontrado neste sistema.\n")
            return 16
        except Exception as ex:
            emit(f"[ERRO]: {ex}\n")
            return 16
        finally:
            if self.process and self.process.stdout:
                try:
                    self.process.stdout.close()
                except Exception:
                    pass

        return code

    def _make_dir(self, path: str, emit: Callable[[str], None], dry_run: bool = False) -> bool:
        if dry_run:
            emit(f"[SIMULAÇÃO] Pasta que seria criada: {path}\n")
            return True
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except Exception as ex:
            emit(f"[ERRO] Não foi possível criar a pasta '{path}': {ex}\n")
            return False

    def _delete(self, path: str, is_dir: bool, emit: Callable[[str], None], dry_run: bool = False) -> bool:
        if dry_run:
            emit(f"[SIMULAÇÃO] Item que seria excluído: {path}\n")
            return True

        if not os.path.exists(path):
            emit(f"[AVISO] Item já não existe mais: {path}\n")
            return True

        try:
            if is_dir:
                _remove_tree(path)
            else:
                _remove_file(path)
            return True
        except Exception as ex:
            emit(f"[ERRO] Não foi possível excluir '{path}': {ex}\n")
            return False


def _clear_read_only(path: str):
    """Remove o atributo somente-leitura, que faz a exclusão falhar no Windows."""
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass


def _remove_file(path: str):
    """Exclui um arquivo, tratando o caso de arquivo somente-leitura."""
    try:
        os.remove(path)
    except PermissionError:
        _clear_read_only(path)
        os.remove(path)


def _remove_tree(path: str):
    """Exclui uma pasta inteira, tratando itens somente-leitura."""
    def _on_error(func, failed_path, _error):
        _clear_read_only(failed_path)
        func(failed_path)

    # A partir do Python 3.12 o parâmetro passou a se chamar "onexc".
    try:
        shutil.rmtree(path, onexc=lambda func, p, exc: _on_error(func, p, exc))
    except TypeError:
        shutil.rmtree(path, onerror=_on_error)
