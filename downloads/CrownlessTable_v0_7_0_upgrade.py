#!/usr/bin/env python3
"""Upgrade Crownless Table 0.6.0 to 0.7.0.

This build replaces fragile nested scrolling with normal document scrolling and
turns the application into a one-click local voice stack launcher.

At application startup it:
- opens Voicebox when a native installation is found;
- otherwise starts a Voicebox-compatible local bridge;
- starts Qwen3-TTS VoiceDesign from AICompanionVoiceLab;
- starts GPT-SoVITS API v2 from AICompanionVoiceLab or D:\\Gpt\\GPT-SoVITS;
- exposes a Start / repair voice stack button in the room.

The fallback bridge preserves Crownless Table's existing profile/generation API
while using Qwen VoiceDesign references and GPT-SoVITS for human-sounding speech.
"""
from __future__ import annotations

import py_compile
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

VERSION = "0.7.0"
BUILD = "one-click-local-voice-stack-document-scroll-v10-20260720"
V060_URL = (
    "https://raw.githubusercontent.com/Rage24ds/Rage24ds.github.io/"
    "master/downloads/CrownlessTable_v0_6_0_upgrade.py"
)


def fail(message: str) -> "NoReturn":
    print(f"\nERROR: {message}")
    raise SystemExit(1)


def download(url: str, destination: Path) -> None:
    with urllib.request.urlopen(url, timeout=45) as response:
        destination.write_bytes(response.read())


def app_candidates() -> list[Path]:
    home = Path.home() / "Documents" / "CrownlessTable"
    cwd = Path.cwd()
    return [
        home / "CrownlessTable.py",
        cwd / "CrownlessTable_v0_6_0.py",
        cwd / "CrownlessTable.py",
        Path.home() / "Downloads" / "New DND with ai" / "CrownlessTable_v0_6_0.py",
    ]


def find_version(version: str) -> Path | None:
    marker = f'VERSION = "{version}"'
    for path in app_candidates():
        if not path.is_file():
            continue
        try:
            text = path.read_text("utf-8")
        except OSError:
            continue
        if marker in text:
            return path.resolve()
    return None


def ensure_060() -> Path:
    found = find_version("0.6.0")
    if found:
        return found
    print("Crownless Table 0.6.0 is not installed. Running its prerequisite upgrader...")
    upgrader = Path.cwd() / "CrownlessTable_v0_6_0_upgrade.py"
    if not upgrader.is_file():
        download(V060_URL, upgrader)
    result = subprocess.run([sys.executable, str(upgrader)], cwd=str(Path.cwd()), check=False)
    if result.returncode != 0:
        fail("The prerequisite 0.6.0 upgrade failed. The installed application was not replaced.")
    found = find_version("0.6.0")
    if not found:
        fail("The 0.6.0 upgrader completed but CrownlessTable 0.6.0 could not be found.")
    return found


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"Patch point {label!r} expected once but was found {count} times.")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        fail(f"Regex patch point {label!r} expected once but was found {count} times.")
    return updated


