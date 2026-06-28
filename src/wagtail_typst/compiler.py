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

Security
--------
Typst markup is treated as **untrusted** by default (in Wagtail, content editors
are only semi-trusted). Three protections apply:

* The compiled HTML is sanitized (``WAGTAIL_TYPST_SANITIZE``) before it is marked
  safe, stripping ``<script>``, event handlers and dangerous URLs.
* Compilation is confined to an isolated project root (``WAGTAIL_TYPST_ROOT``) so
  ``read()`` / ``image()`` cannot reach project files.
* Compilation is time-bounded (``WAGTAIL_TYPST_TIMEOUT``); the binding backend
  runs in a separate process that is terminated on expiry.

Typst's HTML export is still officially experimental, so the produced markup may
change between Typst releases.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile

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

    Note:
        ``full_document=True`` returns the raw Typst HTML document and is **not**
        sanitized (a full page cannot be cleaned as an HTML fragment). Only use
        it with trusted input.
    """
    if source is None or not source.strip():
        return mark_safe("")

    if full_document is None:
        full_document = bool(get_setting("FULL_DOCUMENT"))
    sanitize = not full_document and bool(get_setting("SANITIZE"))

    cached = _cache_get(source, full_document, sanitize)
    if cached is not None:
        return mark_safe(cached)

    document = _render_html(source)
    html = document if full_document else _extract_body(document)
    if sanitize:
        html = _sanitize(html)

    _cache_set(source, full_document, sanitize, html)
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
        import typst  # noqa: F401 - import here for a clear error message
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise TypstCompileError(
            "The 'typst' package is required for the binding backend. "
            "Install it with `pip install wagtail-typst[binding]`."
        ) from exc

    root = _root_dir()
    timeout = get_setting("TIMEOUT")
    data = source.encode("utf-8")
    if timeout is None:
        return _compile_binding_inprocess(data, root)
    return _compile_binding_isolated(data, root, timeout)


def _compile_binding_inprocess(data: bytes, root: str) -> str:
    from ._typst_worker import compile_html, diagnostics

    try:
        return compile_html(data, root).decode("utf-8")
    except Exception as exc:  # typst raises its own error types
        raise TypstCompileError(str(exc), diagnostics=diagnostics(exc)) from exc


def _compile_binding_isolated(data: bytes, root: str, timeout: float) -> str:
    """Compile in a separate process, terminating it if it overruns ``timeout``."""
    import multiprocessing
    import queue as queue_mod

    from ._typst_worker import worker

    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    proc = ctx.Process(target=worker, args=(result_queue, data, root), daemon=True)
    proc.start()
    try:
        # Read before join: draining the queue first avoids a deadlock when the
        # HTML output is larger than the pipe buffer.
        message = result_queue.get(timeout=timeout)
    except queue_mod.Empty:
        raise TypstCompileError(
            f"Typst compilation timed out after {timeout}s."
        ) from None
    finally:
        if proc.is_alive():
            proc.terminate()
        proc.join()

    if message[0] == "ok":
        return message[1].decode("utf-8")
    _, error_message, diagnostics = message
    raise TypstCompileError(error_message, diagnostics=diagnostics)


def _render_with_cli(source: str) -> str:
    cli_path = get_setting("CLI_PATH")
    timeout = get_setting("TIMEOUT")
    root = _root_dir()
    try:
        proc = subprocess.run(
            [
                cli_path,
                "compile",
                "--features",
                "html",
                "--format",
                "html",
                "--root",
                root,
                "-",
                "-",
            ],
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
        raise TypstCompileError(
            f"Typst compilation timed out after {timeout}s."
        ) from exc

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


# --- Sandbox root ----------------------------------------------------------

_SANDBOX_ROOT: str | None = None


def _root_dir() -> str:
    """Directory that Typst file access is confined to.

    Defaults to a process-wide empty temp directory so ``read()`` / ``image()``
    resolve to nothing, neutralising file-disclosure attacks. Override with
    ``WAGTAIL_TYPST_ROOT`` to expose a specific asset directory.
    """
    configured = get_setting("ROOT")
    if configured:
        return str(configured)
    global _SANDBOX_ROOT
    if _SANDBOX_ROOT is None:
        _SANDBOX_ROOT = tempfile.mkdtemp(prefix="wagtail-typst-root-")
    return _SANDBOX_ROOT


# --- Sanitization ----------------------------------------------------------

# Tags Typst's HTML export emits, plus MathML. ``<style>`` is kept because Typst
# puts the MathML layout stylesheet there; its CSS content cannot execute script.
_ALLOWED_TAGS = {
    # Structure / block
    "p",
    "div",
    "span",
    "br",
    "hr",
    "pre",
    "blockquote",
    "figure",
    "figcaption",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "section",
    "article",
    "header",
    "footer",
    # Inline
    "a",
    "b",
    "i",
    "em",
    "strong",
    "u",
    "s",
    "del",
    "ins",
    "sub",
    "sup",
    "small",
    "code",
    "kbd",
    "samp",
    "mark",
    "cite",
    "q",
    "abbr",
    "time",
    "wbr",
    "bdi",
    "bdo",
    # Lists
    "ul",
    "ol",
    "li",
    "dl",
    "dt",
    "dd",
    # Tables
    "table",
    "caption",
    "colgroup",
    "col",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "td",
    "th",
    # Media
    "img",
    # Typst math layout stylesheet
    "style",
    # MathML
    "math",
    "mrow",
    "mi",
    "mo",
    "mn",
    "ms",
    "mtext",
    "mspace",
    "mpadded",
    "mphantom",
    "menclose",
    "msup",
    "msub",
    "msubsup",
    "mfrac",
    "msqrt",
    "mroot",
    "munder",
    "mover",
    "munderover",
    "mtable",
    "mtr",
    "mtd",
    "mlabeledtr",
    "maction",
    "merror",
    "mstyle",
    "mfenced",
    "mglyph",
    "semantics",
    "annotation",
    "annotation-xml",
}

_ALLOWED_ATTRS = {
    "*": {"class", "style", "dir", "id", "title", "lang"},
    # "rel" is managed by nh3's link_rel, so it must not be listed here.
    "a": {"href", "name", "target"},
    "img": {"src", "alt", "width", "height"},
    "col": {"span"},
    "colgroup": {"span"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
    "ol": {"start", "type", "reversed"},
    "time": {"datetime"},
    # MathML
    "math": {"display", "xmlns"},
    "mo": {
        "lspace",
        "rspace",
        "stretchy",
        "fence",
        "separator",
        "accent",
        "movablelimits",
        "largeop",
        "symmetric",
        "minsize",
        "maxsize",
        "form",
    },
    "mfrac": {"linethickness"},
    "mspace": {"width", "height", "depth"},
    "mpadded": {"width", "height", "depth", "lspace", "voffset"},
    "munder": {"accentunder"},
    "mover": {"accent"},
    "munderover": {"accent", "accentunder"},
    "mtable": {"columnalign", "rowalign"},
    "mtd": {"columnalign", "rowalign", "columnspan", "rowspan"},
    "mstyle": {
        "displaystyle",
        "scriptlevel",
        "mathvariant",
        "mathcolor",
        "mathbackground",
    },
    "annotation": {"encoding"},
    "annotation-xml": {"encoding"},
}


def _sanitize(html: str) -> str:
    try:
        import nh3
    except ImportError as exc:  # pragma: no cover - nh3 is a hard dependency
        raise TypstCompileError(
            "The 'nh3' package is required to sanitize Typst output. Install it, "
            "or set WAGTAIL_TYPST_SANITIZE=False only if all input is trusted."
        ) from exc

    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        clean_content_tags={"script"},
        url_schemes={"http", "https", "mailto", "tel"},
    )


# --- Caching ---------------------------------------------------------------


def _cache_key(source: str, full_document: bool, sanitize: bool) -> str:
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return f"wagtail_typst:{int(full_document)}:{int(sanitize)}:{digest}"


def _get_cache():
    if not get_setting("CACHE"):
        return None
    from django.core.cache import caches

    try:
        return caches[get_setting("CACHE_ALIAS")]
    except Exception:  # invalid alias -> behave as if caching is disabled
        return None


def _cache_get(source: str, full_document: bool, sanitize: bool) -> str | None:
    cache = _get_cache()
    if cache is None:
        return None
    return cache.get(_cache_key(source, full_document, sanitize))


def _cache_set(source: str, full_document: bool, sanitize: bool, html: str) -> None:
    cache = _get_cache()
    if cache is None:
        return
    cache.set(
        _cache_key(source, full_document, sanitize), html, get_setting("CACHE_TIMEOUT")
    )
