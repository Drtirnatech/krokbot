import asyncio
import time
from typing import Callable, Any, Optional

class InferenceArbiter:
    """
    Centralized priority arbiter for shared Llama.cpp GPU inference.
    Prevents concurrent token generation requests from causing CUDA OOM
    and context thrashing on unified memory edge devices like NVIDIA Jetson.
    """
    def __init__(self, max_concurrent: int = 1, default_timeout_s: float = 45.0):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.default_timeout_s = default_timeout_s
        self._lock = asyncio.Lock()
        self.metrics = {
            "total_requests": 0,
            "throttled_requests": 0,
            "active_inferences": 0
        }

    async def dispatch(self, coro_func: Callable[[], Any], priority: int = 2, timeout: Optional[float] = None) -> Any:
        """
        Execute an inference coroutine through the arbiter semaphore.
        Lower priority value indicates higher urgency:
          1: Critical / Safety / Sensor Tripwires
          2: Scheduled Crons / Normal Workflow
          3: Interactive Chat / Background Summarization
        """
        self.metrics["total_requests"] += 1
        effective_timeout = timeout or self.default_timeout_s

        # Priority delay scaling: lower priority tasks yield to allow higher priority tasks to claim slots
        if priority > 1:
            await asyncio.sleep(0.005 * (priority - 1))

        async with self.semaphore:
            self.metrics["active_inferences"] += 1
            try:
                res = await asyncio.wait_for(coro_func(), timeout=effective_timeout)
                return res
            finally:
                self.metrics["active_inferences"] -= 1

_global_arbiter: Optional[InferenceArbiter] = None

def get_inference_arbiter() -> InferenceArbiter:
    global _global_arbiter
    if _global_arbiter is None:
        _global_arbiter = InferenceArbiter()
    return _global_arbiter
