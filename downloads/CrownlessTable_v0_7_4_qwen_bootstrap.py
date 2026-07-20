#!/usr/bin/env python3
"""Upgrade Crownless Table to 0.7.4 with automatic Qwen VoiceDesign setup.

The one-click voice stack could start GPT-SoVITS and the local voice bridge, but
it assumed a pre-existing AICompanionVoiceLab\\envs\\qwen3_tts environment.
This update creates that isolated environment when missing, installs the CUDA
PyTorch runtime and qwen-tts package, verifies CUDA and the Qwen import, and
starts the VoiceDesign API automatically after installation.

If the installed application is still 0.7.2, this script first applies the
participant-blind equal-player 0.7.3 update so the final build preserves that
campaign rule.
"""
from __future__ import annotations

import py_compile
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

TARGET_VERSION = "0.7.4"
TARGET_BUILD = "participant-blind-qwen-auto-bootstrap-v14-20260720"
EQUAL_UPDATE_URL = (
    "https://raw.githubusercontent.com/Rage24ds/Rage24ds.github.io/"
    "master/downloads/CrownlessTable_v0_7_3_equal_players.py"
)

OLD_QWEN_METHOD = '''    def _qwen_python(self) -> Path | None:
        lab = self._voice_lab_root()
        candidates = [
            lab / "envs" / "qwen3_tts" / "python.exe",
            lab / "envs" / "qwen3_voice" / "python.exe",
            lab / "envs" / "qwen_voice_design" / "python.exe",
        ]
        return next((p for p in candidates if p.is_file()), None)
'''

