"""Template tags and filters for rendering Typst markup.

Load them in a template with ``{% load wagtail_typst_tags %}``.

Filter::

    {{ page.body|typst }}

Block tag (compiles its literal/rendered contents)::

    {% typst %}
    = Hello
    Some *bold* text.
    {% endtypst %}
"""

from __future__ import annotations

from django import template
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import SafeString

from ..compiler import TypstCompileError, compile_typst

register = template.Library()


@register.simple_tag(name="wagtail_typst_css")
def wagtail_typst_css() -> SafeString:
    """Render a ``<link>`` to the front-end stylesheet for Typst content.

    Drop ``{% wagtail_typst_css %}`` into your base template's ``<head>``. The
    stylesheet bundles Libertinus Serif so the HTML output uses the same default
    font as Typst's PDF export, and applies the ``.typst-content`` wrapper
    styles. Requires ``django.contrib.staticfiles`` (run ``collectstatic`` for
    production).
    """
    href = static("wagtail_typst/css/typst-content.css")
    return format_html('<link rel="stylesheet" href="{}">', href)


@register.filter(name="typst", is_safe=True)
def typst_filter(value) -> SafeString:
    """Compile a Typst string to HTML.

    A compilation error returns an empty (safe) string instead of breaking the
    whole page render. Use the ``.html`` property or ``{% typst %}`` tag if you
    prefer the error to propagate.
    """
    try:
        return compile_typst(value or "")
    except TypstCompileError:
        return compile_typst("")  # returns an empty SafeString


class TypstNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        source = self.nodelist.render(context)
        return compile_typst(source)


@register.tag(name="typst")
def typst_tag(parser, token):
    nodelist = parser.parse(("endtypst",))
    parser.delete_first_token()
    return TypstNode(nodelist)
