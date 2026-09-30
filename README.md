# LYRA

LYRA is a local-first Windows voice assistant built from Python, Faster-Whisper, Ollama, Piper, and controlled desktop skills. Application code and user data are separate. LYRA does not send conversations to a hosted AI service; weather/search features may access the internet when explicitly requested.

**Application version:** `0.2.0` (`lyra/version.py`)

## Architecture

```text
Launcher → optional GitHub Releases updater → Ollama/model checks → LYRA core
                                                          │
Microphone → short Vosk wake gate → multilingual Whisper STT → session/router
                                                          │
                                            built-in skills / safe action planner
                                                          │
                                  Ollama (Phi) ───────── Piper TTS → speakers

User data (%APPDATA%/Lyra on Windows): settings, memory, logs, models
```

- `lyra/ear.py` loads one multilingual Faster-Whisper model per process. The default is CPU `int8`, `base`, with automatic language detection per utterance; `small` is recommended for more accurate Hindi at a CPU/latency cost. Transcription keeps Hindi as Hindi (not English translation) and passes English/Hindi LYRA vocabulary as hotwords. Legacy `.en` model settings are mapped to their multilingual equivalent unless English is explicitly forced.
- `lyra/wake.py` loads the optional Vosk model once. While asleep it processes short audio clips and runs full Whisper only after a wake hit. If the Vosk model is absent, LYRA falls back to a Whisper wake gate: `Ear.transcribe_wake()` decodes the short clip with a pinned language (English unless another language is configured) instead of per-clip language detection, which too often guesses wrong on one or two seconds of audio and hands the matcher text no wake spelling can match. When that English pass contains no wake phrase and `WHISPER_LANGUAGE` is `auto`, one auto-detect retry runs so Hindi native-script names such as `हे लायरा` still work. With `SPEECH_LANGUAGE: "hi"` the clip is decoded in Hindi first, then English, with no auto-detect pass. Every wake clip can be printed with `WAKE_DEBUG`/`--debug-wake`, and a missing Vosk model prints one install hint at startup.
- `lyra/voice.py` caches an English and a Hindi Piper pack, loading the Hindi pack only when first needed. Devanagari and mixed-script sentences use `HINDI_VOICE_MODEL`; Latin-only English uses `VOICE_MODEL`. Unicode vowels and combining marks are preserved, and Hindi danda punctuation can stream sentences early. If the two packs have different sample rates, playback closes/reopens the stream at the correct rate instead of distorting pitch or dropping the sentence. The voice pack download is atomic (temp file + size check + rename), so an interrupted download can never leave a corrupt model. Speaking speed follows `VOICE_SPEED` via Piper's `length_scale`. Piper's 16-bit PCM bytes are validated and converted to NumPy `int16` arrays before sounddevice playback. One lock serializes beeps and speech; streams are stopped and closed after each response. Every spoken sentence is remembered for a short window so the microphone can recognise LYRA's own voice coming back through the speakers.
- Barge-in: while she speaks, a watcher thread (`lyra-barge-in`) keeps the microphone open. Sustained voice — louder than the calibrated room noise times `INTERRUPT_ENERGY_MULTIPLIER` — stops playback immediately; the rest of that phrase is captured, transcribed with the same local Whisper model and handled as the next command. Transcripts that are mostly words she just said are dropped as speaker echo, and "stop"/"be quiet" is always kept.
- `lyra/browsers.py` finds a named browser (brave, chrome, edge, firefox) through the Windows App Paths registry key and standard install folders, and starts it with a URL as an argument list — never through a shell.
- `lyra/transcript.py` appends every exchange (what LYRA heard, her full reply, and what handled it) to a dated transcript file under `logs/`.
- `lyra/brain.py` keeps Ollama warm (`keep_alive`) and streams ordinary responses with a concise, warm assistant persona. Taste/opinion questions are conversation, not computer commands. `lyra/preferences.py` extracts only explicit first-person likes/dislikes for local long-term memory; the model does not guess what to save. The structured planner is invoked only for detected multi-step computer requests to avoid adding an LLM round trip to regular chat or known single commands.
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

Use the **LYRA** Desktop/Start Menu shortcut, or double-click `run_lyra.bat` in the install directory (it changes to its own folder first, so it also works when started from another directory, e.g. `C:\Users\USER\Lyra\run_lyra.bat` from any prompt). For development:

