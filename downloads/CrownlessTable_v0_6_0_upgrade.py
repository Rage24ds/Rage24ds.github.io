#!/usr/bin/env python3
"""Upgrade Crownless Table 0.5.1 to 0.6.0.

Changes:
- Fixes desktop and mobile scrolling with independently scrollable sidebar/feed.
- Removes Microsoft/browser voices from the normal runtime path.
- Uses local Voicebox profiles as the primary TTS runtime.
- Supports direct GPT-SoVITS as an alternate runtime.
- Lets GPT, Claude, Gemini, and Grok design their own voice specifications.
- Lets each model select an existing Voicebox profile or creates a new reference
  voice through a local Qwen3-TTS VoiceDesign API and imports it into Voicebox.
"""
from __future__ import annotations

import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

VERSION = "0.6.0"
BUILD = "local-ai-voice-casting-scroll-v9-20260720"
REPAIR_URL = (
    "https://raw.githubusercontent.com/Rage24ds/Rage24ds.github.io/"
    "master/downloads/CrownlessTable_v0_5_1_repair.py"
)


def fail(message: str) -> "NoReturn":
    print(f"\nERROR: {message}")
    raise SystemExit(1)


def download(url: str, destination: Path) -> None:
    with urllib.request.urlopen(url, timeout=45) as response:
        destination.write_bytes(response.read())


def candidates() -> list[Path]:
    home = Path.home() / "Documents" / "CrownlessTable"
    cwd = Path.cwd()
    return [
        home / "CrownlessTable.py",
        cwd / "CrownlessTable_v0_5_1.py",
        cwd / "CrownlessTable.py",
        cwd / "CrownlessTable_v0_4_2.py",
        Path.home() / "Downloads" / "New DND with ai" / "CrownlessTable_v0_5_1.py",
        Path.home() / "Downloads" / "New DND with ai" / "CrownlessTable_v0_4_2.py",
    ]


def find_app() -> Path | None:
    for path in candidates():
        if not path.is_file():
            continue
        try:
            text = path.read_text("utf-8")
        except OSError:
            continue
        if 'VERSION = "0.5.1"' in text:
            return path.resolve()
    return None


def ensure_051() -> Path:
    found = find_app()
    if found:
        return found
    base_042 = next(
        (
            path
            for path in candidates()
            if path.is_file() and 'VERSION = "0.4.2"' in path.read_text("utf-8", errors="ignore")
        ),
        None,
    )
    if not base_042:
        fail("Crownless Table 0.5.1 or its 0.4.2 base could not be found.")
    print("Crownless Table 0.5.1 is not installed. Running the repaired 0.5.1 upgrade first...")
    repair = Path.cwd() / "CrownlessTable_v0_5_1_repair.py"
    if not repair.is_file():
        download(REPAIR_URL, repair)
    result = subprocess.run([sys.executable, str(repair)], cwd=str(Path.cwd()), check=False)
    if result.returncode != 0:
        fail("The prerequisite 0.5.1 repair failed. The existing installation was not changed.")
    found = find_app()
    if not found:
        fail("The 0.5.1 repair completed but its installed application could not be found.")
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


