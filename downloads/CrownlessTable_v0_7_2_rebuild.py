#!/usr/bin/env python3
"""Cleanly rebuild Crownless Table 0.7.2 from the last valid foundation.

Why this exists:
- the 0.6 generator used a regex replacement string for generated Python code;
- Python's regex engine interpreted \r and \n escapes inside that replacement;
- an invalid CrownlessTable_v0_6_0.py was written before compilation failed;
- later upgraders found that stale file and treated it as a valid foundation.

This rebuild fixes the generator itself, regenerates and validates 0.6.0 from
0.5.1, then applies the repaired one-click voice-stack upgrade as 0.7.2.
Nothing replaces the installed application until each generated stage compiles
and passes its built-in self-test.
"""
from __future__ import annotations

import py_compile
import subprocess
import sys
import urllib.request
from pathlib import Path

V060_URL = (
    "https://raw.githubusercontent.com/Rage24ds/Rage24ds.github.io/"
    "master/downloads/CrownlessTable_v0_6_0_upgrade.py"
)
V070_URL = (
    "https://raw.githubusercontent.com/Rage24ds/Rage24ds.github.io/"
    "master/downloads/CrownlessTable_v0_7_0_upgrade.py"
)

BAD_REGEX = "updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)"
SAFE_REGEX = "updated, count = re.subn(pattern, lambda _match: replacement, text, count=1, flags=re.DOTALL)"


def fail(message: str) -> "NoReturn":
    print(f"\nERROR: {message}")
    raise SystemExit(1)


def download_text(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=45) as response:
            return response.read().decode("utf-8")
    except Exception as exc:
        fail(f"Could not download {url}: {exc}")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"Patch point {label!r} expected once but was found {count} times.")
    return text.replace(old, new, 1)


def run_checked(script: Path, label: str) -> None:
    try:
        py_compile.compile(str(script), doraise=True)
    except Exception as exc:
        fail(f"{label} did not compile: {exc}")
    print(f"{label} compiled successfully.")
    result = subprocess.run([sys.executable, str(script)], cwd=str(Path.cwd()), check=False)
    if result.returncode != 0:
        fail(f"{label} failed. The previously installed application was preserved.")


def validate_application(path: Path, version: str, build: str) -> None:
    if not path.is_file():
        fail(f"Expected application file is missing: {path}")
    text = path.read_text("utf-8", errors="replace")
    if f'VERSION = "{version}"' not in text:
        fail(f"{path.name} does not identify itself as version {version}.")
    if f'BUILD_ID = "{build}"' not in text:
        fail(f"{path.name} does not contain the expected build id {build}.")
    try:
        py_compile.compile(str(path), doraise=True)
    except Exception as exc:
        fail(f"Generated Crownless Table {version} does not compile: {exc}")


def patch_060(text: str) -> str:
    text = replace_once(text, BAD_REGEX, SAFE_REGEX, "0.6 safe regex replacement")
    return text


def patch_070(text: str) -> str:
    opening = "SERVICE_METHODS = r'''"
    closing = "\n'''\n\n\ndef patch(text: str) -> str:"
    text = replace_once(text, opening, 'SERVICE_METHODS = r"""', "service-method opening delimiter")
    text = replace_once(text, closing, '\n"""\n\n\ndef patch(text: str) -> str:', "service-method closing delimiter")
    text = replace_once(text, BAD_REGEX, SAFE_REGEX, "0.7 safe regex replacement")

    broad_patch = '''    text = replace_once(
        text,
        '        self.ensure_git_repo()\\n',
        '        self.ensure_git_repo()\\n'
        '        if not self.demo_override:\\n'
        '            threading.Thread(target=self.ensure_voice_services, kwargs={"wait": False}, daemon=True).start()\\n',
        "automatic voice service launch",
    )
'''
    constructor_patch = '''    text = replace_once(
        text,
        '        self._init_db()\\n'
        '        self._seed_defaults()\\n'
        '        self.export_campaign()\\n'
        '        self.ensure_git_repo()\\n',
        '        self._init_db()\\n'
        '        self._seed_defaults()\\n'
        '        self.export_campaign()\\n'
        '        self.ensure_git_repo()\\n'
        '        if not self.demo_override:\\n'
        '            threading.Thread(target=self.ensure_voice_services, kwargs={"wait": False}, daemon=True).start()\\n',
        "automatic voice service launch",
    )
'''
    text = replace_once(text, broad_patch, constructor_patch, "constructor-specific voice startup")

    text = replace_once(text, 'VERSION = "0.7.0"', 'VERSION = "0.7.2"', "0.7.2 version")
    text = replace_once(
        text,
        'BUILD = "one-click-local-voice-stack-document-scroll-v10-20260720"',
        'BUILD = "one-click-local-voice-stack-document-scroll-v12-20260720"',
        "0.7.2 build id",
    )
    text = text.replace('CrownlessTable_v0_7_0.py', 'CrownlessTable_v0_7_2.py')
    text = text.replace(
        'Crownless Table 0.7.0 installed successfully.',
        'Crownless Table 0.7.2 installed successfully.',
    )
    return text


def main() -> int:
    cwd = Path.cwd()
    installed = Path.home() / "Documents" / "CrownlessTable" / "CrownlessTable.py"

    # Remove only stale generated/download-folder artifacts. The installed app is
    # intentionally left untouched until all regenerated stages pass.
    for name in (
        "CrownlessTable_v0_6_0.py",
        "CrownlessTable_v0_7_1.py",
        "CrownlessTable_v0_7_1_upgrade_internal.py",
        "CrownlessTable_v0_7_2.py",
        "CrownlessTable_v0_6_0_upgrade_fixed.py",
        "CrownlessTable_v0_7_2_upgrade_internal.py",
    ):
        (cwd / name).unlink(missing_ok=True)

    print("Stage 1/2: regenerating a valid Crownless Table 0.6.0...")
    fixed_060 = cwd / "CrownlessTable_v0_6_0_upgrade_fixed.py"
    fixed_060.write_text(patch_060(download_text(V060_URL)), "utf-8")
    run_checked(fixed_060, "Corrected 0.6.0 upgrader")

    generated_060 = cwd / "CrownlessTable_v0_6_0.py"
    if not generated_060.is_file() and installed.is_file():
        installed_text = installed.read_text("utf-8", errors="replace")
        if 'VERSION = "0.6.0"' in installed_text:
            generated_060.write_text(installed_text, "utf-8")
    validate_application(
        generated_060,
        "0.6.0",
        "local-ai-voice-casting-scroll-v9-20260720",
    )
    validate_application(
        installed,
        "0.6.0",
        "local-ai-voice-casting-scroll-v9-20260720",
    )

    print("\nStage 2/2: applying one-click voice services and document scrolling...")
    fixed_072 = cwd / "CrownlessTable_v0_7_2_upgrade_internal.py"
    fixed_072.write_text(patch_070(download_text(V070_URL)), "utf-8")
    run_checked(fixed_072, "Corrected 0.7.2 upgrader")

    generated_072 = cwd / "CrownlessTable_v0_7_2.py"
    validate_application(
        generated_072,
        "0.7.2",
        "one-click-local-voice-stack-document-scroll-v12-20260720",
    )
    validate_application(
        installed,
        "0.7.2",
        "one-click-local-voice-stack-document-scroll-v12-20260720",
    )

    print("\nCrownless Table 0.7.2 installed successfully.")
    print("The generated application and installed copy both compile.")
    print("Run the single installed file:")
    print(f'  py "{installed}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
