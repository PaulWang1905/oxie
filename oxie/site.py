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
from jinja2 import Environment, FileSystemLoader
from pygments.formatters import HtmlFormatter

from .config import SiteConfig
from .content import Post, Category
from .photos import parse_photos_md, generate_thumbnails
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
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"{meta_data['title']} - Blog Posts",
        "description": f"Collection of blog posts from {meta_data['title']}",
        "numberOfItems": len(posts),
        "itemListElement": [
            {
                "@type": "BlogPosting",
                "@id": post.full_link,
                "headline": post.title,
                "author": {
                    "@type": "Person",
                    "name": post.author
                },
                "datePublished": post.date.strftime('%Y-%m-%d'),
                "dateModified": post.last_modified.strftime('%Y-%m-%d') if post.last_modified else post.date.strftime('%Y-%m-%d'),
                "description": post.summary,
                "about": {
                    "@type": "DefinedTerm",
                    "name": post.category,
                    "inDefinedTermSet": {
                        "@type": "DefinedTermSet",
                        "name": "Blog Categories"
                    }
                },
                "keywords": post.tags,
                "url": post.full_link,
                "publisher": {
                    "@type": "Organization",
                    "name": meta_data["title"],
                    "url": meta_data["link"]
                },
                "mainEntityOfPage": {
                    "@type": "WebPage",
                    "@id": post.full_link
                }
            } for post in posts
        ]
    }


class BlogIndex:
    '''
    The blog index page; also renders a page for each category.
    '''

    def __init__(self, site, posts) -> None:
        self.site = site
        self.meta_data = site.meta_data
        self.posts = posts
        self.category_list = set([post.category for post in self.posts])
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
        self.description = None
        self.content = None

    def parse(self) -> None:
        '''
        Parse the index page, index.md in the source directory
        '''
        index_md = self.site.config.source_dir / "index.md"
        with open(index_md, 'r') as md_file:
            md_content = md_file.read()
            md = self.site.markdown()
            self.content = md.convert(md_content)
            # metadata from the md file (Markdown meta extension, lowercase keys)
            self.post_meta_data = md.Meta
            try:
                self.meta_data["title"] = self.post_meta_data.get("title", ["Untitled"])[0]
                self.meta_data["author"] = self.post_meta_data.get("authors", ["Anonymous"])[0]
                self.meta_data["date"] = datetime.strptime(
                    self.post_meta_data.get("date", [datetime.now().strftime('%Y-%m-%d')])[0],
                    '%Y-%m-%d'
                )
                self.meta_data["description"] = self.meta_data.get("description", ["No description available"])[0]
            except KeyError:
                print("Metadata not found in index.md")

    def render(self) -> None:
        '''
        Render the index page
        '''
        updates = self.site.get_recent_updates()

        rendered_html = self.site.template("index.html").render(
            title=self.meta_data["title"],
            author=self.meta_data["author"],
            date=self.meta_data["date"],
            description=self.meta_data["description"],
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

    def __init__(self, config: SiteConfig = None) -> None:
        self.config = config or SiteConfig()
        self.env = Environment(loader=FileSystemLoader(str(self.config.template_dir)))
        with open(self.config.meta_data_file) as f:
            self.meta_data = json.load(f)
        self.posts = []
        self.pages = []
        self.categories = []

    # ---- helpers -------------------------------------------------------

    def template(self, name: str):
        '''Load a template from the site's template directory.'''
        return self.env.get_template(name)

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
        Build the stylesheet with the configured command (e.g. Tailwind via npm)
        '''
        subprocess.run(list(self.config.css_build_command), check=True)

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
        Run the full build pipeline
        '''
        self.clean_old_files()
        self.generate_html()
        self.render_simple_pages()
        if self.config.photography:
            self.render_photography_page()
        self.collect_static_files()
        if self.config.thumbnails:
            self.generate_thumbnails()
        if self.config.css_build_command:
            self.build_css()
        if self.config.pygments_style:
            self.build_pygments_css()
