'''
The Site orchestrator for the oxie static site generator.

A Site binds a SiteConfig to loaded metadata and templates, and exposes
the build pipeline: clean, generate posts/pages/category/index pages,
render extra pages, collect static assets, thumbnails, CSS.
'''
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import markdown
from jinja2 import ChoiceLoader, Environment, FileSystemLoader
from pygments.formatters import HtmlFormatter

from .config import SiteConfig
from .content import Post, Category
from .photos import parse_photos_md, generate_thumbnails
from .seo import (
    SitemapEntry, absolute_url, jsonld_script, last_modified_of, posts_jsonld,
    render_robots_txt, render_rss_feed, render_sitemap, w3c_date,
)
from .updates import UpdateReader


def generate_posts_jsonld(posts, meta_data) -> dict:
    """
    Generate JSON-LD structured data for blog posts using Schema.org vocabulary

    Args:
        posts: List of Post objects
        meta_data: Dictionary containing site metadata

    Returns:
        dict: JSON-LD structured data
    """
    return posts_jsonld(posts, meta_data)


class BlogIndex:
    '''
    The blog index page; also renders a page for each category.
    '''

    def __init__(self, site, posts) -> None:
        self.site = site
        self.meta_data = site.meta_data
        self.posts = posts
        # Sorted, not a bare set: category order has to be stable or every
        # rebuild reorders blog_index.html and the sitemap for no reason.
        self.category_list = sorted(set([post.category for post in self.posts]))
        # Flatten and collect all valid tags from posts
        self.tags = set([
            tag
            for post in self.posts
            for tag in (post.tags if post.tags is not None else [])
        ])

    def render(self) -> None:
        '''
        Render the blog index page, and a page for each category
        '''
        for category_name in self.category_list:
            # Filter posts for current category
            category_posts = [post for post in self.posts if post.category == category_name]
            category = Category(self.site, category_posts, category_name)
            category.render()
            self.site.categories.append(category)

        # Render blog index page for all categories
        rendered_html = self.site.template("blog_template.html").render(
            meta_data=self.meta_data,
            canonical=self.site.url_for("blog_index.html"),
            title=self.meta_data["title"],
            phrases=self.meta_data["phrases"],
            categories=self.site.categories,
            posts=sorted(self.posts, key=lambda p: p.date, reverse=True),
        )
        with open(self.site.config.output_dir / "blog_index.html", "w") as html_file:
            html_file.write(rendered_html)


class IndexPage:
    '''
    The site index (home) page, built from source/index.md.
    '''

    def __init__(self, site, posts, pages) -> None:
        self.site = site
        self.meta_data = site.meta_data
        self.posts = posts
        # Excluded page titles (e.g. Terms of Service) are not listed on the index page
        self.pages = [page for page in pages
                      if page.title not in site.config.index_excluded_titles]
        self.title = None
        self.author = None
        self.date = None
        self.description = None
        self.content = None
        self.post_meta_data = {}

    def parse(self) -> None:
        '''
        Parse the index page, index.md in the source directory.

        The parsed values stay on this object instead of being written back
        into site.meta_data. The home page's own title is not the site title,
        and overwriting it there leaked into the JSON-LD publisher name and
        the feed channel.
        '''
        index_md = self.site.config.source_dir / "index.md"
        with open(index_md, 'r') as md_file:
            md_content = md_file.read()
            md = self.site.markdown()
            self.content = md.convert(md_content)
            # metadata from the md file (Markdown meta extension, lowercase keys)
            self.post_meta_data = md.Meta
            try:
                self.title = self.post_meta_data.get("title", ["Untitled"])[0]
                self.author = self.post_meta_data.get("authors", ["Anonymous"])[0]
                self.date = datetime.strptime(
                    self.post_meta_data.get("date", [datetime.now().strftime('%Y-%m-%d')])[0],
                    '%Y-%m-%d'
                )
                self.description = self._parse_description()
            except KeyError:
                print("Metadata not found in index.md")

    def _parse_description(self) -> str:
        '''
        The home page description: index.md's Summary, then its Description,
        then the site's meta_data.json description.

        The markdown meta extension yields list-valued fields, but the JSON
        metadata is a plain string. Indexing [0] into the latter is what used
        to truncate a description to its first character.
        '''
        for key in ("summary", "description"):
            value = self.post_meta_data.get(key)
            if value:
                return value[0]
        return self.meta_data.get("description", "No description available")

    def render(self) -> None:
        '''
        Render the index page
        '''
        updates = self.site.get_recent_updates()

        rendered_html = self.site.template("index.html").render(
            meta_data=self.meta_data,
            canonical=self.site.url_for("index.html"),
            jsonld=jsonld_script(posts_jsonld(self.posts, self.meta_data))
            if self.posts else None,
            title=self.title,
            author=self.author,
            date=self.date,
            description=self.description,
            phrases=self.meta_data["phrases"],
            content=self.content,
            posts=self.posts,
            pages=self.pages,
            updates=updates
        )
        with open(self.site.config.output_dir / "index.html", "w") as html_file:
            html_file.write(rendered_html)


