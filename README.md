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
| `WAGTAIL_TYPST_CLI_TIMEOUT` | `30` | Compilation timeout (seconds) for the `cli` backend. |
| `WAGTAIL_TYPST_FULL_DOCUMENT` | `False` | Return the whole `<html>` document instead of just the rendered `<body>`. |
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

MIT
