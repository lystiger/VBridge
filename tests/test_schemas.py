import pytest
from pydantic import ValidationError

from shared.schemas import AudioRequest, TranslationRequest


def test_audio_request_validates_required_values() -> None:
    with pytest.raises(ValidationError):
        AudioRequest(session_id="", speaker="speaker_a", audio_path="clip.wav")


def test_translation_request_rejects_unsupported_language() -> None:
    with pytest.raises(ValidationError):
        TranslationRequest(session_id="session", text="hello", source_language="fr")
