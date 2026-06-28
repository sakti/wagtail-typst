"""Security regression tests for the three hardening measures.

1. Output is sanitized (no XSS) while MathML survives.
2. File access is confined to the configured (empty) sandbox root.
3. Compilation is time-bounded via an isolated process.
"""

import pytest

from wagtail_typst.compiler import TypstCompileError, compile_typst

# --- 1. XSS / sanitization -------------------------------------------------

XSS_SOURCE = (
    '#html.elem("script", "alert(document.cookie)")\n'
    '#html.elem("img", attrs: (src: "x", onerror: "alert(1)"))\n'
    '#link("javascript:alert(1)")[click]\n'
)


def test_script_and_event_handlers_are_stripped(settings):
    settings.WAGTAIL_TYPST_CACHE = False
    html = str(compile_typst(XSS_SOURCE))
    assert "<script" not in html
    assert "onerror" not in html
    assert "javascript:" not in html


def test_mathml_survives_sanitization(settings):
    settings.WAGTAIL_TYPST_CACHE = False
    html = str(compile_typst("$a^2 + b^2 = c^2$"))
    assert "<math" in html
    assert "<msup>" in html
    assert "<mi>" in html


def test_sanitize_can_be_disabled(settings):
    settings.WAGTAIL_TYPST_CACHE = False
    settings.WAGTAIL_TYPST_SANITIZE = False
    html = str(compile_typst(XSS_SOURCE))
    assert "<script>alert(document.cookie)</script>" in html


# --- 2. File-access confinement -------------------------------------------


def test_default_root_blocks_file_reads(settings):
    settings.WAGTAIL_TYPST_CACHE = False
    # The default sandbox root is an empty directory, so any read fails.
    with pytest.raises(TypstCompileError):
        compile_typst('#raw(read("secret.txt"))')


def test_absolute_and_traversal_paths_are_blocked(settings):
    settings.WAGTAIL_TYPST_CACHE = False
    with pytest.raises(TypstCompileError):
        compile_typst('#raw(read("/etc/passwd"))')
    with pytest.raises(TypstCompileError):
        compile_typst('#raw(read("../../../../etc/passwd"))')


def test_configured_root_scopes_reads(settings, tmp_path):
    settings.WAGTAIL_TYPST_CACHE = False
    (tmp_path / "note.txt").write_text("ALLOWED-ASSET")
    settings.WAGTAIL_TYPST_ROOT = str(tmp_path)
    html = str(compile_typst('#raw(read("note.txt"))'))
    assert "ALLOWED-ASSET" in html


# --- 3. Timeout / DoS ------------------------------------------------------


def test_isolated_process_compiles(settings):
    settings.WAGTAIL_TYPST_CACHE = False
    settings.WAGTAIL_TYPST_TIMEOUT = 30  # spawn an isolated worker
    html = str(compile_typst("= Hello"))
    assert "<h2>Hello</h2>" in html


def test_timeout_raises(settings):
    settings.WAGTAIL_TYPST_CACHE = False
    settings.WAGTAIL_TYPST_TIMEOUT = 0.001  # too short to ever finish
    with pytest.raises(TypstCompileError) as exc:
        compile_typst("= Hello")
    assert "timed out" in str(exc.value)
