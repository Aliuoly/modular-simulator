from collections.abc import Iterable
from pathlib import Path
import re

BANNED_TOKENS = [
    "_input_streams",
    "_output_streams",
    "write_port_conditions",
    "map_port_conditions_to_balance_terms",
    "ControllerBase",
    "SensorBase",
    "CalculationBase",
    "TagData",
    "PortRole",
    "sp_trajectory",
    "sp_point_dict",
    "controller_sp_point_dict",
    "extend_controller_sp_trajectory",
    "tag_store",
    "setpoint_points",
    "from_legacy",
    "split_fractions",
    "duty_setpoint",
    "target_temperature_setpoint",
]

ACTIVE_REPO_SCOPES = ("src", "docs", "examples")
TEXT_SUFFIXES = {".py", ".md", ".mermaid"}

RUNTIME_FALLBACK_BANNED_SNIPPETS = {
    "resolve_process_outlet_condition_stream_fallback": (
        "return candidate.get_outlet_stream(port_name).to_port_condition()"
    ),
    "flowsheet_stream_snapshot_stream_fallback": (
        "return source_unit.get_outlet_stream(source_port_name)"
    ),
    "flowsheet_unit_results_stream_fallback": (
        'or cast("ProcessStreamIO", cast("object", unit)).get_outlet_stream(port_name)'
    ),
}

TEST_NEGATIVE_OR_FIXTURE_ALLOWLIST: dict[str, set[str]] = {
    "tests/connection/test_migration_hygiene_gate.py": set(BANNED_TOKENS),
    "tests/connection/test_two_tank_reaction_comparison.py": {"_input_streams", "_output_streams"},
    "tests/components/test_controller_wiring_api.py": {
        "duty_setpoint",
        "split_fractions",
        "target_temperature_setpoint",
    },
    "tests/test_save_load_minimal.py": {
        "controller_sp_point_dict",
        "SensorBase",
        "pressure_rise",
        "sp_trajectory",
        "tag_store",
    },
    "tests/unit_process/test_control_surface_contract.py": {
        "duty_setpoint",
        "target_temperature_setpoint",
    },
    "tests/unit_process/test_layer0_material_state.py": {"from_legacy"},
    "tests/unit_process/test_layer4_component_separator.py": {"split_fractions"},
    "tests/unit_process/test_layer4_heater_cooler.py": {
        "duty_setpoint",
        "target_temperature_setpoint",
    },
    "tests/unit_process/test_layer4_pump_valve.py": {"pressure_rise"},
}

ATTRIBUTE_ACCESS_PATTERN = re.compile(r"\.(?:inlet|outlet)_(?![A-Za-z0-9_]*port)[A-Za-z0-9_]+")
EXEMPT_ATTRIBUTE_MATCHES = {".outlet_streams", ".inlet_streams"}
EXEMPT_ATTRIBUTE_SCAN_FILE_NAMES = {"process_binding.py"}

TOKEN_PATTERNS = {
    token: re.compile(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])")
    for token in BANNED_TOKENS
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def to_repo_relative_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root()).as_posix()
    except ValueError:
        return resolved.as_posix()


def iter_scope_paths(scope_directories: Iterable[str]) -> list[Path]:
    root = repo_root()
    paths: list[Path] = []
    for scope in scope_directories:
        scope_root = root / scope
        if not scope_root.exists():
            continue
        for candidate in sorted(scope_root.rglob("*")):
            if candidate.is_file() and candidate.suffix in TEXT_SUFFIXES:
                paths.append(candidate)
    return paths


def _normalized_scannable_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    if path.suffix != ".py":
        return text
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def tokens_in_text(text: str) -> list[str]:
    return [token for token, pattern in TOKEN_PATTERNS.items() if pattern.search(text)]


def scan_paths_for_tokens(paths: Iterable[Path | str]) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for item in paths:
        path = item if isinstance(item, Path) else Path(item)
        if not path.exists() or path.suffix not in TEXT_SUFFIXES:
            continue
        relative_path = to_repo_relative_path(path)
        for token in tokens_in_text(_normalized_scannable_text(path)):
            findings.append((relative_path, token))
    return sorted(findings)


