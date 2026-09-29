# LYRA

LYRA is a local-first Windows voice assistant built from Python, Faster-Whisper, Ollama, Piper, and controlled desktop skills. Application code and user data are separate. LYRA does not send conversations to a hosted AI service; weather/search features may access the internet when explicitly requested.

**Application version:** `0.2.0` (`lyra/version.py`)

## Architecture

```text
Launcher → optional GitHub Releases updater → Ollama/model checks → LYRA core
                                                          │
Microphone → short Vosk wake gate → Whisper Base command STT → session/router
                                                          │
                                            built-in skills / safe action planner
                                                          │
                                  Ollama (Phi) ───────── Piper TTS → speakers

User data (%APPDATA%/Lyra on Windows): settings, memory, logs, models
```

- `lyra/ear.py` loads one Faster-Whisper model per process. The default is CPU `int8`, `base.en`.
- `lyra/wake.py` loads the optional Vosk model once. While asleep it processes short audio clips and runs full Whisper only after a wake hit. If the Vosk model is absent, LYRA safely falls back to the previous Whisper wake gate.
- `lyra/voice.py` loads Piper once. Piper's 16-bit PCM bytes are validated and converted to NumPy `int16` arrays before sounddevice playback. One lock serializes beeps and speech; streams are stopped and closed after each response.
- `lyra/brain.py` keeps Ollama warm (`keep_alive`) and streams ordinary responses. The structured planner is invoked only for detected multi-step computer requests to avoid adding an LLM round trip to regular chat or known single commands.
- `lyra/actions/` validates bounded JSON plans and dispatches only registered Python actions. No model-generated PowerShell, CMD, Python, or shell command is evaluated.
- `lyra/computer/` is the desktop automation adapter; `lyra/screen/` provides `capture_screen()` and window-title capture for future visual reasoning.
- `lyra/updater.py` updates application files from GitHub Releases with SHA-256 verification and rollback. Memory, configuration, logs, and downloaded models live outside the application directory.

## Installation on Windows

### Requirements

