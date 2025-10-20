from typing import Callable, Any, List
from .models import Signal


class SignalBus:
    """Simple in-process pub/sub bus for Signals.

    - subscribe(handler): registers a callable that takes a Signal
    - publish(signal): pushes a single signal to all subscribers
    - publish_many(signals): pushes a list of signals
    """

    def __init__(self) -> None:
        self._subscribers: List[Callable[[Signal], Any]] = []

    def subscribe(self, handler: Callable[[Signal], Any]) -> None:
        self._subscribers.append(handler)

    def publish(self, signal: Signal) -> None:
        for handler in list(self._subscribers):
            try:
                handler(signal)
            except Exception:
                # Intentionally swallow to avoid breaking the bus; handlers should log internally
                pass

    def publish_many(self, signals: List[Signal]) -> None:
        for s in signals:
            self.publish(s)

