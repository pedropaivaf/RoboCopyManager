"""
Testes da Central de Sincronização: leitura colorida do log, painel de ocorrências,
análise de divergências, plano de ações e consolidação de exit codes multi-etapas.
"""

import os
import shutil
import tempfile
import unittest

from robocopy_engine import (
    DESTRUCTIVE_FLAGS,
    OCCURRENCE_CATEGORIES,
    RobocopyConfig,
    analyze_extra_args,
    classify_log_line,
    consolidate_exit_codes,
    decompose_exit_code,
    explain_exit_code,
    extract_occurrences,
    format_size,
    parse_log_entry,
    parse_size,
)
from sync_analyzer import (
    ACTION_COPY_TO_DEST,
    ACTION_COPY_TO_SOURCE,
    ACTION_DELETE_DEST,
    ACTION_SKIP,
    MODE_MIRROR,
    MODE_TWO_WAY,
    MODE_UPDATE,
    PLAN_DELETE_DIR,
    PLAN_DELETE_FILE,
    PLAN_MAKE_DIR,
    PLAN_ROBOCOPY,
    SIDE_DESTINATION,
    SIDE_SOURCE,
    SyncPlanExecutor,
    build_analysis_args,
    build_execution_plan,
    build_step_command,
    join_path,
    name_of,
    parent_of,
    parse_analysis_output,
    relative_to,
    suggest_action,
)

SOURCE = r"C:\Origem"
DESTINATION = r"D:\Destino"

# Saída típica do RoboCopy em português, como aparece na análise (/L /MIR /FP /BYTES).
SAMPLE_PT = [
    "\t  Novo Arquivo  \t\t      1024\tC:\\Origem\\relatorio.docx",
    "\t  Mais Recente  \t\t     20480\tC:\\Origem\\sub\\planilha.xlsx",
    "\t  Mais Antigo   \t\t      4096\tC:\\Origem\\notas.txt",
    "\t*Arquivo EXTRA \t\t       512\tD:\\Destino\\antigo.bak",
    "\t*Arquivo EXTRA \t\t       256\tD:\\Destino\\lixo\\dentro.tmp",
    "\t*Pasta EXTRA   \t\t          \tD:\\Destino\\lixo\\",
    "\t*INCOMPATÍVEL  \t\t          \tD:\\Destino\\config",
    "\t    Novo Dir          2\tC:\\Origem\\nova\\",
    "\t  Novo Arquivo  \t\t       100\tC:\\Origem\\nova\\dentro.txt",
    "2025/09/03 10:12:35 ERRO 5 (0x00000005) Copiando Arquivo C:\\Origem\\protegido.dat",
    "Acesso negado.",
]

# A mesma situação em um Windows em inglês.
SAMPLE_EN = [
    "\t    New File  \t\t      1024\tC:\\Origem\\relatorio.docx",
    "\t      Newer  \t\t     20480\tC:\\Origem\\sub\\planilha.xlsx",
    "\t      Older  \t\t      4096\tC:\\Origem\\notas.txt",
    "\t*EXTRA File \t\t       512\tD:\\Destino\\antigo.bak",
    "\t*EXTRA Dir  \t\t          \tD:\\Destino\\lixo\\",
    "\t   *Mismatch\t\t          \tD:\\Destino\\config",
    "2025/09/03 10:12:35 ERROR 5 (0x00000005) Copying File C:\\Origem\\protegido.dat",
    "Access is denied.",
]


