import pytest
import asyncio
from unittest.mock import patch, MagicMock
from krokbot.arbiter import InferenceArbiter, get_inference_arbiter
from krokbot.bus import KrokBus, get_event_bus

@pytest.mark.asyncio
async def test_arbiter_priority_queueing():
    arbiter = InferenceArbiter()
    order = []

    async def mock_inference(item_id, delay):
        order.append(f"start-{item_id}")
        await asyncio.sleep(delay)
        order.append(f"end-{item_id}")
        return f"result-{item_id}"

    # Schedule a background job (priority 3), then an urgent job (priority 1)
    res3 = await arbiter.dispatch(lambda: mock_inference("bg", 0.05), priority=3)
    res1 = await arbiter.dispatch(lambda: mock_inference("urgent", 0.01), priority=1)

    assert res3 == "result-bg"
    assert res1 == "result-urgent"
    assert "start-bg" in order
    assert "start-urgent" in order

@pytest.mark.asyncio
async def test_krokbus_pub_sub():
    bus = KrokBus()
    received = []

    def on_event(event):
        received.append(event)

    sub_id = bus.subscribe("sensors.temperature", on_event)
    assert sub_id is not None

    await bus.publish(
        topic="sensors.temperature",
        payload={"temp_c": 42.5},
        source_agent="krok-prime-01"
    )

    assert len(received) == 1
    assert received[0]["topic"] == "sensors.temperature"
    assert received[0]["payload"]["temp_c"] == 42.5
    assert received[0]["source_agent"] == "krok-prime-01"

    # Unsubscribe
    bus.unsubscribe(sub_id)
    await bus.publish("sensors.temperature", {"temp_c": 45.0}, "krok-prime-01")
    assert len(received) == 1
