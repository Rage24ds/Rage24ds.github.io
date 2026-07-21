#!/usr/bin/env python3
"""Robust Crownless Table 0.7.8 reference-audio duration repair.

The first 0.7.8 updater tried to edit Python code embedded inside the generated
voice-bridge raw string. That optional defense-in-depth patch depended on an
exact bridge snippet and failed against the 0.7.7 bridge layout.

This corrected updater fixes the actual data path instead:
- asks for a concise 6-10 word reference sentence;
- caps every returned reference line to 10 words;
- normalizes Qwen WAV output into GPT-SoVITS's required 3-10 second window;
- removes existing out-of-range bridge profiles and WAV files;
- clears only voice specs/assignments and disables automatic voice playback;
- preserves campaign events, characters, memories, transcript, world state, Git,
  and all non-voice settings.

It intentionally does not rewrite the embedded bridge source.
"""
from __future__ import annotations

import json
import py_compile
import shutil
import socket
import sqlite3
import subprocess
import sys
import wave
from pathlib import Path

SOURCE_VERSION = 'VERSION = "0.7.7"'
SOURCE_BUILD = 'BUILD_ID = "participant-blind-function-scoped-voice-recovery-v17-20260720"'
TARGET_VERSION = "0.7.8"
TARGET_BUILD = "participant-blind-reference-audio-normalization-v18-20260720"

OLD_REFERENCE_PROMPT = '  "reference_line": "one natural 8-20 second in-character line used to create and judge the voice",\n'
NEW_REFERENCE_PROMPT = '  "reference_line": "one natural in-character sentence of 6-10 words, intended to render in 4-7 seconds",\n'

OLD_SPEC_FINISH = '''                spec["speaker_name"] = self._voice_speaker_name(provider)
                spec["provider"] = provider
                results[provider] = spec
'''
NEW_SPEC_FINISH = '''                reference_words = str(spec.get("reference_line") or "").strip().split()
                if len(reference_words) < 6:
                    reference_words = str(self._fallback_voice_spec(provider)["reference_line"]).split()
                if len(reference_words) > 10:
                    reference_words = reference_words[:10]
                reference_line = " ".join(reference_words).strip()
                if reference_line and reference_line[-1] not in ".!?":
                    reference_line += "."
                spec["reference_line"] = reference_line
                spec["speaker_name"] = self._voice_speaker_name(provider)
                spec["provider"] = provider
                results[provider] = spec
'''

NORMALIZE_METHOD = r'''    @staticmethod
    def _normalize_reference_wav(path: Path, minimum_seconds: float = 3.2, maximum_seconds: float = 9.5) -> float:
        """Normalize a Qwen reference WAV into GPT-SoVITS's accepted duration window."""
        path = Path(path)
        converted = path.with_name(path.stem + "_pcm.wav")
        try:
            try:
                with wave.open(str(path), "rb") as source:
                    channels = source.getnchannels()
                    sample_width = source.getsampwidth()
                    frame_rate = source.getframerate()
                    frames = source.readframes(source.getnframes())
            except (wave.Error, EOFError):
                ffmpeg = shutil.which("ffmpeg")
                if not ffmpeg:
                    raise RuntimeError(
                        "Qwen returned a WAV format Python could not normalize, and FFmpeg was not found."
                    )
                result = subprocess.run(
                    [
                        ffmpeg,
                        "-y",
                        "-loglevel",
                        "error",
                        "-i",
                        str(path),
                        "-ac",
                        "1",
                        "-ar",
                        "32000",
                        "-c:a",
                        "pcm_s16le",
                        str(converted),
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                if result.returncode != 0 or not converted.is_file():
                    raise RuntimeError("FFmpeg could not normalize the Qwen reference WAV: " + result.stderr[-1600:])
                converted.replace(path)
                with wave.open(str(path), "rb") as source:
                    channels = source.getnchannels()
                    sample_width = source.getsampwidth()
                    frame_rate = source.getframerate()
                    frames = source.readframes(source.getnframes())

            if channels < 1 or sample_width < 1 or frame_rate < 8000:
                raise RuntimeError("Qwen returned an invalid reference WAV format.")
            frame_width = channels * sample_width
            frame_count = len(frames) // frame_width
            minimum_frames = int(frame_rate * minimum_seconds)
            maximum_frames = int(frame_rate * maximum_seconds)
            if frame_count > maximum_frames:
                frames = frames[: maximum_frames * frame_width]
                frame_count = maximum_frames
            elif frame_count < minimum_frames:
                missing = minimum_frames - frame_count
                silence_unit = (b"\x80" if sample_width == 1 else b"\x00" * sample_width) * channels
                frames += silence_unit * missing
                frame_count = minimum_frames

            normalized = path.with_name(path.stem + "_normalized.wav")
            with wave.open(str(normalized), "wb") as destination:
                destination.setnchannels(channels)
                destination.setsampwidth(sample_width)
                destination.setframerate(frame_rate)
                destination.setcomptype("NONE", "not compressed")
                destination.writeframes(frames)
            normalized.replace(path)
            duration = frame_count / float(frame_rate)
            if not minimum_seconds <= duration <= maximum_seconds:
                raise RuntimeError(f"Reference audio normalization produced an invalid duration: {duration:.2f}s")
            return duration
        finally:
            converted.unlink(missing_ok=True)

'''