SERVICE_METHODS = r'''    @staticmethod
    def _voice_port_open(port: int, timeout: float = 0.35) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
                return True
        except OSError:
            return False

    def _voice_service_dir(self) -> Path:
        directory = self.home / "voice_services"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _voice_spawn(self, args: list[str], cwd: Path, label: str, env: dict[str, str] | None = None) -> dict[str, Any]:
        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        try:
            process = subprocess.Popen(
                args,
                cwd=str(cwd),
                env=env or dict(os.environ),
                creationflags=flags,
            )
            self.voice_processes[label] = process
            return {"started": True, "pid": process.pid, "command": subprocess.list2cmdline(args)}
        except Exception as exc:
            return {"started": False, "error": str(exc), "command": subprocess.list2cmdline(args)}

    @staticmethod
    def _wait_for_voice_port(port: int, seconds: int) -> bool:
        deadline = time.time() + max(1, seconds)
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", int(port)), timeout=0.45):
                    return True
            except OSError:
                time.sleep(0.5)
        return False

    def _find_voicebox_executable(self) -> Path | None:
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        program_files = [
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")),
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")),
        ]
        candidates = [
            local / "Programs" / "Voicebox" / "Voicebox.exe",
            local / "Programs" / "voicebox" / "Voicebox.exe",
            local / "Voicebox" / "Voicebox.exe",
            *(root / "Voicebox" / "Voicebox.exe" for root in program_files),
        ]
        command = shutil.which("voicebox") or shutil.which("Voicebox")
        if command:
            candidates.insert(0, Path(command))
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        programs = local / "Programs"
        if programs.is_dir():
            for candidate in programs.glob("**/Voicebox.exe"):
                if candidate.is_file():
                    return candidate.resolve()
        return None

    def _voice_lab_root(self) -> Path:
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return local / "AICompanionVoiceLab"

    def _gpt_sovits_paths(self) -> tuple[Path | None, Path | None]:
        lab = self._voice_lab_root()
        roots = [
            lab / "apps" / "GPT-SoVITS",
            Path(r"D:\Gpt\GPT-SoVITS"),
            Path.home() / "GPT-SoVITS",
            Path.home() / "Downloads" / "GPT-SoVITS",
        ]
        pythons = [
            lab / "envs" / "gpt_sovits" / "python.exe",
            Path(r"D:\Gpt\GPT-SoVITS\.venv\Scripts\python.exe"),
        ]
        root = next((p for p in roots if (p / "api_v2.py").is_file()), None)
        python = next((p for p in pythons if p.is_file()), None)
        if root and not python:
            local_venv = root / ".venv" / "Scripts" / "python.exe"
            if local_venv.is_file():
                python = local_venv
        return root, python

    def _qwen_python(self) -> Path | None:
        lab = self._voice_lab_root()
        candidates = [
            lab / "envs" / "qwen3_tts" / "python.exe",
            lab / "envs" / "qwen3_voice" / "python.exe",
            lab / "envs" / "qwen_voice_design" / "python.exe",
        ]
        return next((p for p in candidates if p.is_file()), None)

    def _write_qwen_voice_server(self) -> Path:
        path = self._voice_service_dir() / "qwen_voice_design_server.py"
        source = r'''from __future__ import annotations
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 7811
MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
MODEL = None
MODEL_LOCK = threading.Lock()


def get_model():
    global MODEL
    if MODEL is not None:
        return MODEL
    with MODEL_LOCK:
        if MODEL is not None:
            return MODEL
        import torch
        from qwen_tts import Qwen3TTSModel
        kwargs = {"device_map": "cuda:0", "dtype": torch.bfloat16}
        try:
            MODEL = Qwen3TTSModel.from_pretrained(MODEL_ID, attn_implementation="flash_attention_2", **kwargs)
        except Exception:
            MODEL = Qwen3TTSModel.from_pretrained(MODEL_ID, attn_implementation="sdpa", **kwargs)
        return MODEL


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("QwenVoiceDesign:", fmt % args)

    def send_json(self, value, status=200):
        raw = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.rstrip("/") == "/health":
            self.send_json({"ok": True, "model_loaded": MODEL is not None})
            return
        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path.rstrip("/") != "/v1/audio/speech/design":
            self.send_json({"error": "not found"}, 404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(size).decode("utf-8"))
            text = str(data.get("input") or data.get("text") or "").strip()
            language = str(data.get("language") or "English")
            instruct = str(data.get("voice_description") or data.get("instruct") or "A natural adult human voice")
            if not text:
                raise ValueError("input text is required")
            model = get_model()
            wavs, sample_rate = model.generate_voice_design(text=text, language=language, instruct=instruct)
            import soundfile as sf
            buffer = io.BytesIO()
            sf.write(buffer, wavs[0], sample_rate, format="WAV")
            raw = buffer.getvalue()
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)


if __name__ == "__main__":
    print(f"Qwen VoiceDesign API: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
'''
        path.write_text(source, "utf-8")
        return path

    def _write_voice_bridge(self) -> Path:
        path = self._voice_service_dir() / "crownless_voice_bridge.py"
        source = r'''from __future__ import annotations
import cgi
import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 17493
GPT_URL = "http://127.0.0.1:9880/tts"
ROOT = Path(__file__).resolve().parent / "bridge_data"
PROFILES = ROOT / "profiles"
GENERATIONS = ROOT / "generations"
INDEX = ROOT / "profiles.json"
PROFILES.mkdir(parents=True, exist_ok=True)
GENERATIONS.mkdir(parents=True, exist_ok=True)


def load_profiles():
    if not INDEX.is_file():
        return []
    try:
        value = json.loads(INDEX.read_text("utf-8"))
        return value if isinstance(value, list) else []
    except Exception:
        return []


def save_profiles(profiles):
    INDEX.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), "utf-8")


