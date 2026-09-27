"""
============================================================
 LYRA VOICE PACK SETUP
============================================================
 Downloads Lyra's Piper voice in advance.
 Run:  python -m lyra.setup_voice
 (main.py also auto-downloads on first launch if missing)
============================================================
"""

from . import config
from .voice import ensure_voice_pack


def main():
    print("Voice model:", config.VOICE_MODEL)
    path = ensure_voice_pack()
    print("Voice pack ready at:", path)


if __name__ == "__main__":
    main()
