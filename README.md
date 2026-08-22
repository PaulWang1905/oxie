# oxie

**oxie** is a small static site/blog generator written in Python. It converts
Markdown into a styled, SEO-friendly static website using Jinja2 templates and
**Tailwind CSS v4**.

One package, many sites: each site supplies its own content, templates and
`SiteConfig`, and oxie does the rest. `oxie init` gives you all three,
pre-wired and building.

## Requirements

- Python 3.10+ (3.8 nominally supported but untested)
- Node.js and npm — Tailwind CSS is a required part of the build

## Quick start

```bash
pip install oxie

oxie init myblog --title "My Blog" --author "Your Name"
cd myblog
npm install       # Tailwind CSS v4
python build.py   # writes docs/
```

Open `docs/index.html`, and you have a working blog: home page, a sample post,
an about page, a blog index and a category page, with compiled Tailwind
styling and syntax highlighting.

`oxie init` never overwrites an existing file unless you pass `--force`, so it
is safe to run in a directory that already has content.

## What init creates

```
source/            # content — edit this
  index.md         # home page
  post/*.md        # blog posts
  page/*.md        # standalone pages
  image/           # images, copied to docs/image
  static/          # raw files, copied to the site root
src/               # Jinja2 templates + meta_data.json + styles.css
  base.html        # shared layout the others extend
  index.html  template.html  blog_template.html  category_template.html
  404.html         # served by GitHub Pages for unknown paths
docs/              # generated output (GitHub Pages friendly)
build.py           # your site's config
package.json       # Tailwind v4 via @tailwindcss/cli
```

`build.py` is the whole per-site program:

```python
from oxie import Site, SiteConfig

config = SiteConfig(
    collect_dirs={"source/image": "docs/image", "source/static": "docs"},
    pygments_style="github-dark",
    css_build_command=("npm", "run", "build:css"),
)

if __name__ == "__main__":
    Site(config).build()
```

## Styling

Tailwind v4 is configured **CSS-first** — there is no `tailwind.config.js` and
no `postcss.config.js`. Everything lives in `src/styles.css`:

```css
@import "tailwindcss";
@plugin "@tailwindcss/typography";

@source "../src/**/*.html";
@source "../docs/**/*.html";
@source "../source/**/*.md";
```

Because the Jinja templates in `src/` are scanned as well as the generated
HTML in `docs/`, classes are never purged just because CSS was built before
HTML. Rendered Markdown is wrapped in the typography plugin's `prose` classes,
and the bundled templates support light and dark via `dark:` variants.

The templates copied into `src/` are yours — edit them freely. If you delete
one, oxie falls back to its bundled copy, so a site always renders; set
`use_bundled_templates=False` to make a missing template an error instead.

## What a build does

`Site.build()` runs, in order:

1. `clean_old_files()` — removes generated HTML, the stylesheet and the image
   directory from the output folder.
2. `generate_html()` — Markdown → HTML for every post and page, then
   `posts_metadata.jsonld` (Schema.org `BlogPosting` data), the per-category
   pages, the blog index, and the home page.
3. `render_simple_pages()` — any extra one-off template pages.
4. `render_photography_page()` — optional; parses a `photos.md` album file.
5. `render_error_page()` — optional; `404.html`.
6. `generate_sitemap()` — optional; `sitemap.xml`.
7. `generate_feed()` — optional; RSS 2.0 at `feed.xml`.
8. `generate_robots_txt()` — optional; `robots.txt` pointing at the sitemap.
9. `collect_static_files()` — copies images and static files to the output.
10. `generate_thumbnails()` — optional; gallery thumbnails via Pillow.
11. `build_css()` — optional; runs your CSS command (e.g. `npm run build:css`).
12. `build_pygments_css()` — optional; syntax-highlighting stylesheet.

**Ordering notes:** HTML is generated *before* CSS, so Tailwind sees the
finished HTML — including `404.html`, whose classes would otherwise be purged.
The discovery files are written *before* static files are collected, so a
hand-written `source/static/robots.txt` overrides the generated one.

## Configuration

Every path and feature lives on `SiteConfig`:

