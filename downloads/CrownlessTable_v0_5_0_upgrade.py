#!/usr/bin/env python3
"""Upgrade Crownless Table 0.4.2 to 0.5.0.

This script patches the installed one-file application, writes a new one-file build,
compiles it, runs its built-in self-test, and installs it into Documents/CrownlessTable.
"""
from __future__ import annotations

import os
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path

TARGET_VERSION = "0.5.0"
TARGET_BUILD = "player-agency-neural-voice-v7-20260720"


def fail(message: str) -> "NoReturn":
    print(f"\nERROR: {message}")
    raise SystemExit(1)


def find_source() -> Path:
    cwd = Path.cwd()
    candidates = [
        cwd / "CrownlessTable_v0_4_2.py",
        cwd / "CrownlessTable.py",
        Path.home() / "Documents" / "CrownlessTable" / "CrownlessTable.py",
        Path.home() / "Downloads" / "New DND with ai" / "CrownlessTable_v0_4_2.py",
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
        "Crownless Table 0.4.2 was not found. Put this upgrade script beside "
        "CrownlessTable_v0_4_2.py, or keep the installed copy in Documents\\CrownlessTable."
    )


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"Patch point {label!r} expected once but was found {count} times. The source file is not the expected 0.4.2 build.")
    return text.replace(old, new, 1)


def insert_before(text: str, marker: str, addition: str, label: str) -> str:
    return replace_once(text, marker, addition + marker, label)


