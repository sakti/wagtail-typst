"""A StreamField block for authoring Typst content."""

from __future__ import annotations

from django import forms
from django.utils.functional import cached_property

from wagtail.blocks import TextBlock

from .compiler import compile_typst
from .settings import get_setting
from .widgets import TypstTextarea

__all__ = ["TypstBlock"]


class TypstBlock(TextBlock):
    """Edit Typst markup in a StreamField and render it as HTML.

    Usage::

        from wagtail.fields import StreamField
        from wagtail_typst.blocks import TypstBlock

        class ArticlePage(Page):
            body = StreamField([("typst", TypstBlock())])

    The compiled HTML is exposed to the template as ``html`` and rendered inside
    a wrapper ``<div>`` whose class comes from ``WAGTAIL_TYPST_WRAPPER_CLASS``.
    """

    def __init__(self, *args, full_document: bool | None = None, **kwargs):
        self.full_document = full_document
        kwargs.setdefault("rows", 12)
        super().__init__(*args, **kwargs)

    @cached_property
    def field(self):
        field_kwargs = {"widget": TypstTextarea(attrs={"rows": self.rows})}
        field_kwargs.update(self.field_options)
        return forms.CharField(**field_kwargs)

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context=parent_context)
        context["html"] = compile_typst(value or "", full_document=self.full_document)
        context["wrapper_class"] = get_setting("WRAPPER_CLASS")
        return context

    def render_basic(self, value, context=None):
        return compile_typst(value or "", full_document=self.full_document)

    class Meta:
        icon = "code"
        label = "Typst"
        template = "wagtail_typst/blocks/typst_block.html"
