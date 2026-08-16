'''
Content models for the oxie static site generator.

Post represents a single markdown document (a blog post or a static page)
and Category a per-category listing page. Both are created by a Site,
which supplies configuration, site metadata and templates.
'''
from pathlib import Path

import frontmatter


class Post:
    '''
    A blog post or page.
    Posts and pages are the same, but they live in different directories
    and appear in different areas of index.html.
    '''

    def __init__(self, md_path, html_path, site):
        self.site = site
        self.md_path = str(md_path)
        self.html_path = str(html_path)
        self.title = None
        self.content = None
        self.date = None
        self.author = None
        self.category = None
        self.tags = []
        self.read_time = None
        self.link = None
        self.summary = None
        self.full_link = None
        # Image is the cover image for the post, a path relative to the web
        # root. The default comes from the site's meta_data.json.
        self.image = site.meta_data["image"]
        self.post_meta_data = None

    def parse(self) -> None:
        '''
        Parse the markdown file and extract metadata and content
        '''
        with open(self.md_path, 'r') as md_file:
            md_content = md_file.read()
            post = frontmatter.loads(md_content)
            self.post_meta_data = post.metadata
            self.content = self.site.markdown().convert(post.content)

            # link relative to the web root, and the full link with domain
            self.link = '/' + Path(self.html_path).relative_to(
                self.site.config.output_dir).as_posix()
            self.full_link = self.site.meta_data["link"] + self.link

            try:
                self.title = self.post_meta_data["Title"]
                self.author = self.post_meta_data["Authors"]
                self.summary = self.post_meta_data["Summary"]
                self.category = self.post_meta_data["Category"]
                self.date = self.post_meta_data['Date']
                # Last_modified is optional and defaults to the post date
                self.last_modified = self.post_meta_data.get('Last_modified', self.date)
                print(f"Processing {self.md_path} with last modified date {self.last_modified}")
                self.tags = self.post_meta_data.get('Tags', [])
                # cover image from the metadata, falling back to the default
                self.image = self.post_meta_data.get("Image", self.image)
            except KeyError:
                print(f"Metadata not found in {self.md_path}")
                pass

    def render(self) -> None:
        '''
        Render the post to HTML
        '''
        rendered_html = self.site.template("template.html").render(
            meta_data=self.site.meta_data,
            post_meta_data=self.post_meta_data,
            title=self.title,
            author=self.author,
            summary=self.summary,
            category=self.category,
            date=self.date,
            last_modified=self.last_modified,
            content=self.content,
            phrases=self.site.meta_data["phrases"],
            image=self.image,
            tags=self.tags,
            link=self.link,
        )
        with open(self.html_path, "w") as html_file:
            html_file.write(rendered_html)


class Category:
    '''
    A category listing page, rendered once per category.
    Also carries the list of all tags used within the category.
    '''

    def __init__(self, site, posts, category) -> None:
        self.site = site
        self.meta_data = site.meta_data
        self.posts = posts
        self.category = category
        self.tags = [tag for post in self.posts for tag in post.tags]
        self.link = f"blog_{category}.html"
        self.count = len(self.posts)
        self.last_post = self.posts[0]

    def render(self) -> None:
        '''
        Render the category page
        '''
        rendered_html = self.site.template("category_template.html").render(
            title=self.meta_data["title"],
            phrases=self.meta_data["phrases"],
            posts=self.posts,
            category=self.category,
            tags=self.tags
        )
        output_path = self.site.config.output_dir / f"blog_{self.category}.html"
        with open(output_path, "w") as html_file:
            html_file.write(rendered_html)
