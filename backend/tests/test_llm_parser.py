import pytest
from unittest.mock import patch, MagicMock
import llm_parser
import json

def test_parse_command_llm_success():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "intent": "move",
            "slots": {"direction": "north", "item": None, "action": None}
        })))
    ]
    
    with patch("llm_parser.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response
        
        result = llm_parser.parse_command_llm("go north")
        assert result["intent"] == "move"
        assert result["slots"]["direction"] == "north"

def test_translate_reply_success():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="Look at this!"))
    ]
    
    with patch("llm_parser.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response
        
        result = llm_parser.translate_reply("¡Mira esto!", "en")
        assert result == "Look at this!"

def test_no_api_key_returns_none_or_original():
    with patch("os.getenv", return_value=None):
        # En llm_parser, si no hay key, parse_command devuelve None y translate devuelve el original
        assert llm_parser.parse_command_llm("test") is None
        assert llm_parser.translate_reply("hola", "en") == "hola"