```bat
.venv\Scripts\python.exe -m lyra.launcher
.venv\Scripts\python.exe -m lyra.launcher --text
.venv\Scripts\python.exe -m lyra.launcher --always
.venv\Scripts\python.exe main.py --devices
.venv\Scripts\python.exe main.py --mic-test
.venv\Scripts\python.exe main.py --debug-wake
.venv\Scripts\python.exe main.py --voice-test
.venv\Scripts\python.exe main.py --voice-test --voice-language hi
```

`--text`, `--always`, `--devices`, `--mic-test` and `--debug-wake` are passed through to the core (`--mic-test` skips the Ollama check it does not need). `--no-update-check` skips the optional release check; `--skip-llm-check` is intended for offline/development diagnostics only. `--voice-test` speaks an English sample using `VOICE_MODEL`; add `--voice-language hi` to test only the selected Hindi pack (`HINDI_VOICE_MODEL`). These tests call the core directly and do not require Whisper or Ollama. `--mic-test` measures the live microphone level for five seconds, records one clip and runs it through the real wake gate, printing what the gate heard and whether "Hey Lyra" matched — the fastest way to tell a microphone problem from a wake-matching problem. `--debug-wake` prints one `[wake-debug] engine=… lang=… heard='…' -> WAKE/no wake` line for every captured wake clip (the same switch as `"WAKE_DEBUG": true` in settings). An empty/failed synthesis is reported as a failed test, not silent success.

## Ollama and model setup

Install Ollama separately and leave its local service running. The default model is `phi4-mini:3.8b`. The launcher checks Ollama and the selected model and requests consent before pulling a missing multi-gigabyte model. The equivalent explicit command is:

```bat
ollama pull phi4-mini:3.8b
```

To change the model, update `OLLAMA_MODEL` in the user's settings file (see below). LYRA and Ollama/model files update independently; LYRA updates do not replace or delete Ollama models.

## English and Hindi speech

**Update the application files first.** Settings alone cannot fix an older version that deletes non-ASCII speech text or downloads every voice from the English folder.

From the application folder (the **outer** `Lyra` folder containing `main.py` and `run_lyra.bat`), close LYRA and run in PowerShell:

```powershell
Set-Location "$env:USERPROFILE\Lyra"
.\.venv\Scripts\python.exe -m lyra.setup_voice --language hi --model hi_IN-priyamvada-medium --set-default --whisper-model small
.\.venv\Scripts\python.exe main.py --voice-test --voice-language hi
.\run_lyra.bat
```

If you use the installed Desktop shortcut instead of a source checkout, run these commands in `$env:LOCALAPPDATA\Programs\LYRA` instead. The setup command downloads only the chosen Hindi pack and atomically merges `HINDI_VOICE_MODEL`, `WHISPER_MODEL`, and `WHISPER_LANGUAGE: "auto"` into your existing settings; other settings are preserved. The selected Whisper model downloads on the next voice launch. No microphone audio or reply text is uploaded.

### Hindi voice choices

