'''
oxie — a small static site/blog generator.

Converts Markdown content into a styled, SEO-friendly static website
using Jinja2 templates. A site is described by a SiteConfig (paths and
optional features) and built by a Site:

    from oxie import Site, SiteConfig

    Site(SiteConfig()).build()
'''
from .config import SiteConfig
from .content import Post, Category
from .site import Site, BlogIndex, IndexPage, generate_posts_jsonld
from .updates import Update, UpdateReader

__version__ = "0.1.0"

__all__ = [
    "Site", "SiteConfig", "Post", "Category", "BlogIndex", "IndexPage",
    "generate_posts_jsonld", "Update", "UpdateReader", "__version__",
]
