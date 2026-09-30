"""List/download local Piper voices and safely select bilingual settings.

Examples (use LYRA's private venv Python on Windows):
  python -m lyra.setup_voice --list
  python -m lyra.setup_voice --language hi --set-default --whisper-model small
  python -m lyra.setup_voice --all-hindi

No conversation text or microphone audio is uploaded. Voices download
from the official Piper repository into the user data directory.
"""

import argparse
import logging

from . import config
from .settings import update_settings
from .voice import ensure_voice_pack
from .voice_catalog import VOICE_CHOICES, parse_voice_model

log = logging.getLogger(__name__)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Set up LYRA's local English/Hindi voices")
    parser.add_argument("--list", action="store_true", help="list curated voices without downloading")
    parser.add_argument("--language", choices=("en", "hi"), help="voice language (default: en)")
    parser.add_argument("--model", help="Piper model ID to download/select")
    parser.add_argument("--all-hindi", action="store_true", help="download all three Hindi packs, without changing settings")
    parser.add_argument("--set-default", action="store_true", help="save the selected language's voice to settings.json")
    parser.add_argument("--whisper-model", choices=("tiny", "base", "small", "medium", "large-v3", "turbo"),
                        help="with --set-default, enable multilingual Whisper with automatic language detection")
    args = parser.parse_args(argv)

    if args.list:
        for language, models in VOICE_CHOICES.items():
            print("Hindi:" if language == "hi" else "English:")
            for model in models:
                print("  " + model)
        print("Hindi packs are about 60–65 MB each; downloads happen only when requested or first used.")
        return 0
    if args.whisper_model and not args.set_default:
        parser.error("--whisper-model requires --set-default")
    if args.all_hindi and (args.model or args.language or args.set_default):
        parser.error("--all-hindi only downloads packs; select a default separately")

    if args.all_hindi:
        models = VOICE_CHOICES["hi"]
    else:
        try:
            language = args.language or (parse_voice_model(args.model)[0] if args.model else "en")
            model = args.model or (config.HINDI_VOICE_MODEL if language == "hi" else config.VOICE_MODEL)
            model_language, *_ = parse_voice_model(model)
        except ValueError as error:
            parser.error(str(error))
        if model_language not in {"en", "hi"} or model_language != language:
            parser.error("Choose an en voice for --language en or a hi voice for --language hi")
        models = (model,)

    try:
        for model in models:
            print("Voice model:", model)
            path = ensure_voice_pack(model)
            print("Voice pack ready at:", path)
        if args.set_default:
            key = "HINDI_VOICE_MODEL" if language == "hi" else "VOICE_MODEL"
            updates = {key: model}
            if args.whisper_model:
                updates.update(WHISPER_MODEL=args.whisper_model, WHISPER_LANGUAGE="auto")
            settings_path = update_settings(updates)
            print("Settings saved to:", settings_path)
            print("Restart LYRA to use these settings. Whisper downloads the selected model on next voice launch.")
    except Exception as error:
        log.exception("Voice setup failed")
        print(f"Voice setup failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
