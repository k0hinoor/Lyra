# Lyra

> A local-first AI voice assistant built from scratch with Python, Ollama, Whisper, and Piper TTS.

Lyra is a personal AI assistant designed to run locally on Windows. The project combines speech recognition, a local language model, text-to-speech, persistent memory, and basic PC control into a single modular assistant.

The goal is to gradually evolve Lyra from a simple voice assistant into a capable desktop AI that can understand natural language and interact with the computer.

---

##  Current Capabilities

Lyra currently supports:

- 🎙️ Voice input through a microphone
- 🧠 Local AI responses using **Phi-4-mini**
- 👂 Speech recognition using **Faster-Whisper**
- 🔊 Natural voice output using **Piper TTS**
- 🧠 Persistent long-term memory
- 💬 Short-term conversation context
- 🖥️ Basic Windows PC control
- 🚀 Launching applications through voice commands
- ⚡ Fully local AI processing for the main assistant pipeline

### Current PC Commands

Lyra can currently open:

- Notepad
- Calculator
- Chrome

Example:

> "Lyra, open Notepad."

Lyra responds and launches the application.

---

# 🧠 Architecture

```text
                 ┌─────────────────┐
                 │    Microphone   │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ SpeechRecognition│
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │  Faster-Whisper │
                 │   Speech → Text │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Command Router  │
                 └───────┬─┬───────┘
                         │ │
              PC Command │ │ Normal Question
                         │ │
                         ▼ ▼
                  ┌─────────┐
                  │ Windows │
                  │ Control │
                  └─────────┘
                         │
                         │
                         ▼
                 ┌─────────────────┐
                 │    Ollama       │
                 │  Phi-4-mini     │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Memory + Context│
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │    Piper TTS    │
                 │  Text → Speech  │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │    Speakers     │
                 └─────────────────┘
