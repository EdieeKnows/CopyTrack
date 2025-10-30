"""Simulated hardware controllers for kiosk peripherals."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, List, Optional


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


class CardReaderSimulator:
    """Simulated controller for a card reader device."""

    def __init__(self) -> None:
        self.connected: bool = False
        self._last_card: Optional[str] = None
        self._history: Deque[CardSwipeEvent] = deque(maxlen=20)

    def connect(self) -> None:
        """Simulate connecting the device."""
        self.connected = True

    def disconnect(self) -> None:
        """Simulate disconnecting the device."""
        self.connected = False
        self._last_card = None

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

    def disconnect(self) -> None:
        """Simulate disconnecting the printer."""
        self.connected = False
        self._queue.clear()

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
