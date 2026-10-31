"""Background-safe incremental Ollama bridge for a responsive Streamlit screen."""
from __future__ import annotations

from queue import Queue, Empty
from threading import Thread
from time import monotonic
from collections.abc import Callable, Iterator


def stream_events(chunks: Callable[[], Iterator[str]], tick: float = 0.5):
    """Yield (event, value, elapsed_seconds) without freezing while the model starts.

    The worker only communicates through a queue; Streamlit calls remain on the UI thread.
    """
    messages: Queue[tuple[str, str]] = Queue()
    started = monotonic()

    def work():
        try:
            for chunk in chunks():
                messages.put(("text", chunk))
        except Exception as exc:
            messages.put(("error", str(exc)))
        finally:
            messages.put(("done", ""))

    Thread(target=work, daemon=True, name="ollama-market-stream").start()
    while True:
        try:
            kind, value = messages.get(timeout=tick)
        except Empty:
            yield "waiting", "", monotonic() - started
            continue
        if kind == "done":
            return
        yield kind, value, monotonic() - started