VOICE_METHODS = r'''    def _voice_local_url(self, value: str, label: str) -> str:
        value = str(value or "").strip().rstrip("/")
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError(f"{label} must use a local loopback URL.")
        return value

    @staticmethod
    def _voice_json_request(url: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> Any:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
            method="POST" if data is not None else "GET",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else None

    @staticmethod
    def _multipart_upload(url: str, file_path: Path, reference_text: str, timeout: int = 120) -> Any:
        boundary = "----CrownlessTable" + uuid.uuid4().hex
        body = bytearray()
        def add(value: bytes) -> None:
            body.extend(value)
        add(f"--{boundary}\r\n".encode())
        add(b'Content-Disposition: form-data; name="reference_text"\r\n\r\n')
        add(reference_text.encode("utf-8"))
        add(b"\r\n")
        add(f"--{boundary}\r\n".encode())
        add(
            f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode()
        )
        add(b"Content-Type: audio/wav\r\n\r\n")
        add(file_path.read_bytes())
        add(b"\r\n")
        add(f"--{boundary}--\r\n".encode())
        request = urllib.request.Request(
            url,
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else None

    def _voice_settings_json(self, key: str) -> dict[str, Any]:
        settings = self.get_settings()
        try:
            value = json.loads(str(settings.get(key) or "{}"))
        except json.JSONDecodeError:
            value = {}
        return value if isinstance(value, dict) else {}

    def _voice_speaker_name(self, provider: str) -> str:
        if provider == "openai":
            return "Dungeon Master"
        character = self.get_characters().get(provider, {})
        return str(character.get("name") or PROVIDER_LABELS.get(provider, provider.title()))

    def _fallback_voice_spec(self, provider: str) -> dict[str, Any]:
        defaults = {
            "openai": {
                "voice_description": "A natural adult narrator with a grounded, intimate cinematic voice, precise diction, restrained warmth, and no announcer affect.",
                "delivery": "Conversational and responsive. Vary pace with tension. Never sound like a commercial or navigation system.",
                "reference_line": "The rain has hidden most of the tracks, but not the choice waiting in front of you.",
                "preferred_engine": "qwen",
            },
            "claude": {
                "voice_description": "A believable adult adventurer voice with subtle texture, thoughtful timing, and emotionally responsive delivery.",
                "delivery": "Natural pauses, quiet confidence, and understated reactions rather than theatrical narration.",
                "reference_line": "Give me a moment. Something about this place does not fit together.",
                "preferred_engine": "qwen",
            },
            "gemini": {
                "voice_description": "A distinct human adventurer voice with energetic intelligence, clear speech, and flexible emotional range.",
                "delivery": "Alert, curious, and conversational, with quick changes when a discovery matters.",
                "reference_line": "There is a pattern here, and I think we are standing directly in the middle of it.",
                "preferred_engine": "qwen",
            },
            "grok": {
                "voice_description": "A grounded adult adventurer voice with dry humor, physical presence, and natural roughness without caricature.",
                "delivery": "Relaxed and human, with clipped timing under danger and restrained amusement outside it.",
                "reference_line": "I can watch the door, but I am not promising to be polite about what comes through it.",
                "preferred_engine": "chatterbox_turbo",
            },
        }
        return defaults[provider].copy()

    def voice_design_prompt(self, provider: str) -> str:
        settings = self.get_settings()
        character = self.get_characters().get(provider, {}) if provider != "openai" else {}
        role = (
            "You are the Dungeon Master and narrator."
            if provider == "openai"
            else f"You control this player character: {json.dumps(character, ensure_ascii=False)}"
        )
        return f"""{role}
Design the voice you should use in this persistent D&D campaign.
The result must sound like a real human performance, not a browser voice, assistant voice, announcer, audiobook stereotype, or exaggerated cartoon.
Base it on the character's age presentation, physicality, culture, temperament, and emotional range. Do not imitate a real celebrity or identifiable living person.
Available local runtime engines are qwen, luxtts, chatterbox, chatterbox_turbo, tada, and gpt_sovits.
Return ONLY one JSON object with exactly these keys:
{{
  "voice_description": "detailed natural-language description suitable for Qwen VoiceDesign",
  "delivery": "directions for pace, emotion, texture, accent, and conversational behavior",
  "reference_line": "one natural 8-20 second in-character line used to create and judge the voice",
  "preferred_engine": "qwen|luxtts|chatterbox|chatterbox_turbo|tada|gpt_sovits"
}}
Campaign premise: {settings.get('campaign_premise', '')}
"""

    def design_voice_specs(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(self.run_provider, provider, self.voice_design_prompt(provider)): provider
                for provider in ("openai", "claude", "gemini", "grok")
            }
            for future in concurrent.futures.as_completed(futures):
                provider = futures[future]
                spec = self._fallback_voice_spec(provider)
                try:
                    parsed = safe_json_loads(future.result())
                    if isinstance(parsed, dict):
                        for key in ("voice_description", "delivery", "reference_line", "preferred_engine"):
                            if parsed.get(key):
                                spec[key] = clamp_text(parsed[key], 2500)
                except Exception as exc:
                    spec["design_warning"] = str(exc)
                if spec.get("preferred_engine") not in {
                    "qwen", "luxtts", "chatterbox", "chatterbox_turbo", "tada", "gpt_sovits"
                }:
                    spec["preferred_engine"] = "qwen"
                spec["speaker_name"] = self._voice_speaker_name(provider)
                spec["provider"] = provider
                results[provider] = spec
        self.update_settings({"voice_specs_json": json.dumps(results, ensure_ascii=False, indent=2)})
        self.export_campaign()
        self.checkpoint_git("Design AI character voices")
        return {"ok": True, "voice_specs": results}

    def voice_status(self) -> dict[str, Any]:
        settings = self.get_settings()
        voicebox_url = self._voice_local_url(settings.get("voicebox_url"), "Voicebox URL")
        qwen_url = self._voice_local_url(settings.get("qwen_design_url"), "Qwen VoiceDesign URL")
        status: dict[str, Any] = {
            "engine": settings.get("voice_engine", "voicebox"),
            "voicebox_url": voicebox_url,
            "qwen_design_url": qwen_url,
            "voicebox_ready": False,
            "qwen_design_ready": False,
            "profiles": [],
            "models": [],
            "assignments": self._voice_settings_json("voice_assignments_json"),
            "specs": self._voice_settings_json("voice_specs_json"),
        }
        try:
            self._voice_json_request(voicebox_url + "/health", timeout=4)
            profiles = self._voice_json_request(voicebox_url + "/profiles", timeout=6)
            models = self._voice_json_request(voicebox_url + "/models/status", timeout=6)
            status["voicebox_ready"] = True
            status["profiles"] = profiles if isinstance(profiles, list) else []
            status["models"] = models.get("models", []) if isinstance(models, dict) else []
        except Exception as exc:
            status["voicebox_error"] = str(exc)
        try:
            self._voice_json_request(qwen_url + "/health", timeout=4)
            status["qwen_design_ready"] = True
        except Exception as exc:
            status["qwen_design_error"] = str(exc)
        return status

    def _select_existing_voice(self, provider: str, spec: dict[str, Any], profiles: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not profiles:
            return None
        speaker = self._voice_speaker_name(provider).casefold()
        exact = next(
            (
                profile
                for profile in profiles
                if speaker in str(profile.get("name") or "").casefold()
                or f"crownless {provider}" in str(profile.get("name") or "").casefold()
            ),
            None,
        )
        if exact:
            return exact
        compact = [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "description": p.get("description"),
                "language": p.get("language"),
                "voice_type": p.get("voice_type"),
                "default_engine": p.get("default_engine"),
            }
            for p in profiles[:80]
        ]
        prompt = f"""Choose whether one existing local voice profile fits your campaign voice specification.
Voice specification: {json.dumps(spec, ensure_ascii=False)}
Available profiles: {json.dumps(compact, ensure_ascii=False)}
Return ONLY JSON: {{"profile_id":"an exact id from the list or CREATE","reason":"one sentence","engine":"qwen|luxtts|chatterbox|chatterbox_turbo|tada"}}
Choose CREATE unless a profile genuinely matches. Do not select merely because a name exists.
"""
        try:
            choice = safe_json_loads(self.run_provider(provider, prompt))
            profile_id = str(choice.get("profile_id") or "CREATE") if isinstance(choice, dict) else "CREATE"
            selected = next((p for p in profiles if str(p.get("id")) == profile_id), None)
            if selected:
                selected = dict(selected)
                selected["ai_reason"] = choice.get("reason", "")
                selected["chosen_engine"] = choice.get("engine")
                return selected
        except Exception:
            return None
        return None

    def _create_qwen_voicebox_profile(self, provider: str, spec: dict[str, Any]) -> dict[str, Any]:
        settings = self.get_settings()
        voicebox_url = self._voice_local_url(settings.get("voicebox_url"), "Voicebox URL")
        qwen_url = self._voice_local_url(settings.get("qwen_design_url"), "Qwen VoiceDesign URL")
        reference_line = clamp_text(spec.get("reference_line") or "This is a test of my voice.", 1200)
        payload = {
            "input": reference_line,
            "language": "English",
            "voice_description": clamp_text(spec.get("voice_description") or "A natural adult human voice", 2000),
        }
        request = urllib.request.Request(
            qwen_url + "/v1/audio/speech/design",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with tempfile.TemporaryDirectory(prefix="crownless-voice-design-") as folder:
            reference = Path(folder) / f"{provider}_reference.wav"
            with urllib.request.urlopen(request, timeout=360) as response:
                audio = response.read()
            if not audio:
                raise RuntimeError("Qwen VoiceDesign returned no reference audio.")
            reference.write_bytes(audio)
            profile_name = f"Crownless {self._voice_speaker_name(provider)}"
            profile = self._voice_json_request(
                voicebox_url + "/profiles",
                {
                    "name": profile_name[:100],
                    "description": clamp_text(
                        f"Automatically designed for Crownless Table. {spec.get('voice_description', '')}",
                        1900,
                    ),
                    "language": "en",
                },
                timeout=30,
            )
            profile_id = str(profile.get("id") or "") if isinstance(profile, dict) else ""
            if not profile_id:
                raise RuntimeError("Voicebox created no usable profile id.")
            self._multipart_upload(
                voicebox_url + f"/profiles/{urllib.parse.quote(profile_id)}/samples",
                reference,
                reference_line,
                timeout=180,
            )
            return profile

    def build_ai_voices(self) -> dict[str, Any]:
        status = self.voice_status()
        if not status.get("voicebox_ready"):
            raise RuntimeError(
                "Voicebox is not running at the configured URL. Open Voicebox and keep its local server running."
            )
        specs = self._voice_settings_json("voice_specs_json")
        if not all(provider in specs for provider in ("openai", "claude", "gemini", "grok")):
            specs = self.design_voice_specs()["voice_specs"]
        profiles = status.get("profiles") or []
        assignments: dict[str, Any] = self._voice_settings_json("voice_assignments_json")
        results: dict[str, Any] = {}
        for provider in ("openai", "claude", "gemini", "grok"):
            spec = specs.get(provider) or self._fallback_voice_spec(provider)
            selected = self._select_existing_voice(provider, spec, profiles)
            source = "existing"
            if not selected:
                if not status.get("qwen_design_ready"):
                    results[provider] = {
                        "ok": False,
                        "error": "No fitting profile was selected and the Qwen VoiceDesign API is not running.",
                    }
                    continue
                selected = self._create_qwen_voicebox_profile(provider, spec)
                profiles.append(selected)
                source = "qwen_voice_design"
            engine = str(selected.get("chosen_engine") or spec.get("preferred_engine") or "qwen")
            if engine == "gpt_sovits":
                engine = "qwen"
            if engine not in {"qwen", "luxtts", "chatterbox", "chatterbox_turbo", "tada"}:
                engine = "qwen"
            assignment = {
                "profile_id": str(selected.get("id")),
                "profile_name": str(selected.get("name") or self._voice_speaker_name(provider)),
                "engine": engine,
                "instruct": clamp_text(spec.get("delivery") or "Natural conversational delivery", 1500),
                "source": source,
                "ai_reason": selected.get("ai_reason", ""),
            }
            assignments[provider] = assignment
            results[provider] = {"ok": True, **assignment}
        self.update_settings({"voice_assignments_json": json.dumps(assignments, ensure_ascii=False, indent=2)})
        self.export_campaign()
        self.checkpoint_git("Cast local AI voices")
        return {"ok": all(item.get("ok") for item in results.values()), "voices": results}

    def install_voice_engine(self) -> dict[str, Any]:
        return {
            "ok": True,
            "message": (
                "No generic voice package will be installed. Start Voicebox for Qwen/LuxTTS/Chatterbox/TADA, "
                "start the Qwen VoiceDesign API when new voices must be created, or select direct GPT-SoVITS."
            ),
        }

    def generate_voice(self, provider: str, text: str) -> tuple[bytes, str]:
        provider = provider if provider in {"openai", "claude", "gemini", "grok"} else "openai"
        text = clamp_text(text, 7000)
        if not text:
            raise ValueError("There is no text to speak.")
        settings = self.get_settings()
        engine = str(settings.get("voice_engine") or "voicebox").strip().lower()
        if engine == "off":
            raise ValueError("Voice output is disabled.")
        if engine == "voicebox":
            assignments = self._voice_settings_json("voice_assignments_json")
            assignment = assignments.get(provider) if isinstance(assignments, dict) else None
            if not isinstance(assignment, dict) or not assignment.get("profile_id"):
                self.build_ai_voices()
                assignments = self._voice_settings_json("voice_assignments_json")
                assignment = assignments.get(provider, {})
            voicebox_url = self._voice_local_url(settings.get("voicebox_url"), "Voicebox URL")
            payload = {
                "profile_id": assignment.get("profile_id"),
                "text": text,
                "language": "en",
                "engine": assignment.get("engine") or "qwen",
                "model_size": "1.7B",
                "instruct": assignment.get("instruct") or "Natural conversational delivery",
            }
            generation = self._voice_json_request(voicebox_url + "/generate", payload, timeout=360)
            generation_id = str(generation.get("id") or "") if isinstance(generation, dict) else ""
            if not generation_id:
                raise RuntimeError("Voicebox returned no generation id.")
            with urllib.request.urlopen(
                voicebox_url + "/audio/" + urllib.parse.quote(generation_id), timeout=120
            ) as response:
                audio = response.read()
                content_type = response.headers.get_content_type() or "audio/wav"
            if not audio:
                raise RuntimeError("Voicebox returned no audio.")
            return audio, content_type
        if engine == "gpt_sovits":
            url = self._voice_local_url(str(settings.get("gpt_sovits_url") or ""), "GPT-SoVITS URL")
            try:
                profiles = json.loads(str(settings.get("gpt_sovits_profiles") or "{}"))
            except json.JSONDecodeError as exc:
                raise ValueError("GPT-SoVITS profiles must be valid JSON.") from exc
            profile = profiles.get(provider, {}) if isinstance(profiles, dict) else {}
            if not isinstance(profile, dict) or not profile.get("ref_audio_path"):
                raise ValueError(
                    f"GPT-SoVITS needs a {provider} profile with ref_audio_path, prompt_text, and prompt_lang."
                )
            payload = {
                "text": text,
                "text_lang": str(profile.get("text_lang") or "en"),
                "ref_audio_path": str(profile.get("ref_audio_path")),
                "aux_ref_audio_paths": profile.get("aux_ref_audio_paths") or [],
                "prompt_text": str(profile.get("prompt_text") or ""),
                "prompt_lang": str(profile.get("prompt_lang") or "en"),
                "text_split_method": str(profile.get("text_split_method") or "cut5"),
                "batch_size": 1,
                "media_type": "wav",
                "streaming_mode": False,
            }
            request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=360) as response:
                audio = response.read()
            if not audio:
                raise RuntimeError("GPT-SoVITS returned no audio.")
            return audio, "audio/wav"
        raise ValueError("Unknown voice engine. Choose voicebox, gpt_sovits, or off.")

'''


