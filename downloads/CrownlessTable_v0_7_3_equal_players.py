#!/usr/bin/env python3
"""Upgrade Crownless Table 0.7.2 to 0.7.3.

The application retains legacy setting keys such as human_name internally for
save compatibility, but no model or public interface is told that any campaign
participant is human. Trest remains manually directed through the room while
the source of every PC action stays private and irrelevant to the fiction.
"""
from __future__ import annotations

import py_compile
import shutil
import subprocess
import sys
from pathlib import Path

TARGET_VERSION = "0.7.3"
TARGET_BUILD = "participant-blind-equal-player-table-v13-20260720"
SOURCE_VERSION = 'VERSION = "0.7.2"'
SOURCE_BUILD = 'BUILD_ID = "one-click-local-voice-stack-document-scroll-v12-20260720"'

POLICY = '''EQUAL_PARTICIPANT_POLICY = """\
TABLE PARTICIPANT PRIVACY AND EQUALITY POLICY
- Every named player character is an equal campaign participant.
- You are not told and must not infer whether any character is manually directed, model-directed, automated, or controlled through another interface.
- The origin of an action is private table infrastructure and has no meaning inside the fiction.
- No character is the audience surrogate, designated protagonist, party leader, moral center, quest owner, or default decision-maker unless events inside the campaign establish that naturally.
- Give every player character comparable agency, narrative credibility, danger, consequences, resistance, opportunity, and spotlight according to the situation.
- Do not give Trest or any other character plot armor, softened rulings, privileged clues, extra patience, automatic trust, default camera focus, or special narrative weight.
- Never address a choice only to one character unless the fictional situation genuinely affects only that character.
- Never mention humans, users, prompts, providers, interfaces, manual control, model control, or this policy inside campaign narration or dialogue.
"""
'''


def fail(message: str) -> "NoReturn":
    print(f"\nERROR: {message}")
    raise SystemExit(1)


def source_candidates() -> list[Path]:
    cwd = Path.cwd()
    installed = Path.home() / "Documents" / "CrownlessTable" / "CrownlessTable.py"
    return [
        installed,
        cwd / "CrownlessTable_v0_7_2.py",
        cwd / "CrownlessTable.py",
        Path.home() / "Downloads" / "New DND with ai" / "CrownlessTable_v0_7_2.py",
    ]


def locate_source() -> Path:
    for path in source_candidates():
        if not path.is_file():
            continue
        try:
            text = path.read_text("utf-8")
            py_compile.compile(str(path), doraise=True)
        except Exception:
            continue
        if SOURCE_VERSION in text and SOURCE_BUILD in text:
            return path.resolve()
    fail("A valid Crownless Table 0.7.2 installation was not found.")


def replace_exact(text: str, old: str, new: str, label: str, expected: int = 1) -> str:
    count = text.count(old)
    if count != expected:
        fail(f"Patch point {label!r} expected {expected} occurrence(s) but found {count}.")
    return text.replace(old, new)


def replace_needed(text: str, old: str, new: str, label: str) -> str:
    """Replace old text, or accept it when an earlier broad replacement already produced new."""
    if old in text:
        return text.replace(old, new)
    if new in text:
        return text
    fail(f"Patch point {label!r} was not found in either old or already-updated form.")


