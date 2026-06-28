"""Run ``typst.compile`` for the binding backend, optionally in a subprocess.

This module is intentionally **Django-free**: it imports nothing beyond the
standard library (and ``typst`` lazily, inside the functions). That keeps it safe
to use as a ``multiprocessing`` ``spawn`` target — the child process can import
it and compile without configuring Django.
"""

from __future__ import annotations


def compile_html(source: bytes, root: str) -> bytes:
    """Compile ``source`` (UTF-8 bytes) to HTML bytes, confined to ``root``.

    Passing ``root`` constrains Typst's ``read()`` / ``image()`` / ``include`` to
    that directory, so untrusted markup cannot reach arbitrary files on disk.
    """
    import typst

    # A ``str`` input is treated by typst as a file *path*, so the source must be
    # passed as ``bytes`` to compile it inline.
    output = typst.compile(source, format="html", root=root)
    if isinstance(output, list):  # multi-page output (not expected for html)
        output = output[0]
    return output if isinstance(output, bytes) else str(output).encode("utf-8")


def diagnostics(exc: Exception) -> str:
    """Best-effort extraction of compiler diagnostics from a typst exception."""
    parts = []
    for attr in ("diagnostic", "trace", "hints"):
        value = getattr(exc, attr, None)
        if not value:
            continue
        parts.append(
            "\n".join(value) if isinstance(value, (list, tuple)) else str(value)
        )
    return "\n".join(parts)


def worker(result_queue, source: bytes, root: str) -> None:
    """``multiprocessing`` entry point: compile and report via ``result_queue``."""
    try:
        result_queue.put(("ok", compile_html(source, root)))
    except Exception as exc:  # noqa: BLE001 - any failure is reported to parent
        result_queue.put(("err", str(exc), diagnostics(exc)))