VOICE_UI = '''    <div class="section voice-studio">
      <h3>Local AI voice casting</h3>
      <div class="small">No browser or Microsoft fallback voices. GPT, Claude, Gemini, and Grok design and select their own reusable local voices; you still control the final assignments.</div>
      <div class="field"><label>Runtime voice engine</label><select id="voice_engine"><option value="voicebox">Voicebox: Qwen3 / LuxTTS / Chatterbox / TADA</option><option value="gpt_sovits">Direct GPT-SoVITS</option><option value="off">Off</option></select></div>
      <div class="field"><label>Voicebox API</label><input id="voicebox_url"></div>
      <div class="field"><label>Qwen VoiceDesign API</label><input id="qwen_design_url"></div>
      <div class="field"><label>GPT-SoVITS /tts API</label><input id="gpt_sovits_url"></div>
      <label class="toggle"><input type="checkbox" id="auto_create_voices"> Automatically design and cast voices when the party is created</label>
      <details><summary class="small">Voice designs and assignments</summary>
        <div class="field"><label>AI-generated voice specifications</label><textarea id="voice_specs_json" style="min-height:180px"></textarea></div>
        <div class="field"><label>Voicebox profile assignments</label><textarea id="voice_assignments_json" style="min-height:160px"></textarea></div>
        <div class="field"><label>Direct GPT-SoVITS profiles</label><textarea id="gpt_sovits_profiles" style="min-height:160px" placeholder='{"openai":{"ref_audio_path":"...","prompt_text":"...","prompt_lang":"en","text_lang":"en"}}'></textarea></div>
      </details>
      <div class="actions"><button onclick="scanVoices()">Scan voice apps</button><button onclick="designVoices()">AI design voices</button><button onclick="buildVoices()">Choose / create voices</button><button onclick="testVoices()">Test cast</button><button onclick="stopVoice()">Stop audio</button></div>
      <div id="voiceStatus" class="statusline"></div>
    </div>
'''


