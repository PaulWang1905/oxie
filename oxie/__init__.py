'''
oxie — a small static site/blog generator.

Converts Markdown content into a styled, SEO-friendly static website
using Jinja2 templates. A site is described by a SiteConfig (paths and
optional features) and built by a Site:

    from oxie import Site, SiteConfig

    Site(SiteConfig()).build()

To start a new site from scratch, use the command line instead:

    oxie init myblog --title "My Blog"
'''
from .config import SiteConfig
from .content import Post, Category
from .scaffold import init_site
from .site import Site, BlogIndex, IndexPage, generate_posts_jsonld
from .updates import Update, UpdateReader

__version__ = "0.3.1"

__all__ = [
    "Site", "SiteConfig", "Post", "Category", "BlogIndex", "IndexPage",
    "generate_posts_jsonld", "init_site", "Update", "UpdateReader",
    "__version__",
]
