'''
Site scaffolding for oxie: create a complete, buildable site in one command.

`init_site()` writes the default templates, a Tailwind CSS v4 setup, sample
content and a `build.py`, so a new site goes from empty directory to built
HTML with `npm install && python build.py`.
'''
import json
import shutil
from datetime import date
from pathlib import Path
from typing import List

TEMPLATE_PACKAGE_DIR = Path(__file__).parent / "templates" / "default"

# Template files copied verbatim into the new site's template directory.
TEMPLATE_FILES = [
    "base.html",
    "index.html",
    "template.html",
    "blog_template.html",
    "category_template.html",
]

DEFAULT_PHRASES = [
    "Well begun is half done.",
    "Write drunk, edit sober.",
    "A journey of a thousand miles begins with a single step.",
]

BUILD_PY = '''\
"""Build script for {title}.

Run with:  python build.py
Requires:  pip install -r requirements.txt  &&  npm install
"""
from oxie import Site, SiteConfig

config = SiteConfig(
    # source/, src/ and docs/ are the defaults; override them if you move things.
    collect_dirs={{
        # Everything in source/image is copied to docs/image ...
        "source/image": "docs/image",
        # ... and source/static lands at the site root, next to index.html.
        "source/static": "docs",
    }},
    # Syntax highlighting stylesheet written to docs/pygments.css.
    pygments_style="github-dark",
    # Compiles src/styles.css into docs/styles.css with Tailwind.
    # Set to None if you want to manage CSS yourself.
    css_build_command=("npm", "run", "build:css"),
)

if __name__ == "__main__":
    Site(config).build()
'''

PACKAGE_JSON = {
    "name": "site",
    "private": True,
    "scripts": {
        "build:css": "tailwindcss -i src/styles.css -o docs/styles.css --minify",
        "watch:css": "tailwindcss -i src/styles.css -o docs/styles.css --watch",
    },
    "devDependencies": {
        "@tailwindcss/cli": "^4.3.3",
        "@tailwindcss/typography": "^0.5.20",
    },
}

REQUIREMENTS_TXT = "oxie==0.3.0\n"

GITIGNORE = """\
__pycache__/
*.pyc
.venv/
node_modules/
"""

INDEX_MD = '''\
Title:   {title}
Summary: {description}
Authors: {author}
Date:    {today}

## Hello

This is your home page. It is written in `source/index.md`.

Unlike posts, this file uses simple `Key: value` lines at the top instead of
`---` fenced frontmatter — that is the one format asymmetry in oxie.

Edit it, run `python build.py`, and open `docs/index.html`.
'''

POST_MD = '''\
---
Title: Hello World
Summary: The first post on {title} — how posts work in oxie.
Authors: {author}
Date: {today}
Category: Blog
Tags: [oxie, writing]
---

# Hello World

Every file in `source/post/` becomes a post. The frontmatter above uses
**capitalised keys** (`Title`, `Authors`, `Date`, `Category`, `Tags`), which
oxie reads to build the blog index and per-category pages.

## Things that work out of the box

- Tables, footnotes[^1] and `~~strikethrough~~`
- Fenced code with syntax highlighting:

```python
from oxie import Site, SiteConfig

Site(SiteConfig()).build()
```

- Maths, via `pymdownx.arithmatex`
- Category pages: this post is in *Blog*, so it appears on `blog_Blog.html`

[^1]: Footnotes look like this.

## Next steps

Delete this file, write your own, and rebuild.
'''

ABOUT_MD = '''\
---
Title: About
Summary: About {title}.
Authors: {author}
Date: {today}
Category: Page
Tags: [about]
---

# About

Files in `source/page/` are pages rather than posts: they are listed on the
home page but stay out of the blog index.

Tell your readers who you are here.
'''


def _write(path: Path, content: str, force: bool, created: List[str], skipped: List[str]) -> None:
    '''Write content to path unless it exists and force is False.'''
    if path.exists() and not force:
        skipped.append(str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    created.append(str(path))


def init_site(
    target: str = ".",
    title: str = "My Site",
    author: str = "",
    link: str = "https://example.com",
    description: str = "A site built with oxie.",
    force: bool = False,
) -> dict:
    '''
    Create a new oxie site in `target`.

    Existing files are left alone unless `force` is True, so running this in
    a directory that already has content is safe.

    Returns a dict with 'created' and 'skipped' file lists.
    '''
    root = Path(target)
    created: List[str] = []
    skipped: List[str] = []
    today = date.today().isoformat()
    fields = {
        "title": title,
        "author": author or "Anonymous",
        "today": today,
        "description": description,
    }

    # Content directories, including the ones the build copies verbatim
    for sub in ("source/post", "source/page", "source/image", "source/static", "docs"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    # Jinja templates
    for name in TEMPLATE_FILES:
        destination = root / "src" / name
        if destination.exists() and not force:
            skipped.append(str(destination))
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(TEMPLATE_PACKAGE_DIR / name, destination)
        created.append(str(destination))

    # Tailwind v4 entry point
    _write(root / "src" / "styles.css",
           (TEMPLATE_PACKAGE_DIR / "styles.css").read_text(), force, created, skipped)

    # Site metadata
    meta_data = {
        "title": title,
        "description": description,
        "author": author or "Anonymous",
        "date": today,
        "link": link.rstrip("/"),
        "image": "image/default.png",
        "phrases": DEFAULT_PHRASES,
    }
    _write(root / "src" / "meta_data.json",
           json.dumps(meta_data, indent=4, ensure_ascii=False) + "\n",
           force, created, skipped)

    # Content
    _write(root / "source" / "index.md", INDEX_MD.format(**fields), force, created, skipped)
    _write(root / "source" / "post" / "hello-world.md", POST_MD.format(**fields), force, created, skipped)
    _write(root / "source" / "page" / "about.md", ABOUT_MD.format(**fields), force, created, skipped)

    # Build script and project files
    _write(root / "build.py", BUILD_PY.format(title=title), force, created, skipped)
    package_json = dict(PACKAGE_JSON)
    package_json["name"] = "".join(
        c if c.isalnum() or c in "-_" else "-" for c in title.lower()
    ).strip("-") or "site"
    _write(root / "package.json", json.dumps(package_json, indent=2) + "\n", force, created, skipped)
    _write(root / "requirements.txt", REQUIREMENTS_TXT, force, created, skipped)
    _write(root / ".gitignore", GITIGNORE, force, created, skipped)

    return {"created": created, "skipped": skipped, "root": str(root)}
