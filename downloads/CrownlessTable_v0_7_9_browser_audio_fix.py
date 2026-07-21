#!/usr/bin/env python3
"""Install Crownless Table 0.7.9 browser-audio playback repair.

GPT-SoVITS and the local bridge can successfully return all four test WAVs while
Chrome/Edge still produces silence. The old Test cast handler awaited settings
and HTTP work before calling HTMLAudioElement.play(), by which time the browser's
transient user-activation permission could be gone.

This update:
- unlocks a persistent Web Audio context synchronously from the button click;
- decodes and plays returned WAV bytes through that context;
- keeps an HTMLAudioElement fallback;
- displays Generating / Decoding / Playing status for each speaker;
- reports browser autoplay, decode, and output errors clearly;
- preserves campaign state and all voice profiles.
"""
from __future__ import annotations

import py_compile
import shutil
import socket
import subprocess
import sys
from pathlib import Path

TARGET_VERSION = "0.7.9"
TARGET_BUILD = "participant-blind-browser-audio-unlock-v19-20260720"
SUPPORTED = {
    ("0.7.7", "participant-blind-function-scoped-voice-recovery-v17-20260720"),
    ("0.7.8", "participant-blind-reference-audio-normalization-v18-20260720"),
}

OLD_STATE = "let state=null, initialized=false, activeJob=null, voiceQueue=[], voiceBusy=false, currentAudio=null;"
NEW_STATE = "let state=null, initialized=false, activeJob=null, voiceQueue=[], voiceBusy=false, currentAudio=null, voiceAudioContext=null, currentVoiceSource=null, voiceUnlocked=false;"

OLD_AUDIO = r'''function speak(text,provider){if(!text||state.settings.voice_engine==='off')return;voiceQueue.push({text,provider});pumpVoice()}
async function pumpVoice(){if(voiceBusy||!voiceQueue.length)return;voiceBusy=true;const item=voiceQueue.shift();try{const r=await fetch('/api/voice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)});if(!r.ok){let detail='Voice generation failed.';try{const j=await r.json();detail=j.error||detail}catch{}throw new Error(detail)}const blob=await r.blob();const url=URL.createObjectURL(blob);currentAudio=new Audio(url);await new Promise((resolve,reject)=>{currentAudio.onended=resolve;currentAudio.onerror=()=>reject(new Error('The browser could not play the generated audio.'));currentAudio.play().catch(reject)});URL.revokeObjectURL(url)}catch(e){toast(e.message)}finally{currentAudio=null;voiceBusy=false;pumpVoice()}}
function stopVoice(){voiceQueue=[];if(currentAudio){currentAudio.pause();currentAudio.currentTime=0}voiceBusy=false}'''

NEW_AUDIO = r'''function voiceLabel(provider){return ({openai:'Dungeon Master',claude:'Claude',gemini:'Gemini',grok:'Grok'})[provider]||provider||'Voice'}
function setVoicePlaybackStatus(message){const el=$('voiceStatus');if(el)el.textContent=message}
function unlockVoiceAudio(){
  const AudioCtx=window.AudioContext||window.webkitAudioContext;
  if(!AudioCtx){voiceUnlocked=true;return false}
  try{
    if(!voiceAudioContext)voiceAudioContext=new AudioCtx();
    if(voiceAudioContext.state==='suspended')voiceAudioContext.resume().catch(()=>{});
    const buffer=voiceAudioContext.createBuffer(1,1,22050);
    const source=voiceAudioContext.createBufferSource();
    source.buffer=buffer;source.connect(voiceAudioContext.destination);source.start(0);
    voiceUnlocked=true;return true
  }catch(e){setVoicePlaybackStatus('Audio unlock failed: '+e.message);return false}
}
function speak(text,provider){if(!text||state.settings.voice_engine==='off')return;voiceQueue.push({text,provider});pumpVoice()}
async function playVoiceBytes(bytes,contentType){
  const AudioCtx=window.AudioContext||window.webkitAudioContext;
  if(AudioCtx){
    if(!voiceAudioContext)voiceAudioContext=new AudioCtx();
    if(voiceAudioContext.state==='suspended')await voiceAudioContext.resume();
    let decoded;
    try{decoded=await voiceAudioContext.decodeAudioData(bytes.slice(0))}
    catch(e){throw new Error('The browser could not decode the generated WAV: '+e.message)}
    currentVoiceSource=voiceAudioContext.createBufferSource();
    currentVoiceSource.buffer=decoded;
    currentVoiceSource.connect(voiceAudioContext.destination);
    await new Promise((resolve,reject)=>{
      currentVoiceSource.onended=resolve;
      try{currentVoiceSource.start(0)}catch(e){reject(e)}
    });
    currentVoiceSource=null;return
  }
  const blob=new Blob([bytes],{type:contentType||'audio/wav'});
  const url=URL.createObjectURL(blob);
  currentAudio=new Audio();currentAudio.src=url;currentAudio.preload='auto';currentAudio.volume=1;currentAudio.muted=false;currentAudio.setAttribute('playsinline','');
  try{
    await new Promise((resolve,reject)=>{
      currentAudio.onended=resolve;
      currentAudio.onerror=()=>reject(new Error('The browser could not play the generated audio file.'));
      currentAudio.play().catch(error=>reject(new Error(error.name==='NotAllowedError'?'Browser audio is blocked. Click Test cast again or allow sound for 127.0.0.1.':error.message)))
    })
  }finally{URL.revokeObjectURL(url);currentAudio=null}
}
async function pumpVoice(){
  if(voiceBusy||!voiceQueue.length)return;
  voiceBusy=true;const item=voiceQueue.shift();const label=voiceLabel(item.provider);
  try{
    setVoicePlaybackStatus('Generating '+label+' voice…');
    const r=await fetch('/api/voice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)});
    if(!r.ok){let detail='Voice generation failed.';try{const j=await r.json();detail=j.error||detail}catch{}throw new Error(detail)}
    const bytes=await r.arrayBuffer();
    if(!bytes.byteLength)throw new Error('The voice server returned an empty audio file.');
    setVoicePlaybackStatus('Decoding '+label+' voice…');
    setVoicePlaybackStatus('Playing '+label+'…');
    await playVoiceBytes(bytes,r.headers.get('Content-Type')||'audio/wav');
  }catch(e){setVoicePlaybackStatus('Voice playback failed: '+e.message);toast('Voice playback failed: '+e.message)}
  finally{currentAudio=null;currentVoiceSource=null;voiceBusy=false;if(voiceQueue.length)pumpVoice();else if(!$('voiceStatus').textContent.startsWith('Voice playback failed'))setVoicePlaybackStatus('Test cast finished. Audio playback is ready.')}
}
function stopVoice(){voiceQueue=[];if(currentVoiceSource){try{currentVoiceSource.stop()}catch{}currentVoiceSource=null}if(currentAudio){currentAudio.pause();currentAudio.currentTime=0;currentAudio=null}voiceBusy=false;setVoicePlaybackStatus('Audio stopped.')}'''

