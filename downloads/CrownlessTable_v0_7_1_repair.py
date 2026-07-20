#!/usr/bin/env python3
"""Repair and run the Crownless Table 0.7 one-click voice-stack upgrade.

The original 0.7.0 upgrader embedded two Python server programs inside another
triple-single-quoted string. This wrapper changes the outer delimiter to triple
double quotes, upgrades the generated app identifier to 0.7.1, compiles the
repaired upgrader, and only then executes it.
"""
from __future__ import annotations

import py_compile
import subprocess
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/Rage24ds/Rage24ds.github.io/"
    "master/downloads/CrownlessTable_v0_7_0_upgrade.py"
)


def fail(message: str) -> "NoReturn":
    print(f"\nERROR: {message}")
    raise SystemExit(1)


def main() -> int:
    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=45) as response:
            text = response.read().decode("utf-8")
    except Exception as exc:
        fail(f"Could not download the 0.7.0 source upgrader: {exc}")

    opening = "SERVICE_METHODS = r'''"
    closing = "\n'''\n\n\ndef patch(text: str) -> str:"
    if text.count(opening) != 1:
        fail("The expected SERVICE_METHODS opening delimiter was not found exactly once.")
    if text.count(closing) != 1:
        fail("The expected SERVICE_METHODS closing delimiter was not found exactly once.")

    text = text.replace(opening, 'SERVICE_METHODS = r"""', 1)
    text = text.replace(closing, '\n"""\n\n\ndef patch(text: str) -> str:', 1)
    text = text.replace('VERSION = "0.7.0"', 'VERSION = "0.7.1"', 1)
    text = text.replace(
        'BUILD = "one-click-local-voice-stack-document-scroll-v10-20260720"',
        'BUILD = "one-click-local-voice-stack-document-scroll-v11-20260720"',
        1,
    )
    text = text.replace('CrownlessTable_v0_7_0.py', 'CrownlessTable_v0_7_1.py')
    text = text.replace('Crownless Table 0.7.0 installed successfully.', 'Crownless Table 0.7.1 installed successfully.')

    repaired = Path.cwd() / "CrownlessTable_v0_7_1_upgrade_internal.py"
    repaired.write_text(text, "utf-8")
    try:
        py_compile.compile(str(repaired), doraise=True)
    except Exception as exc:
        repaired.unlink(missing_ok=True)
        fail(f"The repaired upgrader still did not compile: {exc}")

    print("The repaired 0.7.1 upgrader compiled successfully.")
    result = subprocess.run([sys.executable, str(repaired)], cwd=str(Path.cwd()), check=False)
    if result.returncode != 0:
        fail("The repaired upgrade failed. The existing installed Crownless Table file was preserved.")

    installed = Path.home() / "Documents" / "CrownlessTable" / "CrownlessTable.py"
    if not installed.is_file():
        fail("The upgrade exited successfully but the installed CrownlessTable.py file is missing.")
    installed_text = installed.read_text("utf-8", errors="replace")
    if 'VERSION = "0.7.1"' not in installed_text:
        fail("The installed application does not identify itself as Crownless Table 0.7.1.")

    print("\nCrownless Table 0.7.1 is installed.")
    print("Run this single file; it starts the required local voice services itself:")
    print(f'  py "{installed}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
