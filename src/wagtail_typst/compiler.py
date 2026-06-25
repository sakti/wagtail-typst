"""Convert Typst markup into HTML.

The entry point is :func:`compile_typst`, which takes Typst source and returns a
:class:`~django.utils.safestring.SafeString` of HTML ready to be dropped into a
Wagtail template.

Two backends are supported (selected via the ``WAGTAIL_TYPST_BACKEND`` setting):

``binding``
    Uses the bundled `typst <https://pypi.org/project/typst/>`_ Python package.
    No external binary required. This is the default.

``cli``
    Shells out to a ``typst`` executable (``WAGTAIL_TYPST_CLI_PATH``). Useful if
    you want to pin a specific compiler version system-wide.

Typst's HTML export is still officially experimental, so the produced markup may
change between Typst releases.
"""

from __future__ import annotations

import hashlib
import re
import subprocess

from django.utils.safestring import SafeString, mark_safe

from .settings import get_setting

__all__ = ["compile_typst", "TypstCompileError"]


class TypstCompileError(Exception):
    """Raised when Typst source cannot be compiled to HTML.

    The original compiler diagnostics (when available) are kept on
    :attr:`diagnostics` so callers can surface them to content editors.
    """

    def __init__(self, message: str, diagnostics: str = "") -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


_BODY_RE = re.compile(r"<body[^>]*>(?P<body>.*)</body>", re.DOTALL | re.IGNORECASE)
_HEAD_RE = re.compile(r"<head[^>]*>(?P<head>.*?)</head>", re.DOTALL | re.IGNORECASE)
_STYLE_RE = re.compile(r"<style[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)


def compile_typst(source: str, *, full_document: bool | None = None) -> SafeString:
    """Compile Typst ``source`` and return HTML marked safe for templates.

    Args:
        source: Typst markup. An empty / whitespace-only string yields ``""``.
        full_document: Override ``WAGTAIL_TYPST_FULL_DOCUMENT``. When falsey only
            the rendered ``<body>`` (plus any ``<head>`` ``<style>`` blocks) is
            returned so it can be embedded inside an existing page.

    Raises:
        TypstCompileError: If the source fails to compile.
    """
    if source is None or not source.strip():
        return mark_safe("")

    if full_document is None:
        full_document = bool(get_setting("FULL_DOCUMENT"))

    cached = _cache_get(source, full_document)
    if cached is not None:
        return mark_safe(cached)

    document = _render_html(source)
    html = document if full_document else _extract_body(document)

    _cache_set(source, full_document, html)
    return mark_safe(html)


def _render_html(source: str) -> str:
    backend = get_setting("BACKEND")
    if backend == "binding":
        return _render_with_binding(source)
    if backend == "cli":
        return _render_with_cli(source)
    raise TypstCompileError(
        f"Unknown WAGTAIL_TYPST_BACKEND {backend!r} (expected 'binding' or 'cli')."
    )


def _render_with_binding(source: str) -> str:
    try:
        import typst
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise TypstCompileError(
            "The 'typst' package is required for the binding backend. "
            "Install it with `pip install wagtail-typst[binding]`."
        ) from exc

    # NOTE: a ``str`` input is interpreted by typst as a *file path*, so the
    # source must be passed as ``bytes`` to compile it inline.
    try:
        output = typst.compile(source.encode("utf-8"), format="html")
    except Exception as exc:  # typst raises its own error types
        raise TypstCompileError(str(exc), diagnostics=_diagnostics(exc)) from exc

    if isinstance(output, list):  # multi-page output (not expected for html)
        output = output[0]
    return output.decode("utf-8") if isinstance(output, bytes) else str(output)


def _render_with_cli(source: str) -> str:
    cli_path = get_setting("CLI_PATH")
    timeout = get_setting("CLI_TIMEOUT")
    try:
        proc = subprocess.run(
            [cli_path, "compile", "--features", "html", "--format", "html", "-", "-"],
            input=source.encode("utf-8"),
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise TypstCompileError(
            f"Typst executable not found at {cli_path!r}. "
            "Install Typst or set WAGTAIL_TYPST_CLI_PATH."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise TypstCompileError(f"Typst compilation timed out after {timeout}s.") from exc

    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace")
        raise TypstCompileError("Typst compilation failed.", diagnostics=stderr)
    return proc.stdout.decode("utf-8")


def _extract_body(document: str) -> str:
    """Return the inner ``<body>`` HTML, prefixed with any ``<head>`` styles."""
    body_match = _BODY_RE.search(document)
    body = body_match.group("body") if body_match else document

    head_match = _HEAD_RE.search(document)
    styles = ""
    if head_match:
        styles = "".join(_STYLE_RE.findall(head_match.group("head")))
    return styles + body


def _diagnostics(exc: Exception) -> str:
    parts = []
    for attr in ("diagnostic", "trace", "hints"):
        value = getattr(exc, attr, None)
        if not value:
            continue
        parts.append("\n".join(value) if isinstance(value, (list, tuple)) else str(value))
    return "\n".join(parts)


# --- Caching ---------------------------------------------------------------


def _cache_key(source: str, full_document: bool) -> str:
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return f"wagtail_typst:{int(full_document)}:{digest}"


def _get_cache():
    if not get_setting("CACHE"):
        return None
    from django.core.cache import caches

    try:
        return caches[get_setting("CACHE_ALIAS")]
    except Exception:  # invalid alias -> behave as if caching is disabled
        return None


def _cache_get(source: str, full_document: bool) -> str | None:
    cache = _get_cache()
    if cache is None:
        return None
    return cache.get(_cache_key(source, full_document))


def _cache_set(source: str, full_document: bool, html: str) -> None:
    cache = _get_cache()
    if cache is None:
        return
    cache.set(_cache_key(source, full_document), html, get_setting("CACHE_TIMEOUT"))
