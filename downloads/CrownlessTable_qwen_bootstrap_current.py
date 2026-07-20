#!/usr/bin/env python3
"""Run the Crownless Table 0.7.4 Qwen bootstrap with current dependencies.

The original bootstrap pinned qwen-tts 0.1.1 and PyTorch 2.6.0. This wrapper
updates the generated installer before execution:
- prefers Python 3.12 when the Windows py launcher provides it;
- uses PyTorch 2.11.0 CUDA 12.6 wheels;
- installs the current unpinned qwen-tts release recommended by Qwen.
"""
from __future__ import annotations

import py_compile
import subprocess
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/Rage24ds/Rage24ds.github.io/"
    "master/downloads/CrownlessTable_v0_7_4_qwen_bootstrap.py"
)


def fail(message: str) -> "NoReturn":
    print(f"\nERROR: {message}")
    raise SystemExit(1)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"Patch point {label!r} expected once but was found {count} times.")
    return text.replace(old, new, 1)


def main() -> int:
    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=45) as response:
            text = response.read().decode("utf-8")
    except Exception as exc:
        fail(f"Could not download the Qwen bootstrap source: {exc}")

    text = replace_once(
        text,
        '            f"$SourcePython = {q(str(sys.executable))}",\n',
        '            f"$FallbackPython = {q(str(sys.executable))}",\n'
        '            "$SourcePython = $FallbackPython",\n'
        '            "$Py312 = & py -3.12 -c \'import sys; print(sys.executable)\' 2>$null",\n'
        '            "if ($LASTEXITCODE -eq 0 -and $Py312) { $SourcePython = $Py312.Trim() }",\n',
        "prefer Python 3.12",
    )
    text = replace_once(
        text,
        "'torch==2.6.0','torchaudio==2.6.0'",
        "'torch==2.11.0','torchaudio==2.11.0'",
        "supported CUDA PyTorch",
    )
    text = replace_once(
        text,
        "'qwen-tts==0.1.1'",
        "'qwen-tts'",
        "current Qwen package",
    )

    internal = Path.cwd() / "CrownlessTable_qwen_bootstrap_current_internal.py"
    internal.write_text(text, "utf-8")
    try:
        py_compile.compile(str(internal), doraise=True)
    except Exception as exc:
        internal.unlink(missing_ok=True)
        fail(f"The current Qwen bootstrap did not compile: {exc}")

    print("Current Qwen bootstrap compiled successfully.")
    result = subprocess.run([sys.executable, str(internal)], cwd=str(Path.cwd()), check=False)
    if result.returncode != 0:
        fail("The Qwen bootstrap failed. The previous Crownless Table installation was preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
