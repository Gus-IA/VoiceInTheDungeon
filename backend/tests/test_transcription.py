import pytest
from unittest.mock import patch, MagicMock
import transcription
import os

def test_transcribe_audio_success():
    mock_response = MagicMock()
    mock_response.text = "Hola mundo"
    mock_response.language = "es"
    
    with patch("transcription.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.audio.transcriptions.create.return_value = mock_response
        
        # Crear un archivo temporal para el test
        with open("test_audio.webm", "w") as f:
            f.write("fake audio content")
        
        try:
            result = transcription.transcribe_audio("test_audio.webm")
            assert result["text"] == "Hola mundo"
            assert result["language"] == "es"
        finally:
            if os.path.exists("test_audio.webm"):
                os.remove("test_audio.webm")

def test_transcribe_audio_no_key_returns_none():
    with patch("os.getenv", return_value=None):
        result = transcription.transcribe_audio("any_file.webm")
        assert result is None
