"""Static checks for the generated sandbox bundle."""

from __future__ import annotations

import ast
import sys

from gauntlet.orchestrator.code_generator import ALLOWED_GENERATED_FILES


_ALLOWED_THIRD_PARTY_PREFIXES = {"pandas", "matplotlib"}
_BANNED_IMPORT_PREFIXES = {
    "requests",
    "urllib",
    "http",
    "socket",
    "aiohttp",
    "websocket",
    "websockets",
    "ftplib",
    "paramiko",
}
_BANNED_CALLS = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "os.system",
    "os.popen",
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "subprocess.getoutput",
    "subprocess.getstatusoutput",
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.patch",
    "requests.delete",
    "urllib.request.urlopen",
    "socket.socket",
}
_BANNED_WRITE_CALL_SUFFIXES = {
    "open",
    "to_csv",
    "to_json",
    "to_excel",
    "to_parquet",
    "write_text",
    "write_bytes",
    "mkdir",
    "unlink",
    "rmdir",
}
_REQUIRED_FUNCTIONS = {
    "data_loader.py": "load_data",
    "preprocessing.py": "preprocess",
    "analysis.py": "run_analysis",
    "figures.py": "create_figures",
}
_GENERATED_MODULE_NAMES = {
    file_name.removesuffix(".py")
    for file_name in ALLOWED_GENERATED_FILES
}
_ANALYSIS_BANNED_CALLS = {
    "load_data",
    "pd.read_csv",
    "pd.read_excel",
    "pd.read_json",
    "pd.read_parquet",
    "Path",
}
_ANALYSIS_PATH_MARKERS = (".csv", ".tsv", ".xlsx", ".json", ".parquet", "/", "\\")


def validate_generated_bundle(bundle: dict[str, str]) -> None:
    """Raise when the generated bundle violates the file policy."""
    actual_keys = set(bundle.keys())
    expected_keys = set(ALLOWED_GENERATED_FILES)

    if actual_keys != expected_keys:
        raise ValueError("Generated bundle does not match the allowed file set.")

    violations = collect_generated_bundle_violations(bundle)

    if violations:
        raise ValueError(_format_violations("Generated bundle failed file policy checks", violations))


def validate_runtime_contract(bundle: dict[str, str]) -> None:
    """Raise when the generated bundle violates the runtime import contract."""
    violations = collect_runtime_contract_violations(bundle)
    if violations:
        raise ValueError(_format_violations("Generated bundle failed runtime contract checks", violations))


def collect_generated_bundle_violations(bundle: dict[str, str]) -> list[dict[str, str]]:
    """Return structured policy violations for the generated bundle."""
    actual_keys = set(bundle.keys())
    expected_keys = set(ALLOWED_GENERATED_FILES)

    if actual_keys != expected_keys:
        return [_build_violation("bundle", "file_set", "Generated bundle does not match the allowed file set.")]

    violations: list[dict[str, str]] = []
    for file_name, source in bundle.items():
        try:
            tree = ast.parse(source, filename=file_name)
        except SyntaxError as exc:
            violations.append(_build_violation(file_name, "syntax_error", f"syntax error: {exc}"))
            continue

        checker = _PolicyChecker(file_name=file_name)
        checker.visit(tree)
        violations.extend(checker.violations)

    return violations


def collect_runtime_contract_violations(bundle: dict[str, str]) -> list[dict[str, str]]:
    """Return structured runtime contract violations for the generated bundle."""
    actual_keys = set(bundle.keys())
    expected_keys = set(ALLOWED_GENERATED_FILES)

    if actual_keys != expected_keys:
        return [_build_violation("bundle", "file_set", "Generated bundle does not match the allowed file set.")]

    violations: list[dict[str, str]] = []
    for file_name, source in bundle.items():
        try:
            tree = ast.parse(source, filename=file_name)
        except SyntaxError as exc:
            violations.append(_build_violation(file_name, "syntax_error", f"syntax error: {exc}"))
            continue

        function_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        required_function = _REQUIRED_FUNCTIONS[file_name]
        if required_function not in function_names:
            violations.append(
                _build_violation(
                    file_name,
                    "missing_required_function",
                    f"missing required function `{required_function}`",
                )
            )

    return violations


def _validate_one_file(file_name: str, source: str) -> list[str]:
    """Return policy violations for one generated file."""
    try:
        tree = ast.parse(source, filename=file_name)
    except SyntaxError as exc:
        return [f"{file_name}: syntax error: {exc}"]

    checker = _PolicyChecker(file_name=file_name)
    checker.visit(tree)
    return [entry["message"] for entry in checker.violations]


