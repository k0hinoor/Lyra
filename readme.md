# Lyra

> A local-first AI voice assistant built from scratch with Python, Ollama, Whisper, and Piper TTS.
> **Everything runs on your PC. No cloud, no external AI APIs.**

Lyra is a personal AI assistant for Windows that combines speech recognition, a local language
model, text-to-speech, persistent memory, and **full PC control** into one fast, responsive assistant.

Say **"Hey Lyra"** and she wakes up. She stays awake for a short follow-up window so you can keep
talking naturally, then goes back to sleep on her own.

---

##  What's New in v2.0

The old `main.py` was only the brain. Now the whole body is built:

| | Old (v1) | New (v2) |
|---|---|---|
| **Project** | one big file | modular: `lyra/` package (config, ear, voice, brain, memory, 7 skills) |
| **Voice pack** | manual, not in repo | **auto-downloads on first run** (`en_US-amy-medium`, female) |
| **PC control** | 3 commands | **100+ commands** across 7 skill modules |
| **Understands speech** | exact command words only | "can you please turn up the volume", "it's too quiet", "set volume to sixty" — all **executed** |
| **Response speed** | wait for full reply, then speak | **streams — speaks the first sentence while the rest generates** |
| **Listening** | always-on, 1.5s pause lag | wake word "Hey Lyra" + 12s follow-up window, 0.7s pause |
| **Transcription** | writes WAV to disk every time | transcribes straight from RAM, beam size 1 |
| **Dangerous actions** | — | shutdown / restart / sleep / wipe memory **ask for confirmation** |
| **Install** | manual | `install.bat` one-click + `run_lyra.bat` launcher |

### She does it, she doesn't explain it

Ask her to change something and she changes it. She never reads out a manual.

```text
You:  Can you please turn up the volume?
Lyra: Volume set to 40 percent.          (not: "right-click the sound icon...")

You:  It's too quiet in here.
Lyra: Volume set to 50 percent.

You:  Set the volume to sixty.
Lyra: Volume set to 60 percent.
```

Polite padding (`please`, `can you`, `i want you to`, ...) is peeled off before a command is
matched, spoken numbers become digits, and every phrasing — `turn up the volume`,
`make it louder`, `crank up the music`, `crank it up`, `i can't hear you` — lands on the same
control. If she genuinely cannot do something, she says so in one sentence instead of
describing where the button is.

### Why it feels faster now

1. **Streaming pipeline** — Ollama streams tokens → sentences split as they arrive → Piper speaks
   sentence 1 while sentence 2 is still generating → gapless playback. Time-to-first-word drops
   from *full generation time* to *first sentence time*.
2. **Model stays loaded** — `keep_alive` keeps phi4-mini in RAM for 30 min between commands.
3. **Faster listening** — pause threshold cut from 1.5s → 0.7s, so Lyra answers ~0.8s sooner.
4. **No disk I/O** — audio goes to Whisper as a numpy array, not a WAV file. Whisper beam = 1.
5. **Warm start** — the model is warmed in the background at launch; the first command is not slow.

---

##  Install (Windows, one time)

