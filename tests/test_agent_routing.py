import pytest
from unittest.mock import patch
from krokbot.agent.core import KrokBotAgent

def test_weather_prompt_routing(monkeypatch):
    agent = KrokBotAgent()
    monkeypatch.setattr(agent.client, "chat", lambda msgs: {"message": {"content": "The weather in New York is 72°F and sunny.\n\nFinal Answer: Weather query complete."}})
    
    result = agent.run_task("What is the weather in New York?")
    assert result["status"] == "success"
    assert "Drive storage audit complete" not in result["report"]
    assert "Weather query complete" in result["report"]

def test_diagnostic_prompt_routing(monkeypatch):
    agent = KrokBotAgent()
    monkeypatch.setattr(agent.client, "chat", lambda msgs: {"message": {"content": "Final Answer: Storage audit complete."}})
    
    result = agent.run_task("Inspect storage capacity on C: drive")
    assert result["status"] == "success"
    assert result["metrics"] != {}