class TestLogClassification(unittest.TestCase):
    """Colorização do console e identificação de cada tipo de linha."""

    def test_classifies_portuguese_output(self):
        self.assertEqual(classify_log_line(SAMPLE_PT[0]), "new_file")
        self.assertEqual(classify_log_line(SAMPLE_PT[1]), "newer")
        self.assertEqual(classify_log_line(SAMPLE_PT[2]), "older")
        self.assertEqual(classify_log_line(SAMPLE_PT[3]), "extra_file")
        self.assertEqual(classify_log_line(SAMPLE_PT[5]), "extra_dir")
        self.assertEqual(classify_log_line(SAMPLE_PT[6]), "mismatch")
        self.assertEqual(classify_log_line(SAMPLE_PT[7]), "new_dir")
        self.assertEqual(classify_log_line(SAMPLE_PT[9]), "error")

    def test_classifies_english_output(self):
        self.assertEqual(classify_log_line(SAMPLE_EN[0]), "new_file")
        self.assertEqual(classify_log_line(SAMPLE_EN[1]), "newer")
        self.assertEqual(classify_log_line(SAMPLE_EN[2]), "older")
        self.assertEqual(classify_log_line(SAMPLE_EN[3]), "extra_file")
        self.assertEqual(classify_log_line(SAMPLE_EN[4]), "extra_dir")
        self.assertEqual(classify_log_line(SAMPLE_EN[5]), "mismatch")
        self.assertEqual(classify_log_line(SAMPLE_EN[6]), "error")

    def test_summary_block_is_not_confused_with_failures(self):
        """O cabeçalho do resumo contém as palavras FALHA e Incompatível, mas não é ocorrência."""
        header = "                Total   Copiado   Ignorado  Incompatível     FALHA    Extras"
        self.assertEqual(classify_log_line(header), "summary")
        self.assertEqual(classify_log_line("Diretórios:          6         1         5         0         0         1"), "summary")
        self.assertEqual(classify_log_line("   Velocidade:            1234567 Bytes/s."), "summary")
        self.assertNotIn(classify_log_line(header), OCCURRENCE_CATEGORIES)

    def test_engine_lines_are_classified_as_banner_or_step(self):
        self.assertEqual(classify_log_line(">>> [ETAPA 1 DE 2]: Copiando..."), "step")
        self.assertEqual(classify_log_line("=" * 60), "banner")
        self.assertEqual(classify_log_line("Conclusão: [2] Aviso - Existem arquivos extras."), "banner")
        self.assertEqual(classify_log_line("[ERRO NA EXECUÇÃO]: caminho inválido"), "error")

    def test_parses_size_and_path(self):
        entry = parse_log_entry(SAMPLE_PT[0])
        self.assertEqual(entry.category, "new_file")
        self.assertEqual(entry.size, 1024)
        self.assertEqual(entry.path, r"C:\Origem\relatorio.docx")

        extra = parse_log_entry(SAMPLE_PT[3])
        self.assertEqual(extra.size, 512)
        self.assertEqual(extra.path, r"D:\Destino\antigo.bak")

    def test_parse_size_handles_suffixes_and_separators(self):
        self.assertEqual(parse_size("1024"), 1024)
        self.assertEqual(parse_size("1.048.576"), 1048576)
        self.assertEqual(parse_size("1 k"), 1024)
        self.assertEqual(parse_size("1,5 m"), int(1.5 * 1024 ** 2))
        self.assertIsNone(parse_size(""))

    def test_format_size_is_readable(self):
        self.assertEqual(format_size(None), "-")
        self.assertEqual(format_size(512), "512 B")
        self.assertIn("KB", format_size(2048))

    def test_extract_occurrences_only_keeps_what_matters(self):
        occurrences = extract_occurrences(SAMPLE_PT)
        categories = [o.category for o in occurrences]
        self.assertEqual(categories, ["extra_file", "extra_file", "extra_dir", "mismatch", "error"])
        # Arquivos novos e atualizados não são "ocorrências": não exigem decisão do usuário.
        self.assertNotIn("new_file", categories)

    def test_error_detail_is_merged_into_previous_error(self):
        """'Acesso negado.' complementa o erro anterior em vez de virar uma linha solta."""
        occurrences = extract_occurrences(SAMPLE_PT)
        error = occurrences[-1]
        self.assertEqual(error.path, r"C:\Origem\protegido.dat")
        self.assertIn("Acesso negado", error.message)


