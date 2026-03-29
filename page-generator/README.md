# Page Generator

Converts structured `trip-data.json` into deployable HTML pages.

## Components

- `scripts/tpf-generate.py` — Generate trip-data.json from input + Fliggy/Tavily data
- `scripts/tpf-cli.py` — Validate, Build, Deploy commands
- `scripts/wikimedia_image_search.py` — Wikimedia image search (fallback)
- `templates/trip-page-tailwind.html` — HTML skeleton (Tailwind CSS)
- `templates/trip-renderer.js` — Client-side JavaScript renderer
- `templates/themes/light.js` — Theme colors and CSS classes
- `schema/trip-schema.json` — JSON Schema for validation

## Usage

```bash
# Generate
python3 scripts/tpf-generate.py --from-json input.json --with-metro --pretty -o data/trip-data.json

# Validate
python3 scripts/tpf-cli.py validate

# Build
python3 scripts/tpf-cli.py build

# Deploy
python3 scripts/tpf-cli.py deploy --to gh-pages
```

See top-level [SKILL.md](../SKILL.md) for full documentation.
