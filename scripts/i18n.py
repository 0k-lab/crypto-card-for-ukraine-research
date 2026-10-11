"""Local text for the two static editions; shared research data stays unchanged."""
from functools import partial
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ('uk', 'en')


def load_messages(language):
    assert language in LANGUAGES, 'Unsupported language'
    messages = json.loads((ROOT / 'locales' / (language + '.json')).read_text())
    assert isinstance(messages, dict) and all(isinstance(key, str) and isinstance(value, str) for key, value in messages.items())
    return messages


def translate(messages, key, **values):
    return messages[key].format(**values)


def translator(language):
    return partial(translate, load_messages(language))