class TestExitCodes(unittest.TestCase):
    """Explicação e consolidação dos códigos de saída."""

    def test_decompose_exit_code(self):
        self.assertEqual(decompose_exit_code(0), [])
        self.assertEqual(decompose_exit_code(3), [1, 2])
        self.assertEqual(decompose_exit_code(7), [1, 2, 4])
        self.assertEqual(decompose_exit_code(24), [8, 16])

    def test_explanation_mentions_meaning_and_solution(self):
        text = explain_exit_code(2)
        self.assertIn("Arquivos extras no destino", text)
        self.assertIn("Central de Sincronização", text)
        self.assertIn("8 ou mais indicam falha real", text)

    def test_explanation_lists_each_step(self):
        steps = [
            {"label": "Etapa 1 de 2 (Origem -> Destino)", "code": 2, "title": "Aviso"},
            {"label": "Etapa 2 de 2 (Destino -> Origem)", "code": 1, "title": "Sucesso"},
        ]
        text = explain_exit_code(1, steps)
        self.assertIn("Etapa 1 de 2", text)
        self.assertIn("Etapa 2 de 2", text)
        self.assertIn("resultado consolidado", text)

    def test_consolidation_keeps_all_flags_in_single_direction(self):
        self.assertEqual(consolidate_exit_codes([3]), 3)
        self.assertEqual(consolidate_exit_codes([1, 2]), 3)
        self.assertEqual(consolidate_exit_codes([1, 8]), 9)

    def test_two_way_resolves_extra_flag(self):
        """Etapa 2 traz de volta o que a Etapa 1 apontou como extra: o resultado é sucesso."""
        self.assertEqual(consolidate_exit_codes([2, 1], two_way=True), 1)
        self.assertEqual(consolidate_exit_codes([2, 0], two_way=True), 0)
        self.assertEqual(consolidate_exit_codes([3, 3], two_way=True), 1)

    def test_two_way_preserves_real_failures(self):
        """Falhas e incompatibilidades continuam sendo reportadas nas duas direções."""
        # Houve falha de cópia (8): nada é descontado.
        self.assertEqual(consolidate_exit_codes([2, 8], two_way=True), 10)
        # 6 = extras (2) + incompatíveis (4). Só o sinalizador de extras é resolvido pela
        # etapa inversa; a incompatibilidade continua exigindo decisão manual.
        self.assertEqual(consolidate_exit_codes([6, 1], two_way=True), 5)
        self.assertEqual(consolidate_exit_codes([16, 1], two_way=True), 17)

    def test_consolidation_of_single_step_is_unchanged(self):
        self.assertEqual(consolidate_exit_codes([2], two_way=True), 2)
        self.assertEqual(consolidate_exit_codes([]), 0)


class TestExtraArgs(unittest.TestCase):
    """Campo de flags personalizadas."""

    def test_extra_args_are_appended_to_the_command(self):
        engine_config = RobocopyConfig(source=SOURCE, destination=DESTINATION, extra_args="/FFT /Z")
        from robocopy_engine import RobocopyEngine
        command = RobocopyEngine().build_command_string(engine_config)
        self.assertIn("/FFT", command)
        self.assertIn("/Z", command)

    def test_destructive_flags_are_detected(self):
        diagnosis = analyze_extra_args("/PURGE /FFT")
        self.assertTrue(diagnosis["is_destructive"])
        self.assertIn("/PURGE", diagnosis["destructive"])
        self.assertIn("APAGA", diagnosis["warning"])

    def test_flags_managed_by_the_interface_are_flagged(self):
        diagnosis = analyze_extra_args("/MT:32")
        self.assertFalse(diagnosis["is_destructive"])
        self.assertIn("/MT", diagnosis["duplicated"])

    def test_non_flag_tokens_are_reported(self):
        diagnosis = analyze_extra_args("lixo")
        self.assertIn("lixo", diagnosis["suspicious"])

    def test_safe_flags_produce_no_warning(self):
        diagnosis = analyze_extra_args("/FFT /Z /XX")
        self.assertEqual(diagnosis["warning"], "")
        self.assertEqual(len(diagnosis["tokens"]), 3)

    def test_every_destructive_flag_has_an_explanation(self):
        for flag, description in DESTRUCTIVE_FLAGS.items():
            self.assertTrue(flag.startswith("/"))
            self.assertTrue(description)


