import requests
import json
import os
import numpy as np
import sounddevice as sd
import speech_recognition as sr
from faster_whisper import WhisperModel
from piper import PiperVoice


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "phi4-mini:3.8b"

MEMORY_FILE = "memory.json"
VOICE_FILE = "voice.wav"

PIPER_MODEL = "en_US-lessac-high.onnx"

# F&D / Realtek output device
OUTPUT_DEVICE = 5


# ============================================================
# LOAD MEMORY
# ============================================================

if os.path.exists(MEMORY_FILE):
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            memory = json.load(f)
    except Exception:
        memory = []
else:
    memory = []


# ============================================================
# SHORT-TERM CONVERSATION MEMORY
# ============================================================

conversation = []


# ============================================================
# LOAD WHISPER
# ============================================================

print("Loading Whisper Base...")

whisper = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)

print("Whisper loaded.")


# ============================================================
# LOAD PIPER VOICE
# ============================================================

print("Loading Lyra's voice...")

voice = PiperVoice.load(PIPER_MODEL)

print("Lyra's voice loaded.")


# ============================================================
# SPEECH RECOGNIZER
# ============================================================

recognizer = sr.Recognizer()

recognizer.pause_threshold = 1.5
recognizer.non_speaking_duration = 0.5
recognizer.phrase_threshold = 0.3


# ============================================================
# CLEAN TEXT FOR VOICE
# ============================================================

def clean_for_voice(text):

    cleaned = ""

    for char in text:

        if ord(char) < 128:
            cleaned += char

    return cleaned.strip()


# ============================================================
# SPEAK
# ============================================================

def speak(text):

    print("\nLyra:", text, "\n")

    try:

        voice_text = clean_for_voice(text)

        if not voice_text:
            return

        audio_chunks = []

        for chunk in voice.synthesize(voice_text):

            audio_chunks.append(
                chunk.audio_int16_bytes
            )

        audio_data = b"".join(audio_chunks)

        audio_array = np.frombuffer(
            audio_data,
            dtype=np.int16
        )

        sd.play(
            audio_array,
            samplerate=22050,
            device=OUTPUT_DEVICE
        )

        sd.wait()

    except Exception as e:

        print(f"Voice error: {e}")


# ============================================================
# SAVE MEMORY
# ============================================================

def save_memory():

    try:

        with open(
            MEMORY_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                memory,
                f,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:

        print(f"Memory save error: {e}")


# ============================================================
# CORRECT LYRA TRANSCRIPTION
# ============================================================

def correct_lyra(text):

    corrections = {

        "laira": "Lyra",
        "laira,": "Lyra,",
        "laira.": "Lyra.",
        "laira!": "Lyra!",

        "lyra": "Lyra",
        "lyra,": "Lyra,",
        "lyra.": "Lyra.",
        "lyra!": "Lyra!"
    }

    words = text.split()

    corrected_words = []

    for word in words:

        lower_word = word.lower()

        if lower_word in corrections:

            corrected_words.append(
                corrections[lower_word]
            )

        else:

            corrected_words.append(word)

    return " ".join(corrected_words)


# ============================================================
# PC COMMAND EXECUTION
# ============================================================

def execute_command(user_input):

    command = user_input.lower().strip()


    # --------------------------------------------------------
    # NOTEPAD
    # --------------------------------------------------------

    if "open notepad" in command:

        os.system("start notepad")

        return "Opening Notepad."


    # --------------------------------------------------------
    # CALCULATOR
    # --------------------------------------------------------

    if "open calculator" in command:

        os.system("start calc")

        return "Opening Calculator."


    # --------------------------------------------------------
    # GOOGLE CHROME
    # --------------------------------------------------------

    if "open chrome" in command:

        os.system("start chrome")

        return "Opening Chrome."


    # --------------------------------------------------------
    # NO COMMAND FOUND
    # --------------------------------------------------------

    return None


# ============================================================
# ASK OLLAMA
# ============================================================

def ask_ollama(user_input):

    global conversation

    system_prompt = """
You are Lyra, SRK's local AI assistant.
Your name is Lyra.

Never identify yourself as ONYX, Poppy, Phi, Microsoft,
Qwen, or another AI assistant.

You are a personal AI assistant for SRK.
Be helpful, concise, natural, and conversational.
Keep responses short unless SRK asks for detail.
For simple questions, answer in 1-3 sentences.
Do not add unrelated advice, encouragement, or follow-up topics.
Do not mention SRK's memories unless they are directly relevant.

Do not use emojis in your responses.
"""

    prompt = system_prompt + "\n\n"


    # --------------------------------------------------------
    # LONG-TERM MEMORY
    # --------------------------------------------------------

    if memory:

        prompt += "Long-term memory:\n"

        for item in memory:

            prompt += f"- {item}\n"

        prompt += "\n"


    # --------------------------------------------------------
    # RECENT CONVERSATION
    # --------------------------------------------------------

    if conversation:

        prompt += "Recent conversation:\n"

        for message in conversation[-10:]:

            prompt += (
                f"{message['role']}: "
                f"{message['content']}\n"
            )

        prompt += "\n"


    # --------------------------------------------------------
    # CURRENT INPUT
    # --------------------------------------------------------

    prompt += f"SRK: {user_input}\n"
    prompt += "Lyra:"


    # --------------------------------------------------------
    # SEND TO OLLAMA
    # --------------------------------------------------------

    try:

        response = requests.post(

            OLLAMA_URL,

            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            },

            timeout=120
        )

        response.raise_for_status()

        data = response.json()

        reply = data.get(
            "response",
            ""
        ).strip()


        if not reply:

            return "I didn't get a response."


        # ----------------------------------------------------
        # SAVE CONVERSATION
        # ----------------------------------------------------

        conversation.append(
            {
                "role": "user",
                "content": user_input
            }
        )

        conversation.append(
            {
                "role": "assistant",
                "content": reply
            }
        )


        return reply


    except Exception as e:

        print(f"Ollama error: {e}")

        return (
            "I'm having trouble connecting "
            "to my local brain."
        )


