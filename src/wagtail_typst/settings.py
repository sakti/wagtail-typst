"""Resolve ``wagtail-typst`` configuration from Django settings.

All settings are namespaced with the ``WAGTAIL_TYPST_`` prefix and have sane
defaults, so the package works with zero configuration.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

_PREFIX = "WAGTAIL_TYPST_"

DEFAULTS: dict[str, Any] = {
    # Compilation backend: "binding" (uses the bundled ``typst`` Python package)
    # or "cli" (shells out to a ``typst`` executable).
    "BACKEND": "binding",
    # Path/name of the typst executable, used only by the "cli" backend.
    "CLI_PATH": "typst",
    # Return the whole ``<html>`` document instead of just the rendered body.
    "FULL_DOCUMENT": False,
    # CSS class applied to the wrapper element by the block/filter helpers.
    "WRAPPER_CLASS": "typst-content",
    # Cache compiled HTML keyed on the source hash.
    "CACHE": True,
    # Django cache alias to use when caching is enabled.
    "CACHE_ALIAS": "default",
    # Cache timeout in seconds. ``None`` means "cache forever".
    "CACHE_TIMEOUT": None,
    # Compilation timeout in seconds for the "cli" backend.
    "CLI_TIMEOUT": 30,
}


def get_setting(name: str) -> Any:
    """Return the configured value for ``name`` (without the prefix).

    Falls back to :data:`DEFAULTS` when the project has not overridden it.
    """
    try:
        default = DEFAULTS[name]
    except KeyError as exc:  # pragma: no cover - programming error
        raise KeyError(f"Unknown wagtail-typst setting: {name!r}") from exc
    return getattr(settings, _PREFIX + name, default)
