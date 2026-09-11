import asyncio
import time
import fnmatch
import uuid
from typing import Dict, Any, List, Callable, Optional

class KrokBus:
    """
    In-memory Pub/Sub Event Broker for co-located edge agents.
    Enables decoupled inter-agent communication, telemetry fan-out,
    and event-triggered autonomous behaviors.
    """
    def __init__(self, history_limit: int = 200):
        self.subscribers: Dict[str, Dict[str, Any]] = {}
        self.history: List[Dict[str, Any]] = []
        self.history_limit = history_limit

    def subscribe(self, pattern: str, callback: Callable[[Dict[str, Any]], Any]) -> str:
        """Subscribe to a topic pattern (e.g. 'sensors.*' or 'agents/+/status')."""
        sub_id = f"sub-{uuid.uuid4().hex[:8]}"
        self.subscribers[sub_id] = {
            "pattern": pattern,
            "callback": callback
        }
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        """Remove an existing subscription."""
        return self.subscribers.pop(sub_id, None) is not None

    async def publish(self, topic: str, payload: Dict[str, Any], source_agent: str = "system") -> Dict[str, Any]:
        """Publish an event to all matching subscribers."""
        event = {
            "id": f"evt-{uuid.uuid4().hex[:8]}",
            "topic": topic,
            "payload": payload,
            "source_agent": source_agent,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Store in historical ring buffer
        self.history.append(event)
        if len(self.history) > self.history_limit:
            self.history.pop(0)

        # Notify matching subscribers
        for sub_id, sub in list(self.subscribers.items()):
            pattern = sub["pattern"]
            if fnmatch.fnmatch(topic, pattern) or pattern == "*":
                cb = sub["callback"]
                try:
                    if asyncio.iscoroutinefunction(cb):
                        asyncio.create_task(cb(event))
                    else:
                        cb(event)
                except Exception as e:
                    print(f"[KrokBus] Callback error for {sub_id} on {topic}: {e}")

        return event

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.history[-limit:]

_global_bus: Optional[KrokBus] = None

def get_event_bus() -> KrokBus:
    global _global_bus
    if _global_bus is None:
        _global_bus = KrokBus()
    return _global_bus