The curated packs come from the [official Piper Hindi directory](https://huggingface.co/rhasspy/piper-voices/tree/main/hi/hi_IN):

| Piper model ID | Voice |
| --- | --- |
| `hi_IN-priyamvada-medium` | Priyamvada (default Hindi voice) |
| `hi_IN-pratham-medium` | Pratham |
| `hi_IN-rohan-medium` | Rohan |

Each pack is roughly 60–65 MB. List choices without a download, or explicitly download all three for later comparison:

```powershell
.\.venv\Scripts\python.exe -m lyra.setup_voice --list
.\.venv\Scripts\python.exe -m lyra.setup_voice --all-hindi
```

To select another voice, replace the model ID in the setup command, for example:

```powershell
.\.venv\Scripts\python.exe -m lyra.setup_voice --language hi --model hi_IN-rohan-medium --set-default
.\.venv\Scripts\python.exe main.py --voice-test --voice-language hi
```

English still uses your existing `VOICE_MODEL`. LYRA selects a pack per sentence: Hindi/English mixed-script speech uses Hindi. Romanized Hindi alone is not reliably detectable from spelling; the chat prompt asks for Hindi replies in Devanagari so they use the Hindi voice. This is local Piper speech, not a clone of a movie character's voice.

### Speech language: `SPEECH_LANGUAGE`

One setting decides which language LYRA listens and answers in:

| `SPEECH_LANGUAGE` | Recognition (Whisper) | Replies (chat, skills, confirmations, errors) |
| --- | --- | --- |
| `"hi"` (shipped default) | always Hindi | always Hindi, Hindi voice pack |
| `"en"` | always English | English |
| `"auto"` | as `WHISPER_LANGUAGE` says | follow the user (the behaviour before this setting existed) |

Set it in `settings.json` (`"SPEECH_LANGUAGE": "auto"`) or with the `LYRA_SPEECH_LANGUAGE` environment variable, then restart. `--mic-test` prints the active value.

**Trade-off of `"hi"`:** Whisper is pinned to Hindi, so English you speak is decoded *as Hindi* (usually in Devanagari transliteration). Recognised Hindi commands and the brand names below still work, and typed `--text` English is unaffected, but for a mostly-English spoken session use `"auto"` or `"en"`.

In `"hi"` mode:

- **Hindi commands run offline.** A small, fixed vocabulary is turned into the English command the skills already understand, without any model or network: `नोटपैड खोलो` → open notepad, `ब्रेव क्रोम यूट्यूब खोलो` → YouTube in Brave, `यूट्यूब` → open YouTube, `आवाज़ बढ़ाओ` / `आवाज़ 50 कर दो` / `आवाज़ थोड़ा कम करो`, `आवाज़ बंद करो` (mute), `चमक बढ़ाओ`, `गाना बजाओ`, `समय बताओ`, `मौसम कैसा है`, `कंप्यूटर बंद करो` (asks first; answer `हाँ` or `नहीं`), `रुको`. Brand names may be in either script (`Brave YouTube खोलो`). Anything outside that vocabulary — `मुझे कहानी सुनाओ`, `मुझे यूट्यूब पसंद है` — is never translated and goes to the chat model as you said it.
- **Every reply is Hindi**: the fixed replies come from `lyra/messages.py` (English text there is exactly what LYRA always said), the chat model gets a Hindi-only instruction (everyday Hindi, feminine first person, no invented names), and the Hindi Piper pack speaks every sentence. If that pack is missing LYRA says so, names `python -m lyra.setup_voice --language hi`, and keeps printing text replies.
- `सो जाओ`, `धन्यवाद`, `चुप रहो` and a transliterated "terminate execution" work like their English forms.

### Hindi recognition and wake words

- For Hindi, `small` is the practical minimum: `tiny`/`base` often loop ("यूट्यूट्यूट्यूब…") or hallucinate on short Hindi commands, and LYRA logs a warning when they are used with `SPEECH_LANGUAGE: "hi"`. Switch with `python -m lyra.setup_voice --language hi --set-default --whisper-model small` (`--whisper-model` always needs `--set-default`; the model downloads on the next voice launch).
- Use multilingual `base`, `small`, etc., **not** `base.en` or `small.en`. With `WHISPER_LANGUAGE: "auto"`, English, Hindi and mixed speech can reach the conversational model in their original language. Whisper is not a perfect recognizer, especially for short utterances, accents, background noise or frequent code-switching.
- `small` usually improves Hindi recognition but is larger and slower on a CPU. Choose `base` in the setup command for lower latency. `WHISPER_BEAM` accepts `1`–`5` (default `3`); `1` is quicker.
- If automatic detection keeps guessing the wrong language during an all-Hindi session, set `WHISPER_LANGUAGE` to `"hi"` in settings and restart. Use `"en"` for an intentionally English-only session.
- Say **“Hey Lyra”** first, then speak Hindi during the follow-up window. With Whisper wake fallback, common Hindi transcriptions such as `हे लायरा` and `हे लाइरा` also work. In `"auto"`/`"en"` the wake clip is decoded in English first and retried with language detection when that misses; in `"hi"` it is decoded in Hindi first, then in English (no language detection). The English pass is biased only with `WHISPER_WAKE_HOTWORDS` (spellings of "Hey Lyra"), never with Hindi words; `--debug-wake` prints one line per pass with the language used and which pass matched. The optional **English Vosk** wake pack still expects the English wake phrase; it does not become a Hindi acoustic model.
- Repetition loops (`यूट्यूट्यूट्यूब…`, `hi hi hi hi hi hi`) are collapsed or, when the whole transcript is a loop, dropped instead of being answered; the wake debug line still shows the raw text.
- Hindi conversation, taste memory, and explicit Hindi memory commands work. In `"hi"` mode the Hindi command vocabulary above runs the matching skills; other Hindi desktop requests are not translated into actions (and in `"auto"`/`"en"` the skills expect their documented **English** commands).

### Natural conversation and remembered tastes

“Do you like music?” now stays in conversation instead of being reduced to “music” and answered with a volume level. LYRA's chat prompt has a consistent conversational taste (soulful Hindi melodies, mellow jazz, cinematic instrumentals), avoids repetitive customer-service offers, and allows a brief relevant follow-up. Its persona is not a claim of human feelings or real listening experiences. Actual phrasing and Hindi fluency still depend on the configured local Ollama model.

Clear first-person likes/dislikes are saved locally **before** the current chat reply, and are available after restarting LYRA. For example:

- “I like Arijit Singh but I don't like rap.”
- “मुझे अरिजीत के गाने पसंद हैं लेकिन मुझे रैप पसंद नहीं है।”
- Later: “What music do I like?” or “मुझे किस तरह का संगीत पसंद है?”

Repeating the same taste does not duplicate it; changing from liking to disliking the same topic replaces that automatically captured preference. This also supports other explicitly stated tastes, not just music. Questions, uncertain statements, quotations and statements about other people are not inferred into a user profile. Complex descriptions can be stored explicitly with “remember that …” or “याद रखना कि …”.

Use “what do you remember” / “तुम्हें क्या याद है”, “forget about rap” / “रैप के बारे में भूल जाओ”, or the existing confirmed “forget everything” command to inspect/remove memories. Set `AUTO_REMEMBER_PREFERENCES` to `false` to disable automatic capture; explicit remember/forget commands still work. The existing list-shaped `memory.json` stays compatible, writes are atomic, and the model is told about a new save only after the write succeeds.

### If Hindi still has no sound

1. Run `main.py --voice-test --voice-language hi` using the private venv as above; it isolates speech from recognition and the chat model.
2. Check that the Hindi pack download completed and `HINDI_VOICE_MODEL` is a `hi_IN-...` ID. Setup refuses a malformed settings file rather than overwriting it. Environment overrides such as `LYRA_HINDI_VOICE_MODEL` take precedence over JSON settings.
3. If the model loads but there is still no sound, check the default output device or run `main.py --devices` and set `OUTPUT_DEVICE`. Inspect `%APPDATA%\Lyra\logs\lyra.log` for synthesis/playback errors. A missing Hindi pack is logged visibly and does not disable later English replies.

## Wake-word setup

The intended phrase is **“Hey Lyra.”** The wake matcher requires a wake prefix at the start of the phrase and tolerates a small edit distance only on the following name. This allows the tested forms `Lyra`, `Laira`, `Lira`, `Laura`, `later`, `Leyra`, `Leira`, `Lyrah`, plus the explicitly requested `Bobby` transcription; phrases such as “see you later”, “okay”, and “hip hop” do not satisfy the prefix/name shape.

The matcher also accepts the mishearings seen most often after "Hey": `Lara`, `Leera`, `Lyre`, `Lyrics`, `Hilera`, glued greetings (`heylyra`, `hailyra`), a leading `a` (`a lyra`) and the multi-word forms (`hi lyra`, `hello lyra`, `ok lyra`, `hey laura`). Only the plain `Lyra` and its Devanagari spellings may wake LYRA with no greeting at all, so "see you later", "the lyrics are wrong" and "hey there" stay background speech.

For lightweight wake recognition, install the optional Vosk English model once (about 40 MB):

```bat
.venv\Scripts\python.exe -m lyra.setup_wake_model
```

This download is explicit and goes into the user data directory. Restart LYRA afterward. With no model installed, LYRA prints one line at startup saying so and uses the Whisper wake gate instead: the short clip is decoded in English first (instead of per-clip language detection, which is unreliable on one or two seconds of audio) with the same hotword bias as commands, and one auto-detect retry runs only if that misses. Full Whisper command recognition is unchanged and runs after the gate accepts a wake phrase.

When the wake gate still ignores you, look at what it actually hears:

```bat
.venv\Scripts\python.exe main.py --mic-test
.venv\Scripts\python.exe main.py --debug-wake
```

`--mic-test` prints `[wake-debug] engine=<vosk|whisper> lang=<detected> heard='<text>' -> WAKE/no wake` for the clip it records and exits non-zero when the phrase did not match. A rejected clip prints nothing during normal running by design — background chatter must stay silent — so use `--debug-wake` (or `"WAKE_DEBUG": true`) whenever "she ignores me" has to be diagnosed.

## Configuration and user data

On Windows, settings and user data live in `%APPDATA%\Lyra` (typically `C:\Users\<you>\AppData\Roaming\Lyra`). Development can override the location with `LYRA_DATA_DIR`. LYRA creates the directory as needed.

Create `%APPDATA%\Lyra\settings.json` from `config/settings.example.json`. Supported overrides include:

```json
{
  "OLLAMA_MODEL": "phi4-mini:3.8b",
  "VOICE_MODEL": "en_US-lessac-medium",
  "HINDI_VOICE_MODEL": "hi_IN-priyamvada-medium",
  "VOICE_SPEED": 1.15,
  "INTERRUPT_ENERGY_MULTIPLIER": 2.0,
  "BROWSER": "",
  "OUTPUT_DEVICE": null,
  "INPUT_DEVICE": null,
  "ENERGY_THRESHOLD_MAX": 1000,
  "WAKE_DEBUG": false,
  "WAKE_FUZZY_MAX_DISTANCE": 2,
  "WAKE_WINDOW_SECONDS": 4.0,
  "WHISPER_MODEL": "base",
  "WHISPER_LANGUAGE": "auto",
  "SPEECH_LANGUAGE": "hi",
  "WHISPER_BEAM": 3,
  "AUTO_REMEMBER_PREFERENCES": true,
  "OLLAMA_URL": "http://localhost:11434/api/chat",
  "LOG_LEVEL": "INFO",
  "CONSOLE_LOG_LEVEL": "WARNING"
}
```

Setting notes:

- `VOICE_MODEL` — any English Piper voice name (`en_US-lessac-medium` is the default; `en_US-amy-medium`, `en_US-lessac-high`, `en_GB-jenny-high`, ...). Packs download atomically on first use (temp file + size check + rename), so an interrupted download cannot leave a corrupt model. Test a change with `python main.py --voice-test`.
- `HINDI_VOICE_MODEL` — Hindi Piper pack, default `hi_IN-priyamvada-medium`; alternatives and setup commands are above. Test with `main.py --voice-test --voice-language hi`.
- `SPEECH_LANGUAGE` — `"hi"` (default), `"en"` or `"auto"`; see [Speech language](#speech-language-speech_language). `"auto"` restores the earlier behaviour exactly.
- `WHISPER_MODEL`, `WHISPER_LANGUAGE`, `WHISPER_BEAM` — multilingual recognition model, `auto` / `en` / `hi` (used when `SPEECH_LANGUAGE` is `"auto"`), and decoding beam width (`1`–`5`). `small` is the practical minimum for Hindi.
- `WHISPER_WAKE_HOTWORDS`, `WHISPER_HINDI_HOTWORDS` — Whisper bias words for the English wake pass (wake-name spellings only) and for Hindi commands (a short list of common command words).
- `AUTO_REMEMBER_PREFERENCES` — `true` by default; capture only explicit first-person likes/dislikes. Set `false` for explicit-memory-only mode.
- `VOICE_SPEED` — speaking-speed multiplier, clamped to `0.8`–`1.5`; default `1.15` (a little faster than the Piper default). Internally passed to Piper as `length_scale = 1 / VOICE_SPEED`.
- `INTERRUPT_ENERGY_MULTIPLIER` — how much louder than the calibrated room noise your voice must be to cut LYRA off, clamped to `1.0`–`10.0`; default `2.0`. Raise it in a room where the microphone over-hears her (or where she interrupts herself through the speakers); lower it if a quiet "stop" no longer interrupts. Only a sustained sound counts — a cough or a keyboard tap is ignored.
- `BROWSER` — `"brave"`, `"chrome"`, `"edge"`, `"firefox"` or `""` (empty = the Windows default browser). Used by all web commands when no browser is named in the request; see Commands below.
- `INPUT_DEVICE` — microphone index for `speech_recognition`, or `null` for the Windows default input device. Run `python main.py --devices` to see the indices (input and output, with the Windows defaults marked) and set the one you want; the startup banner prints the device name it opened. Wrong indices are ignored with a warning instead of stopping LYRA.
- `ENERGY_THRESHOLD_MAX` — ceiling for the noise floor calibrated at startup, in RMS units (default `1000`). `adjust_for_ambient_noise` measures the room, and a noisy room can settle on a threshold louder than your voice; every later `listen()` then ignores you, which looks exactly like a dead microphone. Raise it only in a genuinely loud room.
- `WAKE_DEBUG` — `true` prints one `[wake-debug] engine=… lang=… heard='…' -> WAKE/no wake` line for every wake-gate clip (same as `main.py --debug-wake`). Use it to see mishearings instead of silent rejections.
- `LOG_LEVEL` — detail written to `logs/lyra.log` (default `INFO`, full diagnostics for bug reports).
- `CONSOLE_LOG_LEVEL` — what the console shows (default `WARNING`, so INFO chatter such as Whisper's audio-duration lines stays out of the conversation view).

Environment variables such as `LYRA_OLLAMA_MODEL`, `LYRA_VOICE_MODEL`, `LYRA_HINDI_VOICE_MODEL`, `LYRA_WHISPER_MODEL`, `LYRA_WHISPER_LANGUAGE`, `LYRA_SPEECH_LANGUAGE`, `LYRA_WHISPER_BEAM`, `LYRA_AUTO_REMEMBER_PREFERENCES`, `LYRA_VOICE_SPEED`, `LYRA_INTERRUPT_ENERGY_MULTIPLIER`, `LYRA_BROWSER`, `LYRA_CONSOLE_LOG_LEVEL`, `LYRA_OUTPUT_DEVICE`, `LYRA_INPUT_DEVICE`, `LYRA_ENERGY_THRESHOLD_MAX`, and `LYRA_WAKE_DEBUG` override JSON settings. Never put API credentials in source or commit personal settings. Local state includes:

- `memory.json` — persistent user memory
- `settings.json` — non-secret user preferences
- `logs/lyra.log` — rotating diagnostics (full INFO detail even when the console is quiet)
- `logs/conversation-YYYY-MM-DD.txt` — dated transcript: what LYRA heard, her full reply, and what handled it (which skill, the planner, or the chat model)
- `models/` — Piper and optional Vosk assets

An existing project-root `memory.json` is copied to the user data directory on first load when no new memory file exists. The original is not deleted.

## Updating LYRA

The launcher checks the latest stable GitHub Release and compares semantic versions; it does not compare timestamps or download a branch. If a newer release is available it shows `LYRA update available: vX → vY` and asks before downloading. It verifies the release SHA-256, stages files, backs up replaced files, and rolls back on an installation error. User data is outside the update tree and is preserved.

After a successful install the launcher re-runs `pip install -r requirements.txt` (with the private venv's Python) and then **restarts the LYRA process** with `--no-update-check`, because the modules already loaded in memory are the old ones; only a fresh interpreter runs the updated files. If the restart itself fails, LYRA tells you to start it again manually.

To publish a release from a clean, committed checkout after merging the change to your release branch:

1. Update `LYRA_VERSION` in `lyra/version.py` to a new semantic version.
2. Commit the version change, merge it to the branch intended for release, and run the helper below from that clean checkout.

The helper checks that the tag matches the source version, pushes the current branch and version tag, builds `lyra-app.zip`, generates its SHA-256 sidecar, and publishes both assets using GitHub CLI (`gh`). Example:

```powershell
.\launcher\publish_release.ps1 -Tag v0.3.0
```

Install/configure GitHub CLI (`gh auth login`) before publishing. The updater intentionally requires both assets and refuses an archive whose digest does not match. It does not update Ollama or its model files.

## Structured actions, computer control, and screen API

Existing deterministic skills remain in place. Multi-step desktop requests can be planned as a JSON list of allow-listed actions: open an approved app, open a safe URL (`open_url`), generate text, type generated or short user-given text, press a limited key, use a shortcut, move/click, scroll, or drag/drop. Python validates every field, action count, app name, key, URL, coordinates, and operation before dispatch. Unknown actions and terminal apps requested through the LLM planner are rejected. There is no automatic arbitrary command, code, delete, shutdown, message, or email action.

`open_url` accepts only `http://` and `https://` URLs, validated with `urllib.parse`: a host is required and URLs with embedded credentials or `javascript:`/`file:`/`data:` schemes are refused. The optional `browser` field names brave, chrome, edge, or firefox; without it the configured/default browser is used. `type_text` comes in two shapes: `"source": "generated_text"` (types what a preceding `generate_text` step wrote) or `"text": "..."` (types a short literal the user gave, such as a search query).

The planner sends Ollama a JSON Schema of the plan (structured outputs, Ollama 0.5+; older versions fall back to plain JSON mode), and `coerce_plan()` rewrites the formats small models commonly produce anyway, such as `"open_app(app=notepad)"` or `{"open_app": {...}}`, into the canonical shape. Coercion only restructures; the strict validator still decides. A rejected plan is logged together with the model's reply. Text to type is produced by a dedicated writing prompt, and an Ollama error aborts the task instead of being typed. Before any keyboard action in an app the plan opened, LYRA brings that app's window to the front and verifies it; if it cannot, nothing is typed.

`ActionExecutor` returns `SUCCESS`, `FAILURE`, `UNKNOWN`, or `STOPPED`. Without an independent visual observer, successful input dispatch is reported as `UNKNOWN`, not claimed as verified. `capture_screen()` in `lyra/screen/capture.py` returns a `ScreenFrame`; `capture_screen(window_title="...")` uses optional window enumeration and crops the matching window.

Potentially dangerous legacy actions continue to use their existing confirmation prompts. Ctrl+C and `terminate execution` remain supported. The executor has a cancellation event and stop hook; see Known limitations for the current voice-loop constraint.

## Current built-in commands

Known commands are handled by the existing modular skills in `lyra/skills/` (apps/settings, media and brightness, windows/tabs, keyboard/clipboard, web/search/weather, system information, memory, fun, and confirmed power actions). Examples:

- “Open Notepad”, “open sound settings”, “close Chrome”
- “Turn the volume up”, “set brightness to 50”
- “Type hello there”, “press enter”, “copy”, “switch window”, “scroll down”
- “Search YouTube for lo-fi music”, “what time is it” (also “so what time is it”, “tell me the time”, “current time”, …), “remember that my exam is Friday”
- Compound desktop request: “Open Notepad and write 20 words about India.” (structured planner; allow-listed Notepad only)

Browsers and multi-step web tasks:

- Named browser: “open YouTube in Brave”, “search YouTube for lofi in Brave”, “open Gmail in Chrome” (brave, chrome, edge, firefox — launched as an executable with the URL argument, located via the App Paths registry or standard install folders).
- Default browser: set `BROWSER` in `settings.json` (or `LYRA_BROWSER`) and every web command that does not name a browser uses it; empty means the Windows default.
- Run-on web tasks, handled directly (no planner round trip): “open Brave and open YouTube”, “open Brave and go to YouTube”, “open Brave and search YouTube for lofi”, “open YouTube and search for lofi”.

Opening applications:

- Any installed app can be opened by name. LYRA checks its own tables first (Notepad, browsers, media players), then the Start Menu: the user’s `%APPDATA%\Microsoft\Windows\Start Menu\Programs` and the machine-wide `%PROGRAMDATA%` one are searched for a matching `.lnk` shortcut, so “open davinci resolve” finds `DaVinci Resolve.lnk` and “open OBS” finds `OBS Studio (64bit).lnk` without a hand-written table entry. Uninstall, remove, repair, setup and update shortcuts are never matched, so “open davinci resolve” can never launch “Uninstall DaVinci Resolve”.
- If nothing matches, Windows itself resolves the name. A launch that does not start anything is reported as “I couldn’t find an app called X” — LYRA never says “Opening…” for something it did not start.
- Run-on speech: a conversational tail belongs to the chat, so “open notepad and tell me what is going on” opens Notepad and then answers. A second step belongs to the planner, so “open notepad and write about india” and “open brave and search youtube for lofi” are left to the web skill and the action planner.
- Name repair: after “I couldn’t find an app called X”, the next turn is treated as a correction — “no I meant Notepad”, “I said Notepad”, “actually it’s called Notepad”, “I’m saying Notepad” (with or without the open verb, with or without “please”) opens the corrected app. A second miss buys exactly one more try, and any other reply closes the repair window.

Window and tab controls:

- “full screen”, “make it full screen”, “exit full screen” — toggles F11 (never touches brightness).
- “next tab”, “previous tab”, “switch tab” (Ctrl+Tab / Ctrl+Shift+Tab), “reopen closed tab” (Ctrl+Shift+T).

Power:

- “Put the PC to sleep”, “sleep mode”, “put my windows in sleep mode” — all ask for confirmation first.

Unknown ordinary conversation uses the local Ollama model. The chat model never claims to have performed a PC action it cannot see or control — requests that reach it by mistake get a short “I can't do that one”, and every chat request carries the current local date and time. In voice mode, filler-only utterances such as “Okay.” are dropped instead of being sent to chat.

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
- **Wake word ignored / "she prints nothing when I speak":** run `.venv\Scripts\python.exe main.py --mic-test`. It shows the live level (flat at zero = the microphone, Windows privacy settings or `INPUT_DEVICE`), the calibrated energy threshold (capped at `ENERGY_THRESHOLD_MAX`), one `[wake-debug]` line for the recorded clip, and whether `strip_wake_word` matched. Then run LYRA with `--debug-wake` (or set `"WAKE_DEBUG": true`) to see every clip while it runs. The gate drops non-wake clips silently on purpose, so a misheard "Hey Lyra" is invisible without it.
- **No lightweight wake detector:** run `.venv\Scripts\python.exe -m lyra.setup_wake_model`; without that optional model LYRA prints one startup line and falls back to Whisper wake detection (English-first on the wake clip, one auto-detect retry). Install it if wake misses are frequent — Vosk is the faster, more reliable gate.
- **Wake word only works sometimes:** the wake clip is 1–2 seconds long and Whisper may hear "Hey Lyra" as something else (`lara`, `leera`, `lyre`, `lyrics`, `hilyra`, ...). Those spellings are already accepted after a greeting; `--debug-wake` shows what the gate really heard, and `WHISPER_MODEL: "small"` recognises short clips better than `base` at a CPU cost.
- **Hindi commands misheard, looped or answered with an essay:** check `--mic-test` first — it prints `Speech language: hi` and the Whisper model. Use `WHISPER_MODEL: "small"` (`python -m lyra.setup_voice --language hi --set-default --whisper-model small`); `base` loops and hallucinates on Hindi. If `--mic-test` says the microphone is *very loud*, lower the input level in Windows Settings > System > Sound > Input and turn off automatic gain control / audio "enhancements" for that microphone: clipped audio is the most common cause of Whisper repetition loops. Make sure `INPUT_DEVICE` points at the microphone you actually speak into (`main.py --devices`). English-heavy sessions belong in `"auto"` (see the trade-off under [Speech language](#speech-language-speech_language)).
- **Mic too quiet or too noisy:** `main.py --mic-test` shows the level and the threshold. If the threshold was capped, the console says so; if the microphone is wrong, pick one with `main.py --devices` and set `INPUT_DEVICE`.
- **No/wrong speaker:** run `.venv\Scripts\python.exe main.py --devices`, set `OUTPUT_DEVICE` in `settings.json`, then restart.
- **Piper playback error:** inspect `%APPDATA%\Lyra\logs\lyra.log`. Diagnostics include sample rate, chunk byte count, output device, and stack traces; playback requires signed 16-bit mono PCM.
- **No microphone access:** Windows Settings → Privacy & security → Microphone → allow desktop apps.
- **Volume commands fail:** LYRA supports both the current pycaw API (`AudioDevice.EndpointVolume`) and the older `Activate()` one; any other error is printed as `Volume error: ...` and logged.
- **"I couldn't create a valid, safe action plan":** the `WARNING ... Rejected malformed computer-action plan` line in the console and `lyra.log` gives the reason and the model's reply.
- **Updater offers no update:** only published stable GitHub Releases with a higher semantic version and both required archive/checksum assets are eligible. After installing, LYRA re-runs `pip install -r requirements.txt` and restarts the process so the updated code actually runs.
- **Reporting a bug:** attach the day's `logs/conversation-YYYY-MM-DD.txt` (what LYRA heard, her exact reply, and which skill/planner/chat handled it) plus `logs/lyra.log` (full INFO diagnostics — the console intentionally shows only warnings and errors).
- **Voice sounds wrong after a settings change:** run `.venv\Scripts\python.exe main.py --voice-test`. Interrupted voice downloads repair themselves on next start (temp file + size check + rename, so a corrupt model is never left behind).

## Project tree

```text
main.py                     interactive session/core
lyra/launcher.py            desktop entrypoint and Ollama/update checks
lyra/updater.py             verified GitHub Releases updater
lyra/version.py             application version
lyra/config.py              defaults and user-data/config paths
lyra/wake.py                optional Vosk wake gate + Whisper fallback, wake debug line
lyra/ear.py                 persistent Faster-Whisper recognizer (hotword-biased)
lyra/voice.py               persistent Piper model + typed sounddevice playback
lyra/brain.py               Ollama streaming and structured plan requests
lyra/hindi.py               offline Hindi command vocabulary -> English skill commands
lyra/messages.py            every fixed reply, English + Hindi, t(key) by SPEECH_LANGUAGE
lyra/browsers.py            named-browser lookup/launch for web commands
lyra/transcript.py          dated conversation transcript writer
lyra/logging_setup.py       quiet console + full-detail file logging
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
- If the Vosk model is absent, wake detection falls back to Whisper and has the old idle transcription cost. The fallback now pins English for the wake clip and retries once with language detection, but a quiet or heavily accented "Hey Lyra" can still be transcribed as something outside the alias list; `--debug-wake` is the supported way to see and report that.
- The action planner is used for a constrained set of multi-step requests, not a general autonomous computer agent. Screen capture exists, but no visual observer/OCR currently verifies app state; results are usually `UNKNOWN`.
- Voice-mode multi-step tasks run in a background worker so the microphone remains available for “stop”/“cancel task”. Cancellation is cooperative between actions; it cannot undo an OS action already in progress or interrupt an Ollama request mid-flight. Text-mode task execution is synchronous; Ctrl+C and `terminate execution` remain available. A non-blocking task/voice-control loop is a future development phase.
- The source installer still requires a supported Python runtime and internet access once. It does not bundle Python, Ollama, or the model. Start-with-Windows is not enabled.
