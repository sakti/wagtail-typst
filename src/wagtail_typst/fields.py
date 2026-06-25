"""A model/form field that stores Typst source and renders it to HTML."""

from __future__ import annotations

from django import forms
from django.db import models
from django.utils.functional import cached_property
from django.utils.safestring import SafeString

from .compiler import compile_typst
from .widgets import TypstTextarea

__all__ = ["TypstText", "TypstFormField", "TypstField"]


class TypstText(str):
    """A ``str`` subclass that lazily exposes its compiled HTML.

    Instances behave exactly like the underlying Typst source string, so they
    keep working in forms and admin listings, while templates can render the
    HTML with ``{{ page.body.html }}``.
    """

    @cached_property
    def html(self) -> SafeString:
        return compile_typst(str(self))


class TypstFormField(forms.CharField):
    widget = TypstTextarea


class TypstField(models.TextField):
    """A :class:`~django.db.models.TextField` holding Typst markup.

    The raw source is stored in the database; the compiled HTML is produced on
    demand (and cached) via the :class:`TypstText` value's ``.html`` property,
    the ``{% typst %}`` template tag or the ``|typst`` filter.
    """

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return TypstText(value)

    def to_python(self, value):
        if value is None or isinstance(value, TypstText):
            return value
        return TypstText(value)

    def formfield(self, **kwargs):
        kwargs.setdefault("form_class", TypstFormField)
        # TextField.formfield() injects a plain Textarea; override it unless the
        # caller explicitly passed their own widget.
        kwargs.setdefault("widget", TypstTextarea)
        return super().formfield(**kwargs)
