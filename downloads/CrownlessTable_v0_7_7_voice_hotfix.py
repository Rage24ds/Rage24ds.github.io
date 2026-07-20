#!/usr/bin/env python3
"""Function-scoped voice recovery for Crownless Table.

This replaces the failed generic HTTP patch used by the earlier recovery. The
same urlopen block appears in two helpers, so this updater edits only the
_voice_json_request method. It accepts the participant-blind 0.7.4 build left
by the previous attempt, preserves the campaign, clears incomplete voice state,
and installs 0.7.7 only after compilation and the built-in self-test pass.
"""
from __future__ import annotations

import json
import py_compile
import shutil
import socket
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path

TARGET_VERSION = "0.7.7"
TARGET_BUILD = "participant-blind-function-scoped-voice-recovery-v17-20260720"
SOURCE_VERSION = 'VERSION = "0.7.4"'
SOURCE_BUILD = 'BUILD_ID = "participant-blind-qwen-auto-bootstrap-v14-20260720"'
BOOTSTRAP_URL = (
    "https://raw.githubusercontent.com/Rage24ds/Rage24ds.github.io/"
    "master/downloads/CrownlessTable_qwen_bootstrap_current.py"
)

OLD_HTTP = '''        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else None
'''
NEW_HTTP = '''        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Local voice service rejected the request with HTTP {exc.code}: "
                + clamp_text(detail or exc.reason, 2400)
            ) from exc
        return json.loads(raw.decode("utf-8")) if raw else None
'''

OLD_ASSIGNMENT = '''            assignments = self._voice_settings_json("voice_assignments_json")
            assignment = assignments.get(provider) if isinstance(assignments, dict) else None
            if not isinstance(assignment, dict) or not assignment.get("profile_id"):
                self.build_ai_voices()
                assignments = self._voice_settings_json("voice_assignments_json")
                assignment = assignments.get(provider, {})
'''
NEW_ASSIGNMENT = '''            assignments = self._voice_settings_json("voice_assignments_json")
            assignment = assignments.get(provider) if isinstance(assignments, dict) else None
            if not isinstance(assignment, dict) or not assignment.get("profile_id"):
                status = self.voice_service_snapshot()
                qwen = status.get("qwen_voice_design", {})
                if qwen.get("installing") or not qwen.get("ready"):
                    raise RuntimeError(
                        "The local character voices are not ready yet. Let the one-time Qwen VoiceDesign installer finish, "
                        "press Start / repair voice stack, then press AI design voices and Choose / create voices."
                    )
                self.build_ai_voices()
                assignments = self._voice_settings_json("voice_assignments_json")
                assignment = assignments.get(provider, {})
            if not isinstance(assignment, dict) or not assignment.get("profile_id"):
                raise RuntimeError("No completed local voice assignment exists for this speaker yet.")
'''

OLD_PROFILE_ROUTE = '''        if path == "/profiles":
            self.send_json(load_profiles())
            return
'''
NEW_PROFILE_ROUTE = '''        if path == "/profiles":
            profiles = []
            for profile in load_profiles():
                reference = str(profile.get("ref_audio_path") or "")
                if reference and Path(reference).is_file():
                    profiles.append(profile)
            self.send_json(profiles)
            return
'''

OLD_AUTO_VOICE = '''  const newest=events.length?events[events.length-1].id:0;if(initialized&&state.settings.auto_voice){const fresh=events.filter(e=>e.id>window.lastSpokenId&&e.kind!=='player'&&e.kind!=='error');for(const e of fresh)speak(e.public_text,e.provider)}window.lastSpokenId=newest;initialized=true;
'''
NEW_AUTO_VOICE = '''  const newest=events.length?events[events.length-1].id:0;const castReady=Object.keys((state.voice&&state.voice.assignments)||{}).length>=4;if(initialized&&state.settings.auto_voice&&castReady){const fresh=events.filter(e=>e.id>window.lastSpokenId&&e.kind!=='player'&&e.kind!=='error');for(const e of fresh)speak(e.public_text,e.provider)}window.lastSpokenId=newest;initialized=true;
'''


def fail(message: str) -> "NoReturn":
    print(f"\nERROR: {message}")
    raise SystemExit(1)


def installed_path() -> Path:
    return Path.home() / "Documents" / "CrownlessTable" / "CrownlessTable.py"


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"Patch point {label!r} expected once but was found {count} times.")
    return text.replace(old, new, 1)


def replace_in_method(text: str, method_marker: str, old: str, new: str, label: str) -> str:
    start = text.find(method_marker)
    if start < 0:
        fail(f"Method for patch point {label!r} was not found.")
    search_from = start + len(method_marker)
    boundaries = [
        text.find("\n    def ", search_from),
        text.find("\n    @staticmethod", search_from),
        text.find("\n    @classmethod", search_from),
    ]
    valid = [position for position in boundaries if position >= 0]
    end = min(valid) if valid else len(text)
    segment = text[start:end]
    count = segment.count(old)
    if count != 1:
        fail(
            f"Patch point {label!r} expected once inside {method_marker.strip()} but was found {count} times there."
        )
    segment = segment.replace(old, new, 1)
    return text[:start] + segment + text[end:]