# ============================================================
# STARTUP
# ============================================================

print()
print("====================================")
print("          LYRA IS ONLINE")
print("====================================")
print()
print("Kill command: 'terminate execution'")
print("Emergency stop: Ctrl+C")
print()


# ============================================================
# MAIN LOOP
# ============================================================

with sr.Microphone() as source:

    print("Calibrating microphone...")

    recognizer.adjust_for_ambient_noise(
        source,
        duration=0.5
    )

    print("Microphone ready.")
    print()

    speak("Online.")


    while True:

        try:

            # ------------------------------------------------
            # LISTEN
            # ------------------------------------------------

            print("Listening...")

            audio = recognizer.listen(
                source,
                timeout=10,
                phrase_time_limit=20
            )


            # ------------------------------------------------
            # SAVE AUDIO
            # ------------------------------------------------

            with open(
                VOICE_FILE,
                "wb"
            ) as f:

                f.write(
                    audio.get_wav_data()
                )


            # ------------------------------------------------
            # WHISPER TRANSCRIPTION
            # ------------------------------------------------

            segments, info = whisper.transcribe(

                VOICE_FILE,

                language="en",

                vad_filter=True,

                vad_parameters={
                    "min_silence_duration_ms": 500,
                    "speech_pad_ms": 300
                },

                temperature=0,

                beam_size=5,

                condition_on_previous_text=False
            )


            user_input = ""

            for segment in segments:

                user_input += segment.text


            user_input = user_input.strip()


            # ------------------------------------------------
            # CORRECT LYRA
            # ------------------------------------------------

            user_input = correct_lyra(
                user_input
            )


            if not user_input:

                print("No speech detected.")
                print()

                continue


            # ------------------------------------------------
            # SHOW TRANSCRIPTION
            # ------------------------------------------------

            print(
                f"You: {user_input}"
            )


            # ------------------------------------------------
            # TERMINATE COMMAND
            # ------------------------------------------------

            normalized_input = (

                user_input
                .lower()
                .strip()
                .replace(",", "")
                .replace(".", "")
                .replace("!", "")
                .replace("?", "")
            )


            if normalized_input in [

                "terminate execution",

                "terminate execution lyra",

                "lyra terminate execution"

            ]:

                speak(
                    "Terminating execution"
                )

                break


            # ------------------------------------------------
            # MEMORY COMMAND
            # ------------------------------------------------

            if user_input.lower().startswith(
                "remember that "
            ):

                memory_item = user_input[
                    len("remember that "):
                ].strip()


                if memory_item:

                    memory.append(
                        memory_item
                    )

                    save_memory()

                    speak(
                        "I'll remember that."
                    )

                continue


            # ------------------------------------------------
            # PC COMMAND
            # ------------------------------------------------

            command_result = execute_command(
                user_input
            )

            if command_result:

                speak(
                    command_result
                )

                continue


            # ------------------------------------------------
            # ASK LYRA
            # ------------------------------------------------

            reply = ask_ollama(
                user_input
            )

            speak(
                reply
            )


        # ====================================================
        # NO SPEECH / TIMEOUT
        # ====================================================

        except sr.WaitTimeoutError:

            print(
                "No speech detected."
            )

            continue


        # ====================================================
        # CTRL+C
        # ====================================================

        except KeyboardInterrupt:

            print()
            print(
                "Lyra stopped by user."
            )

            break


        # ====================================================
        # OTHER ERRORS
        # ====================================================

        except Exception as e:

            print(
                f"Error: {e}"
            )

            continue


# ============================================================
# SHUTDOWN
# ============================================================

print()
print("Lyra offline.")