class TestPathHelpers(unittest.TestCase):
    """Utilitários de caminho usados pela análise (funcionam com caminhos do Windows)."""

    def test_relative_to(self):
        self.assertEqual(relative_to(r"C:\Origem\sub\a.txt", r"C:\Origem"), r"sub\a.txt")
        self.assertEqual(relative_to(r"c:\origem\a.txt", r"C:\Origem"), "a.txt")
        self.assertEqual(relative_to(r"C:\Origem", r"C:\Origem"), "")
        self.assertIsNone(relative_to(r"D:\Outro\a.txt", r"C:\Origem"))

    def test_join_parent_and_name(self):
        self.assertEqual(join_path(r"C:\Origem", r"sub\a.txt"), r"C:\Origem\sub\a.txt")
        self.assertEqual(parent_of(r"sub\a.txt"), "sub")
        self.assertEqual(parent_of("a.txt"), "")
        self.assertEqual(name_of(r"sub\a.txt"), "a.txt")


class TestAnalysisParsing(unittest.TestCase):
    """Leitura da análise: quais arquivos, em quais caminhos e de que lado."""

    def test_analysis_command_never_writes(self):
        args = build_analysis_args(RobocopyConfig(source=SOURCE, destination=DESTINATION))
        self.assertIn("/L", args, "A análise precisa rodar em modo somente-listagem.")
        self.assertIn("/MIR", args, "/MIR com /L é o que faz o RoboCopy relatar os itens extras.")
        self.assertIn("/FP", args)
        self.assertIn("/BYTES", args)
        self.assertEqual(args[1], SOURCE)
        self.assertEqual(args[2], DESTINATION)

    def test_analysis_command_respects_filters(self):
        config = RobocopyConfig(
            source=SOURCE, destination=DESTINATION,
            exclude_files="*.tmp *.bak", exclude_dirs=".git", max_size="52428800",
        )
        args = build_analysis_args(config)
        self.assertIn("/XF", args)
        self.assertIn("*.tmp", args)
        self.assertIn("/XD", args)
        self.assertIn("/MAX:52428800", args)

    def test_each_difference_has_path_side_and_action(self):
        analysis = parse_analysis_output(SAMPLE_PT, SOURCE, DESTINATION, MODE_TWO_WAY)
        by_path = {d.relative_path: d for d in analysis.differences}

        novo = by_path["relatorio.docx"]
        self.assertEqual(novo.side, SIDE_SOURCE)
        self.assertEqual(novo.source_path, r"C:\Origem\relatorio.docx")
        self.assertEqual(novo.dest_path, r"D:\Destino\relatorio.docx")
        self.assertEqual(novo.size, 1024)
        self.assertEqual(novo.action, ACTION_COPY_TO_DEST)

        extra = by_path["antigo.bak"]
        self.assertEqual(extra.side, SIDE_DESTINATION)
        self.assertEqual(extra.dest_path, r"D:\Destino\antigo.bak")
        self.assertTrue(extra.explanation)

        aninhado = by_path[r"sub\planilha.xlsx"]
        self.assertEqual(aninhado.source_path, r"C:\Origem\sub\planilha.xlsx")

    def test_english_output_produces_the_same_differences(self):
        analysis = parse_analysis_output(SAMPLE_EN, SOURCE, DESTINATION, MODE_TWO_WAY)
        paths = sorted(d.relative_path for d in analysis.differences)
        self.assertEqual(paths, ["antigo.bak", "config", "lixo", "notas.txt", "relatorio.docx", r"sub\planilha.xlsx"])

    def test_directories_do_not_show_item_count_as_size(self):
        analysis = parse_analysis_output(SAMPLE_PT, SOURCE, DESTINATION, MODE_TWO_WAY)
        nova = next(d for d in analysis.differences if d.relative_path == "nova")
        self.assertTrue(nova.is_dir)
        self.assertIsNone(nova.size)
        self.assertEqual(nova.size_text, "-")

    def test_errors_are_separated_from_differences(self):
        analysis = parse_analysis_output(SAMPLE_PT, SOURCE, DESTINATION, MODE_TWO_WAY)
        self.assertEqual(len(analysis.errors), 1)
        self.assertEqual(analysis.errors[0].path, r"C:\Origem\protegido.dat")
        self.assertIn("Acesso negado", analysis.errors[0].message)
        self.assertNotIn("error", [d.category for d in analysis.differences])

    def test_summary_text_reports_every_category(self):
        analysis = parse_analysis_output(SAMPLE_PT, SOURCE, DESTINATION, MODE_TWO_WAY)
        summary = analysis.summary_text()
        self.assertIn("divergência", summary)
        self.assertIn("Arquivo EXTRA", summary)
        counts = analysis.counts()
        self.assertEqual(counts["extra_file"], 2)
        self.assertEqual(counts["source_only"], 5)
        self.assertEqual(counts["destination_only"], 4)

    def test_identical_folders_report_no_difference(self):
        analysis = parse_analysis_output([], SOURCE, DESTINATION, MODE_TWO_WAY)
        self.assertEqual(analysis.differences, [])
        self.assertIn("idênticos", analysis.summary_text())

    def test_output_without_full_paths_uses_the_directory_header(self):
        """Quando o RoboCopy imprime só o nome do arquivo, a pasta vem do cabeçalho."""
        lines = [
            "\t                   6\tC:\\Origem\\sub\\",
            "\t  Novo Arquivo  \t\t      1024\tarquivo.txt",
        ]
        analysis = parse_analysis_output(lines, SOURCE, DESTINATION, MODE_TWO_WAY)
        self.assertEqual(analysis.differences[0].relative_path, r"sub\arquivo.txt")


