#!/usr/bin/env python3
"""Run the direct Crownless Table voice recovery with current Qwen dependencies.

This wrapper uses the tested 0.7.5 recovery logic but routes its prerequisite
through the current Qwen bootstrap, then identifies the finished application as
0.7.6.
"""
from __future__ import annotations

import py_compile
import subprocess
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/Rage24ds/Rage24ds.github.io/"
    "master/downloads/CrownlessTable_v0_7_5_voice_recovery.py"
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
        fail(f"Could not download the voice recovery source: {exc}")

    text = replace_once(text, 'TARGET_VERSION = "0.7.5"', 'TARGET_VERSION = "0.7.6"', "target version")
    text = replace_once(
        text,
        'TARGET_BUILD = "participant-blind-voice-recovery-v15-20260720"',
        'TARGET_BUILD = "participant-blind-current-qwen-voice-recovery-v16-20260720"',
        "target build",
    )
    text = replace_once(
        text,
        'master/downloads/CrownlessTable_v0_7_4_qwen_bootstrap.py',
        'master/downloads/CrownlessTable_qwen_bootstrap_current.py',
        "current Qwen bootstrap URL",
    )
    text = text.replace('VERSION = "0.7.5"', 'VERSION = "0.7.6"')
    text = text.replace('CrownlessTable_v0_7_5.py', 'CrownlessTable_v0_7_6.py')
    text = text.replace('Crownless Table 0.7.5 voice recovery completed.', 'Crownless Table 0.7.6 voice recovery completed.')

    internal = Path.cwd() / "CrownlessTable_v0_7_6_recovery_internal.py"
    internal.write_text(text, "utf-8")
    try:
        py_compile.compile(str(internal), doraise=True)
    except Exception as exc:
        internal.unlink(missing_ok=True)
        fail(f"The final recovery updater did not compile: {exc}")

    print("Crownless Table 0.7.6 recovery updater compiled successfully.")
    result = subprocess.run([sys.executable, str(internal)], cwd=str(Path.cwd()), check=False)
    if result.returncode != 0:
        fail("The direct recovery failed. The previous installed application was preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
