set dotenv-load := false

# Show available recipes
default:
    @just --list

# Create the venv and install the package with dev extras (editable)
install:
    uv sync --extra dev

# Alias for install
sync: install

# Run the test suite (pass extra args, e.g. `just test -k compiler`)
test *args:
    uv run pytest {{args}}

# Run tests in watch mode (requires pytest-watcher: `uvx ptw`)
watch:
    uvx pytest-watcher . --

# Lint with ruff (no install needed via uvx)
lint:
    uvx ruff check src tests

# Format with ruff
fmt:
    uvx ruff format src tests

# Verify formatting without writing changes (CI-friendly)
fmt-check:
    uvx ruff format --check src tests

# Lint + format-check + tests, the full pre-commit gate
check: lint fmt-check test

# Build the sdist and wheel into dist/
build:
    uv build

# List the data files bundled in the built wheel
wheel-contents: build
    @uv run python -c "import zipfile, glob; w = sorted(glob.glob('dist/*.whl'))[-1]; print(w); print('\n'.join(zipfile.ZipFile(w).namelist()))"

# Compile a Typst snippet to HTML from the CLI, e.g. `just compile '= Hi *there*'`
compile source:
    @uv run python -c "import django; from django.conf import settings; settings.configure(INSTALLED_APPS=['wagtail_typst'], CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}); django.setup(); from wagtail_typst import compile_typst; print(compile_typst('''{{source}}'''))"

# Remove build artifacts and caches
clean:
    rm -rf dist build *.egg-info src/*.egg-info
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
    rm -rf .pytest_cache .ruff_cache
