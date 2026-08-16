# oxie

**oxie** is a small static site/blog generator written in Python. It converts
Markdown into a styled, SEO-friendly static website using Jinja2 templates,
and leaves styling to whatever CSS toolchain you prefer (the author's sites
use Tailwind + DaisyUI).

One package, many sites: each site supplies its own content, templates and
`SiteConfig`, and oxie does the rest.

## Install

```bash
pip install git+https://github.com/PaulWang1905/oxie.git@v0.1.0
```

## Quick start

A site is a folder of Markdown plus a folder of templates. The default layout:

```
source/            # content
  index.md         # home page
  post/*.md        # blog posts
  page/*.md        # standalone pages
  image/           # images, copied to the output
  static/          # raw files, copied to the output
src/               # Jinja2 templates + meta_data.json
docs/              # generated output (GitHub Pages friendly)
build.py           # your site's config, below
```

`build.py` is the whole per-site program:

```python
from oxie import Site, SiteConfig

config = SiteConfig(
    simple_pages={"readings_note_template.html": "readings_note.html"},
    photography=True,
    thumbnails=True,
    pygments_style="github-dark",
)

if __name__ == "__main__":
    Site(config).build()
```

Then `python build.py`.

## What a build does

`Site.build()` runs, in order:

1. `clean_old_files()` — removes generated HTML, the stylesheet and the image
   directory from the output folder.
2. `generate_html()` — Markdown → HTML for every post and page, then
   `posts_metadata.jsonld` (Schema.org `BlogPosting` data), the per-category
   pages, the blog index, and the home page.
3. `render_simple_pages()` — any extra one-off template pages.
4. `render_photography_page()` — optional; parses a `photos.md` album file.
5. `collect_static_files()` — copies images and static files to the output.
6. `generate_thumbnails()` — optional; gallery thumbnails via Pillow.
7. `build_css()` — optional; runs your CSS command (e.g. `npm run build:css`).
8. `build_pygments_css()` — optional; syntax-highlighting stylesheet.

**Ordering note:** HTML is generated *before* CSS, so utility-class scanners
like Tailwind's `content` globs see the finished HTML.

## Configuration

Every path and feature lives on `SiteConfig`:

| Field | Default | Purpose |
|---|---|---|
| `source_dir` | `source` | Markdown content root |
| `template_dir` | `src` | Jinja2 templates |
| `output_dir` | `docs` | Generated site |
| `meta_data_file` | `src/meta_data.json` | Site metadata (title, link, image, phrases…) |
| `markdown_extensions` / `..._configs` | pymdownx set | Markdown pipeline |
| `collect_dirs` | `source/image`→`docs/image`, `source/static`→`docs/page` | Static asset copying |
| `index_excluded_titles` | Terms of Service, Privacy Policy | Pages hidden from the index listing |
| `simple_pages` | `{}` | template name → output name, rendered once |
| `photography` / `photos_md` | `False` | Photo album page |
| `thumbnails` / `thumbnail_dir` / `thumbnail_width` | `False` / … / `600` | Gallery thumbnails |
| `css_build_command` | `("npm", "run", "build:css")` | Set to `None` to skip |
| `pygments_style` | `None` | e.g. `"github-dark"` |

## Content format

Posts and pages use YAML frontmatter with capitalised keys:

```markdown
---
Title:   Silver Age
Summary: A short story about a deduplication officer.
Authors: Puyu Wang
Date:    2026-07-17
Category: Story
Tags: [Story]
Last_modified: 2026-07-18   # optional, defaults to Date
Image: image/cover.jpg      # optional, defaults to meta_data["image"]
---

Your markdown here.
```

`index.md` uses the Markdown `meta` extension style instead (`Key: value`
lines at the top of the file, no `---` fences).

Templates the generator expects in `template_dir`: `template.html` (posts and
pages), `index.html`, `blog_template.html`, `category_template.html`, plus any
you list in `simple_pages` and `photography_template.html` if enabled.

### Recent updates from a Google Sheet (optional)

If `meta_data.json` contains `update_spreedsheet_id`, oxie reads that public
spreadsheet's CSV export (columns `Date` and `Content`) and passes the five
most recent entries to the index template as `updates`. Omit the key and the
list is simply empty — no network access is attempted.

## Development

```bash
uv venv && uv pip install -e . --python .venv/bin/python
.venv/bin/python -m unittest discover -s tests -v
```

The test suite runs fully offline.

## Status and known issues

Version 0.1.0, extracted from the generator behind
[puyuwang.org](https://puyuwang.org). Two behaviours are carried over from
that codebase and preserved deliberately:

- Category order on the blog index comes from iterating a Python `set`, so the
  file's contents can differ between runs. Set `PYTHONHASHSEED=0` when
  comparing builds.
- `IndexPage.parse()` overwrites `meta_data["title"]` with the title from
  `index.md`, and indexes into the description string, which yields its first
  character rather than the whole description.

`pandas` is a dependency only because of the Google Sheets reader; it will
likely become an optional extra.

## Licence

ISC — see [LICENSE](LICENSE).
