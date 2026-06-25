"""Typst fields and blocks for Wagtail.

This package converts `Typst <https://typst.app>`_ markup into HTML so it can be
authored and rendered inside Wagtail content (model fields, StreamField blocks
and templates).

The public API is intentionally small::

    from wagtail_typst import compile_typst, TypstCompileError
    from wagtail_typst.fields import TypstField
    from wagtail_typst.blocks import TypstBlock

Note that submodules import Django/Wagtail, so only ``__version__`` is exposed at
the top level to keep importing the package side-effect free before Django is
configured.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]


def __getattr__(name: str):
    # Lazily expose the most common helpers without importing Django at
    # package-import time (e.g. during build/metadata inspection).
    if name in {"compile_typst", "TypstCompileError"}:
        from . import compiler

        return getattr(compiler, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