class TestSuggestedActions(unittest.TestCase):
    """A ação sugerida muda conforme o modo escolhido na Central."""

    def test_mirror_deletes_extras(self):
        self.assertEqual(suggest_action("extra_file", MODE_MIRROR), ACTION_DELETE_DEST)
        self.assertEqual(suggest_action("new_file", MODE_MIRROR), ACTION_COPY_TO_DEST)

    def test_update_never_deletes(self):
        self.assertEqual(suggest_action("extra_file", MODE_UPDATE), ACTION_SKIP)
        self.assertEqual(suggest_action("older", MODE_UPDATE), ACTION_SKIP)

    def test_two_way_brings_both_sides_together(self):
        self.assertEqual(suggest_action("extra_file", MODE_TWO_WAY), ACTION_COPY_TO_SOURCE)
        self.assertEqual(suggest_action("older", MODE_TWO_WAY), ACTION_COPY_TO_SOURCE)
        self.assertEqual(suggest_action("newer", MODE_TWO_WAY), ACTION_COPY_TO_DEST)

    def test_mismatch_always_requires_manual_decision(self):
        for mode in (MODE_MIRROR, MODE_UPDATE, MODE_TWO_WAY):
            self.assertEqual(suggest_action("mismatch", mode), ACTION_SKIP)

    def test_available_actions_depend_on_the_side(self):
        analysis = parse_analysis_output(SAMPLE_PT, SOURCE, DESTINATION, MODE_TWO_WAY)
        by_path = {d.relative_path: d for d in analysis.differences}

        # Um arquivo que só existe na origem não pode ser "excluído do destino".
        self.assertNotIn(ACTION_DELETE_DEST, by_path["relatorio.docx"].available_actions())
        self.assertIn(ACTION_DELETE_DEST, by_path["antigo.bak"].available_actions())
        self.assertEqual(by_path["config"].available_actions(), [ACTION_SKIP])