def patch(text: str) -> str:
    text = replace_once(text, 'VERSION = "0.5.1"', f'VERSION = "{VERSION}"', "version")
    text = replace_once(
        text,
        'BUILD_ID = "player-agency-neural-voice-sqlite-fix-v8-20260720"',
        f'BUILD_ID = "{BUILD}"',
        "build id",
    )

    text = replace_once(text, '    "voice_engine": "edge",', '    "voice_engine": "voicebox",', "voice default")
    text = replace_once(
        text,
        '    "gpt_sovits_profiles": "{}",\n',
        '    "gpt_sovits_profiles": "{}",\n'
        '    "voicebox_url": "http://127.0.0.1:17493",\n'
        '    "qwen_design_url": "http://127.0.0.1:7811",\n'
        '    "voice_specs_json": "{}",\n'
        '    "voice_assignments_json": "{}",\n'
        '    "auto_create_voices": True,\n',
        "local voice settings",
    )
    text = replace_once(
        text,
        '            elif key in {"human_character", "additional_human_players", "gpt_sovits_profiles"}:\n',
        '            elif key in {"human_character", "additional_human_players", "gpt_sovits_profiles", "voice_specs_json", "voice_assignments_json"}:\n',
        "large voice settings",
    )
    text = replace_once(
        text,
        '            elif key in {"demo_mode", "auto_voice"}:\n',
        '            elif key in {"demo_mode", "auto_voice", "auto_create_voices"}:\n',
        "voice boolean settings",
    )

    text = regex_once(
        text,
        r"    def voice_status\(self\).*?(?=    def provider_status\(self\))",
        VOICE_METHODS,
        "voice method block",
    )

    text = regex_once(
        text,
        r'    <div class="section">\n      <h3>AI neural voices</h3>.*?    </div>\n(?=    <div class="section"><h3>AI connections</h3>)',
        VOICE_UI,
        "voice studio UI",
    )

    # Desktop: two visible, independently scrollable panes. Mobile: normal page scrolling.
    text = replace_once(
        text,
        'height:100vh;overflow:hidden}',
        'height:100dvh;min-height:0;overflow:hidden}',
        "body viewport",
    )
    text = replace_once(
        text,
        '.app{display:grid;grid-template-columns:330px 1fr;height:100vh}',
        '.app{display:grid;grid-template-columns:minmax(300px,370px) minmax(0,1fr);height:100dvh;min-height:0;overflow:hidden}',
        "app scrolling",
    )
    text = replace_once(
        text,
        '.side{background:rgba(19,23,32,.96);border-right:1px solid var(--line);overflow:auto;padding:18px}',
        '.side{background:rgba(19,23,32,.96);border-right:1px solid var(--line);height:100%;min-height:0;overflow-y:scroll;overflow-x:hidden;overscroll-behavior:contain;scrollbar-gutter:stable;padding:18px}',
        "sidebar scrolling",
    )
    text = replace_once(
        text,
        '.main{display:grid;grid-template-rows:auto 1fr auto;min-width:0}',
        '.main{display:grid;grid-template-rows:auto minmax(0,1fr) auto;min-width:0;min-height:0;height:100%;overflow:hidden}',
        "main scrolling",
    )
    text = replace_once(
        text,
        '.feed{overflow:auto;padding:22px 5vw 32px}',
        '.feed{min-height:0;overflow-y:scroll;overflow-x:hidden;overscroll-behavior:contain;scrollbar-gutter:stable;padding:22px 5vw 32px}',
        "feed scrolling",
    )
    text = replace_once(
        text,
        '@media(max-width:850px){body{overflow:auto}.app{display:block;height:auto}.side{border-right:0;border-bottom:1px solid var(--line)}.main{height:75vh}',
        '@media(max-width:850px){body{height:auto;min-height:100vh;overflow:auto}.app{display:block;height:auto;min-height:100vh;overflow:visible}.side{height:auto;max-height:none;overflow:visible;border-right:0;border-bottom:1px solid var(--line)}.main{height:auto;min-height:75vh;overflow:visible}.feed{min-height:55vh;max-height:70vh;overflow-y:auto}',
        "mobile scrolling",
    )

    # Replace render settings and save payload with the local voice studio fields.
    text = regex_once(
        text,
        r"  for\(const id of \['campaign_name'.*?renderProviders\(\);renderCharacters\(\);renderEvents\(\);renderGit\(\);",
        "  for(const id of ['campaign_name','campaign_premise','human_name','human_character','additional_human_players','repo_name','voicebox_url','qwen_design_url','gpt_sovits_url','gpt_sovits_profiles','voice_specs_json','voice_assignments_json'])if(document.activeElement!==$(id))$(id).value=state.settings[id]??'';\n"
        "  $('demo_mode').checked=!!state.settings.demo_mode;$('auto_voice').checked=!!state.settings.auto_voice;$('auto_create_voices').checked=!!state.settings.auto_create_voices;\n"
        "  $('voice_engine').value=state.settings.voice_engine||'voicebox';if(!$('acting_character').value)$('acting_character').value=state.settings.human_name||'Trest';\n"
        "  const vs=state.voice||{};const assigned=Object.keys(vs.assignments||{}).length;$('voiceStatus').textContent=(vs.voicebox_ready?'Voicebox ready':'Voicebox offline')+' · '+(vs.qwen_design_ready?'Qwen VoiceDesign ready':'Qwen VoiceDesign offline')+' · '+assigned+' voices assigned';\n"
        "  renderProviders();renderCharacters();renderEvents();renderGit();",
        "render local voice settings",
    )
    text = regex_once(
        text,
        r"async function saveSettings\(silent=false\)\{const body=\{.*?\};await api\('/api/settings','POST',body\);await refresh\(\);if\(!silent\)toast\('Settings saved and checkpointed\.'\)\}",
        "async function saveSettings(silent=false){const body={campaign_name:$('campaign_name').value,campaign_premise:$('campaign_premise').value,human_name:$('human_name').value,human_character:$('human_character').value,additional_human_players:$('additional_human_players').value,repo_name:$('repo_name').value,demo_mode:$('demo_mode').checked,auto_voice:$('auto_voice').checked,auto_create_voices:$('auto_create_voices').checked,voice_engine:$('voice_engine').value,voicebox_url:$('voicebox_url').value,qwen_design_url:$('qwen_design_url').value,gpt_sovits_url:$('gpt_sovits_url').value,gpt_sovits_profiles:$('gpt_sovits_profiles').value,voice_specs_json:$('voice_specs_json').value,voice_assignments_json:$('voice_assignments_json').value};await api('/api/settings','POST',body);await refresh();if(!silent)toast('Settings saved and checkpointed.')}",
        "save local voice settings",
    )

    # Add browser actions beside the existing queued audio playback.
    marker = "async function testVoices(){await saveSettings(true);"
    idx = text.find(marker)
    if idx < 0:
        fail("Could not find the existing voice test function.")
    end = text.find("}", idx) + 1
    replacement = """async function scanVoices(){await saveSettings(true);try{const r=await api('/api/voice/scan','POST',{});toast(JSON.stringify(r,null,2));await refresh()}catch(e){toast(e.message)}}
async function designVoices(){await saveSettings(true);await startJob('/api/voice/design',{},'GPT, Claude, Gemini, and Grok are designing natural voices for themselves...')}
async function buildVoices(){await saveSettings(true);await startJob('/api/voice/build',{},'The models are auditioning existing local profiles and creating missing voices with Qwen VoiceDesign...')}
async function testVoices(){await saveSettings(true);speak('The road ahead is quiet, but not empty.','openai');speak('I will check the evidence before touching it.','claude');speak('There is a pattern here. Give me a moment.','gemini');speak('I will watch the door while everyone gets clever.','grok')}"""
    text = text[:idx] + replacement + text[end:]

    # Add job-capable local voice routes.
    route_marker = '''                if parsed.path == "/api/voice/install":
                    self.send_json(app.install_voice_engine())
                    return
'''
    route_addition = '''                if parsed.path == "/api/voice/scan":
                    self.send_json(app.voice_status())
                    return
                if parsed.path == "/api/voice/design":
                    self.send_json({"job_id": app.start_job("voice-design", app.design_voice_specs)})
                    return
                if parsed.path == "/api/voice/build":
                    self.send_json({"job_id": app.start_job("voice-build", app.build_ai_voices)})
                    return
'''
    text = replace_once(text, route_marker, route_marker + route_addition, "local voice routes")

    # Automatically design/cast after character creation when enabled. Failure remains visible but does not erase the party.
    auto_marker = '''            self.export_campaign()
            self.checkpoint_git("Create AI party and opening scene")
'''
    auto_replacement = '''            if self.get_settings().get("auto_create_voices"):
                try:
                    voice_result = self.build_ai_voices()
                    ready_names = [v.get("profile_name") for v in voice_result.get("voices", {}).values() if v.get("ok")]
                    if ready_names:
                        self.append_event("Voice Director", "system", "system", "Local character voices are ready: " + ", ".join(ready_names) + ".", turn_number=max(1, self.current_turn()))
                except Exception as exc:
                    self.append_event("Voice Director", "system", "error", "The party was created, but automatic local voice casting needs attention: " + str(exc), turn_number=max(1, self.current_turn()))
            self.export_campaign()
            self.checkpoint_git("Create AI party, opening scene, and local voice cast")
'''
    text = replace_once(text, auto_marker, auto_replacement, "automatic voice casting")

    return text