1. Install [Python 3.10–3.12](https://python.org) (tick **Add to PATH**) and [Ollama](https://ollama.com).
2. Double-click **`install.bat`**. It will:
   - create a virtual environment
   - install every package from `requirements.txt`
   - download Lyra's voice pack (~60 MB, one time)
   - pull the brain model `phi4-mini:3.8b` through Ollama (~2.5 GB, one time)

##  Run

Double-click **`run_lyra.bat`**, or:

```bat
python main.py            :: wake-word mode (default)
python main.py --always   :: always-listening mode (no wake word)
python main.py --text     :: type commands instead of talking (testing)
python main.py --devices  :: list audio output devices (to pick speakers)
```

### Talking to Lyra

```text
You:  Hey Lyra                      (beep — she's awake for 12 seconds)
You:  What time is it?
Lyra: It's 9:41 PM.
You:  Weather in Bhubaneswar?
Lyra: Bhubaneswar: hazy, 29 degrees, feels like 32...
You:  Go to sleep                   (she beeps and sleeps)
```

Kill switch: **"Lyra, terminate execution"** or Ctrl+C.

---

##  Command Reference

### Apps, folders & settings — *"open / close ..."*
Notepad, Calculator, Chrome, Edge, Firefox, VS Code, Spotify, WhatsApp, Telegram, Discord, Steam,
VLC, Word, Excel, PowerPoint, Task Manager, CMD, PowerShell, Paint, Snipping Tool, Camera,
File Explorer, Control Panel, Downloads / Documents / Pictures / Desktop folders, C: / D: drives,
Windows Settings pages (Bluetooth, Wi-Fi, Display, Sound, Storage, Update...) — plus **any app
name Windows knows**. `"close chrome"`, `"close notepad"`, ...

### Web — *"search ... / open ..."*
`"search for best laptops"`, `"google python tutorial"`, `"play beliver on youtube"`,
`"search youtube for lofi beats"`, `"wikipedia albert einstein"`, `"open youtube"`, `"open gmail"`,
`"open github"`, `"open flipkart"`, `"open google dot com"`, and any `.com` domain.

### Media — volume, brightness, playback
Say it however you like — she does the rest:

| Instead of | Say |
|---|---|
| `"volume up"`, `"turn the volume up"`, `"increase the volume"`, `"make it louder"`, `"crank up the music"`, `"louder please"` | volume **up** |
| `"volume down"`, `"turn it down"`, `"make it quieter"`, `"lower the volume"` | volume **down** |
| `"set volume to 40"`, `"volume to 40"`, `"set the volume to sixty"`, `"full volume"`, `"half volume"`, `"volume to the max"` | an exact level |
| `"volume up a bit"` (+5), `"turn the volume up a lot"` (+25), `"turn it up by 5"` | a step |
| `"it's too quiet"`, `"i can't hear you"`, `"it's too loud"`, `"too dark"` | a complaint, fixed at once |
| `"mute"`, `"mute the sound"`, `"silence the audio"`, `"turn off the sound"`, `"unmute"` | mute / unmute |
| `"volume"`, `"what's the volume"`, `"how loud is it"` | the current level, read out |
| `"brightness up"`, `"make the screen brighter"`, `"it's too dark"`, `"set brightness to 70"` | brightness |
| `"play/pause music"`, `"stop the music"`, `"next track"`, `"skip to the next song"`, `"previous track"` | playback |

Turning it up while it is muted also unmutes it, and volume never goes past
`MAX_VOLUME` in `lyra/config.py` (lower it to 70 if your speakers are loud).

### Windows & tabs
`"minimize/maximize window"`, `"show desktop"`, `"switch window"`, `"task view"`,
`"new/close/reopen tab"`, `"new window"`, `"close this window"`, `"refresh"`, `"go back/forward"`,
`"scroll up/down"`, `"zoom in/out"`, `"fullscreen"`.

### Typing & keyboard
`"type hello world"` (types it in whatever box is focused), `"press enter/escape/f5"`,
`"copy/cut/paste/select all/undo/redo/save/find/print"`, `"copy this to clipboard"`,
`"copy SRK to clipboard"`, `"read my clipboard"`, `"clear clipboard"`.

### System info
`"what time is it"`, `"what's the date"`, `"battery"`, `"cpu usage"`, `"how is my pc"`,
`"disk space"`, `"what's my ip"`, `"uptime"`, `"wifi password"`, `"take a screenshot"`.

### Power  *(asks "say confirm or cancel")*
`"shutdown the pc"`, `"restart"`, `"put the pc to sleep"`, `"lock my pc"`,
`"empty the recycle bin"`, `"cancel shutdown"`.

### Memory
`"remember that my exam is on Friday"`, `"what do you remember"`, `"forget that ..."`,
`"forget everything"` (confirmed).

### Fun
`"tell me a joke"`, `"another one"`, `"flip a coin"`, `"roll a dice"`, `"pick a number between 1 and 100"`.

The jokes are developer puns, so Lyra **decodes the pun after the punchline** — nobody can look
up what UDP is while she's talking:

> *"I would tell you a UDP joke, but you might not get it. UDP is a way of sending data over
> the internet that never checks whether it arrived, so the joke could simply get lost on the way."*

### Anything else
Goes to the local brain (phi4-mini via Ollama) with your memory + conversation context.

---

#  Architecture

```text
                 ┌─────────────────┐
                 │    Microphone   │
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │ SpeechRecognition│  0.7s pause detection (was 1.5s)
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │  Faster-Whisper │  RAM → numpy, beam 1, VAD
                 │   Speech → Text │  no WAV files on disk
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐        "Hey Lyra" wake word
                 │  Wake Word Gate │ +----+ + 12s follow-up window
                 └────────┬────────┘      |
                          ▼               |
                 ┌─────────────────┐      |
                 │ Command Router  │      |
                 └───────┬─┬───────┘      |
             PC Command  │ │  Question    |
                         ▼ ▼              |
              ┌──────────┐  ┌──────────────┐
              │  Skills   │  │    Ollama    │  phi4-mini, keep_alive 30m
              │ (7 modules)│ │  STREAMING  │  tokens → sentences on the fly
              └─────┬────┘  └──────┬───────┘
                    │              │
                    │      ┌───────────────┐
                    │      │ Memory+Context│  memory.json + 12-turn history
                    │      └───────┬───────┘
                    ▼              ▼
                 ┌─────────────────────────┐
                 │       Piper TTS         │  speaks sentence 1 while the
                 │  pipelined, gapless     │  rest is still being generated
                 └────────┬────────────────┘
                          ▼
                 ┌─────────────────┐
                 │     Speakers    │
                 └─────────────────┘
```

### Project layout

```text
Lyra/
├── main.py                  ← launcher: wake-word loop, session, confirmations
├── install.bat / run_lyra.bat
├── requirements.txt
├── memory.json              ← your long-term memory (auto-created)
└── lyra/
    ├── config.py            ← EVERY setting lives here — edit this, not code
    ├── utils.py             ← normalize, polite-filler stripping, wake-word matching, sentence streaming
    ├── memory.py            ← persistent memory
    ├── brain.py             ← Ollama streaming client + persona prompt
    ├── ear.py               ← faster-whisper STT (from RAM, beam 1)
    ├── voice.py             ← Piper TTS + auto voice-pack download + pipelined playback
    ├── setup_voice.py       ← python -m lyra.setup_voice (pre-download the voice)
    └── skills/
        ├── apps.py          ← open/close apps, folders, settings pages
        ├── web.py           ← searches, websites, YouTube, Wikipedia, weather
        ├── media.py         ← volume, brightness, playback keys (understands speech, not keywords)
        ├── typing.py        ← dictated typing, keys, hotkeys, clipboard
        ├── windows.py       ← window/tab management
        ├── system.py        ← screenshots, battery, power, Wi-Fi, IP ...
        ├── fun.py           ← jokes, coin, dice
        └── __init__.py      ← router (skill order matters)
```

---

##  Configuration

Everything is in **`lyra/config.py`**:

| Setting | Default | Notes |
|---|---|---|
| `WAKE_MODE` | `"wake"` | `"always"` = react to everything |
| `FOLLOW_UP_SECONDS` | `12` | how long Lyra stays awake after a reply |
| `WHISPER_MODEL` | `"base.en"` | `"tiny.en"` = faster, `"small.en"` = more accurate |
| `VOICE_MODEL` | `"en_US-amy-medium"` | or `en_US-lessac-high`, `en_GB-jenny-high`... |
| `OUTPUT_DEVICE` | `None` | run `python main.py --devices`, then set your index (e.g. `5`) |
| `OLLAMA_MODEL` | `"phi4-mini:3.8b"` | any Ollama model works |
| `PAUSE_THRESHOLD` | `0.7` | lower = snappier, higher = waits longer for slow speakers |
| `SPEAK_BEEP` | `True` | attention beep on wake/sleep |
| `MAX_VOLUME` | `100` | hard ceiling for `"turn up the volume"` — drop to `70` if the speakers are loud |
| `MAX_BRIGHTNESS` | `100` | same, for the screen |
| `DEFAULT_CITY` | `"Bhubaneswar"` | for `"weather"` without a city |

##  Testing

Lyra's logic is covered by a pytest suite that runs headless — on Linux CI and on
Windows — with **no microphone, no speakers, no Ollama and no real key presses**:
every hardware dependency (pyautogui, pyperclip, psutil, pycaw, brightness) is
swapped for a fake in `tests/conftest.py`.

```bat
pip install -r requirements-dev.txt
pytest                 :: the whole suite, about 1 second
pytest -m manual -s    :: live keyboard check — opens a REAL Notepad and types
```

| What is covered | File |
|---|---|
| normalize, wake word, sentence splitter, voice cleanup | `tests/test_utils.py` |
| persistent memory (add / dedupe / forget / context block) | `tests/test_memory.py` |
| skill router: ordering, confirmations, error isolation | `tests/test_router.py` |
| one file per skill — apps, web, media, system, typing, windows, fun | `tests/test_skills_*.py` |
| Ollama streaming, prompt building, offline fallback | `tests/test_brain.py` |
| session flow: memory commands, confirm/cancel, terminate | `tests/test_session.py` |
| live keyboard check (opt-in, needs a real desktop) | `tests/manual/test_keyboard_live.py` |

The old root-level `test_keyboard.py` live check moved to `tests/manual/` and is
now `pytest -m manual` instead of a plain script.

**CI** (`.github/workflows/tests.yml`) runs the suite on every push and pull
request, on Ubuntu + Windows with Python 3.10 and 3.12, plus a byte-compile
syntax check.

##  Troubleshooting

- **"I can't reach my local brain"** → Ollama isn't running. Start Ollama, run `ollama pull phi4-mini:3.8b`.
- **No sound / wrong speakers** → `python main.py --devices`, put the index in `OUTPUT_DEVICE`.
- **Mic picks up nothing** → Settings → Privacy → Microphone → allow desktop apps.
- **Wake word misfires** → Whisper hears "laira/lira/laura" — those aliases are already handled;
  add more in `WAKE_ALIASES`.
- **First command after boot is slow** → Ollama loads the model on first use; keep Ollama running
  in the background (`keep_alive` holds it in RAM for 30 min between uses).