class TestExecutionPlan(unittest.TestCase):
    """Conversão das ações escolhidas em operações concretas."""

    def _differences(self, mode=MODE_TWO_WAY):
        return parse_analysis_output(SAMPLE_PT, SOURCE, DESTINATION, mode).differences

    def test_ignored_items_never_enter_the_plan(self):
        differences = self._differences()
        for diff in differences:
            diff.action = ACTION_SKIP
        self.assertEqual(build_execution_plan(differences), [])

    def test_files_in_the_same_folder_share_one_call(self):
        differences = self._differences(MODE_MIRROR)
        plan = build_execution_plan(differences)
        root_copy = [
            s for s in plan
            if s.kind == PLAN_ROBOCOPY and s.source_dir == SOURCE and not s.recursive
        ]
        self.assertEqual(len(root_copy), 1)
        self.assertEqual(sorted(root_copy[0].files), ["notas.txt", "relatorio.docx"])

    def test_deletions_always_come_after_the_copies(self):
        plan = build_execution_plan(self._differences(MODE_MIRROR))
        kinds = [step.kind for step in plan]
        first_deletion = min(
            (index for index, kind in enumerate(kinds) if kind in (PLAN_DELETE_FILE, PLAN_DELETE_DIR)),
            default=len(kinds),
        )
        last_copy = max(
            (index for index, kind in enumerate(kinds) if kind in (PLAN_ROBOCOPY, PLAN_MAKE_DIR)),
            default=-1,
        )
        self.assertLess(last_copy, first_deletion, "Nada pode ser apagado antes de tudo ser copiado.")

    def test_items_inside_a_deleted_folder_are_not_deleted_twice(self):
        plan = build_execution_plan(self._differences(MODE_MIRROR))
        deleted_paths = [s.path for s in plan if s.kind in (PLAN_DELETE_FILE, PLAN_DELETE_DIR)]
        self.assertIn(r"D:\Destino\lixo", deleted_paths)
        self.assertNotIn(r"D:\Destino\lixo\dentro.tmp", deleted_paths)

    def test_extra_folder_returns_to_the_source_as_a_whole_tree(self):
        plan = build_execution_plan(self._differences(MODE_TWO_WAY))
        tree = [s for s in plan if s.recursive]
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0].source_dir, r"D:\Destino\lixo")
        self.assertEqual(tree[0].dest_dir, r"C:\Origem\lixo")
        # O arquivo de dentro já vai junto com a pasta: não é copiado de novo.
        individual = [s for s in plan if not s.recursive and "dentro.tmp" in s.files]
        self.assertEqual(individual, [])

    def test_new_folder_is_created_at_the_destination(self):
        plan = build_execution_plan(self._differences(MODE_TWO_WAY))
        created = [s.path for s in plan if s.kind == PLAN_MAKE_DIR]
        self.assertIn(r"D:\Destino\nova", created)

    def test_long_lists_are_split_into_several_calls(self):
        differences = self._differences(MODE_MIRROR)
        plan = build_execution_plan(differences, chunk_size=1)
        root_calls = [s for s in plan if s.kind == PLAN_ROBOCOPY and s.source_dir == SOURCE and not s.recursive]
        self.assertEqual(len(root_calls), 2)

    def test_step_command_copies_only_the_listed_files(self):
        plan = build_execution_plan(self._differences(MODE_MIRROR))
        step = next(s for s in plan if s.kind == PLAN_ROBOCOPY and not s.recursive)
        command = build_step_command(step, RobocopyConfig(retries=3, wait_time=5))

        self.assertEqual(command[0], "robocopy")
        self.assertIn("/R:3", command)
        self.assertIn("/W:5", command)
        for dangerous in ("/MIR", "/PURGE", "/MOVE", "/E"):
            self.assertNotIn(dangerous, command, f"{dangerous} não pode entrar em uma cópia item a item.")
        for filename in step.files:
            self.assertIn(filename, command)

    def test_step_command_of_a_folder_is_recursive(self):
        plan = build_execution_plan(self._differences(MODE_TWO_WAY))
        step = next(s for s in plan if s.recursive)
        command = build_step_command(step, RobocopyConfig())
        self.assertIn("/E", command)

    def test_paths_keep_their_original_separator(self):
        """A pasta de cada etapa preserva o separador do caminho informado pelo usuário."""
        linhas = [
            "\t  Novo Arquivo  \t\t      1024\t/dados/origem/sub/a.txt",
            "\t  Novo Arquivo  \t\t      2048\t/dados/origem/b.txt",
        ]
        diferencas = parse_analysis_output(linhas, "/dados/origem", "/dados/destino", MODE_MIRROR).differences
        self.assertEqual(len(diferencas), 2)

        plano = build_execution_plan(diferencas)
        pastas = {(step.source_dir, step.dest_dir) for step in plano if step.kind == PLAN_ROBOCOPY}
        self.assertIn(("/dados/origem/sub", "/dados/destino/sub"), pastas)
        self.assertIn(("/dados/origem", "/dados/destino"), pastas)

    def test_windows_paths_produce_windows_folders(self):
        differences = self._differences(MODE_MIRROR)
        plan = build_execution_plan(differences)
        pastas = {(s.source_dir, s.dest_dir) for s in plan if s.kind == PLAN_ROBOCOPY and not s.recursive}
        self.assertIn((r"C:\Origem\sub", r"D:\Destino\sub"), pastas)
        self.assertIn((r"C:\Origem", r"D:\Destino"), pastas)

    def test_step_command_honours_dry_run_and_extra_args(self):
        plan = build_execution_plan(self._differences(MODE_MIRROR))
        step = next(s for s in plan if s.kind == PLAN_ROBOCOPY)
        command = build_step_command(step, RobocopyConfig(dry_run=True, extra_args="/FFT"))
        self.assertIn("/L", command)
        self.assertIn("/FFT", command)


