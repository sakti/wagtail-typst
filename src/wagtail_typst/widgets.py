"""Form widget used to edit Typst source in the Wagtail admin."""

from __future__ import annotations

from django import forms


class TypstTextarea(forms.Textarea):
    """A monospace textarea tuned for editing Typst markup.

    It disables spellcheck/autocorrect, requests a monospace font via the
    bundled stylesheet and tags the element with ``data-typst-input`` so custom
    JavaScript (e.g. a live preview) can hook into it.
    """

    template_name = "wagtail_typst/widgets/typst_textarea.html"

    def __init__(self, attrs=None):
        default_attrs = {
            "rows": 12,
            "class": "typst-input",
            "spellcheck": "false",
            "autocomplete": "off",
            "autocapitalize": "off",
            "data-typst-input": "true",
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    class Media:
        css = {"all": ["wagtail_typst/css/typst.css"]}