OLD_TEST = "async function testVoices(){await saveSettings(true);speak('The road ahead is quiet, but not empty.','openai');speak('I will check the evidence before touching it.','claude');speak('There is a pattern here. Give me a moment.','gemini');speak('I will watch the door while everyone gets clever.','grok')}"
NEW_TEST = "async function testVoices(){unlockVoiceAudio();setVoicePlaybackStatus('Audio unlocked. Preparing the four-voice test…');await saveSettings(true);speak('The road ahead is quiet, but not empty.','openai');speak('I will check the evidence before touching it.','claude');speak('There is a pattern here. Give me a moment.','gemini');speak('I will watch the door while everyone gets clever.','grok')}"

OLD_STARTUP = "$('action').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();sendTurn()}});window.lastSpokenId=0;"
NEW_STARTUP = "document.addEventListener('pointerdown',()=>unlockVoiceAudio(),{once:true,capture:true});$('action').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();sendTurn()}});window.lastSpokenId=0;"


def fail(message: str) -> "NoReturn":
    print(f"\nERROR: {message}")
    raise SystemExit(1)


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


def installed_path() -> Path:
    return Path.home() / "Documents" / "CrownlessTable" / "CrownlessTable.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"Patch point {label!r} expected once but was found {count} times.")
    return text.replace(old, new, 1)


def source_identity(text: str) -> tuple[str, str] | None:
    for version, build in SUPPORTED:
        if f'VERSION = "{version}"' in text and f'BUILD_ID = "{build}"' in text:
            return version, build
    if f'VERSION = "{TARGET_VERSION}"' in text and f'BUILD_ID = "{TARGET_BUILD}"' in text:
        return TARGET_VERSION, TARGET_BUILD
    return None


def patch(text: str, version: str, build: str) -> str:
    text = replace_once(text, f'VERSION = "{version}"', f'VERSION = "{TARGET_VERSION}"', "version")
    text = replace_once(text, f'BUILD_ID = "{build}"', f'BUILD_ID = "{TARGET_BUILD}"', "build id")
    text = replace_once(text, OLD_STATE, NEW_STATE, "browser voice state")
    text = replace_once(text, OLD_AUDIO, NEW_AUDIO, "browser audio queue")
    text = replace_once(text, OLD_TEST, NEW_TEST, "test-cast audio unlock")
    text = replace_once(text, OLD_STARTUP, NEW_STARTUP, "first-interaction audio unlock")
    return text


def main() -> int:
    if port_open(8765):
        fail("Crownless Table is still running. Press Ctrl+C in its console, then run this update again.")
    source = installed_path()
    if not source.is_file():
        fail("The installed CrownlessTable.py file was not found.")
    try:
        py_compile.compile(str(source), doraise=True)
    except Exception as exc:
        fail(f"The installed application does not compile: {exc}")
    current = source.read_text("utf-8", errors="replace")
    identity = source_identity(current)
    if not identity:
        fail("This updater requires Crownless Table 0.7.7 or 0.7.8.")
    if identity[0] == TARGET_VERSION:
        print("Crownless Table 0.7.9 is already installed.")
        return 0

    output = Path.cwd() / "CrownlessTable_v0_7_9.py"
    output.write_text(patch(current, *identity), "utf-8")
    try:
        py_compile.compile(str(output), doraise=True)
    except Exception as exc:
        output.unlink(missing_ok=True)
        fail(f"The generated 0.7.9 application did not compile: {exc}")

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

    backup = source.parent / f"CrownlessTable_v{identity[0].replace('.', '_')}_backup_before_0_7_9.py"
    if not backup.exists():
        shutil.copy2(source, backup)
    shutil.copy2(output, source)
    py_compile.compile(str(source), doraise=True)

    print("\nCrownless Table 0.7.9 installed successfully.")
    print("Browser audio now unlocks immediately from Test cast and plays through a persistent Web Audio context.")
    print("Campaign and voice profiles were preserved.")
    print("Self-test output:")
    print(test.stdout.strip())
    print("\nRun:")
    print(f'  py "{source}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
