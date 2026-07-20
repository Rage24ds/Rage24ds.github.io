#!/usr/bin/env python3
"""Repair the Crownless Table 0.5 upgrade on Windows.

The 0.5.0 feature upgrade passed its assertions but leaked SQLite connections.
Windows then refused to delete the temporary campaign.db, causing the upgrader
mistakenly to report failure and leave 0.4.2 installed.

This repair:
1. Patches the 0.4.2 database context manager so every connection closes.
2. Reuses the existing 0.5.0 feature upgrader in an isolated temporary folder.
3. Produces and installs Crownless Table 0.5.1 only after its self-test exits 0.
"""
from __future__ import annotations

import py_compile
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

OLD_UPGRADER_URL = (
    "https://raw.githubusercontent.com/Rage24ds/Rage24ds.github.io/"
    "master/downloads/CrownlessTable_v0_5_0_upgrade.py"
)

OLD_DB = '''    def db(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        return con
'''

NEW_DB = '''    @contextlib.contextmanager
    def db(self):
        con = sqlite3.connect(self.db_path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
'''


def fail(message: str) -> "NoReturn":
    print(f"\nERROR: {message}")
    raise SystemExit(1)


def locate_source() -> Path:
    cwd = Path.cwd()
    candidates = [
        cwd / "CrownlessTable_v0_4_2.py",
        Path.home() / "Downloads" / "New DND with ai" / "CrownlessTable_v0_4_2.py",
        Path.home() / "Documents" / "CrownlessTable" / "CrownlessTable.py",
        Path.home() / "Documents" / "CrownlessTable" / "CrownlessTable_v0_4_2_backup.py",
    ]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            text = candidate.read_text("utf-8")
        except OSError:
            continue
        if 'VERSION = "0.4.2"' in text and 'BUILD_ID = "antigravity-output-file-v6-20260720"' in text:
            return candidate.resolve()
    fail(
        "Crownless Table 0.4.2 was not found. Keep CrownlessTable_v0_4_2.py "
        "in this folder or keep the installed copy in Documents\\CrownlessTable."
    )


def load_feature_upgrader() -> str:
    local = Path.cwd() / "CrownlessTable_v0_5_0_upgrade.py"
    if local.is_file():
        return local.read_text("utf-8")
    try:
        with urllib.request.urlopen(OLD_UPGRADER_URL, timeout=30) as response:
            return response.read().decode("utf-8")
    except Exception as exc:
        fail(f"Could not download the 0.5 feature upgrader: {exc}")


def patch_source(text: str) -> str:
    if NEW_DB in text:
        return text
    count = text.count(OLD_DB)
    if count != 1:
        fail(f"Expected one old database helper but found {count}. The 0.4.2 file is not the expected build.")
    return text.replace(OLD_DB, NEW_DB, 1)


def patch_upgrader(text: str) -> str:
    replacements = [
        ('TARGET_VERSION = "0.5.0"', 'TARGET_VERSION = "0.5.1"'),
        (
            'TARGET_BUILD = "player-agency-neural-voice-v7-20260720"',
            'TARGET_BUILD = "player-agency-neural-voice-sqlite-fix-v8-20260720"',
        ),
        ('CrownlessTable_v0_5_0.py', 'CrownlessTable_v0_5_1.py'),
        ('Crownless Table 0.5.0 created successfully.', 'Crownless Table 0.5.1 created successfully.'),
    ]
    for old, new in replacements:
        if old not in text:
            fail(f"The feature upgrader is missing expected patch point: {old}")
        text = text.replace(old, new)
    return text


def main() -> int:
    source = locate_source()
    print(f"Base application: {source}")
    source_text = patch_source(source.read_text("utf-8"))
    upgrader_text = patch_upgrader(load_feature_upgrader())

    destination_dir = Path.cwd()
    final_output = destination_dir / "CrownlessTable_v0_5_1.py"

    with tempfile.TemporaryDirectory(prefix="crownless-repair-") as folder:
        work = Path(folder)
        patched_source = work / "CrownlessTable_v0_4_2.py"
        patched_upgrader = work / "CrownlessTable_v0_5_1_upgrade.py"
        patched_source.write_text(source_text, "utf-8")
        patched_upgrader.write_text(upgrader_text, "utf-8")
        py_compile.compile(str(patched_source), doraise=True)
        py_compile.compile(str(patched_upgrader), doraise=True)

        print("Running the repaired full upgrade and self-test...")
        result = subprocess.run(
            [sys.executable, str(patched_upgrader)],
            cwd=str(work),
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            fail(
                "The repaired upgrader still failed. Nothing was installed. "
                "Copy the full output from this window back into the chat."
            )

        generated = work / "CrownlessTable_v0_5_1.py"
        if not generated.is_file():
            fail("The repaired upgrader exited successfully but did not produce CrownlessTable_v0_5_1.py.")
        generated_text = generated.read_text("utf-8")
        if 'VERSION = "0.5.1"' not in generated_text:
            fail("The generated file does not identify itself as version 0.5.1.")
        if NEW_DB not in generated_text:
            fail("The generated file is missing the SQLite connection fix.")
        shutil.copy2(generated, final_output)

    installed = Path.home() / "Documents" / "CrownlessTable" / "CrownlessTable.py"
    if not installed.is_file() or 'VERSION = "0.5.1"' not in installed.read_text("utf-8"):
        fail("The self-test passed, but the Documents installation was not updated to 0.5.1.")

    print("\nRepair complete.")
    print(f"Download-folder copy: {final_output}")
    print(f"Installed copy: {installed}")
    print("\nLaunch it with:")
    print(f'  py "{installed}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