def scan_runtime_fallback_snippets(paths: Iterable[Path | str]) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for item in paths:
        path = item if isinstance(item, Path) else Path(item)
        if not path.exists() or path.suffix != ".py":
            continue
        relative_path = to_repo_relative_path(path)
        text = _normalized_scannable_text(path)
        for snippet_key, snippet in RUNTIME_FALLBACK_BANNED_SNIPPETS.items():
            if snippet in text:
                findings.append((relative_path, snippet_key))
    return sorted(findings)


def connection_runtime_scope_paths() -> list[Path]:
    root = repo_root()
    directories = [
        root / "src" / "modular_simulation" / "connection",
        root / "src" / "modular_simulation" / "flowsheet",
        root / "src" / "modular_simulation" / "framework",
    ]
    paths: list[Path] = []
    for directory in directories:
        if not directory.exists():
            continue
        paths.extend(sorted(directory.rglob("*.py")))
    return paths


def scan_attribute_paths(paths: Iterable[Path | str]) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for item in paths:
        path = item if isinstance(item, Path) else Path(item)
        if not path.exists() or path.name in EXEMPT_ATTRIBUTE_SCAN_FILE_NAMES:
            continue
        for match in ATTRIBUTE_ACCESS_PATTERN.findall(_normalized_scannable_text(path)):
            if match in EXEMPT_ATTRIBUTE_MATCHES:
                continue
            findings.append((to_repo_relative_path(path), match))
    return sorted(findings)


def test_active_repo_has_no_banned_tokens() -> None:
    findings = scan_paths_for_tokens(iter_scope_paths(ACTIVE_REPO_SCOPES))
    assert findings == [], f"Found banned tokens in active repo scope: {findings}"


def test_tests_scope_allows_only_explicit_negative_or_fixture_banned_tokens() -> None:
    findings = scan_paths_for_tokens(iter_scope_paths(("tests",)))
    unexpected: list[tuple[str, str]] = []
    for relative_path, token in findings:
        if token in TEST_NEGATIVE_OR_FIXTURE_ALLOWLIST.get(relative_path, set()):
            continue
        unexpected.append((relative_path, token))
    assert unexpected == [], f"Found non-allowlisted banned tokens in tests scope: {unexpected}"


def test_active_repo_runtime_and_flowsheet_has_no_banned_fallback_acceptance_paths() -> None:
    findings = scan_runtime_fallback_snippets(iter_scope_paths(ACTIVE_REPO_SCOPES))
    assert findings == [], f"Found banned runtime/flowsheet fallback acceptance path: {findings}"


def test_core_connection_does_not_add_direct_unit_inlet_outlet_field_access() -> None:
    findings = scan_attribute_paths(connection_runtime_scope_paths())
    assert findings == [], (
        "Direct `.inlet_/ .outlet_` attribute access detected in connection/flowsheet/framework "
        f"scope: {findings}"
    )


def test_core_connection_detects_direct_unit_inlet_outlet_field_access(tmp_path: Path) -> None:
    temp = tmp_path / "forbidden.py"
    temp.write_text(
        "final_value = some_unit.inlet_flow + some_unit.outlet_pressure", encoding="utf-8"
    )
    findings = scan_attribute_paths(connection_runtime_scope_paths() + [temp])
    assert any(
        p == to_repo_relative_path(temp) and tok == ".inlet_flow" for (p, tok) in findings
    ), f"Synthetic forbidden attribute access was not detected: {findings}"


def test_detection_case_finds_banned_tokens(tmp_path: Path) -> None:
    temp = tmp_path / "migrate_sample.py"
    _ = temp.write_text(
        "def migrate(v):\n    token = ControllerBase\n    return token\n",
        encoding="utf-8",
    )
    findings = scan_paths_for_tokens(iter_scope_paths(ACTIVE_REPO_SCOPES) + [temp])
    assert any(
        p == to_repo_relative_path(temp) and tok == "ControllerBase" for (p, tok) in findings
    ), f"Temp file not reported in findings: {findings}"