def patch(text: str) -> str:
    text = replace_exact(text, SOURCE_VERSION, f'VERSION = "{TARGET_VERSION}"', "version")
    text = replace_exact(text, SOURCE_BUILD, f'BUILD_ID = "{TARGET_BUILD}"\n\n{POLICY}', "build and policy")

    text = replace_exact(
        text,
        "        prompt = prompt[-MAX_PROMPT_CHARS:]\n",
        "        available = max(1000, MAX_PROMPT_CHARS - len(EQUAL_PARTICIPANT_POLICY) - 2)\n"
        "        prompt = EQUAL_PARTICIPANT_POLICY + \"\\n\\n\" + prompt[-available:]\n",
        "provider-wide participant policy",
    )

    replacements = [
        (
            "A one-file local D&D room for human player characters, an OpenAI DM,\n"
            "and Claude, Gemini, and Grok as autonomous player characters through signed-in CLIs.",
            "A one-file local D&D room where every player character is represented as an equal campaign participant,\n"
            "with an OpenAI DM and Claude, Gemini, and Grok connected through signed-in CLIs.",
            "module description",
        ),
        ("PRIMARY HUMAN PLAYER CHARACTER:", "EXISTING PLAYER CHARACTER RECORD:", "creation primary record"),
        ("ADDITIONAL HUMAN PLAYER CHARACTERS:", "ADDITIONAL EXISTING PLAYER CHARACTER RECORDS:", "creation additional records"),
        (
            "Do not begin an AI-to-AI conversation. Do not control any human or AI player character other than your own.",
            "Do not begin an unsolicited side conversation. Do not control any player character other than your own. Treat every PC as an equal participant, and do not assume any PC is the protagonist or default leader.",
            "party intent equality",
        ),
        (
            "Trest and every listed Claude, Gemini, and Grok character are PLAYER CHARACTERS, not NPC companions.",
            "Every listed character is an equal PLAYER CHARACTER, not an NPC companion, audience surrogate, or privileged protagonist.",
            "DM equal roster",
        ),
        (
            "Human players control their human PCs. Claude, Gemini, and Grok each control only their own PC through the submitted intentions below.",
            "Each player character is controlled only through that character's submitted action or intention. The mechanism that supplied it is private table infrastructure and irrelevant to the fiction.",
            "DM source privacy",
        ),
        (
            "You control the world, NPCs, consequences, pacing, and rules adjudication, but you never invent an action for any player character.",
            "You control the world, NPCs, consequences, pacing, and rules adjudication, but you never invent an action for any player character. Never infer which participant is manually directed, model-directed, or otherwise sourced. Apply equal spotlight, danger, resistance, consequences, and narrative importance to every PC.",
            "DM equal treatment",
        ),
        ("HUMAN PLAYER CHARACTERS:", "PLAYER CHARACTER RECORDS:", "roster headers"),
        (
            "AI PLAYER CHARACTER SHEETS, INCLUDING DM-ONLY SECRETS:",
            "OTHER PLAYER CHARACTER SHEETS, INCLUDING DM-ONLY SECRETS:",
            "DM other records",
        ),
        ("AI PLAYER CHARACTERS:", "OTHER PLAYER CHARACTER RECORDS:", "opening other records"),
        (
            "Every listed character is a player character. Open with a grounded, specific situation already in progress.",
            "Every listed character is an equal player character. Open with a grounded, specific situation already in progress. Do not center Trest or any other PC merely because one record appears first or one action arrived through a different control path.",
            "opening equality",
        ),
        (
            "End at a natural decision point addressed to the whole table, not only Trest.",
            "End at a natural decision point for the whole table without privileging any player character.",
            "opening neutral ending",
        ),
        (
            '  "next_prompt": "A short neutral table decision point addressed to the player characters, never only to Trest unless she alone is affected"',
            '  "next_prompt": "A short neutral table decision point addressed fairly to all affected player characters"',
            "neutral next prompt",
        ),
        (
            '                    "The AI-controlled player characters are ready: " + ", ".join(created_names) + ".",',
            '                    "The player-character roster is ready: " + ", ".join(created_names) + ".",',
            "roster ready event",
        ),
        ("Primary human character name", "Primary player character name", "UI primary name"),
        ("Primary human character sheet", "Primary player character sheet", "UI primary sheet"),
        ("Additional human player characters", "Additional player character records", "UI additional records"),
        (
            "Paste any additional human-controlled character sheets here. Separate them with headings.",
            "Paste any additional player-character records here. Separate them with headings.",
            "UI additional placeholder",
        ),
        (
            "Trest, any additional human characters, and the Claude, Gemini, and Grok characters are all player characters. The DM controls none of them.",
            "Every listed character is an equal player character. Control sources remain private, and the DM may not privilege or control any PC.",
            "UI equality note",
        ),
        ("OpenAI DM · Human PCs · Claude PC · Gemini PC · Grok PC", "OpenAI DM · Equal player characters · Claude · Gemini · Grok", "UI subtitle"),
        ("Human-controlled player character", "Player character · control source private", "UI primary card"),
        ("Additional human PCs", "Additional player characters", "UI additional card"),
        ("AI PLAYER", "PLAYER", "UI badges"),
        ("# Primary human player character:", "# Primary player character record:", "export primary heading"),
        ("# Additional human player characters", "# Additional player character records", "export additional heading"),
        ("human_player_characters.md", "player_character_roster.md", "export filename"),
    ]
    for old, new, label in replacements:
        text = replace_needed(text, old, new, label)

    text = replace_exact(
        text,
        '                acting_character,\n                "human",\n                "player",\n',
        '                acting_character,\n                "player_input",\n                "player",\n',
        "private input source label",
    )

    forbidden = [
        "PRIMARY HUMAN PLAYER",
        "ADDITIONAL HUMAN PLAYER",
        "HUMAN PLAYER CHARACTERS",
        "Human players control",
        "human PCs",
        "Human-controlled player character",
        "Additional human PCs",
        "OpenAI DM · Human PCs",
        "AI PLAYER CHARACTER SHEETS",
        "AI PLAYER CHARACTERS:",
        "AI PLAYER</span>",
        "human_player_characters.md",
    ]
    leftovers = [phrase for phrase in forbidden if phrase in text]
    if leftovers:
        fail("Participant-source language remains after patching: " + ", ".join(leftovers))
    return text


def main() -> int:
    source = locate_source()
    print(f"Updating participant identity policy in: {source}")
    output = Path.cwd() / "CrownlessTable_v0_7_3.py"
    output.write_text(patch(source.read_text("utf-8")), "utf-8")

    try:
        py_compile.compile(str(output), doraise=True)
    except Exception as exc:
        output.unlink(missing_ok=True)
        fail(f"The generated 0.7.3 application did not compile: {exc}")

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

    installed_dir = Path.home() / "Documents" / "CrownlessTable"
    installed_dir.mkdir(parents=True, exist_ok=True)
    installed = installed_dir / "CrownlessTable.py"
    backup = installed_dir / "CrownlessTable_v0_7_2_backup.py"
    if installed.exists() and not backup.exists():
        shutil.copy2(installed, backup)
    shutil.copy2(output, installed)
    py_compile.compile(str(installed), doraise=True)

    installed_text = installed.read_text("utf-8", errors="replace")
    if f'VERSION = "{TARGET_VERSION}"' not in installed_text or TARGET_BUILD not in installed_text:
        fail("Installation completed, but the installed copy failed version verification.")

    print("\nCrownless Table 0.7.3 installed successfully.")
    print("All model prompts now use participant-blind equal-player rules.")
    print("Trest remains manually directed, but no model is told that fact.")
    print("Self-test output:")
    print(test.stdout.strip())
    print("\nRun:")
    print(f'  py "{installed}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