OLD_REFERENCE_WRITE = '''            reference.write_bytes(audio)
            profile_name = f"Crownless {self._voice_speaker_name(provider)}"
'''
NEW_REFERENCE_WRITE = '''            reference.write_bytes(audio)
            reference_duration = self._normalize_reference_wav(reference)
            profile_name = f"Crownless {self._voice_speaker_name(provider)}"
'''

OLD_PROFILE_DESCRIPTION = '''                        f"Automatically designed for Crownless Table. {spec.get('voice_description', '')}",
'''
NEW_PROFILE_DESCRIPTION = '''                        f"Automatically designed for Crownless Table. Reference {reference_duration:.2f}s. {spec.get('voice_description', '')}",
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


def replace_in_method(text: str, marker: str, old: str, new: str, label: str) -> str:
    start = text.find(marker)
    if start < 0:
        fail(f"Method for patch point {label!r} was not found.")
    search_from = start + len(marker)
    boundaries = [
        text.find("\n    def ", search_from),
        text.find("\n    @staticmethod", search_from),
        text.find("\n    @classmethod", search_from),
    ]
    positions = [position for position in boundaries if position >= 0]
    end = min(positions) if positions else len(text)
    segment = text[start:end]
    count = segment.count(old)
    if count != 1:
        fail(f"Patch point {label!r} expected once inside {marker.strip()} but was found {count} times.")
    segment = segment.replace(old, new, 1)
    return text[:start] + segment + text[end:]


def patch(text: str) -> str:
    text = replace_once(text, SOURCE_VERSION, f'VERSION = "{TARGET_VERSION}"', "version")
    text = replace_once(text, SOURCE_BUILD, f'BUILD_ID = "{TARGET_BUILD}"', "build id")
    imports = text.split("EQUAL_PARTICIPANT_POLICY", 1)[0]
    if "import wave\n" not in imports:
        text = replace_once(text, "import webbrowser\n", "import webbrowser\nimport wave\n", "wave import")
    text = replace_once(text, OLD_REFERENCE_PROMPT, NEW_REFERENCE_PROMPT, "reference-line duration prompt")
    text = replace_once(text, OLD_SPEC_FINISH, NEW_SPEC_FINISH, "reference-line word cap")
    text = replace_once(
        text,
        "    def _create_qwen_voicebox_profile(self, provider: str, spec: dict[str, Any]) -> dict[str, Any]:\n",
        NORMALIZE_METHOD + "    def _create_qwen_voicebox_profile(self, provider: str, spec: dict[str, Any]) -> dict[str, Any]:\n",
        "reference WAV normalizer",
    )
    text = replace_in_method(
        text,
        "    def _create_qwen_voicebox_profile(",
        OLD_REFERENCE_WRITE,
        NEW_REFERENCE_WRITE,
        "normalize generated reference",
    )
    text = replace_in_method(
        text,
        "    def _create_qwen_voicebox_profile(",
        OLD_PROFILE_DESCRIPTION,
        NEW_PROFILE_DESCRIPTION,
        "record normalized duration",
    )
    return text


def wav_duration(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as source:
            rate = source.getframerate()
            return source.getnframes() / float(rate) if rate else None
    except Exception:
        return None


def clean_invalid_voice_state(home: Path) -> dict[str, int]:
    result = {"settings_reset": 0, "profiles_removed": 0, "audio_removed": 0}
    database = home / "campaign.db"
    if database.is_file():
        con = sqlite3.connect(database, timeout=30)
        try:
            for key, value in {
                "auto_voice": False,
                "auto_create_voices": False,
                "voice_specs_json": "{}",
                "voice_assignments_json": "{}",
            }.items():
                con.execute(
                    "INSERT INTO settings(key, value_json) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
                    (key, json.dumps(value)),
                )
                result["settings_reset"] += 1
            con.commit()
        finally:
            con.close()

    index = home / "voice_services" / "bridge_data" / "profiles.json"
    if index.is_file():
        try:
            profiles = json.loads(index.read_text("utf-8"))
        except Exception:
            profiles = []
        kept = []
        if isinstance(profiles, list):
            for profile in profiles:
                if not isinstance(profile, dict):
                    result["profiles_removed"] += 1
                    continue
                path_value = str(profile.get("ref_audio_path") or "")
                path = Path(path_value) if path_value else None
                duration = wav_duration(path) if path is not None and path.is_file() else None
                if duration is not None and 3.0 <= duration <= 10.0:
                    kept.append(profile)
                else:
                    result["profiles_removed"] += 1
                    if path is not None and path.is_file():
                        path.unlink(missing_ok=True)
                        result["audio_removed"] += 1
            index.write_text(json.dumps(kept, ensure_ascii=False, indent=2), "utf-8")
    return result


def main() -> int:
    if port_open(8765):
        fail("Crownless Table is still running. Press Ctrl+C, close the old voice-bridge window, then run this update.")
    source = installed_path()
    if not source.is_file():
        fail("The installed CrownlessTable.py file was not found.")
    try:
        py_compile.compile(str(source), doraise=True)
    except Exception as exc:
        fail(f"The installed application does not compile: {exc}")
    current = source.read_text("utf-8", errors="replace")
    if SOURCE_VERSION not in current or SOURCE_BUILD not in current:
        fail("This corrected updater requires the installed Crownless Table 0.7.7 build.")

    output = Path.cwd() / "CrownlessTable_v0_7_8.py"
    output.write_text(patch(current), "utf-8")
    try:
        py_compile.compile(str(output), doraise=True)
    except Exception as exc:
        output.unlink(missing_ok=True)
        fail(f"The generated 0.7.8 application did not compile: {exc}")

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

    backup = source.parent / "CrownlessTable_v0_7_7_backup.py"
    if not backup.exists():
        shutil.copy2(source, backup)
    shutil.copy2(output, source)
    py_compile.compile(str(source), doraise=True)
    cleaned = clean_invalid_voice_state(source.parent)

    print("\nCrownless Table 0.7.8 installed successfully.")
    print(f"Voice settings reset: {cleaned['settings_reset']}")
    print(f"Invalid reference profiles removed: {cleaned['profiles_removed']}")
    print(f"Invalid reference WAV files removed: {cleaned['audio_removed']}")
    print("Campaign content was preserved.")
    print("Self-test output:")
    print(test.stdout.strip())
    print("\nRun:")
    print(f'  py "{source}"')
    print("\nThen use Start / repair voice stack, AI design voices, Choose / create voices, and Test cast.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
