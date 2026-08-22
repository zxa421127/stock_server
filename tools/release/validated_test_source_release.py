# -*- coding: utf-8 -*-
"""Validate the TEST source tree and build a reproducible, secret-scanned release ZIP.

This is a reusable release-gate implementation. The Windows entrypoint lives at:
deploy/windows/Invoke-ValidatedTestSourceRelease.ps1

Runtime artifacts are written only below data-test/release-gates and external
package/backup roots. Production source, Production DB, and the real Caddy file
must remain unchanged throughout this gate.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
PROD_ROOT = Path(r"C:\stockdata\stock_server").resolve()
CANDIDATE = Path(r"C:\stockdata\stock_server_candidate")
CADDY = Path(r"C:\caddy\Caddyfile")
PY = Path(sys.executable).resolve()

POLICY = ROOT / "settings" / "platform_policy.json"
SEMANTICS = ROOT / "services" / "platform_policy_semantics.py"
SEMANTIC_TEST = ROOT / "tests" / "test_platform_policy_semantics.py"
SINGLE_SOURCE_TEST = ROOT / "tests" / "test_single_policy_source.py"
PACKAGER = ROOT / "tools" / "release" / "build_source_package.py"
SCANNER = ROOT / "tools" / "security" / "scan_release_secrets.py"
WORKFLOW = ROOT / "deploy" / "windows" / "Apply-TestPlatformPolicy.ps1"
PUBLISH = ROOT / "deploy" / "windows" / "Publish-StockCodeToProduction.ps1"

GATE_PY = ROOT / "tools" / "release" / "validated_test_source_release.py"
GATE_PS1 = ROOT / "deploy" / "windows" / "Invoke-ValidatedTestSourceRelease.ps1"

C3F_INSTALLER = (
    ROOT
    / "deploy"
    / "windows"
    / "Invoke-TestPlatformPolicySemanticValidation.ps1"
)
C3F_RECOVERY = (
    ROOT
    / "deploy"
    / "windows"
    / "Recover-InterruptedTestPlatformPolicySemanticValidation.ps1"
)
ROOT_C3F_OLD = ROOT / "C3F-SemanticValidation.ps1"

EXPECTED_POLICY_SHA256 = (
    "9D9C54590CAB8AC6703FE895A5B74A913A1FF78682BD8FCA500F523A76F02655"
)
EXPECTED_C3F_INSTALLER_SHA256 = (
    "D570C7AA0772338C2D1FEC7891A1921780BA42F3EC2516A0A8C2B4C87A0590EA"
)
EXPECTED_C3F_RECOVERY_SHA256 = (
    "E51883B814894448F44D63E02F987119235B5CC65A1B9913C77E590A255AB34C"
)

STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
WORK_ROOT = ROOT / "data-test" / "release-gates" / ("c3g-" + STAMP)
UNPACK_ROOT = WORK_ROOT / "unpacked"
ARCHIVE_ROOT = (
    Path(r"C:\stockdata\backups")
    / ("policy-consolidation-c3g-tools-" + STAMP)
)
PACKAGE_ROOT = Path(r"C:\stockdata\packages")
PACKAGE = PACKAGE_ROOT / ("stock-server-c3g-" + STAMP + ".zip")
PACKAGE_REPRO = PACKAGE_ROOT / ("stock-server-c3g-" + STAMP + ".repro.zip")
RECEIPT = PACKAGE_ROOT / ("stock-server-c3g-" + STAMP + ".release.json")
SHA_FILE = PACKAGE_ROOT / ("stock-server-c3g-" + STAMP + ".sha256.txt")

REQUIRED_PACKAGE_FILES = {
    "config.py",
    ".env.example",
    "settings/platform_policy.json",
    "services/platform_policy.py",
    "services/platform_policy_semantics.py",
    "services/plan_catalog.py",
    "run_waitress.py",
    "run_waitress_web_only.py",
    "tools/db/verify_plan_catalog.py",
    "tools/db/plan_catalog_sync.py",
    "tools/db/sync_test_plan_catalog.py",
    "tools/release/build_source_package.py",
    "tools/release/validated_test_source_release.py",
    "tools/security/scan_release_secrets.py",
    "deploy/windows/Apply-TestPlatformPolicy.ps1",
    "deploy/windows/Publish-StockCodeToProduction.ps1",
    "deploy/windows/Invoke-ValidatedTestSourceRelease.ps1",
    "tests/test_single_policy_source.py",
    "tests/test_platform_policy_semantics.py",
    "SOURCE_MANIFEST.json",
    "SHA256SUMS.txt",
}

FORBIDDEN_EXACT = {
    "deploy/windows/Invoke-TestPlatformPolicySemanticValidation.ps1",
    "deploy/windows/Recover-InterruptedTestPlatformPolicySemanticValidation.ps1",
    "C3F-SemanticValidation.ps1",
}

FORBIDDEN_BASENAMES = {
    ".env",
    "pyvenv.cfg",
    "membership_test_tokens.json",
    "interface_test_token.txt",
    "RELEASE_MANIFEST.json",
    "DEV_SOURCE_MANIFEST.json",
    "TEST_REPORT.txt",
}

FORBIDDEN_PREFIXES = {
    "docs/archive",
    "security/admin-client-ca",
}

FORBIDDEN_DIR_PARTS = {
    ".git",
    ".idea",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "data",
    "data-dev",
    "data-test",
    "logs",
    "logs-dev",
    "dist",
    "build",
    "patch_backups",
    "node_modules",
}

FORBIDDEN_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".key",
    ".pem",
    ".pfx",
    ".p12",
    ".jks",
    ".keystore",
    ".log",
    ".zip",
    ".7z",
    ".rar",
    ".pyc",
}

SPECIAL_GENERATED = {
    "SOURCE_MANIFEST.json",
    "SHA256SUMS.txt",
}


def banner(text: str) -> None:
    print()
    print("=" * 72)
    print(text)
    print("=" * 72)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def run(
    args: list[str | Path],
    *,
    check: bool = True,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> int:
    rendered = [str(item) for item in args]
    print()
    print("RUN=" + " ".join(rendered))
    result = subprocess.run(
        rendered,
        cwd=str(cwd or ROOT),
        env=env,
        check=False,
    )
    print("EXIT=" + str(result.returncode))
    if check and result.returncode != 0:
        raise RuntimeError("COMMAND_FAILED:" + str(result.returncode))
    return int(result.returncode)


def py(
    *args: str | Path,
    check: bool = True,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> int:
    return run(
        [PY, "-B", "-X", "utf8", *args],
        check=check,
        cwd=cwd,
        env=env,
    )


def listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def pid(port: int) -> int:
    command = (
        "$x=@(Get-NetTCPConnection "
        "-LocalPort "
        + str(port)
        + " -State Listen -ErrorAction SilentlyContinue);"
        "if($x.Count -ne 1){exit 3};"
        "Write-Output $x[0].OwningProcess"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("LISTENER_GATE_FAILED:" + str(port))
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return int(lines[-1])


def http(url: str) -> tuple[int, str]:
    with urlopen(url, timeout=15) as response:
        return (
            int(response.status),
            response.read().decode("utf-8", errors="replace"),
        )


def safe_rel_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    if normalized.startswith("/"):
        raise RuntimeError("ZIP_ABSOLUTE_PATH")
    if re.match(r"^[A-Za-z]:", normalized):
        raise RuntimeError("ZIP_DRIVE_PATH")
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if ".." in parts:
        raise RuntimeError("ZIP_PATH_TRAVERSAL")
    return "/".join(parts)


def validate_zip_structure(
    path: Path,
    *,
    required_files: set[str] | None = None,
) -> tuple[list[str], dict[str, object]]:
    required = REQUIRED_PACKAGE_FILES if required_files is None else required_files

    with zipfile.ZipFile(path, "r") as archive:
        raw_names = [item.filename for item in archive.infolist()]
        names = [safe_rel_name(name) for name in raw_names]

        if len(names) != len(set(names)):
            raise RuntimeError("ZIP_DUPLICATE_ENTRY")

        name_set = set(names)
        missing = sorted(required - name_set)
        if missing:
            raise RuntimeError("PACKAGE_REQUIRED_FILES_MISSING:" + repr(missing))

        forbidden: list[str] = []
        for name in names:
            parts = tuple(part for part in name.split("/") if part)
            suffix = Path(name).suffix.lower()

            if name in FORBIDDEN_EXACT:
                forbidden.append(name)
                continue
            if parts and parts[-1] in FORBIDDEN_BASENAMES:
                forbidden.append(name)
                continue
            if any(part in FORBIDDEN_DIR_PARTS for part in parts):
                forbidden.append(name)
                continue
            if any(
                name == prefix or name.startswith(prefix + "/")
                for prefix in FORBIDDEN_PREFIXES
            ):
                forbidden.append(name)
                continue
            if suffix in FORBIDDEN_SUFFIXES:
                forbidden.append(name)
                continue

        if forbidden:
            raise RuntimeError(
                "PACKAGE_FORBIDDEN_ASSET_COUNT=" + str(len(forbidden))
            )

        manifest_data = archive.read("SOURCE_MANIFEST.json")
        sums_data = archive.read("SHA256SUMS.txt")
        manifest = json.loads(manifest_data.decode("utf-8"))

        if not isinstance(manifest, dict):
            raise RuntimeError("SOURCE_MANIFEST_NOT_OBJECT")
        if manifest.get("package_type") != "development-source":
            raise RuntimeError("SOURCE_MANIFEST_PACKAGE_TYPE_INVALID")

        items = manifest.get("files")
        if not isinstance(items, list):
            raise RuntimeError("SOURCE_MANIFEST_FILES_INVALID")

        seen: set[str] = set()
        expected_sum_lines: list[str] = []

        for item in items:
            if not isinstance(item, dict):
                raise RuntimeError("SOURCE_MANIFEST_ITEM_INVALID")

            rel = safe_rel_name(str(item.get("path", "")))
            if not rel or rel in seen:
                raise RuntimeError("SOURCE_MANIFEST_DUPLICATE_OR_EMPTY_PATH")
            seen.add(rel)

            if rel not in name_set:
                raise RuntimeError("SOURCE_MANIFEST_ENTRY_MISSING_FROM_ZIP")

            data = archive.read(rel)
            actual_size = len(data)
            actual_hash = hashlib.sha256(data).hexdigest()

            if item.get("size") != actual_size:
                raise RuntimeError("SOURCE_MANIFEST_SIZE_MISMATCH:" + rel)

            if str(item.get("sha256", "")).lower() != actual_hash:
                raise RuntimeError("SOURCE_MANIFEST_HASH_MISMATCH:" + rel)

            expected_sum_lines.append(actual_hash + "  " + rel + "\n")

        expected_manifest_names = name_set - SPECIAL_GENERATED
        if seen != expected_manifest_names:
            raise RuntimeError("SOURCE_MANIFEST_FILE_SET_MISMATCH")

        expected_sums = "".join(expected_sum_lines).encode("utf-8")
        if sums_data != expected_sums:
            raise RuntimeError("SHA256SUMS_CONTENT_MISMATCH")

        summary: dict[str, object] = {
            "file_count": len(items),
            "manifest_sha256": sha_bytes(manifest_data),
            "sha256sums_sha256": sha_bytes(sums_data),
        }
        return names, summary


def validate_package_matches_source(path: Path) -> None:
    with zipfile.ZipFile(path, "r") as archive:
        manifest = json.loads(
            archive.read("SOURCE_MANIFEST.json").decode("utf-8")
        )

        for item in manifest["files"]:
            rel = safe_rel_name(str(item["path"]))
            source = ROOT / Path(*rel.split("/"))
            if not source.is_file():
                raise RuntimeError("SOURCE_FILE_MISSING_AFTER_BUILD:" + rel)

            data = source.read_bytes()
            if len(data) != item["size"]:
                raise RuntimeError("SOURCE_SIZE_CHANGED_AFTER_BUILD:" + rel)

            if hashlib.sha256(data).hexdigest() != str(item["sha256"]).lower():
                raise RuntimeError("SOURCE_HASH_CHANGED_AFTER_BUILD:" + rel)


def validate_python_syntax_in_unpacked(root: Path) -> int:
    count = 0
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if any(part in FORBIDDEN_DIR_PARTS for part in rel.parts):
            continue
        source = path.read_text(encoding="utf-8-sig")
        compile(source, str(rel), "exec")
        count += 1
    return count


def target_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        out: set[str] = set()
        for item in target.elts:
            out.update(target_names(item))
        return out
    return set()


def assigned_names(node: ast.AST) -> set[str]:
    out: set[str] = set()
    if isinstance(node, ast.Assign):
        for target in node.targets:
            out.update(target_names(target))
    elif isinstance(node, ast.AnnAssign):
        out.update(target_names(node.target))
    return out


def validate_unpacked_single_source(root: Path) -> None:
    policy = json.loads(
        (root / "settings" / "platform_policy.json").read_text(
            encoding="utf-8-sig"
        )
    )
    managed = set(policy["config"])
    if len(managed) != 82:
        raise RuntimeError("UNPACKED_MANAGED_CONFIG_COUNT_INVALID")

    config_path = root / "config.py"
    source = config_path.read_text(encoding="utf-8-sig")
    marker = "PLATFORM_POLICY_RUNTIME_OVERLAY_V1"
    if source.count(marker) != 1:
        raise RuntimeError("UNPACKED_CONFIG_MARKER_INVALID")

    marker_line = next(
        index
        for index, line in enumerate(source.splitlines(), 1)
        if marker in line
    )
    tree = ast.parse(source, filename=str(config_path))

    assignments = [
        (node.lineno, sorted(assigned_names(node) & managed))
        for node in tree.body
        if (
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and node.lineno < marker_line
            and assigned_names(node) & managed
        )
    ]
    if assignments:
        raise RuntimeError("UNPACKED_CONFIG_POLICY_DUPLICATE_ASSIGNMENTS")

    reads = [
        (node.id, node.lineno)
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in managed
            and node.lineno < marker_line
        )
    ]
    if reads:
        raise RuntimeError("UNPACKED_CONFIG_POLICY_READ_BEFORE_OVERLAY")

    env_path = root / ".env.example"
    env_source = env_path.read_text(encoding="utf-8-sig")
    env_marker = "PLATFORM_POLICY_ENV_EXAMPLE_SINGLE_SOURCE_V1"
    doc_value = "managed in settings/platform_policy.json"

    if env_source.count(env_marker) != 1:
        raise RuntimeError("UNPACKED_ENV_POLICY_MARKER_INVALID")

    active: list[str] = []
    documented: list[str] = []

    for raw in env_source.splitlines():
        line = raw.strip()
        if not line:
            continue

        if line.startswith("#"):
            body = line[1:].strip()
            if "=" in body:
                key, value = body.split("=", 1)
                if key.strip() in managed and value.strip() == doc_value:
                    documented.append(key.strip())
            continue

        if "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in managed:
                active.append(key)

    if active:
        raise RuntimeError("UNPACKED_ENV_ACTIVE_POLICY_DUPLICATES")

    if len(documented) != 82 or set(documented) != managed:
        raise RuntimeError("UNPACKED_ENV_POLICY_DOCUMENTATION_INVALID")


def fresh_unpacked_policy_validation(root: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)

    code = (
        "from services.platform_policy import "
        "load_platform_policy,managed_config,expand_plans,waitress_backlog;"
        "from services.platform_policy_semantics import CONFIG_RULES;"
        "p=load_platform_policy();"
        "assert len(CONFIG_RULES)==82;"
        "assert len(managed_config(p))==82;"
        "assert len(expand_plans(p))==7;"
        "assert waitress_backlog(p)>=1;"
        "print('UNPACKED_POLICY_SEMANTIC_VALIDATION=PASS')"
    )

    py("-c", code, cwd=root, env=env)


def production_source_fingerprint(root: Path) -> str:
    denied_parts = {
        ".venv",
        "__pycache__",
        ".pytest_cache",
        "data",
        "data-dev",
        "data-test",
        "logs",
        "logs-dev",
    }
    rows: list[bytes] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in denied_parts for part in rel.parts):
            continue
        rows.append(
            rel.as_posix().encode("utf-8")
            + b"\0"
            + hashlib.sha256(path.read_bytes()).digest()
        )
    return sha_bytes(b"\n".join(rows))


def find_unexpected_c3f_tool_references() -> list[str]:
    needles = {
        C3F_INSTALLER.name,
        C3F_RECOVERY.name,
        ROOT_C3F_OLD.name,
    }
    allowed_suffixes = {
        ".py",
        ".ps1",
        ".psm1",
        ".cmd",
        ".bat",
        ".md",
        ".txt",
        ".toml",
        ".json",
        ".yaml",
        ".yml",
    }

    # These two release-gate files are allowed to name the one-off C3F tools
    # because they are responsible for archiving them safely.
    allowed_reference_files = {
        GATE_PY.resolve(),
        GATE_PS1.resolve(),
        C3F_INSTALLER.resolve(),
        C3F_RECOVERY.resolve(),
    }

    findings: list[str] = []

    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.resolve() in allowed_reference_files:
            continue
        rel = path.relative_to(ROOT)
        if any(part in FORBIDDEN_DIR_PARTS for part in rel.parts):
            continue
        if path.suffix.lower() not in allowed_suffixes:
            continue

        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue

        hits = sorted(name for name in needles if name in text)
        if hits:
            findings.append(rel.as_posix() + ":" + ",".join(hits))

    return findings


def archive_c3f_one_off_tools(
    moved: list[tuple[Path, Path]]
) -> None:
    if ROOT_C3F_OLD.exists():
        raise RuntimeError("ROOT_C3F_OLD_SCRIPT_STILL_EXISTS")

    expected = (
        (C3F_INSTALLER, EXPECTED_C3F_INSTALLER_SHA256),
        (C3F_RECOVERY, EXPECTED_C3F_RECOVERY_SHA256),
    )

    for source, expected_hash in expected:
        if not source.is_file():
            raise RuntimeError("C3F_ONE_OFF_TOOL_MISSING:" + source.name)
        if sha_file(source) != expected_hash:
            raise RuntimeError("C3F_ONE_OFF_TOOL_HASH_CHANGED:" + source.name)

    references = find_unexpected_c3f_tool_references()
    if references:
        raise RuntimeError(
            "C3F_ONE_OFF_TOOL_REFERENCED_ELSEWHERE_COUNT="
            + str(len(references))
        )

    ARCHIVE_ROOT.mkdir(parents=True, exist_ok=False)

    for source, _ in expected:
        destination = ARCHIVE_ROOT / source.name
        moved.append((source, destination))
        shutil.move(str(source), str(destination))

        if source.exists() or not destination.is_file():
            raise RuntimeError("C3F_ONE_OFF_TOOL_ARCHIVE_FAILED:" + source.name)

    if sha_file(ARCHIVE_ROOT / C3F_INSTALLER.name) != EXPECTED_C3F_INSTALLER_SHA256:
        raise RuntimeError("ARCHIVED_INSTALLER_HASH_MISMATCH")
    if sha_file(ARCHIVE_ROOT / C3F_RECOVERY.name) != EXPECTED_C3F_RECOVERY_SHA256:
        raise RuntimeError("ARCHIVED_RECOVERY_HASH_MISMATCH")


def restore_archived_tools(
    moved: list[tuple[Path, Path]]
) -> None:
    for source, destination in reversed(moved):
        if destination.is_file() and not source.exists():
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(destination), str(source))

    for source, expected_hash in (
        (C3F_INSTALLER, EXPECTED_C3F_INSTALLER_SHA256),
        (C3F_RECOVERY, EXPECTED_C3F_RECOVERY_SHA256),
    ):
        if not source.is_file() or sha_file(source) != expected_hash:
            raise RuntimeError("C3G_ROLLBACK_TOOL_RESTORE_FAILED:" + source.name)

    print("C3G_ONE_OFF_TOOL_ROLLBACK=PASS")


def clean_outputs() -> None:
    PACKAGE.unlink(missing_ok=True)
    PACKAGE_REPRO.unlink(missing_ok=True)
    RECEIPT.unlink(missing_ok=True)
    SHA_FILE.unlink(missing_ok=True)
    if UNPACK_ROOT.exists():
        shutil.rmtree(UNPACK_ROOT, ignore_errors=True)


def build_package(path: Path) -> dict[str, object]:
    from tools.release.build_source_package import build

    try:
        result = build(path)
    except BaseException as error:
        print("SOURCE_PACKAGE_BUILD_EXCEPTION=" + type(error).__name__)
        raise RuntimeError("SOURCE_PACKAGE_BUILD_FAILED") from None

    if not path.is_file():
        raise RuntimeError("SOURCE_PACKAGE_NOT_CREATED")

    return dict(result)


def scan_package_without_echoing_findings(path: Path) -> int:
    from tools.security.scan_release_secrets import scan_zip

    findings = scan_zip(
        path,
        ignore_fixture_prefixes=("tests/",),
    )
    count = len(findings)
    print("C3G_SECRET_SCAN_FINDING_COUNT=" + str(count))
    if count:
        raise RuntimeError("C3G_SECRET_SCAN_FAILED")
    return count


def _self_test_zip() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        good = root / "good.zip"

        files = {
            "a.txt": b"alpha\n",
            "b.py": b"print('ok')\n",
        }

        manifest_items = []
        for name in sorted(files):
            data = files[name]
            manifest_items.append(
                {
                    "path": name,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )

        manifest_data = json.dumps(
            {
                "package_type": "development-source",
                "files": manifest_items,
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

        sums = "".join(
            item["sha256"] + "  " + item["path"] + "\n"
            for item in manifest_items
        ).encode("utf-8")

        with zipfile.ZipFile(good, "w") as archive:
            for name in sorted(files):
                archive.writestr(name, files[name])
            archive.writestr("SOURCE_MANIFEST.json", manifest_data)
            archive.writestr("SHA256SUMS.txt", sums)

        validate_zip_structure(
            good,
            required_files={"SOURCE_MANIFEST.json", "SHA256SUMS.txt"},
        )

        try:
            safe_rel_name("../escape.txt")
        except RuntimeError:
            pass
        else:
            raise AssertionError("path traversal self-test failed")

        bad = root / "bad.zip"
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr("secrets/private.pem", b"x")
            archive.writestr(
                "SOURCE_MANIFEST.json",
                json.dumps(
                    {
                        "package_type": "development-source",
                        "files": [
                            {
                                "path": "secrets/private.pem",
                                "size": 1,
                                "sha256": hashlib.sha256(b"x").hexdigest(),
                            }
                        ],
                    }
                ).encode("utf-8"),
            )
            archive.writestr(
                "SHA256SUMS.txt",
                (
                    hashlib.sha256(b"x").hexdigest()
                    + "  secrets/private.pem\n"
                ).encode("utf-8"),
            )

        try:
            validate_zip_structure(
                bad,
                required_files={"SOURCE_MANIFEST.json", "SHA256SUMS.txt"},
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("forbidden asset self-test failed")


def main() -> None:
    banner("C3G CLEAN RELEASE PACKAGE / SECRET SCAN / MANIFEST")

    if Path.cwd().resolve() != ROOT.resolve():
        raise RuntimeError("NOT_TEST_ROOT")

    if GATE_PY.resolve() != Path(__file__).resolve():
        raise RuntimeError("C3G_PYTHON_GATE_PATH_INVALID")

    if CANDIDATE.exists() or listening(8900):
        raise RuntimeError("CANDIDATE_OR_8900_ACTIVE")

    if not PROD_ROOT.is_dir():
        raise RuntimeError("PRODUCTION_ROOT_MISSING")

    required_local = (
        POLICY,
        SEMANTICS,
        SEMANTIC_TEST,
        SINGLE_SOURCE_TEST,
        PACKAGER,
        SCANNER,
        WORKFLOW,
        PUBLISH,
        GATE_PY,
        GATE_PS1,
        CADDY,
        C3F_INSTALLER,
        C3F_RECOVERY,
    )
    missing_local = [str(path) for path in required_local if not path.is_file()]
    if missing_local:
        raise RuntimeError("C3G_REQUIRED_FILE_MISSING:" + repr(missing_local))

    _self_test_zip()
    print("C3G_INTERNAL_SELFTEST=PASS")

    if sha_file(POLICY) != EXPECTED_POLICY_SHA256:
        raise RuntimeError("C3G_POLICY_HASH_CHANGED")

    py(
        "-c",
        (
            "from services.platform_policy import "
            "load_platform_policy,managed_config,expand_plans,waitress_backlog;"
            "from services.platform_policy_semantics import CONFIG_RULES;"
            "p=load_platform_policy();"
            "assert len(CONFIG_RULES)==82;"
            "assert len(managed_config(p))==82;"
            "assert len(expand_plans(p))==7;"
            "assert waitress_backlog(p)>=1;"
            "print('C3G_C3F_BASELINE=PASS')"
        ),
    )

    test_pid_before = pid(8898)
    prod_pid_before = pid(8899)
    caddy_hash_before = sha_file(CADDY)
    prod_source_before = production_source_fingerprint(PROD_ROOT)

    test_status, test_body = http("http://127.0.0.1:8898/ping")
    prod_status, prod_body = http("http://127.0.0.1:8899/ping")
    public_status, _ = http("https://api.lifesupermarket.cn/ping")

    if not (
        test_status == 200
        and test_body == "pong"
        and prod_status == 200
        and prod_body == "pong"
        and public_status == 200
    ):
        raise RuntimeError("C3G_SERVICE_BASELINE_FAILED")

    print("TEST_PID_BEFORE=" + str(test_pid_before))
    print("PRODUCTION_PID_BEFORE=" + str(prod_pid_before))
    print("C3G_SERVICE_BASELINE=PASS")

    py(
        "-m",
        "tools.db.verify_plan_catalog",
        "--project-root",
        ROOT,
    )
    print("C3G_INITIAL_TEST_PLAN_DRIFT=0")

    moved: list[tuple[Path, Path]] = []
    archive_committed = False

    try:
        banner("C3G ARCHIVE ONE-OFF C3F ORCHESTRATION")

        archive_c3f_one_off_tools(moved)
        print("C3G_C3F_ONE_OFF_TOOL_COUNT=2")
        print("C3G_C3F_ONE_OFF_TOOLS_ARCHIVED=PASS")
        print("C3G_ONE_OFF_TOOL_ARCHIVE=" + str(ARCHIVE_ROOT))

        if find_unexpected_c3f_tool_references():
            raise RuntimeError("C3G_REFERENCE_RESCAN_FAILED")

        banner("C3G RELEASE TARGETED TESTS")

        targets = [
            "tests/test_release_package_hardening.py",
            "tests/test_release_secret_scanner.py",
            "tests/test_single_policy_source.py",
            "tests/test_platform_policy_semantics.py",
            "tests/test_platform_policy.py",
            "tests/test_windows_apply_test_platform_policy.py",
            "tests/test_windows_script_portability.py",
            "tests/test_windows_publish_stock_code_to_production.py",
            "tests/test_production_readiness.py",
            "tests/test_web_only_candidate_launcher.py",
        ]
        existing = [name for name in targets if (ROOT / name).is_file()]

        py("-m", "tools.environment_preflight")
        print("C3G_ENVIRONMENT_PREFLIGHT=PASS")

        py("-m", "pip", "check")
        print("C3G_PIP_CHECK=PASS")

        py("-m", "pytest", "-q", *existing)
        print("C3G_RELEASE_TARGETED_PYTEST=PASS")

        banner("C3G FRESH FULL PYTEST")
        print("IMPORTANT=FULL PYTEST MAY TAKE SEVERAL MINUTES; DO NOT PRESS CTRL+C")

        full_start = time.monotonic()
        full_exit = py("-m", "pytest", "-q", check=False)
        full_seconds = round(time.monotonic() - full_start, 2)

        print("C3G_FULL_PYTEST_EXIT=" + str(full_exit))
        print("C3G_FULL_PYTEST_SECONDS=" + str(full_seconds))

        if full_exit != 0:
            raise RuntimeError("C3G_FULL_PYTEST_FAILED")

        print("C3G_FULL_PYTEST=PASS")

        py(
            "-m",
            "tools.db.verify_plan_catalog",
            "--project-root",
            ROOT,
        )
        print("C3G_POST_PYTEST_PLAN_DRIFT=0")

        banner("C3G BUILD REPRODUCIBLE SOURCE PACKAGE")

        PACKAGE_ROOT.mkdir(parents=True, exist_ok=True)
        WORK_ROOT.mkdir(parents=True, exist_ok=True)

        result1 = build_package(PACKAGE)
        hash1 = sha_file(PACKAGE)

        if str(result1.get("sha256", "")).upper() != hash1:
            raise RuntimeError("C3G_PACKAGE_BUILD_1_HASH_REPORT_MISMATCH")

        print("C3G_PACKAGE_BUILD_1=PASS")
        print("C3G_PACKAGE_1_SHA256=" + hash1)
        print("C3G_PACKAGE_1_FILE_COUNT=" + str(result1.get("file_count")))

        result2 = build_package(PACKAGE_REPRO)
        hash2 = sha_file(PACKAGE_REPRO)

        if str(result2.get("sha256", "")).upper() != hash2:
            raise RuntimeError("C3G_PACKAGE_BUILD_2_HASH_REPORT_MISMATCH")

        print("C3G_PACKAGE_BUILD_2=PASS")
        print("C3G_PACKAGE_2_SHA256=" + hash2)

        if hash1 != hash2:
            raise RuntimeError("C3G_PACKAGE_NOT_REPRODUCIBLE")

        print("C3G_PACKAGE_REPRODUCIBLE=PASS")

        _, package_summary = validate_zip_structure(PACKAGE)

        print("C3G_PACKAGE_STRUCTURE=PASS")
        print("C3G_PACKAGE_MANIFEST=PASS")
        print("C3G_PACKAGE_SHA256SUMS=PASS")
        print(
            "C3G_PACKAGE_MANIFEST_FILE_COUNT="
            + str(package_summary["file_count"])
        )

        scan_package_without_echoing_findings(PACKAGE)
        print("C3G_SECRET_SCAN=PASS")

        validate_package_matches_source(PACKAGE)
        print("C3G_PACKAGE_MATCHES_TEST_SOURCE=PASS")

        if C3F_INSTALLER.exists() or C3F_RECOVERY.exists() or ROOT_C3F_OLD.exists():
            raise RuntimeError("C3G_ONE_OFF_C3F_TOOL_REAPPEARED")

        with zipfile.ZipFile(PACKAGE, "r") as archive:
            archive.extractall(UNPACK_ROOT)

        print("C3G_PACKAGE_UNPACK=PASS")

        syntax_count = validate_python_syntax_in_unpacked(UNPACK_ROOT)
        print("C3G_UNPACKED_PYTHON_SYNTAX=PASS")
        print("C3G_UNPACKED_PYTHON_FILE_COUNT=" + str(syntax_count))

        validate_unpacked_single_source(UNPACK_ROOT)
        print("C3G_UNPACKED_SINGLE_POLICY_SOURCE=PASS")

        fresh_unpacked_policy_validation(UNPACK_ROOT)
        print("C3G_UNPACKED_POLICY_VALIDATION=PASS")

        validate_package_matches_source(PACKAGE)
        print("C3G_FINAL_PACKAGE_SOURCE_MATCH=PASS")

        PACKAGE_REPRO.unlink(missing_ok=True)

        test_pid_after = pid(8898)
        prod_pid_after = pid(8899)

        if test_pid_after != test_pid_before:
            raise RuntimeError("C3G_TEST_PID_CHANGED")
        if prod_pid_after != prod_pid_before:
            raise RuntimeError("C3G_PRODUCTION_PID_CHANGED")
        if sha_file(CADDY) != caddy_hash_before:
            raise RuntimeError("C3G_CADDY_CHANGED")
        if production_source_fingerprint(PROD_ROOT) != prod_source_before:
            raise RuntimeError("C3G_PRODUCTION_SOURCE_CHANGED")

        test_status, test_body = http("http://127.0.0.1:8898/ping")
        prod_status, prod_body = http("http://127.0.0.1:8899/ping")
        public_status, _ = http("https://api.lifesupermarket.cn/ping")

        if not (
            test_status == 200
            and test_body == "pong"
            and prod_status == 200
            and prod_body == "pong"
            and public_status == 200
        ):
            raise RuntimeError("C3G_FINAL_HEALTH_FAILED")

        py(
            "-m",
            "tools.db.verify_plan_catalog",
            "--project-root",
            ROOT,
        )

        receipt = {
            "gate": "C3G",
            "status": "PASS",
            "package": str(PACKAGE),
            "package_sha256": hash1,
            "package_file_count": package_summary["file_count"],
            "source_manifest_sha256": package_summary["manifest_sha256"],
            "sha256sums_sha256": package_summary["sha256sums_sha256"],
            "policy_sha256": sha_file(POLICY),
            "semantic_rule_count": 82,
            "full_pytest_exit": 0,
            "test_plan_drift": 0,
            "one_off_c3f_tools_archived": [
                C3F_INSTALLER.name,
                C3F_RECOVERY.name,
            ],
            "one_off_tool_archive": str(ARCHIVE_ROOT),
            "production_write_executed": False,
            "caddy_reload_executed": False,
        }

        RECEIPT.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        SHA_FILE.write_text(
            hash1 + "  " + PACKAGE.name + "\n",
            encoding="ascii",
        )

        archive_committed = True

        banner("C3G FINAL")

        print("POLICY_CONSOLIDATION_C3G_FINAL=PASS")
        print("C3F_ONE_OFF_TOOLS_ARCHIVED=TRUE")
        print("C3F_ONE_OFF_TOOL_COUNT=2")
        print("C3G_INTERNAL_SELFTEST=PASS")
        print("C3G_ENVIRONMENT_PREFLIGHT=PASS")
        print("C3G_PIP_CHECK=PASS")
        print("C3G_RELEASE_TARGETED_PYTEST=PASS")
        print("C3G_FULL_PYTEST=PASS")
        print("C3G_PACKAGE_REPRODUCIBLE=PASS")
        print("C3G_PACKAGE_STRUCTURE=PASS")
        print("C3G_PACKAGE_MANIFEST=PASS")
        print("C3G_PACKAGE_SHA256SUMS=PASS")
        print("C3G_SECRET_SCAN=PASS")
        print("C3G_SECRET_SCAN_FINDING_COUNT=0")
        print("C3G_PACKAGE_MATCHES_TEST_SOURCE=PASS")
        print("C3G_UNPACKED_PYTHON_SYNTAX=PASS")
        print("C3G_UNPACKED_SINGLE_POLICY_SOURCE=PASS")
        print("C3G_UNPACKED_POLICY_VALIDATION=PASS")
        print("FINAL_TEST_PLAN_DRIFT=0")
        print("TEST_PID_BEFORE=" + str(test_pid_before))
        print("TEST_PID_AFTER=" + str(test_pid_after))
        print("PRODUCTION_PID_BEFORE=" + str(prod_pid_before))
        print("PRODUCTION_PID_AFTER=" + str(prod_pid_after))
        print("PRODUCTION_SOURCE_MODIFIED=FALSE")
        print("PRODUCTION_DB_WRITE_EXECUTED=FALSE")
        print("REAL_CADDY_FILE_UNCHANGED=TRUE")
        print("REAL_CADDY_RELOAD_EXECUTED=FALSE")
        print("PUBLIC_PING_AFTER=200")
        print("C3G_RELEASE_READY=TRUE")
        print("C3G_PACKAGE=" + str(PACKAGE))
        print("C3G_PACKAGE_SHA256=" + hash1)
        print("C3G_RELEASE_RECEIPT=" + str(RECEIPT))
        print("C3G_SHA256_FILE=" + str(SHA_FILE))
        print("C3G_ONE_OFF_TOOL_ARCHIVE=" + str(ARCHIVE_ROOT))

    except BaseException as error:
        print()
        print("C3G_EXCEPTION=" + type(error).__name__)
        print("C3G_FAILURE_STAGE=FAIL_CLOSED")

        if not archive_committed:
            clean_outputs()
            if moved:
                try:
                    restore_archived_tools(moved)
                except BaseException as rollback_error:
                    print(
                        "C3G_ROLLBACK_FAILED="
                        + type(rollback_error).__name__
                    )
        else:
            print("C3G_ARCHIVE_COMMITTED_BEFORE_LATE_FAILURE=TRUE")

        raise


if __name__ == "__main__":
    main()