def profile_by_id(profile_id):
    return next((p for p in load_profiles() if str(p.get("id")) == str(profile_id)), None)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("CrownlessVoiceBridge:", fmt % args)

    def send_json(self, value, status=200):
        raw = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "/health":
            self.send_json({"ok": True, "backend": "Qwen VoiceDesign + GPT-SoVITS"})
            return
        if path == "/profiles":
            self.send_json(load_profiles())
            return
        if path == "/models/status":
            self.send_json({"models": [{"id": "gpt_sovits", "name": "GPT-SoVITS", "status": "ready"}]})
            return
        if path.startswith("/audio/"):
            generation_id = path.split("/")[-1]
            file_path = GENERATIONS / f"{generation_id}.wav"
            if not file_path.is_file():
                self.send_json({"error": "audio not found"}, 404)
                return
            raw = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        try:
            if path == "/profiles":
                size = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(size).decode("utf-8"))
                profiles = load_profiles()
                profile = {
                    "id": uuid.uuid4().hex,
                    "name": str(data.get("name") or "Crownless Voice"),
                    "description": str(data.get("description") or ""),
                    "language": str(data.get("language") or "en"),
                    "voice_type": "cloned",
                    "default_engine": "gpt_sovits",
                }
                profiles.append(profile)
                save_profiles(profiles)
                self.send_json(profile)
                return
            if path.startswith("/profiles/") and path.endswith("/samples"):
                profile_id = path.split("/")[2]
                profile = profile_by_id(profile_id)
                if not profile:
                    self.send_json({"error": "profile not found"}, 404)
                    return
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers.get("Content-Type", "")},
                )
                file_item = form["file"]
                reference_text = str(form.getfirst("reference_text", ""))
                sample_path = PROFILES / f"{profile_id}.wav"
                sample_path.write_bytes(file_item.file.read())
                profiles = load_profiles()
                for item in profiles:
                    if str(item.get("id")) == profile_id:
                        item["ref_audio_path"] = str(sample_path)
                        item["reference_text"] = reference_text
                save_profiles(profiles)
                self.send_json({"ok": True, "profile_id": profile_id})
                return
            if path == "/generate":
                size = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(size).decode("utf-8"))
                profile = profile_by_id(str(data.get("profile_id") or ""))
                if not profile or not profile.get("ref_audio_path"):
                    self.send_json({"error": "profile has no reference sample"}, 400)
                    return
                payload = {
                    "text": str(data.get("text") or ""),
                    "text_lang": "en",
                    "ref_audio_path": str(profile["ref_audio_path"]),
                    "aux_ref_audio_paths": [],
                    "prompt_text": str(profile.get("reference_text") or ""),
                    "prompt_lang": "en",
                    "text_split_method": "cut5",
                    "batch_size": 1,
                    "media_type": "wav",
                    "streaming_mode": False,
                    "speed_factor": 1.0,
                }
                request = urllib.request.Request(
                    GPT_URL,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(request, timeout=360) as response:
                        audio = response.read()
                except urllib.error.HTTPError as exc:
                    detail = exc.read().decode("utf-8", errors="replace")
                    self.send_json({"error": "GPT-SoVITS failed: " + detail}, 502)
                    return
                generation_id = uuid.uuid4().hex
                (GENERATIONS / f"{generation_id}.wav").write_bytes(audio)
                self.send_json({"id": generation_id})
                return
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)
            return
        self.send_json({"error": "not found"}, 404)