class TestPlanExecutionOnDisk(unittest.TestCase):
    """Execução real das etapas que não dependem do robocopy.exe."""

    def setUp(self):
        self.temp = tempfile.mkdtemp(prefix="rcm_plan_")
        self.executor = SyncPlanExecutor()
        self.output = []

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def _emit(self, line):
        self.output.append(line)

    def test_creates_missing_folder(self):
        target = os.path.join(self.temp, "nova", "subpasta")
        self.assertTrue(self.executor._make_dir(target, self._emit))
        self.assertTrue(os.path.isdir(target))

    def test_deletes_file_and_folder(self):
        file_path = os.path.join(self.temp, "arquivo.txt")
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write("conteudo")
        folder = os.path.join(self.temp, "pasta")
        os.makedirs(os.path.join(folder, "interna"))
        with open(os.path.join(folder, "interna", "b.txt"), "w", encoding="utf-8") as handle:
            handle.write("x")

        self.assertTrue(self.executor._delete(file_path, False, self._emit))
        self.assertFalse(os.path.exists(file_path))

        self.assertTrue(self.executor._delete(folder, True, self._emit))
        self.assertFalse(os.path.exists(folder))

    def test_dry_run_never_touches_the_disk(self):
        file_path = os.path.join(self.temp, "protegido.txt")
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write("conteudo")

        self.assertTrue(self.executor._delete(file_path, False, self._emit, dry_run=True))
        self.assertTrue(os.path.exists(file_path), "Em simulação nada pode ser apagado.")
        self.assertTrue(any("SIMULAÇÃO" in line for line in self.output))

    def test_missing_item_is_not_an_error(self):
        self.assertTrue(self.executor._delete(os.path.join(self.temp, "nao_existe.txt"), False, self._emit))

    def test_execution_reports_consolidated_result(self):
        folder = os.path.join(self.temp, "criar")
        plan = build_execution_plan([])
        self.assertEqual(plan, [])

        from sync_analyzer import PlanStep
        result = self.executor.execute(
            [PlanStep(kind=PLAN_MAKE_DIR, label="Criar pasta", path=folder)],
            RobocopyConfig(),
            on_line=self._emit,
        )
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["copied"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertTrue(os.path.isdir(folder))


if __name__ == "__main__":
    unittest.main()
