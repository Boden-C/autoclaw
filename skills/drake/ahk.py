from __future__ import annotations

import os
import subprocess
from pathlib import Path


DRAKE_DIR = Path(__file__).resolve().parent
CSV_AHK = DRAKE_DIR / "csv.ahk"


def ensure_csv_ahk_running() -> str:
    """Start csv.ahk when it is not already running."""

    if is_csv_ahk_running():
        return "csv.ahk is already running."

    executable = find_autohotkey_exe(CSV_AHK)
    if not executable:
        raise RuntimeError(
            "No compatible AutoHotkey executable found for csv.ahk. "
            "This script uses AutoHotkey v1 syntax. Install AutoHotkey v1 or set AUTOHOTKEY_EXE "
            "to a v1 executable such as AutoHotkeyU64.exe."
        )

    subprocess.Popen(
        [str(executable), str(CSV_AHK)],
        cwd=str(DRAKE_DIR),
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    return f"Started csv.ahk with {executable}."


def is_csv_ahk_running() -> bool:
    script_path = str(CSV_AHK).casefold()
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.CommandLine -and $_.CommandLine.ToLower().Contains('csv.ahk') } | "
            "Select-Object -First 1 -ExpandProperty CommandLine"
        ),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError:
        return False
    output = result.stdout.casefold()
    return "csv.ahk" in output and (script_path in output or "skills\\drake\\csv.ahk" in output)


def find_autohotkey_exe(script_path: Path) -> Path | None:
    needs_v2 = script_uses_v2(script_path)

    env_value = os.environ.get("AUTOHOTKEY_EXE")
    if env_value:
        env_path = Path(env_value)
        if env_path.exists() and is_exe_compatible(env_path, needs_v2):
            return env_path

    program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
    local_app_data = Path(os.environ.get("LocalAppData", ""))

    v1_candidates = [
        program_files / "AutoHotkey" / "AutoHotkeyU64.exe",
        program_files / "AutoHotkey" / "AutoHotkeyU32.exe",
        program_files / "AutoHotkey" / "AutoHotkeyA32.exe",
        program_files / "AutoHotkey" / "AutoHotkey.exe",
        program_files_x86 / "AutoHotkey" / "AutoHotkeyU64.exe",
        program_files_x86 / "AutoHotkey" / "AutoHotkeyU32.exe",
        program_files_x86 / "AutoHotkey" / "AutoHotkeyA32.exe",
        program_files_x86 / "AutoHotkey" / "AutoHotkey.exe",
    ]
    v2_candidates = [
        program_files / "AutoHotkey" / "v2" / "AutoHotkey64.exe",
        program_files / "AutoHotkey" / "v2" / "AutoHotkey32.exe",
        program_files / "AutoHotkey" / "v2" / "AutoHotkey.exe",
        local_app_data / "Programs" / "AutoHotkey" / "v2" / "AutoHotkey64.exe",
        local_app_data / "Programs" / "AutoHotkey" / "AutoHotkey64.exe",
        local_app_data / "Programs" / "AutoHotkey" / "AutoHotkey.exe",
    ]

    candidates = v2_candidates if needs_v2 else v1_candidates
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def script_uses_v2(script_path: Path) -> bool:
    try:
        first_chunk = script_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    for raw_line in first_chunk.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.casefold()
        if lowered.startswith("#requires") and "autohotkey" in lowered and "v2" in lowered:
            return True
        if lowered.startswith("#noenv"):
            return False
        break
    return False


def is_exe_compatible(exe_path: Path, needs_v2: bool) -> bool:
    lowered = str(exe_path).casefold()
    looks_v2 = "\\v2\\" in lowered or "autohotkey64.exe" in lowered or "autohotkey32.exe" in lowered
    if needs_v2:
        return looks_v2
    return not ("\\v2\\" in lowered)