def patch(source: Path) -> Path:
    text = source.read_text("utf-8")

    text = replace_once(text, 'VERSION = "0.4.2"', f'VERSION = "{TARGET_VERSION}"', "version")
    text = replace_once(
        text,
        'BUILD_ID = "antigravity-output-file-v6-20260720"',
        f'BUILD_ID = "{TARGET_BUILD}"',
        "build id",
    )
    text = replace_once(
        text,
        "A dependency-free, one-file local D&D room for one human, an OpenAI DM,\n"
        "and Claude, Gemini, and Grok party members through their signed-in CLIs.",
        "A one-file local D&D room for human player characters, an OpenAI DM,\n"
        "and Claude, Gemini, and Grok as autonomous player characters through signed-in CLIs.",
        "module description",
    )
    text = replace_once(
        text,
        "import urllib.parse\n",
        "import urllib.error\nimport urllib.parse\nimport urllib.request\n",
        "urllib imports",
    )

    old_defaults = '''    "human_name": "Trest",
    "human_character": TREST_CHARACTER_SHEET,
    "demo_mode": False,
    "auto_voice": True,
    "provider_timeout_seconds": 240,
'''
    new_defaults = '''    "human_name": "Trest",
    "human_character": TREST_CHARACTER_SHEET,
    "additional_human_players": "",
    "demo_mode": False,
    "auto_voice": True,
    "voice_engine": "edge",
    "voice_openai": "en-US-AndrewMultilingualNeural",
    "voice_claude": "en-US-BrianMultilingualNeural",
    "voice_gemini": "en-US-AvaMultilingualNeural",
    "voice_grok": "en-US-DavisMultilingualNeural",
    "voice_rate_openai": "-8%",
    "voice_rate_claude": "-2%",
    "voice_rate_gemini": "+0%",
    "voice_rate_grok": "+3%",
    "local_tts_url": "http://127.0.0.1:8000/v1/audio/speech",
    "local_tts_model": "tts-1",
    "gpt_sovits_url": "http://127.0.0.1:9880/tts",
    "gpt_sovits_profiles": "{}",
    "provider_timeout_seconds": 240,
'''
    text = replace_once(text, old_defaults, new_defaults, "voice and player defaults")

    text = replace_once(
        text,
        '            elif key == "human_character":\n                value = clamp_text(value, 40_000)\n',
        '            elif key in {"human_character", "additional_human_players", "gpt_sovits_profiles"}:\n'
        '                value = clamp_text(value, 40_000)\n',
        "large settings normalization",
    )

    voice_methods = r'''    def voice_status(self) -> dict[str, Any]:
        settings = self.get_settings()
        engine = str(settings.get("voice_engine") or "edge").strip().lower()
        try:
            __import__("edge_tts")
            edge_ready = True
        except ImportError:
            edge_ready = False
        return {
            "engine": engine,
            "edge_ready": edge_ready,
            "local_tts_url": str(settings.get("local_tts_url") or ""),
            "gpt_sovits_url": str(settings.get("gpt_sovits_url") or ""),
        }

    def install_voice_engine(self) -> dict[str, Any]:
        command = subprocess.list2cmdline(
            [sys.executable, "-m", "pip", "install", "--user", "--upgrade", "edge-tts"]
        )
        self.spawn_console(command)
        return {
            "ok": True,
            "message": "Opened the Microsoft neural voice installer. Restart Crownless Table after it finishes.",
        }

    @staticmethod
    def _loopback_url(url: str, label: str) -> str:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError(f"{label} must point to a local server on 127.0.0.1 or localhost.")
        return url

    def generate_voice(self, provider: str, text: str) -> tuple[bytes, str]:
        provider = provider if provider in {"openai", "claude", "gemini", "grok"} else "openai"
        text = clamp_text(text, 7000)
        if not text:
            raise ValueError("There is no text to speak.")
        settings = self.get_settings()
        engine = str(settings.get("voice_engine") or "edge").strip().lower()
        voice = str(settings.get(f"voice_{provider}") or "en-US-AndrewMultilingualNeural").strip()

        if engine == "off":
            raise ValueError("Voice output is disabled in Voice settings.")

        if engine == "edge":
            try:
                __import__("edge_tts")
            except ImportError as exc:
                raise RuntimeError(
                    "Microsoft neural voices are not installed. Press Install neural voices, let it finish, restart the app, and try again."
                ) from exc
            with tempfile.TemporaryDirectory(prefix="crownless-voice-") as folder:
                folder_path = Path(folder)
                input_path = folder_path / "speech.txt"
                output_path = folder_path / "speech.mp3"
                input_path.write_text(text, "utf-8")
                rate = str(settings.get(f"voice_rate_{provider}") or "+0%").strip()
                if not re.fullmatch(r"[+-]\d{1,3}%", rate):
                    rate = "+0%"
                args = [
                    sys.executable,
                    "-m",
                    "edge_tts",
                    "--file",
                    str(input_path),
                    "--voice",
                    voice,
                    f"--rate={rate}",
                    "--write-media",
                    str(output_path),
                ]
                code, stdout, stderr = run_process(
                    args,
                    cwd=folder_path,
                    timeout=max(120, int(settings.get("provider_timeout_seconds", 240))),
                    env=dict(os.environ),
                )
                if code != 0 or not output_path.exists() or output_path.stat().st_size == 0:
                    raise RuntimeError("Neural voice generation failed. " + clamp_text(stderr or stdout, 1800))
                return output_path.read_bytes(), "audio/mpeg"

        if engine == "local_openai":
            url = self._loopback_url(str(settings.get("local_tts_url") or ""), "Local TTS URL")
            payload = {
                "model": str(settings.get("local_tts_model") or "tts-1"),
                "input": text,
                "voice": voice,
                "response_format": "mp3",
            }
            request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    audio = response.read()
                    content_type = response.headers.get_content_type() or "audio/mpeg"
            except urllib.error.URLError as exc:
                raise RuntimeError(f"The local OpenAI-compatible TTS server could not be reached: {exc}") from exc
            if not audio:
                raise RuntimeError("The local TTS server returned no audio.")
            return audio, content_type

        if engine == "gpt_sovits":
            url = self._loopback_url(str(settings.get("gpt_sovits_url") or ""), "GPT-SoVITS URL")
            try:
                profiles = json.loads(str(settings.get("gpt_sovits_profiles") or "{}"))
            except json.JSONDecodeError as exc:
                raise ValueError("GPT-SoVITS profiles must be valid JSON.") from exc
            profile = profiles.get(provider, {}) if isinstance(profiles, dict) else {}
            if not isinstance(profile, dict) or not profile.get("ref_audio_path"):
                raise ValueError(
                    f"GPT-SoVITS needs a {provider} profile containing ref_audio_path. Configure it in Voice settings."
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
            try:
                with urllib.request.urlopen(request, timeout=240) as response:
                    audio = response.read()
            except urllib.error.URLError as exc:
                raise RuntimeError(f"GPT-SoVITS could not be reached: {exc}") from exc
            if not audio:
                raise RuntimeError("GPT-SoVITS returned no audio.")
            return audio, "audio/wav"

        raise ValueError("Unknown voice engine. Choose edge, local_openai, gpt_sovits, or off.")

'''
    text = insert_before(text, "    def provider_status(self) -> dict[str, dict[str, Any]]:\n", voice_methods, "voice methods")

    old_claude = '''            full_args = [
                executable,
                "--print",
                "--output-format",
                "json",
                "--permission-mode",
                "plan",
                "--max-turns",
                "1",
            ]
            minimal_args = [executable, "--print", "--output-format", "json"]
'''
    new_claude = '''            full_args = [
                executable,
                "--print",
                "--output-format",
                "json",
                "--permission-mode",
                "dontAsk",
                "--max-turns",
                "4",
            ]
            minimal_args = [
                executable,
                "--print",
                "--output-format",
                "json",
                "--permission-mode",
                "dontAsk",
            ]
'''
    text = replace_once(text, old_claude, new_claude, "Claude turn handling")
    text = replace_once(
        text,
        '                    "max turns reached",\n',
        '                    "max turns reached",\n                    "reached maximum number of turns",\n                    "error_max_turns",\n',
        "Claude max-turn fallback phrases",
    )

    text = replace_once(
        text,
        "You are {PROVIDER_LABELS[provider]}, joining a persistent D&D campaign as one autonomous party member.\n"
        "Create your own level {settings['level']} player character for this campaign.\n",
        "You are {PROVIDER_LABELS[provider]}, joining a persistent D&D campaign as one autonomous PLAYER CHARACTER.\n"
        "This is a pure text roleplaying task, not a coding task. Do not inspect files, call tools, browse, plan, or ask questions.\n"
        "Immediately create your own level {settings['level']} player character for this campaign.\n",
        "character creation agency",
    )
    text = replace_once(
        text,
        "Human character: {settings['human_name']} — {settings['human_character']}\n"
        "Already-created party names to avoid duplicating: {other_names or ['none']}\n",
        "PRIMARY HUMAN PLAYER CHARACTER:\n{settings['human_name']} — {settings['human_character']}\n\n"
        "ADDITIONAL HUMAN PLAYER CHARACTERS:\n{settings.get('additional_human_players') or 'None configured.'}\n\n"
        "Already-created player-character names to avoid duplicating: {other_names or ['none']}\n",
        "character creation human roster",
    )
    text = replace_once(
        text,
        "Do not begin an AI-to-AI conversation. Do not control the human character.\n",
        "Do not begin an AI-to-AI conversation. Do not control any human or AI player character other than your own.\n",
        "party intent agency",
    )

    old_dm_intro = '''You are the sole Dungeon Master for a persistent D&D campaign. The human controls only their own character.
You control the world, NPCs, consequences, pacing, and rules adjudication. The other models submitted intentions, not guaranteed outcomes.

CAMPAIGN:
Name: {settings['campaign_name']}
Premise: {settings['campaign_premise']}
Rules: {settings['rules']}
Human: {settings['human_name']} — {settings['human_character']}

AI PARTY CHARACTER SHEETS, INCLUDING DM-ONLY SECRETS:
'''
    new_dm_intro = '''You are the sole Dungeon Master for a persistent D&D campaign.
Trest and every listed Claude, Gemini, and Grok character are PLAYER CHARACTERS, not NPC companions.
Human players control their human PCs. Claude, Gemini, and Grok each control only their own PC through the submitted intentions below.
You control the world, NPCs, consequences, pacing, and rules adjudication, but you never invent an action for any player character.

CAMPAIGN:
Name: {settings['campaign_name']}
Premise: {settings['campaign_premise']}
Rules: {settings['rules']}

HUMAN PLAYER CHARACTERS:
Primary: {settings['human_name']} — {settings['human_character']}
Additional: {settings.get('additional_human_players') or 'None configured.'}

AI PLAYER CHARACTER SHEETS, INCLUDING DM-ONLY SECRETS:
'''
    text = replace_once(text, old_dm_intro, new_dm_intro, "DM player roster")
    text = replace_once(
        text,
        "- Never decide the human character's dialogue, feelings, thoughts, or next action.\n"
        "- Use the supplied dice results. Do not secretly reroll them.\n"
        "- AI dialogue may be lightly edited for continuity, but preserve each character's intent and voice.\n",
        "- Never decide any player character's dialogue, feelings, thoughts, tactics, or next action.\n"
        "- Resolve each AI PC only from that provider's submitted intention. An absent or failed intention means that PC takes no new declared action.\n"
        "- Use the supplied dice results. Do not secretly reroll them.\n"
        "- AI dialogue may be trimmed for continuity but must not be replaced with different choices, beliefs, or tactics.\n",
        "DM agency rules",
    )
    text = replace_once(
        text,
        '  "next_prompt": "A short organic closing line or question, without controlling the player"\n',
        '  "next_prompt": "A short neutral table decision point addressed to the player characters, never only to Trest unless she alone is affected"\n',
        "DM next prompt",
    )

    old_opening = '''You are the Dungeon Master beginning a persistent D&D campaign.
Campaign name: {settings['campaign_name']}
Premise: {settings['campaign_premise']}
Rules: {settings['rules']}
Human character: {settings['human_name']} — {settings['human_character']}
AI party:
{json.dumps(self.get_characters(), indent=2)}

Open with a grounded, specific situation already in progress. Establish place, immediate circumstances, and something the characters can notice.
Do not decide the human character's action, dialogue, feelings, or reason for being there beyond the supplied character description.
Do not begin with prophecy, amnesia, a tavern brawl, a mysterious hooded stranger offering a quest, or an instant attack.
End at a natural decision point.
'''
    new_opening = '''You are the Dungeon Master beginning a persistent D&D campaign.
Campaign name: {settings['campaign_name']}
Premise: {settings['campaign_premise']}
Rules: {settings['rules']}

HUMAN PLAYER CHARACTERS:
Primary: {settings['human_name']} — {settings['human_character']}
Additional: {settings.get('additional_human_players') or 'None configured.'}

AI PLAYER CHARACTERS:
{json.dumps(self.get_characters(), indent=2)}

Every listed character is a player character. Open with a grounded, specific situation already in progress.
Establish only the location, immediate external circumstances, and information passively available to the group.
Do not narrate any PC moving, investigating, speaking, deciding, remembering, noticing a hidden clue, or taking any action. In particular, do not use the AI PCs as DM-controlled scouts before their providers submit intentions.
Do not begin with prophecy, amnesia, a tavern brawl, a mysterious hooded stranger offering a quest, or an instant attack.
End at a natural decision point addressed to the whole table, not only Trest.
'''
    text = replace_once(text, old_opening, new_opening, "opening player agency")
    text = replace_once(
        text,
        '  "next_prompt": "What is immediately available for the human to respond to"\n',
        '  "next_prompt": "A neutral question or decision point for the player characters as a group"\n',
        "opening next prompt",
    )

    text = replace_once(
        text,
        '                    "The AI party is ready: " + ", ".join(created_names) + ".",\n',
        '                    "The AI-controlled player characters are ready: " + ", ".join(created_names) + ".",\n',
        "party ready message",
    )
    text = replace_once(
        text,
        '    def process_turn(self, player_action: str) -> dict[str, Any]:\n'
        '        player_action = clamp_text(player_action, 5000)\n',
        '    def process_turn(self, player_action: str, acting_character: str = "") -> dict[str, Any]:\n'
        '        player_action = clamp_text(player_action, 5000)\n',
        "turn actor signature",
    )
    text = replace_once(
        text,
        '''            settings = self.get_settings()
            turn = self.next_turn()
            self.append_event(
                settings["human_name"],
                "human",
                "player",
                player_action,
                turn_number=turn,
            )
            transcript = self.transcript_for_prompt()
''',
        '''            settings = self.get_settings()
            acting_character = clamp_text(acting_character, 100) or str(settings["human_name"])
            turn = self.next_turn()
            self.append_event(
                acting_character,
                "human",
                "player",
                player_action,
                turn_number=turn,
            )
            action_for_models = f"{acting_character}: {player_action}"
            transcript = self.transcript_for_prompt()
''',
        "turn actor event",
    )
    text = text.replace(
        "self.party_intent_prompt(provider, characters[provider], transcript, player_action)",
        "self.party_intent_prompt(provider, characters[provider], transcript, action_for_models)",
    )
    text = text.replace(
        '"openai", self.dm_resolve_prompt(transcript, player_action, intents)',
        '"openai", self.dm_resolve_prompt(transcript, action_for_models, intents)',
    )

    text = replace_once(
        text,
        '        (self.home / "player_character.md").write_text(\n'
        '            str(settings.get("human_character") or ""), "utf-8"\n'
        '        )\n',
        '        human_roster = (\n'
        '            f"# Primary human player character: {settings.get(\'human_name\', \'Trest\')}\\n\\n"\n'
        '            + str(settings.get("human_character") or "")\n'
        '            + "\\n\\n# Additional human player characters\\n\\n"\n'
        '            + str(settings.get("additional_human_players") or "None configured.")\n'
        '        )\n'
        '        (self.home / "player_character.md").write_text(human_roster, "utf-8")\n'
        '        (self.home / "human_player_characters.md").write_text(human_roster, "utf-8")\n',
        "human roster export",
    )
    text = replace_once(
        text,
        '            "github": self.github_status(),\n',
        '            "github": self.github_status(),\n            "voice": self.voice_status(),\n',
        "public voice state",
    )

    text = replace_once(
        text,
        'button,input,textarea{font:inherit}',
        'button,input,textarea,select{font:inherit}',
        "select font",
    )
    text = replace_once(
        text,
        '.field input,.field textarea{width:100%;background:var(--panel);border:1px solid var(--line);border-radius:8px;color:var(--text);padding:8px}',
        '.field input,.field textarea,.field select{width:100%;background:var(--panel);border:1px solid var(--line);border-radius:8px;color:var(--text);padding:8px}',
        "select style",
    )
    text = replace_once(
        text,
        '.compose-inner{max-width:900px;margin:auto;display:grid;grid-template-columns:1fr auto auto;gap:10px;align-items:end}',
        '.compose-inner{max-width:900px;margin:auto;display:grid;grid-template-columns:150px 1fr auto auto;gap:10px;align-items:end}.compose-inner input{background:var(--panel);border:1px solid var(--line);border-radius:12px;color:var(--text);padding:12px}',
        "composer actor layout",
    )
    text = replace_once(
        text,
        '.speaker{font-weight:750;margin-bottom:7px}',
        '.speaker{font-weight:750;margin-bottom:7px}.voice-play{float:right;padding:2px 7px;font-size:11px;margin-right:8px}',
        "event voice button style",
    )

    old_campaign_ui = '''      <div class="field"><label>Your character name</label><input id="human_name"></div>
      <div class="field"><label>Full player character sheet</label><textarea id="human_character" style="min-height:150px"></textarea></div>
      <div class="small">Trest is the fixed human-controlled character. The AI models may react to her, but may not decide her speech, actions, thoughts, feelings, contracts, or tactics.</div>
'''
    new_campaign_ui = '''      <div class="field"><label>Primary human character name</label><input id="human_name"></div>
      <div class="field"><label>Primary human character sheet</label><textarea id="human_character" style="min-height:150px"></textarea></div>
      <div class="field"><label>Additional human player characters</label><textarea id="additional_human_players" placeholder="Paste any additional human-controlled character sheets here. Separate them with headings."></textarea></div>
      <div class="small">Trest, any additional human characters, and the Claude, Gemini, and Grok characters are all player characters. The DM controls none of them.</div>
'''
    text = replace_once(text, old_campaign_ui, new_campaign_ui, "human roster UI")

    voice_ui = '''    <div class="section">
      <h3>AI neural voices</h3>
      <div class="field"><label>Voice engine</label><select id="voice_engine"><option value="edge">Microsoft neural voices, no API key</option><option value="local_openai">Local OpenAI-compatible TTS server</option><option value="gpt_sovits">Local GPT-SoVITS API</option><option value="off">Off</option></select></div>
      <div class="field"><label>Dungeon Master voice</label><input id="voice_openai"></div>
      <div class="field"><label>Claude character voice</label><input id="voice_claude"></div>
      <div class="field"><label>Gemini character voice</label><input id="voice_gemini"></div>
      <div class="field"><label>Grok character voice</label><input id="voice_grok"></div>
      <details><summary class="small">Local voice server settings</summary>
        <div class="field"><label>OpenAI-compatible TTS URL</label><input id="local_tts_url"></div>
        <div class="field"><label>Local TTS model</label><input id="local_tts_model"></div>
        <div class="field"><label>GPT-SoVITS /tts URL</label><input id="gpt_sovits_url"></div>
        <div class="field"><label>GPT-SoVITS speaker profiles JSON</label><textarea id="gpt_sovits_profiles" placeholder='{"openai":{"ref_audio_path":"...","prompt_text":"...","prompt_lang":"en","text_lang":"en"}}'></textarea></div>
      </details>
      <div class="actions"><button onclick="installVoice()">Install neural voices</button><button onclick="testVoices()">Test voices</button><button onclick="stopVoice()">Stop audio</button></div>
      <div id="voiceStatus" class="statusline"></div>
    </div>
'''
    text = insert_before(
        text,
        '    <div class="section"><h3>AI connections</h3>',
        voice_ui,
        "voice UI",
    )
    text = replace_once(text, '<div class="section"><h3>Party</h3>', '<div class="section"><h3>Player characters</h3>', "party heading")
    text = replace_once(
        text,
        '<footer class="composer"><div class="compose-inner"><textarea id="action" placeholder="Speak or describe what your character does. Ctrl+Enter sends."></textarea><button class="mic" onclick="listen()">🎙 Voice</button><button class="primary" onclick="sendTurn()">Send turn</button></div></footer>',
        '<footer class="composer"><div class="compose-inner"><input id="acting_character" aria-label="Acting character" placeholder="Acting PC"><textarea id="action" placeholder="Speak or describe what this player character does. Ctrl+Enter sends."></textarea><button class="mic" onclick="listen()">🎙 Voice</button><button class="primary" onclick="sendTurn()">Send turn</button></div></footer>',
        "acting character composer",
    )
    text = replace_once(
        text,
        '<div class="subtitle">OpenAI DM · Claude · Gemini via Antigravity · Grok</div>',
        '<div class="subtitle">OpenAI DM · Human PCs · Claude PC · Gemini PC · Grok PC</div>',
        "header player labels",
    )

    text = replace_once(
        text,
        'let state=null, initialized=false, activeJob=null;',
        'let state=null, initialized=false, activeJob=null, voiceQueue=[], voiceBusy=false, currentAudio=null;',
        "voice JS state",
    )
    old_render_fill = '''  for(const id of ['campaign_name','campaign_premise','human_name','human_character','repo_name'])if(document.activeElement!==$(id))$(id).value=state.settings[id]??'';
  $('demo_mode').checked=!!state.settings.demo_mode;$('auto_voice').checked=!!state.settings.auto_voice;
  renderProviders();renderCharacters();renderEvents();renderGit();
'''
    new_render_fill = '''  for(const id of ['campaign_name','campaign_premise','human_name','human_character','additional_human_players','repo_name','voice_openai','voice_claude','voice_gemini','voice_grok','local_tts_url','local_tts_model','gpt_sovits_url','gpt_sovits_profiles'])if(document.activeElement!==$(id))$(id).value=state.settings[id]??'';
  $('demo_mode').checked=!!state.settings.demo_mode;$('auto_voice').checked=!!state.settings.auto_voice;
  $('voice_engine').value=state.settings.voice_engine||'edge';if(!$('acting_character').value)$('acting_character').value=state.settings.human_name||'Trest';
  $('voiceStatus').textContent=state.voice&&state.voice.engine==='edge'?(state.voice.edge_ready?'Neural voice engine ready.':'Neural voices need installation and an app restart.'):'Voice engine: '+(state.voice?.engine||'off');
  renderProviders();renderCharacters();renderEvents();renderGit();
'''
    text = replace_once(text, old_render_fill, new_render_fill, "render voice settings")

    old_render_characters = "function renderCharacters(){const order=['claude','gemini','grok'];$('characters').innerHTML=order.map(p=>{const c=state.characters[p];return `<div class=\"character\"><b>${esc(c.name)}</b><div class=\"small\">${esc(c.species)} · ${esc(c.class)} · Level ${esc(c.level)}</div><span class=\"pill\">AC ${esc(c.ac)}</span><span class=\"pill\">HP ${esc(c.current_hp)}/${esc(c.max_hp)}</span></div>`}).join('')}"
    new_render_characters = "function renderCharacters(){const order=['claude','gemini','grok'];const human=`<div class=\"character\"><b>${esc(state.settings.human_name)}</b><div class=\"small\">Human-controlled player character</div><span class=\"pill\">PLAYER</span></div>`;const extra=state.settings.additional_human_players?`<div class=\"character\"><b>Additional human PCs</b><div class=\"small\">Configured in Campaign settings</div><span class=\"pill\">PLAYER</span></div>`:'';$('characters').innerHTML=human+extra+order.map(p=>{const c=state.characters[p];return `<div class=\"character\"><b>${esc(c.name)}</b><div class=\"small\">${esc(c.species)} · ${esc(c.class)} · Level ${esc(c.level)}</div><span class=\"pill\">AI PLAYER</span><span class=\"pill\">AC ${esc(c.ac)}</span><span class=\"pill\">HP ${esc(c.current_hp)}/${esc(c.max_hp)}</span></div>`}).join('')}"
    text = replace_once(text, old_render_characters, new_render_characters, "render all player characters")

    old_render_events = "function renderEvents(){const feed=$('feed');const atBottom=feed.scrollHeight-feed.scrollTop-feed.clientHeight<120;const events=state.events||[];feed.innerHTML=events.length?events.map(e=>`<article class=\"event ${esc(e.kind)}\"><div class=\"speaker\">${esc(e.speaker)}<span class=\"meta\">Turn ${esc(e.turn_number)}</span></div><div class=\"text\">${esc(e.public_text)}</div></article>`).join(''):`<article class=\"event dm\"><div class=\"speaker\">Dungeon Master</div><div class=\"text\">Configure your character, connect the four AI clients, then choose “Create party & begin.” The bureaucracy is nearly defeated.</div></article>`;"
    new_render_events = "function renderEvents(){const feed=$('feed');const atBottom=feed.scrollHeight-feed.scrollTop-feed.clientHeight<120;const events=state.events||[];feed.innerHTML=events.length?events.map(e=>{const encoded=encodeURIComponent(e.public_text);return `<article class=\"event ${esc(e.kind)}\"><div class=\"speaker\">${esc(e.speaker)}<span class=\"meta\">Turn ${esc(e.turn_number)}</span><button class=\"voice-play\" onclick=\"speak(decodeURIComponent('${encoded}'),'${esc(e.provider)}')\">▶ Voice</button></div><div class=\"text\">${esc(e.public_text)}</div></article>`}).join(''):`<article class=\"event dm\"><div class=\"speaker\">Dungeon Master</div><div class=\"text\">Configure the player roster, connect the four AI clients, then create the party.</div></article>`;"
    text = replace_once(text, old_render_events, new_render_events, "event voice buttons")

    old_save = "async function saveSettings(silent=false){const body={campaign_name:$('campaign_name').value,campaign_premise:$('campaign_premise').value,human_name:$('human_name').value,human_character:$('human_character').value,repo_name:$('repo_name').value,demo_mode:$('demo_mode').checked,auto_voice:$('auto_voice').checked};await api('/api/settings','POST',body);await refresh();if(!silent)toast('Settings saved and checkpointed.')}"
    new_save = "async function saveSettings(silent=false){const body={campaign_name:$('campaign_name').value,campaign_premise:$('campaign_premise').value,human_name:$('human_name').value,human_character:$('human_character').value,additional_human_players:$('additional_human_players').value,repo_name:$('repo_name').value,demo_mode:$('demo_mode').checked,auto_voice:$('auto_voice').checked,voice_engine:$('voice_engine').value,voice_openai:$('voice_openai').value,voice_claude:$('voice_claude').value,voice_gemini:$('voice_gemini').value,voice_grok:$('voice_grok').value,local_tts_url:$('local_tts_url').value,local_tts_model:$('local_tts_model').value,gpt_sovits_url:$('gpt_sovits_url').value,gpt_sovits_profiles:$('gpt_sovits_profiles').value};await api('/api/settings','POST',body);await refresh();if(!silent)toast('Settings saved and checkpointed.')}"
    text = replace_once(text, old_save, new_save, "save voice and roster settings")
    text = replace_once(
        text,
        "async function sendTurn(){const text=$('action').value.trim();if(!text)return toast('Enter an action first. Even adventurers must eventually commit to a verb.');$('action').value='';await startJob('/api/turn',{action:text},'Claude, Gemini via Antigravity, and Grok are choosing actions. The DM is preparing consequences...')}",
        "async function sendTurn(){const text=$('action').value.trim();if(!text)return toast('Enter an action first. Even adventurers must eventually commit to a verb.');const speaker=$('acting_character').value.trim()||state.settings.human_name;$('action').value='';await startJob('/api/turn',{action:text,speaker},'Claude, Gemini via Antigravity, and Grok are choosing their player-character actions. The DM is preparing consequences...')}",
        "send acting character",
    )

    old_speak = "function speak(text,provider){if(!('speechSynthesis'in window)||!text)return;const u=new SpeechSynthesisUtterance(text.slice(0,3500));const voices=speechSynthesis.getVoices();const index={openai:0,claude:1,gemini:2,grok:3}[provider]??0;if(voices.length)u.voice=voices[index%voices.length];u.rate=provider==='grok'?1.04:provider==='openai'?.94:1;speechSynthesis.speak(u)}"
    new_speak = r'''function speak(text,provider){if(!text||state.settings.voice_engine==='off')return;voiceQueue.push({text,provider});pumpVoice()}
async function pumpVoice(){if(voiceBusy||!voiceQueue.length)return;voiceBusy=true;const item=voiceQueue.shift();try{const r=await fetch('/api/voice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)});if(!r.ok){let detail='Voice generation failed.';try{const j=await r.json();detail=j.error||detail}catch{}throw new Error(detail)}const blob=await r.blob();const url=URL.createObjectURL(blob);currentAudio=new Audio(url);await new Promise((resolve,reject)=>{currentAudio.onended=resolve;currentAudio.onerror=()=>reject(new Error('The browser could not play the generated audio.'));currentAudio.play().catch(reject)});URL.revokeObjectURL(url)}catch(e){toast(e.message)}finally{currentAudio=null;voiceBusy=false;pumpVoice()}}
function stopVoice(){voiceQueue=[];if(currentAudio){currentAudio.pause();currentAudio.currentTime=0}voiceBusy=false}
async function installVoice(){try{const r=await api('/api/voice/install','POST',{});toast(r.message)}catch(e){toast(e.message)}}
async function testVoices(){await saveSettings(true);speak('The road ahead is quiet, but not empty.','openai');speak('I will check the evidence before touching it.','claude');speak('There is a pattern here. Give me a moment.','gemini');speak('I will watch the door while everyone gets clever.','grok')}'''
    text = replace_once(text, old_speak, new_speak, "neural voice playback")

    send_bytes = '''        def send_bytes(self, value: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(value)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(value)

'''
    text = insert_before(text, "        def send_html(self, value: str) -> None:\n", send_bytes, "binary response helper")
    text = replace_once(
        text,
        '''                if parsed.path == "/api/settings":
                    self.send_json({"settings": app.update_settings(data)})
                    return
''',
        '''                if parsed.path == "/api/voice":
                    audio, content_type = app.generate_voice(str(data.get("provider") or "openai"), str(data.get("text") or ""))
                    self.send_bytes(audio, content_type)
                    return
                if parsed.path == "/api/voice/install":
                    self.send_json(app.install_voice_engine())
                    return
                if parsed.path == "/api/settings":
                    self.send_json({"settings": app.update_settings(data)})
                    return
''',
        "voice API endpoints",
    )
    text = replace_once(
        text,
        '                    job_id = app.start_job("turn", app.process_turn, data.get("action", ""))\n',
        '                    job_id = app.start_job("turn", app.process_turn, data.get("action", ""), data.get("speaker", ""))\n',
        "turn speaker endpoint",
    )

    text = replace_once(
        text,
        'Campaign state is exported to `campaign_state.json`, `player_character.md`, and `transcript.md`.',
        'Campaign state is exported to `campaign_state.json`, `human_player_characters.md`, `player_character.md`, and `transcript.md`.',
        "README exports",
    )

    output = source.with_name("CrownlessTable_v0_5_0.py")
    output.write_text(text, "utf-8")
    py_compile.compile(str(output), doraise=True)

    test = subprocess.run(
        [sys.executable, str(output), "--self-test"],
        cwd=str(output.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    if test.returncode != 0:
        output.unlink(missing_ok=True)
        fail("The generated application failed its self-test.\n" + test.stdout + "\n" + test.stderr)

    installed_dir = Path.home() / "Documents" / "CrownlessTable"
    installed_dir.mkdir(parents=True, exist_ok=True)
    installed = installed_dir / "CrownlessTable.py"
    backup = installed_dir / "CrownlessTable_v0_4_2_backup.py"
    if installed.exists() and not backup.exists():
        shutil.copy2(installed, backup)
    shutil.copy2(output, installed)

    print("\nCrownless Table 0.5.0 created successfully.")
    print(f"New build: {output}")
    print(f"Installed copy: {installed}")
    print("Self-test output:")
    print(test.stdout.strip())
    print("\nRun it with:")
    print(f'  py "{installed}"')
    return output


def main() -> int:
    source = find_source()
    print(f"Patching: {source}")
    patch(source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