def ensure_074() -> Path:
    installed = installed_path()
    if not installed.is_file():
        fail("The installed CrownlessTable.py file was not found.")
    try:
        py_compile.compile(str(installed), doraise=True)
    except Exception as exc:
        fail(f"The installed application does not compile: {exc}")
    text = installed.read_text("utf-8", errors="replace")
    if SOURCE_VERSION in text and SOURCE_BUILD in text:
        return installed
    if f'VERSION = "{TARGET_VERSION}"' in text and TARGET_BUILD in text:
        return installed
    if 'VERSION = "0.7.2"' in text or 'VERSION = "0.7.3"' in text:
        print("Applying participant-blind rules and automatic Qwen setup first...")
        bootstrap = Path.cwd() / "CrownlessTable_qwen_bootstrap_current.py"
        try:
            with urllib.request.urlopen(BOOTSTRAP_URL, timeout=45) as response:
                bootstrap.write_bytes(response.read())
        except Exception as exc:
            fail(f"Could not download the prerequisite Qwen bootstrap: {exc}")
        result = subprocess.run([sys.executable, str(bootstrap)], cwd=str(Path.cwd()), check=False)
        if result.returncode != 0:
            fail("The prerequisite update failed. The previous installation was preserved.")
        text = installed.read_text("utf-8", errors="replace")
        if SOURCE_VERSION in text and SOURCE_BUILD in text:
            return installed
    fail(
        "This hotfix requires the valid Crownless Table 0.7.4 build left by the previous recovery attempt. "
        "The installed version/build did not match."
    )


def patch_application(text: str) -> str:
    text = replace_once(text, SOURCE_VERSION, f'VERSION = "{TARGET_VERSION}"', "version")
    text = replace_once(text, SOURCE_BUILD, f'BUILD_ID = "{TARGET_BUILD}"', "build id")
    if "import urllib.error\n" not in text:
        text = replace_once(
            text,
            "import urllib.parse\n",
            "import urllib.error\nimport urllib.parse\n",
            "urllib.error import",
        )
    text = replace_in_method(
        text,
        "    def _voice_json_request(",
        OLD_HTTP,
        NEW_HTTP,
        "voice HTTP diagnostics",
    )
    text = replace_once(text, OLD_ASSIGNMENT, NEW_ASSIGNMENT, "voice assignment readiness")
    text = replace_once(text, OLD_PROFILE_ROUTE, NEW_PROFILE_ROUTE, "fallback profile validation")
    text = replace_once(text, OLD_AUTO_VOICE, NEW_AUTO_VOICE, "automatic playback readiness")
    return text


def clean_voice_state(home: Path) -> dict[str, int]:
    result = {"settings_reset": 0, "invalid_profiles_removed": 0}
    database = home / "campaign.db"
    if database.is_file():
        con = sqlite3.connect(database, timeout=30)
        try:
            values = {
                "auto_voice": False,
                "auto_create_voices": False,
                "voice_assignments_json": "{}",
            }
            for key, value in values.items():
                con.execute(
                    "INSERT INTO settings(key, value_json) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
                    (key, json.dumps(value)),
                )
                result["settings_reset"] += 1
            con.commit()
        finally:
            con.close()

    profile_index = home / "voice_services" / "bridge_data" / "profiles.json"
    if profile_index.is_file():
        try:
            profiles = json.loads(profile_index.read_text("utf-8"))
        except Exception:
            profiles = []
        if isinstance(profiles, list):
            valid = []
            for profile in profiles:
                reference_value = str(profile.get("ref_audio_path") or "") if isinstance(profile, dict) else ""
                reference = Path(reference_value) if reference_value else None
                if isinstance(profile, dict) and reference is not None and reference.is_file():
                    valid.append(profile)
                else:
                    result["invalid_profiles_removed"] += 1
            profile_index.write_text(json.dumps(valid, ensure_ascii=False, indent=2), "utf-8")
    return result


def main() -> int:
    if port_open(8765):
        fail("Crownless Table is still running. Press Ctrl+C in its window, then run this hotfix again.")

    source = ensure_074()
    current = source.read_text("utf-8", errors="replace")
    if f'VERSION = "{TARGET_VERSION}"' in current and TARGET_BUILD in current:
        installed = source
        print("Crownless Table 0.7.7 is already installed; refreshing the damaged voice state.")
    else:
        print(f"Applying function-scoped voice recovery to: {source}")
        generated = Path.cwd() / "CrownlessTable_v0_7_7.py"
        generated.write_text(patch_application(current), "utf-8")
        try:
            py_compile.compile(str(generated), doraise=True)
        except Exception as exc:
            generated.unlink(missing_ok=True)
            fail(f"The generated 0.7.7 application did not compile: {exc}")

        test = subprocess.run(
            [sys.executable, str(generated), "--self-test"],
            cwd=str(generated.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
        if test.returncode != 0:
            generated.unlink(missing_ok=True)
            fail("The generated application failed its self-test.\n" + test.stdout + "\n" + test.stderr)

        installed = installed_path()
        backup = installed.parent / "CrownlessTable_v0_7_4_backup.py"
        if installed.exists() and not backup.exists():
            shutil.copy2(installed, backup)
        shutil.copy2(generated, installed)
        py_compile.compile(str(installed), doraise=True)
        print(test.stdout.strip())

    cleaned = clean_voice_state(installed.parent)
    print("\nCrownless Table 0.7.7 voice recovery completed.")
    print(f"Voice settings reset: {cleaned['settings_reset']}")
    print(f"Incomplete fallback profiles removed: {cleaned['invalid_profiles_removed']}")
    print("Campaign events, characters, memories, and world state were preserved.")
    print("\nRun:")
    print(f'  py "{installed}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