NEW_QWEN_METHODS = r'''    def _qwen_env_root(self) -> Path:
        return self._voice_lab_root() / "envs" / "qwen3_tts"

    def _qwen_install_lock(self) -> Path:
        return self._qwen_env_root() / ".crownless-installing"

    def _qwen_python(self) -> Path | None:
        lab = self._voice_lab_root()
        candidates = [
            lab / "envs" / "qwen3_tts" / "Scripts" / "python.exe",
            lab / "envs" / "qwen3_tts" / "python.exe",
            lab / "envs" / "qwen3-tts" / "Scripts" / "python.exe",
            lab / "envs" / "qwen3_voice" / "Scripts" / "python.exe",
            lab / "envs" / "qwen3_voice" / "python.exe",
            lab / "envs" / "qwen_voice_design" / "Scripts" / "python.exe",
            lab / "envs" / "qwen_voice_design" / "python.exe",
            lab / "envs" / "qwen3_voice_design" / "Scripts" / "python.exe",
        ]
        downloads = Path.home() / "Downloads"
        if downloads.is_dir():
            for root in downloads.glob("Qwen3*"):
                candidates.extend(
                    [
                        root / ".venv" / "Scripts" / "python.exe",
                        root / "venv" / "Scripts" / "python.exe",
                        root / "env" / "Scripts" / "python.exe",
                        root / "python" / "python.exe",
                    ]
                )
        return next((path.resolve() for path in candidates if path.is_file()), None)

    @staticmethod
    def _powershell_literal(value: str) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    def _start_qwen_installer(self) -> dict[str, Any]:
        existing = self._qwen_python()
        if existing:
            return {"started": False, "already_installed": True, "python": str(existing)}

        env_root = self._qwen_env_root()
        env_python = env_root / "Scripts" / "python.exe"
        lock = self._qwen_install_lock()
        process = self.voice_processes.get("qwen_installer")
        if process is not None and process.poll() is None:
            return {"started": False, "installing": True, "pid": process.pid, "environment": str(env_root)}
        if lock.exists():
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                age = 0
            if age < 7200:
                return {"started": False, "installing": True, "environment": str(env_root)}
            with contextlib.suppress(OSError):
                lock.unlink()

        env_root.mkdir(parents=True, exist_ok=True)
        lock.write_text(now_iso(), "utf-8")
        server_script = self._write_qwen_voice_server()
        installer = self._voice_service_dir() / "install_qwen_voice_design.ps1"
        q = self._powershell_literal
        lines = [
            "$ErrorActionPreference = 'Stop'",
            f"$SourcePython = {q(str(sys.executable))}",
            f"$EnvDir = {q(str(env_root))}",
            f"$EnvPython = {q(str(env_python))}",
            f"$ServerScript = {q(str(server_script))}",
            f"$LockFile = {q(str(lock))}",
            "function Run-Step([string]$Exe, [string[]]$Arguments, [string]$Name) {",
            "    Write-Host ''",
            "    Write-Host ('=== ' + $Name + ' ===') -ForegroundColor Cyan",
            "    & $Exe @Arguments",
            "    if ($LASTEXITCODE -ne 0) { throw ($Name + ' failed with exit code ' + $LASTEXITCODE) }",
            "}",
            "try {",
            "    New-Item -ItemType Directory -Force -Path (Split-Path $EnvDir) | Out-Null",
            "    if (-not (Test-Path $EnvPython)) {",
            "        Run-Step $SourcePython @('-m','venv',$EnvDir) 'Create isolated Qwen environment'",
            "    }",
            "    Run-Step $EnvPython @('-m','pip','install','--upgrade','pip','setuptools','wheel') 'Update Python packaging tools'",
            "    Run-Step $EnvPython @('-m','pip','install','--upgrade','torch==2.6.0','torchaudio==2.6.0','--index-url','https://download.pytorch.org/whl/cu126') 'Install CUDA PyTorch runtime'",
            "    Run-Step $EnvPython @('-m','pip','install','--upgrade','qwen-tts==0.1.1') 'Install Qwen3-TTS VoiceDesign'",
            "    Run-Step $EnvPython @('-c',\"import torch; from qwen_tts import Qwen3TTSModel; assert torch.cuda.is_available(), 'CUDA is not available'; print('Qwen ready:', torch.__version__, 'CUDA', torch.version.cuda)\") 'Verify Qwen and CUDA'",
            "    Write-Host ''",
            "    Write-Host 'Qwen VoiceDesign installed. Starting the local API on port 7811.' -ForegroundColor Green",
            "    Start-Process -FilePath $EnvPython -ArgumentList @($ServerScript) -WorkingDirectory (Split-Path $ServerScript)",
            "} catch {",
            "    Write-Host ''",
            "    Write-Host ('Qwen VoiceDesign installation failed: ' + $_.Exception.Message) -ForegroundColor Red",
            "    Read-Host 'Press Enter to close this installer'",
            "    exit 1",
            "} finally {",
            "    Remove-Item $LockFile -Force -ErrorAction SilentlyContinue",
            "}",
        ]
        installer.write_text("\n".join(lines) + "\n", "utf-8")
        powershell = shutil.which("powershell.exe") or shutil.which("powershell") or "powershell.exe"
        result = self._voice_spawn(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(installer)],
            installer.parent,
            "qwen_installer",
        )
        if not result.get("started"):
            with contextlib.suppress(OSError):
                lock.unlink()
        result["installing"] = bool(result.get("started"))
        result["environment"] = str(env_root)
        result["message"] = (
            "A one-time Qwen VoiceDesign installer was opened. The model environment is reused after installation."
        )
        return result
'''

OLD_MISSING_BRANCH = '''                else:
                    results["qwen_voice_design"] = {
                        "started": False,
                        "error": "The qwen3_tts environment was not found in AICompanionVoiceLab.",
                    }
'''

NEW_MISSING_BRANCH = '''                else:
                    results["qwen_voice_design"] = self._start_qwen_installer()
'''

OLD_SNAPSHOT = '''            "qwen_voice_design": {"port": 7811, "ready": self._voice_port_open(7811), "python": str(self._qwen_python() or "")},
'''
NEW_SNAPSHOT = '''            "qwen_voice_design": {
                "port": 7811,
                "ready": self._voice_port_open(7811),
                "python": str(self._qwen_python() or ""),
                "installing": self._qwen_install_lock().exists(),
                "environment": str(self._qwen_env_root()),
            },
'''


