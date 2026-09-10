import pytest
from krokbot.sandbox.browser import BrowserToolWrapper

@pytest.mark.asyncio
async def test_browser_tool_wrapper_initialization_and_wait():
    wrapper = BrowserToolWrapper()
    res = await wrapper.execute_action("wait", duration=0.1)
    assert res["status"] == "success"
    assert "waited" in res["output"]

@pytest.mark.asyncio
async def test_browser_tool_wrapper_invalid_action():
    wrapper = BrowserToolWrapper()
    res = await wrapper.execute_action("invalid_action_name")
    assert res["status"] == "error"
