import asyncio
import pytest
from krokbot.sandbox.browser import BrowserToolWrapper

def test_browser_tool_wrapper_initialization_and_wait():
    wrapper = BrowserToolWrapper()
    res = asyncio.run(wrapper.execute_action("wait", duration=0.1))
    assert res["status"] == "success"
    assert "waited" in res["output"]

def test_browser_tool_wrapper_invalid_action():
    wrapper = BrowserToolWrapper()
    res = asyncio.run(wrapper.execute_action("invalid_action_name"))
    assert res["status"] == "error"