class _PolicyChecker(ast.NodeVisitor):
    """AST-based checks that keep the generated code constrained."""

    def __init__(self, file_name: str) -> None:
        self.file_name = file_name
        self.violations: list[dict[str, str]] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Check direct imports against the allowed module policy."""
        for alias in node.names:
            self._check_import_name(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check `from x import y` statements."""
        module_name = node.module or ""
        self._check_import_name(module_name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Check dangerous execution and write primitives."""
        call_name = _get_full_name(node.func)
        if not call_name:
            self.generic_visit(node)
            return

        if call_name in _BANNED_CALLS:
            self._add_violation("banned_call", f"banned call `{call_name}`")

        call_suffix = call_name.split(".")[-1]
        if call_suffix in _BANNED_WRITE_CALL_SUFFIXES and not self._is_allowed_figure_save(call_name):
            self._add_violation("write_like_call", f"disallowed write-like call `{call_name}`")

        if self.file_name == "analysis.py" and call_name in _ANALYSIS_BANNED_CALLS:
            self._add_violation(
                "analysis_file_loading",
                f"analysis.py must not load files or call `{call_name}`",
            )

        if self.file_name == "figures.py" and call_name == "plt.show":
            self._add_violation(
                "figures_show_call",
                "figures.py must save figures and return paths instead of calling `plt.show`",
            )

        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        """Block standalone script entrypoints inside generated modules."""
        if _is_main_guard(node.test):
            self._add_violation(
                "main_block",
                "generated files must not contain `if __name__ == \"__main__\"` blocks",
            )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        """Detect file-path style literals inside the analysis module."""
        if self.file_name == "analysis.py" and isinstance(node.value, str):
            if any(marker in node.value for marker in _ANALYSIS_PATH_MARKERS):
                self._add_violation(
                    "analysis_file_path_reference",
                    "analysis.py must consume the provided data dictionary and not reference file paths",
                )
        self.generic_visit(node)

    def _check_import_name(self, module_name: str) -> None:
        """Block imports that fall outside the approved dependency set."""
        if not module_name:
            return

        root_name = module_name.split(".")[0]

        if root_name in _GENERATED_MODULE_NAMES:
            self._add_violation(
                "sibling_module_import",
                f"sibling generated module import `{module_name}` is not allowed",
            )
            return

        if root_name in _BANNED_IMPORT_PREFIXES:
            self._add_violation("banned_import", f"banned import `{module_name}`")
            return

        if root_name in _ALLOWED_THIRD_PARTY_PREFIXES:
            return

        if root_name in sys.stdlib_module_names:
            return

        self._add_violation("unsupported_dependency", f"unsupported dependency `{module_name}`")

    def _is_allowed_figure_save(self, call_name: str) -> bool:
        """Allow limited output-directory operations inside `figures.py`."""
        if self.file_name != "figures.py":
            return False
        return call_name.endswith("savefig") or call_name.endswith("mkdir")

    def _add_violation(self, rule: str, message: str) -> None:
        """Store a structured violation payload."""
        self.violations.append(_build_violation(self.file_name, rule, message))


def _get_full_name(node: ast.AST) -> str | None:
    """Resolve a dotted function name from a call target."""
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        parent_name = _get_full_name(node.value)
        if not parent_name:
            return None
        return f"{parent_name}.{node.attr}"

    return None


def _build_violation(file_name: str, rule: str, message: str) -> dict[str, str]:
    """Return one structured violation entry."""
    return {
        "file": file_name,
        "rule": rule,
        "message": f"{file_name}: {message}",
    }


def _format_violations(prefix: str, violations: list[dict[str, str]]) -> str:
    """Render structured violations into the existing error string shape."""
    rendered = "; ".join(entry["message"] for entry in violations)
    return f"{prefix}: {rendered}"


def _is_main_guard(node: ast.AST) -> bool:
    """Detect `if __name__ == "__main__"` script entrypoints."""
    if not isinstance(node, ast.Compare):
        return False

    if not isinstance(node.left, ast.Name) or node.left.id != "__name__":
        return False

    if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
        return False

    if len(node.comparators) != 1:
        return False

    comparator = node.comparators[0]
    return isinstance(comparator, ast.Constant) and comparator.value == "__main__"
