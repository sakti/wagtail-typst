from django.template import Context, Template

from wagtail_typst.blocks import TypstBlock
from wagtail_typst.fields import TypstField, TypstText
from wagtail_typst.widgets import TypstTextarea

SOURCE = "= Title\n\nHello *world*.\n"


# --- Field ----------------------------------------------------------------


def test_typst_text_renders_html():
    value = TypstText(SOURCE)
    assert isinstance(value, str)
    assert "<strong>world</strong>" in value.html


def test_field_from_db_value_wraps_in_typst_text():
    field = TypstField()
    value = field.from_db_value(SOURCE, None, None)
    assert isinstance(value, TypstText)
    assert "<h2>Title</h2>" in value.html


def test_field_formfield_uses_typst_widget():
    field = TypstField()
    form_field = field.formfield()
    assert isinstance(form_field.widget, TypstTextarea)


# --- Block ----------------------------------------------------------------


def test_block_render_basic_returns_html():
    block = TypstBlock()
    html = block.render_basic(SOURCE)
    assert "<strong>world</strong>" in html


def test_block_render_uses_template_wrapper():
    block = TypstBlock()
    html = block.render(SOURCE)
    assert 'class="typst-content"' in html
    assert "<strong>world</strong>" in html


def test_block_field_uses_typst_widget():
    block = TypstBlock()
    assert isinstance(block.field.widget, TypstTextarea)


# --- Template tags --------------------------------------------------------


def test_typst_filter():
    template = Template("{% load wagtail_typst_tags %}{{ source|typst }}")
    rendered = template.render(Context({"source": SOURCE}))
    assert "<strong>world</strong>" in rendered


def test_typst_block_tag():
    template = Template(
        "{% load wagtail_typst_tags %}{% typst %}Hello *bold*{% endtypst %}"
    )
    rendered = template.render(Context({}))
    assert "<strong>bold</strong>" in rendered


def test_wagtail_typst_css_tag():
    template = Template("{% load wagtail_typst_tags %}{% wagtail_typst_css %}")
    rendered = template.render(Context({}))
    assert "<link" in rendered
    assert "wagtail_typst/css/typst-content.css" in rendered