def fail(message: str) -> "NoReturn":
    print(f"\nERROR: {message}")
    raise SystemExit(1)


def download(url: str, destination: Path) -> None:
    with urllib.request.urlopen(url, timeout=45) as response:
        destination.write_bytes(response.read())


def installed_path() -> Path:
    return Path.home() / "Documents" / "CrownlessTable" / "CrownlessTable.py"


def ensure_equal_player_build() -> Path:
    installed = installed_path()
    if not installed.is_file():
        fail("The installed CrownlessTable.py file was not found.")
    try:
        py_compile.compile(str(installed), doraise=True)
    except Exception as exc:
        fail(f"The installed application does not compile: {exc}")
    text = installed.read_text("utf-8", errors="replace")
    if 'VERSION = "0.7.3"' in text:
        return installed
    if 'VERSION = "0.7.2"' not in text:
        fail("This updater requires a valid Crownless Table 0.7.2 or 0.7.3 installation.")
    print("Applying the participant-blind equal-player update first...")
    updater = Path.cwd() / "CrownlessTable_v0_7_3_equal_players.py"
    download(EQUAL_UPDATE_URL, updater)
    result = subprocess.run([sys.executable, str(updater)], cwd=str(Path.cwd()), check=False)
    if result.returncode != 0:
        fail("The prerequisite equal-player update failed. The installed application was preserved.")
    text = installed.read_text("utf-8", errors="replace")
    if 'VERSION = "0.7.3"' not in text:
        fail("The equal-player updater completed but the installed application is not version 0.7.3.")
    return installed


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"Patch point {label!r} expected once but was found {count} times.")
    return text.replace(old, new, 1)


def patch(text: str) -> str:
    text = replace_once(text, 'VERSION = "0.7.3"', f'VERSION = "{TARGET_VERSION}"', "version")
    text = replace_once(
        text,
        'BUILD_ID = "participant-blind-equal-player-table-v13-20260720"',
        f'BUILD_ID = "{TARGET_BUILD}"',
        "build id",
    )
    text = replace_once(text, OLD_QWEN_METHOD, NEW_QWEN_METHODS, "Qwen environment discovery and bootstrap")
    text = replace_once(text, OLD_MISSING_BRANCH, NEW_MISSING_BRANCH, "missing Qwen environment behavior")
    text = replace_once(text, OLD_SNAPSHOT, NEW_SNAPSHOT, "Qwen service status")
    return text


def main() -> int:
    source = ensure_equal_player_build()
    print(f"Adding automatic Qwen VoiceDesign setup to: {source}")
    output = Path.cwd() / "CrownlessTable_v0_7_4.py"
    output.write_text(patch(source.read_text("utf-8")), "utf-8")
    try:
        py_compile.compile(str(output), doraise=True)
    except Exception as exc:
        output.unlink(missing_ok=True)
        fail(f"The generated 0.7.4 application did not compile: {exc}")

    test = subprocess.run(
        [sys.executable, str(output), "--self-test"],
        cwd=str(output.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    if test.returncode != 0:
        output.unlink(missing_ok=True)
        fail("The generated application failed its self-test.\n" + test.stdout + "\n" + test.stderr)

    installed = installed_path()
    backup = installed.parent / "CrownlessTable_v0_7_3_backup.py"
    if installed.exists() and not backup.exists():
        shutil.copy2(installed, backup)
    shutil.copy2(output, installed)
    py_compile.compile(str(installed), doraise=True)

    print("\nCrownless Table 0.7.4 installed successfully.")
    print("The missing Qwen VoiceDesign environment will now install automatically when the voice stack starts.")
    print("Self-test output:")
    print(test.stdout.strip())
    print("\nRun:")
    print(f'  py "{installed}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
