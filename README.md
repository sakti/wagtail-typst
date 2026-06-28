# Wagtail Typst

Author [Typst](https://typst.app) markup in Wagtail and render it as HTML.

`wagtail-typst` gives you a model **field**, a StreamField **block**, and
template **tags/filters** that compile Typst source into HTML using Typst's
(experimental) HTML export — no LaTeX, no headless browser.

> ⚠️ Typst's HTML export is officially experimental. The generated markup may
> change between Typst releases.

## Installation

```bash
pip install wagtail-typst
```

This pulls in the [`typst`](https://pypi.org/project/typst/) Python package, so
the Typst compiler is bundled — no external binary is required.

Add the app to your Django settings:

```python
INSTALLED_APPS = [
    # ...
    "wagtail_typst",
]
```

## Usage

### Model field

Store Typst source on a model and render its compiled HTML in a template:

```python
from wagtail.models import Page
from wagtail.admin.panels import FieldPanel
from wagtail_typst.fields import TypstField


class ArticlePage(Page):
    body = TypstField(blank=True)

    content_panels = Page.content_panels + [FieldPanel("body")]
```

```django
{# template #}
{{ page.body.html }}
```

The raw Typst source is stored in the database; the compiled HTML is produced
on demand via the `.html` property (and cached).

### StreamField block

```python
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail_typst.blocks import TypstBlock


class ArticlePage(Page):
    body = StreamField(
        [
            ("typst", TypstBlock()),
            # ... your other blocks
        ],
        use_json_field=True,
    )
```

The block renders inside a wrapper element:

```html
<div class="typst-content"> ... compiled HTML ... </div>
```

### Matching Typst's default font

Typst's HTML export emits only semantic markup, so by default the browser
renders it in its own default font instead of the **Libertinus Serif** font
Typst uses for PDF output. To make the HTML match, load the bundled stylesheet
in your base template's `<head>`:

```django
{% load wagtail_typst_tags %}
{% wagtail_typst_css %}
```

This ships Libertinus Serif for body text and DejaVu Sans Mono for `code`/raw
blocks (Typst's defaults, as WOFF2) and applies them to the `.typst-content`
wrapper. It needs `django.contrib.staticfiles`; run `collectstatic` for
production. If you set a custom `WAGTAIL_TYPST_WRAPPER_CLASS`, add matching
`font-family` rules yourself.

### Template tag & filter

```django
{% load wagtail_typst_tags %}

{# Compile a string variable #}
{{ some_typst_source|typst }}

{# Compile a literal block #}
{% typst %}
= Hello
Some *bold* and _italic_ text with a $sqrt(x^2 + y^2)$ formula.
{% endtypst %}
```

## Configuration

All settings are optional and namespaced with `WAGTAIL_TYPST_`:

| Setting | Default | Description |
| --- | --- | --- |
| `WAGTAIL_TYPST_BACKEND` | `"binding"` | `"binding"` (bundled `typst` package) or `"cli"` (shell out to a `typst` executable). |
| `WAGTAIL_TYPST_CLI_PATH` | `"typst"` | Path/name of the executable for the `cli` backend. |
| `WAGTAIL_TYPST_TIMEOUT` | `30` | Compilation timeout (seconds). Bounds the `cli` subprocess; for the `binding` backend it runs compilation in a separate process that is terminated on expiry. `None` disables it (binding then runs in-process — trusted input only). |
| `WAGTAIL_TYPST_SANITIZE` | `True` | Sanitize compiled HTML (strip `<script>`, event handlers, dangerous URLs) before marking it safe, keeping formatting and MathML. Turn off only if every author of Typst source is fully trusted. Applies to embedded output only. |
| `WAGTAIL_TYPST_ROOT` | `None` | Directory that Typst `read()` / `image()` / `include` are confined to. `None` uses an isolated empty directory so untrusted markup cannot read project files. Point it at an asset directory to allow embedding those files. |
| `WAGTAIL_TYPST_FULL_DOCUMENT` | `False` | Return the whole `<html>` document instead of just the rendered `<body>`. **Not sanitized** — trusted input only. |
| `WAGTAIL_TYPST_WRAPPER_CLASS` | `"typst-content"` | CSS class on the block wrapper element. |
| `WAGTAIL_TYPST_CACHE` | `True` | Cache compiled HTML keyed on the source hash. |
| `WAGTAIL_TYPST_CACHE_ALIAS` | `"default"` | Django cache alias used when caching is enabled. |
| `WAGTAIL_TYPST_CACHE_TIMEOUT` | `None` | Cache timeout in seconds (`None` = forever). |

## How it works

The Python API entry point is `compile_typst`:

```python
from wagtail_typst import compile_typst

html = compile_typst("= Title\n\nHello *world*")
```

It compiles the source to a full HTML document, extracts the rendered `<body>`
(plus any `<head>` `<style>` blocks), marks it safe, and caches the result.
A `TypstCompileError` is raised when the source fails to compile (the original
diagnostics are available on the exception's `.diagnostics` attribute).

## Development

```bash
uv sync --extra dev
uv run pytest
```

## License

MIT, except for the bundled fonts in
`wagtail_typst/static/wagtail_typst/fonts/`:

- **Libertinus Serif** (body text) — SIL Open Font License 1.1, see
  `fonts/OFL.txt`. Copyright © 2012–2024 The Libertinus Project Authors.
- **DejaVu Sans Mono** (`code`/raw) — Bitstream Vera / Arev license, see
  `fonts/LICENSE-DejaVu.txt`. Copyright © 2003 Bitstream, Inc. and © 2006
  Tavmjong Bah.