class Site:
    '''
    One static site: configuration, metadata, templates, and the build
    pipeline that turns markdown in source_dir into HTML in output_dir.
    '''

    #: Templates shipped with the package. `oxie init` copies these into a
    #: new site; they also act as a fallback for anything a site omits.
    BUNDLED_TEMPLATE_DIR = Path(__file__).parent / "templates" / "default"

    def __init__(self, config: SiteConfig = None) -> None:
        self.config = config or SiteConfig()
        # The site's own templates always win; the bundled defaults fill any
        # gaps, so a site renders before every template has been customised.
        loaders = [FileSystemLoader(str(self.config.template_dir))]
        if self.config.use_bundled_templates:
            loaders.append(FileSystemLoader(str(self.BUNDLED_TEMPLATE_DIR)))
        self.env = Environment(loader=ChoiceLoader(loaders))
        with open(self.config.meta_data_file) as f:
            self.meta_data = json.load(f)
        self.posts = []
        self.pages = []
        self.categories = []
        # Available to every template without threading them through each
        # render call, since the head of the shared layout needs them.
        self.env.globals['site_url'] = self.meta_data.get('link', '')
        self.env.globals['feed_url'] = (
            self.url_for(self.config.feed_file) if self.config.feed else None)

    # ---- helpers -------------------------------------------------------

    def template(self, name: str):
        '''Load a template from the site's template directory.'''
        return self.env.get_template(name)

    def url_for(self, path) -> str:
        '''
        The absolute URL for a path relative to the web root.

        Post.link has a leading slash and Category.link does not, so this
        normalises both rather than concatenating onto the base URL.
        '''
        return absolute_url(self.meta_data.get('link', ''), path)

    def markdown(self) -> markdown.Markdown:
        '''A fresh Markdown converter with the site's extensions.'''
        return markdown.Markdown(
            extensions=self.config.markdown_extensions,
            extension_configs=self.config.markdown_extension_configs,
            tab_length=2,
        )

    def get_recent_updates(self, limit: int = 5) -> list:
        '''
        Recent updates from the site's Google Spreadsheet, or an empty
        list if no update_spreedsheet_id is configured in meta_data.
        '''
        spreadsheet_id = self.meta_data.get("update_spreedsheet_id")
        if not spreadsheet_id:
            return []
        updates = UpdateReader(spreadsheet_id=spreadsheet_id)
        updates.load_from_spreadsheet()
        return updates.get_recent_updates(limit)

    # ---- pipeline steps ------------------------------------------------

    def clean_old_files(self) -> None:
        '''
        Clean old generated files from the output directory
        '''
        print("Cleaning old files")
        docs_dir = self.config.output_dir
        # Remove all .html files in the output directory and subdirectories
        for html_file in docs_dir.rglob('*.html'):
            html_file.unlink()
        print("Old files cleaned")
        # Remove styles.css if it exists
        styles_css = docs_dir / "styles.css"
        if styles_css.exists():
            styles_css.unlink()
        print("styles.css removed")
        # Discovery files, so switching a feature off does not leave a stale
        # sitemap or feed behind in the output directory
        for name in (self.config.sitemap_file, self.config.feed_file,
                     self.config.robots_file):
            stale = docs_dir / name
            if stale.exists():
                stale.unlink()
                print(f"{name} removed")
        # Remove image directory if it exists
        images_dir = docs_dir / "image"
        if images_dir.exists():
            shutil.rmtree(images_dir)
            print("images directory removed")

    def generate_html(self) -> None:
        '''
        Generate HTML files from Markdown files in source/page and
        source/post (index.md is handled by IndexPage), then the JSON-LD
        posts metadata, the blog index and the site index.
        '''
        source_root = self.config.source_dir
        docs_root = self.config.output_dir
        directories = [source_root / "page", source_root / "post"]

        for dir_path in directories:
            print(f"Processing Folder: {dir_path}")
            for md_path in dir_path.rglob('*.md'):
                # Mirror the source tree into the output directory
                relative_md_path = md_path.relative_to(source_root)
                html_path = (docs_root / relative_md_path).with_suffix('.html')
                html_path.parent.mkdir(parents=True, exist_ok=True)
                post = Post(str(md_path), str(html_path), self)
                post.parse()
                if dir_path.name == "post":
                    self.posts.append(post)
                else:
                    self.pages.append(post)
                post.render()

        # sort the posts to show the latest post first
        self.posts.sort(key=lambda post: (
            -datetime.combine(post.date, datetime.min.time()).timestamp(),
            post.title
        ))

        # Output JSON-LD file with linked data schema for posts
        json_ld_data = generate_posts_jsonld(self.posts, self.meta_data)
        with open(docs_root / "posts_metadata.jsonld", "w") as json_file:
            json.dump(json_ld_data, json_file, indent=2, ensure_ascii=False)
        print(f"Posts metadata written to {docs_root / 'posts_metadata.jsonld'} ({len(self.posts)} posts)")

        BlogIndex(self, self.posts).render()
        index = IndexPage(self, self.posts, self.pages)
        index.parse()
        index.render()

    def render_simple_pages(self) -> None:
        '''
        Render the configured standalone template pages (e.g. reading notes)
        '''
        for template_name, output_name in self.config.simple_pages.items():
            print(f"Building {output_name}")
            rendered = self.template(template_name).render(
                meta_data=self.meta_data,
                phrases=self.meta_data["phrases"]
            )
            with open(self.config.output_dir / output_name, "w") as f:
                f.write(rendered)
            print(f"{output_name} built successfully")

    def render_photography_page(self) -> None:
        '''
        Render the photography page. Parses photos.md into structured
        album/photo data and passes it directly to the Jinja template.
        '''
        albums = parse_photos_md(str(self.config.photos_md), self.config.source_dir)
        all_photos = []
        for album in albums:
            for photo in album['photos']:
                filename = photo['src'].split('/')[-1]
                thumb_src = photo['src'].replace(filename, f'thumb/{filename}')
                all_photos.append({'album': album['name'], 'thumb': thumb_src, **photo})
        rendered_html = self.template("photography_template.html").render(
            meta_data=self.meta_data,
            phrases=self.meta_data["phrases"],
            albums=albums,
            all_photos=all_photos,
        )
        with open(self.config.output_dir / "photography.html", "w") as html_file:
            html_file.write(rendered_html)

    def render_error_page(self) -> None:
        '''
        Render the 404 page. GitHub Pages serves docs/404.html for any path
        it cannot resolve.
        '''
        template_name = self.config.error_page_template
        print(f"Building {template_name}")
        rendered_html = self.template(template_name).render(
            meta_data=self.meta_data,
            title=self.meta_data["title"],
            phrases=self.meta_data["phrases"],
        )
        with open(self.config.output_dir / template_name, "w") as html_file:
            html_file.write(rendered_html)

    def sitemap_entries(self) -> list:
        '''
        Every indexable page, in a stable order: the home and blog index
        pages, then posts newest first, then pages, categories and any
        configured standalone pages.

        Posts are already sorted by generate_html, but pages come from rglob,
        whose order is filesystem-dependent, so they are sorted here. The 404
        page is deliberately left out.
        '''
        newest = max((post.date for post in self.posts
                      if getattr(post, 'date', None)), default=None)
        entries = [
            SitemapEntry(self.url_for("index.html"), w3c_date(newest)),
            SitemapEntry(self.url_for("blog_index.html"), w3c_date(newest)),
        ]
        for post in self.posts:
            entries.append(SitemapEntry(self.url_for(post.link),
                                        w3c_date(last_modified_of(post))))
        for page in sorted(self.pages, key=lambda p: p.link):
            entries.append(SitemapEntry(self.url_for(page.link),
                                        w3c_date(last_modified_of(page))))
        for category in sorted(self.categories, key=lambda c: c.category):
            latest = max((post.date for post in category.posts
                          if getattr(post, 'date', None)), default=None)
            entries.append(SitemapEntry(self.url_for(category.link),
                                        w3c_date(latest)))
        if self.config.photography:
            entries.append(SitemapEntry(self.url_for("photography.html")))
        for output_name in sorted(self.config.simple_pages.values()):
            entries.append(SitemapEntry(self.url_for(output_name)))
        return entries

    def generate_sitemap(self) -> None:
        '''
        Write sitemap.xml listing every indexable page
        '''
        entries = self.sitemap_entries()
        path = self.config.output_dir / self.config.sitemap_file
        with open(path, "w") as f:
            f.write(render_sitemap(entries))
        print(f"Sitemap written to {path} ({len(entries)} urls)")

    def generate_feed(self) -> None:
        '''
        Write an RSS 2.0 feed of the most recent posts
        '''
        posts = self.posts[:self.config.feed_max_items]
        path = self.config.output_dir / self.config.feed_file
        with open(path, "w") as f:
            f.write(render_rss_feed(
                title=self.meta_data["title"],
                link=self.url_for("index.html"),
                description=self.meta_data.get("description", ""),
                feed_url=self.url_for(self.config.feed_file),
                posts=posts,
            ))
        print(f"Feed written to {path} ({len(posts)} items)")

    def generate_robots_txt(self) -> None:
        '''
        Write robots.txt, pointing at the sitemap when one is generated
        '''
        sitemap_url = (self.url_for(self.config.sitemap_file)
                       if self.config.sitemap else None)
        path = self.config.output_dir / self.config.robots_file
        with open(path, "w") as f:
            f.write(render_robots_txt(sitemap_url))
        print(f"robots.txt written to {path}")

    def collect_static_files(self, static_dirs: dict = None) -> None:
        """
        Collect static files from the configured directories without
        deleting the target directories.
        """
        if static_dirs is None:
            static_dirs = self.config.collect_dirs

        for source, target in static_dirs.items():
            source_dir = Path(source)
            target_dir = Path(target)
            print(f"Copying files from {source_dir} to {target_dir}")

            if not source_dir.exists():
                print(f"Source directory {source_dir} does not exist")
                continue

            target_dir.mkdir(parents=True, exist_ok=True)

            try:
                for item in source_dir.iterdir():
                    source_item = source_dir / item.name
                    target_item = target_dir / item.name

                    if source_item.is_dir():
                        shutil.copytree(source_item, target_item, dirs_exist_ok=True)
                    else:
                        shutil.copy2(source_item, target_item)
                print("Files copied successfully")
            except Exception as e:
                print(f"Error copying files: {e}")
                raise

    def generate_thumbnails(self) -> None:
        '''
        Generate gallery thumbnails for the configured photo directory
        '''
        generate_thumbnails(self.config.thumbnail_dir, self.config.thumbnail_width)

    def build_css(self) -> None:
        '''
        Build the stylesheet with the configured command (Tailwind via npm by
        default). Raises a readable error when the tool is not installed
        rather than a bare FileNotFoundError.
        '''
        command = list(self.config.css_build_command)
        try:
            subprocess.run(command, check=True)
        except FileNotFoundError:
            raise RuntimeError(
                f"Could not run {command[0]!r} for the CSS build "
                f"({' '.join(command)}).\n"
                "oxie styles sites with Tailwind CSS, which needs Node.js:\n"
                "  1. install Node.js  2. run `npm install` in this site\n"
                "Set css_build_command=None in your SiteConfig to skip this step."
            ) from None

    def build_pygments_css(self) -> None:
        '''
        Generate Pygments syntax highlighting CSS in the output directory
        '''
        style = self.config.pygments_style
        css = HtmlFormatter(style=style).get_style_defs('.highlight')
        with open(self.config.output_dir / 'pygments.css', 'w') as f:
            f.write(css)
        print(f"Pygments CSS generated with style '{style}'")

    # ---- full build ----------------------------------------------------

    def build(self) -> None:
        '''
        Run the full build pipeline.

        The discovery files are generated before the static files are
        collected, so a hand-written source/static/robots.txt still wins.
        The 404 page is rendered before the CSS step, like every other page,
        because Tailwind scans the emitted HTML for class names.
        '''
        self.clean_old_files()
        self.generate_html()
        self.render_simple_pages()
        if self.config.photography:
            self.render_photography_page()
        if self.config.error_page:
            self.render_error_page()
        if self.config.sitemap:
            self.generate_sitemap()
        if self.config.feed:
            self.generate_feed()
        if self.config.robots_txt:
            self.generate_robots_txt()
        self.collect_static_files()
        if self.config.thumbnails:
            self.generate_thumbnails()
        if self.config.css_build_command:
            self.build_css()
        if self.config.pygments_style:
            self.build_pygments_css()