| Field | Default | Purpose |
|---|---|---|
| `source_dir` | `source` | Markdown content root |
| `template_dir` | `src` | Jinja2 templates |
| `output_dir` | `docs` | Generated site |
| `meta_data_file` | `src/meta_data.json` | Site metadata (title, link, image, phrases…) |
| `use_bundled_templates` | `True` | Fall back to oxie's templates for anything the site omits |
| `markdown_extensions` / `..._configs` | pymdownx set | Markdown pipeline |
| `collect_dirs` | `source/image`→`docs/image`, `source/static`→`docs/page` | Static asset copying |
| `index_excluded_titles` | Terms of Service, Privacy Policy | Pages hidden from the index listing |
| `simple_pages` | `{}` | template name → output name, rendered once |
| `photography` / `photos_md` | `False` | Photo album page |
| `thumbnails` / `thumbnail_dir` / `thumbnail_width` | `False` / … / `600` | Gallery thumbnails |
| `sitemap` / `sitemap_file` | `True` / `sitemap.xml` | XML sitemap of every indexable page |
| `robots_txt` / `robots_file` | `True` / `robots.txt` | Permissive robots.txt pointing at the sitemap |
| `feed` / `feed_file` / `feed_max_items` | `True` / `feed.xml` / `20` | RSS 2.0 feed of recent posts |
| `error_page` / `error_page_template` | `True` / `404.html` | Not-found page |
| `css_build_command` | `("npm", "run", "build:css")` | Set to `None` to skip |
| `pygments_style` | `None` | e.g. `"github-dark"` |

All four discovery outputs build their URLs from `meta_data["link"]`, so that
must be the site's real base URL. Set any switch to `False` to skip it — the
matching file is then removed from the output directory rather than left
stale.

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
you list in `simple_pages` and `photography_template.html` if enabled. `oxie
init` writes the first four (and a shared `base.html` they extend); the
generator falls back to its bundled copies for any you remove.

Context passed to each template differs, and the comment at the top of each
bundled template lists exactly what it gets. Every page receives `canonical`
(its absolute URL) and, where there is structured data to embed, `jsonld`.
`site_url` and `feed_url` are Jinja globals, available in every template
without being passed. Post and page renders additionally get `full_link` and
`image_url` for social preview tags.

### Recent updates from a Google Sheet (optional)

If `meta_data.json` contains `update_spreedsheet_id`, oxie reads that public
spreadsheet's CSV export (columns `Date` and `Content`) and passes the five
most recent entries to the index template as `updates`. Omit the key and the
list is simply empty — no network access is attempted.

This feature requires the optional Sheets dependencies:

```bash
pip install 'oxie[sheets]'
```

## Development

```bash
uv venv && uv pip install -e '.[sheets]' --python .venv/bin/python
.venv/bin/python -m unittest discover -s tests -v
```

The test suite runs fully offline.

## SEO and syndication

Out of the box a built site carries a `sitemap.xml`, a `robots.txt`, an RSS 2.0
feed, a `404.html`, canonical link tags, Open Graph and Twitter card metadata,
and inline Schema.org JSON-LD (`BlogPosting` per post, `ItemList` on the home
page). `posts_metadata.jsonld` is still written for anything that consumed it.

Generated files are **deterministic**: no build timestamps are used anywhere,
so rebuilding unchanged content produces byte-identical output instead of a
spurious diff. Note that the bundled `base.html` picks a random footer phrase,
which does change per build — pin `phrases` to a single entry if you need
fully reproducible HTML.

## Status

Version 0.4.0, extracted from the generator behind
[puyuwang.org](https://puyuwang.org).

Three behaviours carried over from that codebase were fixed in 0.4.0 and will
change your output on upgrade: category order on the blog index is now sorted
rather than set-iteration order; `IndexPage` no longer overwrites
`meta_data["title"]`; and the home page description is no longer truncated to
its first character. The metadata key `update_spreedsheet_id` keeps its
original spelling, since renaming it would break existing sites.

## Licence

Apache License 2.0 — see the
[LICENSE](https://github.com/PaulWang1905/oxie/blob/main/LICENSE).
