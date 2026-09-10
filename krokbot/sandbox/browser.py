import sys
import types
import asyncio
from typing import Dict, Any, Optional, Tuple

# Pre-emptively register dummy loop module in sys.modules on Windows to avoid strftime crash in marinabox.computer_use.loop
if "marinabox.computer_use.loop" not in sys.modules:
    dummy_loop = types.ModuleType("marinabox.computer_use.loop")
    dummy_loop.SYSTEM_PROMPT = ""
    dummy_loop.sampling_loop = None
    sys.modules["marinabox.computer_use.loop"] = dummy_loop

class BrowserToolWrapper:

    """
    Wrapper around MarinaBox ComputerTool providing GUI browser automation,
    clicking, typing, screenshots, and navigation.
    """
    def __init__(self, port: int = 8002):
        from marinabox.computer_use.tools.computer import ComputerTool
        self.computer_tool = ComputerTool(port=port)

    async def execute_action(
        self,
        action: str,
        text: Optional[str] = None,
        coordinate: Optional[Tuple[int, int]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        try:
            res = await self.computer_tool(action=action, text=text, coordinate=coordinate, **kwargs)
            error_msg = getattr(res, "error", None)
            output_msg = getattr(res, "output", "") or ""
            return {
                "status": "success" if not error_msg else "error",
                "output": output_msg if not error_msg else f"Error: {error_msg}",
                "base64_image": getattr(res, "base64_image", None)
            }
        except Exception as e:
            return {
                "status": "error",
                "output": f"Browser execution exception: {str(e)}",
                "base64_image": None
            }