def main() -> int:
    source = ensure_051()
    print(f"Upgrading: {source}")
    text = patch(source.read_text("utf-8"))
    output = Path.cwd() / "CrownlessTable_v0_6_0.py"
    output.write_text(text, "utf-8")
    py_compile.compile(str(output), doraise=True)

    # The built-in self-test uses demo providers and does not require any voice server.
    test = subprocess.run(
        [sys.executable, str(output), "--self-test"],
        cwd=str(output.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
        check=False,
    )
    if test.returncode != 0:
        fail("The generated application failed its self-test.\n" + test.stdout + "\n" + test.stderr)

    installed_dir = Path.home() / "Documents" / "CrownlessTable"
    installed_dir.mkdir(parents=True, exist_ok=True)
    installed = installed_dir / "CrownlessTable.py"
    backup = installed_dir / "CrownlessTable_v0_5_1_backup.py"
    if installed.exists() and not backup.exists():
        shutil.copy2(installed, backup)
    shutil.copy2(output, installed)

    print("\nCrownless Table 0.6.0 installed successfully.")
    print(f"Generated copy: {output}")
    print(f"Installed copy: {installed}")
    print("Self-test output:")
    print(test.stdout.strip())
    print("\nStart Voicebox, optionally start Qwen VoiceDesign on port 7811, then run:")
    print(f'  py "{installed}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
