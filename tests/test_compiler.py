import pytest

from wagtail_typst.compiler import TypstCompileError, compile_typst

SOURCE = "= Heading\n\nSome *bold* and _italic_ text.\n\n- one\n- two\n"


def test_compiles_body_only_by_default():
    html = compile_typst(SOURCE)
    assert "<h2>Heading</h2>" in html
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html
    assert "<li>one</li>" in html
    # Body extraction strips the document scaffolding.
    assert "<!DOCTYPE" not in html
    assert "<body" not in html
    assert "<head" not in html


def test_full_document_keeps_scaffolding():
    html = compile_typst(SOURCE, full_document=True)
    assert "<!DOCTYPE html>" in html
    assert "<body" in html


@pytest.mark.parametrize("value", ["", "   \n  ", None])
def test_empty_input_returns_empty(value):
    assert compile_typst(value) == ""


def test_result_is_marked_safe():
    html = compile_typst(SOURCE)
    assert hasattr(html, "__html__")


def test_invalid_source_raises():
    with pytest.raises(TypstCompileError):
        # #undefined() is not a valid function call -> compile error.
        compile_typst("#this_is_not_defined()")


def test_caching_returns_consistent_output(settings):
    settings.WAGTAIL_TYPST_CACHE = True
    first = compile_typst(SOURCE)
    second = compile_typst(SOURCE)
    assert str(first) == str(second)
