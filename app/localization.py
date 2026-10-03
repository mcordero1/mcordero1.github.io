"""Locale context shared by the static build and optional FastAPI preview."""
import json
from pathlib import Path
from app.schemas import Profile

CONTENT = Path(__file__).resolve().parent.parent / 'content'


def localized_profile(language: str) -> Profile:
    filename = 'profile.en.json' if language == 'en' else 'profile.json'
    return Profile.model_validate_json((CONTENT / filename).read_text(encoding='utf-8'))


def locale_context(language: str, language_url: str) -> dict:
    if language not in {'es', 'en'}:
        raise ValueError('Unsupported language')
    return {
        'language': language,
        'other_language': 'en' if language == 'es' else 'es',
        'language_url': language_url,
        'ui': json.loads((CONTENT / f'ui.{language}.json').read_text(encoding='utf-8')),
    }
