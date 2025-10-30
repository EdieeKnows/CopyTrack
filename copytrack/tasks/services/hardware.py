"""Simulated hardware controllers for kiosk peripherals."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from threading import Condition
from typing import Any, Deque, Dict, List, Optional

from django.utils import timezone


@dataclass(frozen=True)
class CardSwipeEvent:
    """Record of a simulated card swipe."""

    timestamp: datetime
    card_number: str


@dataclass(frozen=True)
class PrintEvent:
    """Record of a simulated label print job."""

    timestamp: datetime
    content: str
    copies: int


class HardwareStatusBroadcaster:
    """Maintain hardware connection status and broadcast updates."""

    def __init__(self) -> None:
        self._state: Dict[str, bool] = {
            "card_reader": False,
            "label_printer": False,
        }
        self._condition = Condition()
        self._events: Deque[Dict[str, Any]] = deque(maxlen=100)
        self._version = 0
        self._record_event(changed_device=None)

    def set_connected(self, device: str, connected: bool) -> Dict[str, Any] | None:
        """Update connection status and notify listeners if it changed."""
        with self._condition:
            current = self._state.get(device)
            if current is not None and current == connected:
                return None
            self._state[device] = connected
            event = self._record_event(changed_device=device)
            self._condition.notify_all()
            return event

    def latest_event(self) -> Dict[str, Any]:
        """Return the most recent status event."""
        with self._condition:
            if not self._events:
                return self._record_event(changed_device=None)
            return self._events[-1]

    def wait_for_event(self, last_event_id: int | None = None) -> Dict[str, Any]:
        """Block until a newer event is available."""
        with self._condition:
            while True:
                for event in self._events:
                    if event["id"] > (last_event_id or 0):
                        return event
                self._condition.wait()

    def snapshot(self) -> Dict[str, bool]:
        """Return a copy of the current connection state."""
        with self._condition:
            return dict(self._state)

    def _record_event(self, changed_device: str | None) -> Dict[str, Any]:
        self._version += 1
        payload = {
            "id": self._version,
            "changed_device": changed_device,
            "statuses": dict(self._state),
            "timestamp": timezone.now().isoformat(),
        }
        self._events.append(payload)
        return payload


class CardReaderSimulator:
    """Simulated controller for a card reader device."""

    def __init__(self) -> None:
        self.connected: bool = False
        self._last_card: Optional[str] = None
        self._history: Deque[CardSwipeEvent] = deque(maxlen=20)

    def connect(self) -> None:
        """Simulate connecting the device."""
        self.connected = True
        HARDWARE_STATUS.set_connected("card_reader", True)

    def disconnect(self) -> None:
        """Simulate disconnecting the device."""
        self.connected = False
        self._last_card = None
        HARDWARE_STATUS.set_connected("card_reader", False)

    def simulate_swipe(self, card_number: str) -> str:
        """Simulate a user swiping a card through the reader."""
        if not self.connected:
            raise RuntimeError("Card reader is not connected")
        card_number = card_number.strip()
        event = CardSwipeEvent(timestamp=datetime.now(), card_number=card_number)
        self._history.appendleft(event)
        self._last_card = card_number
        return card_number

    @property
    def last_card(self) -> Optional[str]:
        """Return the last card number recorded by the simulator."""
        return self._last_card

    def history(self) -> List[CardSwipeEvent]:
        """Return swipe history ordered from newest to oldest."""
        return list(self._history)

    def clear_history(self) -> None:
        """Reset the swipe history."""
        self._history.clear()
        self._last_card = None


class LabelPrinterSimulator:
    """Simulated controller for a label printer device."""

    def __init__(self) -> None:
        self.connected: bool = False
        self._queue: Deque[PrintEvent] = deque()
        self._history: Deque[PrintEvent] = deque(maxlen=50)

    def connect(self) -> None:
        """Simulate connecting the printer."""
        self.connected = True
        HARDWARE_STATUS.set_connected("label_printer", True)

    def disconnect(self) -> None:
        """Simulate disconnecting the printer."""
        self.connected = False
        self._queue.clear()
        HARDWARE_STATUS.set_connected("label_printer", False)

    def simulate_print(self, content: str, copies: int = 1) -> PrintEvent:
        """Simulate sending a print job to the printer."""
        if not self.connected:
            raise RuntimeError("Label printer is not connected")
        event = PrintEvent(timestamp=datetime.now(), content=content.strip(), copies=copies)
        self._queue.append(event)
        self._history.appendleft(event)
        return event

    def process_next_job(self) -> Optional[PrintEvent]:
        """Simulate the printer completing the next job in the queue."""
        if self._queue:
            return self._queue.popleft()
        return None

    def pending_jobs(self) -> List[PrintEvent]:
        """Return pending jobs waiting to be processed."""
        return list(self._queue)

    def history(self) -> List[PrintEvent]:
        """Return processed job history ordered from newest to oldest."""
        return list(self._history)

    def clear_history(self) -> None:
        """Reset job history."""
        self._history.clear()


HARDWARE_STATUS = HardwareStatusBroadcaster()