- Windows 10/11 and Python 3.10–3.12 (the installer uses the Python launcher where possible; Python does not need to be used manually after installation).
- Ollama is a separate application. Install it from [ollama.com](https://ollama.com).
- Microphone, speakers, and internet access for initial Python/voice downloads.

### Install once

1. Download/clone the LYRA source package.
2. Double-click `install.bat`.
3. It copies application files to `%LOCALAPPDATA%\Programs\LYRA`, creates a private `.venv`, installs dependencies, and creates Desktop and Start Menu shortcuts.
4. Install and start Ollama if it is not already installed.
5. Double-click **LYRA**. At first launch the launcher checks Ollama and the configured model. If the model is missing it explains that the download is several GB and asks before running `ollama pull`.

The installer does **not** silently fetch Phi model files. The Piper voice pack downloads on first speech (approximately 60 MB for the default voice); see Configuration to use another voice.

### Launch

Use the **LYRA** Desktop/Start Menu shortcut, or double-click `run_lyra.bat` in the install directory. For development:

```bat
.venv\Scripts\python.exe -m lyra.launcher
.venv\Scripts\python.exe -m lyra.launcher --text
.venv\Scripts\python.exe -m lyra.launcher --always
.venv\Scripts\python.exe main.py --devices
```

`--text` and `--always` are passed through to the core. `--no-update-check` skips the optional release check; `--skip-llm-check` is intended for offline/development diagnostics only.

## Ollama and model setup

Install Ollama separately and leave its local service running. The default model is `phi4-mini:3.8b`. The launcher checks Ollama and the selected model and requests consent before pulling a missing multi-gigabyte model. The equivalent explicit command is:

```bat
ollama pull phi4-mini:3.8b
```

To change the model, update `OLLAMA_MODEL` in the user's settings file (see below). LYRA and Ollama/model files update independently; LYRA updates do not replace or delete Ollama models.

## Wake-word setup

The intended phrase is **“Hey Lyra.”** The wake matcher requires a wake prefix at the start of the phrase and tolerates a small edit distance only on the following name. This allows the tested forms `Lyra`, `Laira`, `Lira`, `Laura`, `later`, `Leyra`, `Leira`, `Lyrah`, plus the explicitly requested `Bobby` transcription; phrases such as “see you later”, “okay”, and “hip hop” do not satisfy the prefix/name shape.

For lightweight wake recognition, install the optional Vosk English model once (about 40 MB):

```bat
.venv\Scripts\python.exe -m lyra.setup_wake_model
```

This download is explicit and goes into the user data directory. Restart LYRA afterward. With no model installed, the existing Whisper wake behavior remains available. Full Whisper command recognition is unchanged and runs after the lightweight gate accepts a wake phrase.

## Configuration and user data

On Windows, settings and user data live in `%APPDATA%\Lyra` (typically `C:\Users\<you>\AppData\Roaming\Lyra`). Development can override the location with `LYRA_DATA_DIR`. LYRA creates the directory as needed.

Create `%APPDATA%\Lyra\settings.json` from `config/settings.example.json`. Supported overrides include:

```json
{
  "OLLAMA_MODEL": "phi4-mini:3.8b",
  "VOICE_MODEL": "en_US-amy-medium",
  "OUTPUT_DEVICE": null,
  "WAKE_FUZZY_MAX_DISTANCE": 2,
  "WAKE_WINDOW_SECONDS": 4.0,
  "WHISPER_MODEL": "base.en",
  "OLLAMA_URL": "http://localhost:11434/api/chat",
  "LOG_LEVEL": "INFO"
}
```

Environment variables such as `LYRA_OLLAMA_MODEL`, `LYRA_VOICE_MODEL`, and `LYRA_OUTPUT_DEVICE` override JSON settings. Never put API credentials in source or commit personal settings. Local state includes:

- `memory.json` — persistent user memory
- `settings.json` — non-secret user preferences
- `logs/lyra.log` — rotating diagnostics
- `models/` — Piper and optional Vosk assets

An existing project-root `memory.json` is copied to the user data directory on first load when no new memory file exists. The original is not deleted.

## Updating LYRA

The launcher checks the latest stable GitHub Release and compares semantic versions; it does not compare timestamps or download a branch. If a newer release is available it shows `LYRA update available: vX → vY` and asks before downloading. It verifies the release SHA-256, stages files, backs up replaced files, and rolls back on an installation error. User data is outside the update tree and is preserved.

To publish a release from a clean, committed checkout after merging the change to your release branch:

1. Update `LYRA_VERSION` in `lyra/version.py` to a new semantic version.
2. Commit the version change, merge it to the branch intended for release, and run the helper below from that clean checkout.

The helper checks that the tag matches the source version, pushes the current branch and version tag, builds `lyra-app.zip`, generates its SHA-256 sidecar, and publishes both assets using GitHub CLI (`gh`). Example:

```powershell
.\launcher\publish_release.ps1 -Tag v0.3.0
```

Install/configure GitHub CLI (`gh auth login`) before publishing. The updater intentionally requires both assets and refuses an archive whose digest does not match. It does not update Ollama or its model files.

## Structured actions, computer control, and screen API

Existing deterministic skills remain in place. Multi-step desktop requests can be planned as a JSON list of allow-listed actions: open an approved app, generate text, type generated text, press a limited key, use a shortcut, move/click, scroll, or drag/drop. Python validates every field, action count, app name, key, coordinates, and operation before dispatch. Unknown actions and terminal apps requested through the LLM planner are rejected. There is no automatic arbitrary command, code, delete, shutdown, message, or email action.

The planner sends Ollama a JSON Schema of the plan (structured outputs, Ollama 0.5+; older versions fall back to plain JSON mode), and `coerce_plan()` rewrites the formats small models commonly produce anyway, such as `"open_app(app=notepad)"` or `{"open_app": {...}}`, into the canonical shape. Coercion only restructures; the strict validator still decides. A rejected plan is logged together with the model's reply. Text to type is produced by a dedicated writing prompt, and an Ollama error aborts the task instead of being typed. Before any keyboard action in an app the plan opened, LYRA brings that app's window to the front and verifies it; if it cannot, nothing is typed.

`ActionExecutor` returns `SUCCESS`, `FAILURE`, `UNKNOWN`, or `STOPPED`. Without an independent visual observer, successful input dispatch is reported as `UNKNOWN`, not claimed as verified. `capture_screen()` in `lyra/screen/capture.py` returns a `ScreenFrame`; `capture_screen(window_title="...")` uses optional window enumeration and crops the matching window.

Potentially dangerous legacy actions continue to use their existing confirmation prompts. Ctrl+C and `terminate execution` remain supported. The executor has a cancellation event and stop hook; see Known limitations for the current voice-loop constraint.

## Current built-in commands

Known commands are handled by the existing modular skills in `lyra/skills/` (apps/settings, media and brightness, windows/tabs, keyboard/clipboard, web/search/weather, system information, memory, fun, and confirmed power actions). Examples:

- “Open Notepad”, “open sound settings”, “close Chrome”
- “Turn the volume up”, “set brightness to 50”
- “Type hello there”, “press enter”, “copy”, “switch window”, “scroll down”
- “Search YouTube for lo-fi music”, “what time is it”, “remember that my exam is Friday”
- Compound desktop request: “Open Notepad and write 20 words about India.” (structured planner; allow-listed Notepad only)

Unknown ordinary conversation uses the local Ollama model.

## Development and tests

Use Python 3.10–3.12. From the repository root:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q main.py lyra
```

The tests run without physical audio devices or Ollama. Hardware-dependent functions are faked. `pytest -m manual -s` is opt-in and requires a real Windows desktop.

## Troubleshooting

- **Ollama missing/not running:** install/start Ollama, then relaunch. The launcher offers a retry.
- **Model missing:** consent to the launcher prompt or run `ollama pull phi4-mini:3.8b`.
- **No lightweight wake detector:** run `python -m lyra.setup_wake_model`; without that optional model LYRA falls back to Whisper wake detection.
- **No/wrong speaker:** run `.venv\Scripts\python.exe main.py --devices`, set `OUTPUT_DEVICE` in `settings.json`, then restart.
- **Piper playback error:** inspect `%APPDATA%\Lyra\logs\lyra.log`. Diagnostics include sample rate, chunk byte count, output device, and stack traces; playback requires signed 16-bit mono PCM.
- **No microphone access:** Windows Settings → Privacy & security → Microphone → allow desktop apps.
- **Volume commands fail:** LYRA supports both the current pycaw API (`AudioDevice.EndpointVolume`) and the older `Activate()` one; any other error is printed as `Volume error: ...` and logged.
- **"I couldn't create a valid, safe action plan":** the `WARNING ... Rejected malformed computer-action plan` line in the console and `lyra.log` gives the reason and the model's reply.
- **Updater offers no update:** only published stable GitHub Releases with a higher semantic version and both required archive/checksum assets are eligible.

## Project tree

```text
main.py                     interactive session/core
lyra/launcher.py            desktop entrypoint and Ollama/update checks
lyra/updater.py             verified GitHub Releases updater
lyra/version.py             application version
lyra/config.py              defaults and user-data/config paths
lyra/wake.py                optional Vosk wake gate
lyra/ear.py                 persistent Faster-Whisper recognizer
lyra/voice.py               persistent Piper model + typed sounddevice playback
lyra/brain.py               Ollama streaming and structured plan requests
lyra/actions/                schema and task executor
lyra/computer/               safe desktop automation adapter
lyra/screen/                 screen and window capture interface
lyra/skills/                 existing modular commands
launcher/                    shortcut creation and GitHub release helpers
config/settings.example.json user settings template
install.bat / run_lyra.bat   Windows installer and launcher
```

## Known limitations

- Real microphone/speaker playback, Vosk recognition quality, Ollama model output, Windows shortcut installation, and desktop actions cannot be validated in a headless CI environment.
- Vosk's optional small English model is a general recognizer rather than a dedicated Lyra acoustic wake model. Wake phrase matching reduces false positives but must be evaluated in the user's room/accent; the explicit “Hey Bobby” accommodation necessarily raises a narrow false-trigger tradeoff.
- If the Vosk model is absent, wake detection falls back to Whisper and has the old idle transcription cost.
- The action planner is used for a constrained set of multi-step requests, not a general autonomous computer agent. Screen capture exists, but no visual observer/OCR currently verifies app state; results are usually `UNKNOWN`.
- Voice-mode multi-step tasks run in a background worker so the microphone remains available for “stop”/“cancel task”. Cancellation is cooperative between actions; it cannot undo an OS action already in progress or interrupt an Ollama request mid-flight. Text-mode task execution is synchronous; Ctrl+C and `terminate execution` remain available. A non-blocking task/voice-control loop is a future development phase.
- The source installer still requires a supported Python runtime and internet access once. It does not bundle Python, Ollama, or the model. Start-with-Windows is not enabled.