if __name__ == "__main__":
    print(f"Crownless local voice bridge: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
'''
        path.write_text(source, "utf-8")
        return path

    def voice_service_snapshot(self) -> dict[str, Any]:
        root, gpt_python = self._gpt_sovits_paths()
        return {
            "voice_api": {"port": 17493, "ready": self._voice_port_open(17493)},
            "qwen_voice_design": {"port": 7811, "ready": self._voice_port_open(7811), "python": str(self._qwen_python() or "")},
            "gpt_sovits": {"port": 9880, "ready": self._voice_port_open(9880), "root": str(root or ""), "python": str(gpt_python or "")},
            "voicebox_executable": str(self._find_voicebox_executable() or ""),
        }

    def ensure_voice_services(self, wait: bool = False) -> dict[str, Any]:
        if self.demo_override:
            return self.voice_service_snapshot()
        with self.voice_service_lock:
            results: dict[str, Any] = {}

            # GPT-SoVITS provides the stable cloned-voice runtime for the fallback bridge.
            if not self._voice_port_open(9880):
                root, python = self._gpt_sovits_paths()
                if root and python:
                    config = root / "GPT_SoVITS" / "configs" / "tts_infer.yaml"
                    args = [str(python), str(root / "api_v2.py"), "-a", "127.0.0.1", "-p", "9880"]
                    if config.is_file():
                        args += ["-c", str(config)]
                    env = dict(os.environ)
                    env["CUDA_VISIBLE_DEVICES"] = "0"
                    results["gpt_sovits"] = self._voice_spawn(args, root, "gpt_sovits", env)
                else:
                    results["gpt_sovits"] = {
                        "started": False,
                        "error": "GPT-SoVITS was not found under AICompanionVoiceLab or D:\\Gpt\\GPT-SoVITS.",
                    }
            else:
                results["gpt_sovits"] = {"started": False, "already_ready": True}

            # Qwen server starts quickly because the 1.7B model is loaded only on the first design request.
            if not self._voice_port_open(7811):
                python = self._qwen_python()
                if python:
                    script = self._write_qwen_voice_server()
                    env = dict(os.environ)
                    env["CUDA_VISIBLE_DEVICES"] = "0"
                    results["qwen_voice_design"] = self._voice_spawn(
                        [str(python), str(script)], script.parent, "qwen_voice_design", env
                    )
                else:
                    results["qwen_voice_design"] = {
                        "started": False,
                        "error": "The qwen3_tts environment was not found in AICompanionVoiceLab.",
                    }
            else:
                results["qwen_voice_design"] = {"started": False, "already_ready": True}

            # Prefer the real Voicebox application because it exposes Qwen, LuxTTS,
            # Chatterbox, Chatterbox Turbo, TADA, and Kokoro through one API.
            if not self._voice_port_open(17493):
                voicebox = self._find_voicebox_executable()
                if voicebox:
                    results["voicebox"] = self._voice_spawn([str(voicebox)], voicebox.parent, "voicebox")
                    self._wait_for_voice_port(17493, 18)
                if not self._voice_port_open(17493):
                    bridge = self._write_voice_bridge()
                    results["voice_bridge"] = self._voice_spawn(
                        [sys.executable, str(bridge)], bridge.parent, "voice_bridge"
                    )
            else:
                results["voice_api"] = {"started": False, "already_ready": True}

        if wait:
            self._wait_for_voice_port(9880, 90)
            self._wait_for_voice_port(7811, 15)
            self._wait_for_voice_port(17493, 25)
        snapshot = self.voice_service_snapshot()
        snapshot["launch_results"] = results
        return snapshot

'''


def patch(text: str) -> str:
    text = replace_once(text, 'VERSION = "0.6.0"', f'VERSION = "{VERSION}"', "version")
    text = replace_once(
        text,
        'BUILD_ID = "local-ai-voice-casting-scroll-v9-20260720"',
        f'BUILD_ID = "{BUILD}"',
        "build id",
    )

    # One normal document scroll. No nested fixed-height grid traps.
    text = regex_once(
        text,
        r'body\{margin:0;background:radial-gradient\(circle at top,#1c2433 0,#11141b 48%\);color:var\(--text\);font:15px/1\.45 system-ui,-apple-system,Segoe UI,sans-serif;.*?\}',
        'body{margin:0;background:radial-gradient(circle at top,#1c2433 0,#11141b 48%);color:var(--text);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;min-height:100vh;height:auto;overflow-x:hidden;overflow-y:auto}',
        "document body scroll",
    )
    text = regex_once(
        text,
        r'\.app\{display:grid;grid-template-columns:.*?\}',
        '.app{display:grid;grid-template-columns:minmax(300px,370px) minmax(0,1fr);align-items:start;min-height:100vh;height:auto;overflow:visible}',
        "document app layout",
    )
    text = regex_once(
        text,
        r'\.side\{background:rgba\(19,23,32,\.96\);border-right:1px solid var\(--line\);.*?padding:18px\}',
        '.side{background:rgba(19,23,32,.96);border-right:1px solid var(--line);min-height:100vh;height:auto;max-height:none;overflow:visible;padding:18px}',
        "sidebar normal flow",
    )
    text = regex_once(
        text,
        r'\.main\{display:grid;grid-template-rows:.*?\}',
        '.main{display:flex;flex-direction:column;min-width:0;min-height:100vh;height:auto;overflow:visible}',
        "main normal flow",
    )
    text = regex_once(
        text,
        r'\.feed\{.*?padding:22px 5vw 32px\}',
        '.feed{display:block;min-height:55vh;height:auto;overflow:visible;padding:22px 5vw 32px}',
        "feed normal flow",
    )
    text = text.replace('scrollbar-gutter:stable;', '')
    text = text.replace('overscroll-behavior:contain;', '')

    # Service manager state and automatic launch.
    text = replace_once(
        text,
        '        self.jobs: dict[str, dict[str, Any]] = {}\n',
        '        self.jobs: dict[str, dict[str, Any]] = {}\n'
        '        self.voice_service_lock = threading.Lock()\n'
        '        self.voice_processes: dict[str, subprocess.Popen[Any]] = {}\n',
        "voice process state",
    )
    text = replace_once(
        text,
        '        self.ensure_git_repo()\n',
        '        self.ensure_git_repo()\n'
        '        if not self.demo_override:\n'
        '            threading.Thread(target=self.ensure_voice_services, kwargs={"wait": False}, daemon=True).start()\n',
        "automatic voice service launch",
    )
    text = replace_once(
        text,
        '    def _voice_local_url(self, value: str, label: str) -> str:\n',
        SERVICE_METHODS + '    def _voice_local_url(self, value: str, label: str) -> str:\n',
        "service manager methods",
    )

    # Service readiness is refreshed and exposed in public state.
    text = replace_once(
        text,
        '    def voice_status(self) -> dict[str, Any]:\n        settings = self.get_settings()\n',
        '    def voice_status(self) -> dict[str, Any]:\n'
        '        if not self.demo_override:\n'
        '            threading.Thread(target=self.ensure_voice_services, kwargs={"wait": False}, daemon=True).start()\n'
        '        settings = self.get_settings()\n',
        "voice status auto repair",
    )
    text = replace_once(
        text,
        '        return status\n\n    def _select_existing_voice',
        '        status["services"] = self.voice_service_snapshot()\n'
        '        return status\n\n    def _select_existing_voice',
        "voice service status response",
    )
    text = replace_once(
        text,
        '    def build_ai_voices(self) -> dict[str, Any]:\n        status = self.voice_status()\n',
        '    def build_ai_voices(self) -> dict[str, Any]:\n'
        '        self.ensure_voice_services(wait=True)\n'
        '        status = self.voice_status()\n',
        "voice build startup",
    )
    text = replace_once(
        text,
        '    def generate_voice(self, provider: str, text: str) -> tuple[bytes, str]:\n        provider =',
        '    def generate_voice(self, provider: str, text: str) -> tuple[bytes, str]:\n'
        '        self.ensure_voice_services(wait=True)\n'
        '        provider =',
        "voice generation startup",
    )

    # Rename the UI so the fallback stack is not mislabeled as mandatory Voicebox.
    text = text.replace('Voicebox: Qwen3 / LuxTTS / Chatterbox / TADA', 'Automatic local stack: Voicebox when installed, otherwise Qwen + GPT-SoVITS')
    text = text.replace('<label>Voicebox API</label>', '<label>Local voice API / Voicebox-compatible bridge</label>')
    text = text.replace('Scan voice apps</button>', 'Start / repair voice stack</button>')
    text = text.replace(
        "async function scanVoices(){await saveSettings(true);try{const r=await api('/api/voice/scan','POST',{});toast(JSON.stringify(r,null,2));await refresh()}catch(e){toast(e.message)}}",
        "async function scanVoices(){await saveSettings(true);try{const r=await api('/api/voice/start','POST',{});toast(JSON.stringify(r,null,2));await refresh()}catch(e){toast(e.message)}}",
    )

    # Add an explicit manual restart endpoint.
    route_marker = '''                if parsed.path == "/api/voice/scan":
                    self.send_json(app.voice_status())
                    return
'''
    route_addition = '''                if parsed.path == "/api/voice/start":
                    self.send_json(app.ensure_voice_services(wait=True))
                    return
'''
    text = replace_once(text, route_marker, route_marker + route_addition, "voice stack route")

    return text


def main() -> int:
    source = ensure_060()
    print(f"Upgrading: {source}")
    text = patch(source.read_text("utf-8"))
    output = Path.cwd() / "CrownlessTable_v0_7_0.py"
    output.write_text(text, "utf-8")
    py_compile.compile(str(output), doraise=True)

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
        fail("The generated application failed its self-test.\n" + test.stdout + "\n" + test.stderr)

    installed_dir = Path.home() / "Documents" / "CrownlessTable"
    installed_dir.mkdir(parents=True, exist_ok=True)
    installed = installed_dir / "CrownlessTable.py"
    backup = installed_dir / "CrownlessTable_v0_6_0_backup.py"
    if installed.exists() and not backup.exists():
        shutil.copy2(installed, backup)
    shutil.copy2(output, installed)

    print("\nCrownless Table 0.7.0 installed successfully.")
    print(f"Generated copy: {output}")
    print(f"Installed copy: {installed}")
    print("Self-test output:")
    print(test.stdout.strip())
    print("\nRun one file. It will start the local voice stack itself:")
    print(f'  py "{installed}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
