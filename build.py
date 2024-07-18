import subprocess
import os
import markdown
from jinja2 import Template
from datetime import datetime
from markupsafe import Markup, escape
# Function to build CSS using Tailwind CSS

# Read the template only once
# The template locatio: oxie/src/template.html

# Metadata for the index page, this is a dictionary.
# It is hard coded here for now, because this generator is for a single blog only,
# but it can be read from a file or a database.
meta_data = {
    "title": "Puyu Blog",
    "content": "Welcome to my website.",
    "author": "Puyu",
    "date": "2024-07-17",
    "link": ""
}


template = Template(open("src/template.html").read())
index_template = Template(open("src/index.html").read())
posts = []
pages = []


def build_css():
    subprocess.run(["npm", "run", "build:css"], check=True)


class POST:
    '''
    Class to represent a blog post or page.
    post and page are the same, but there will be in different directories and different areas in index.html. 
    '''
    def __init__(self, md_path, html_path):
        self.md_path = md_path
        self.html_path = html_path
        self.title = None
        self.content = None
        self.date = None
        self.author = None
        self.tags = None
        self.read_time = None
        self.link = None

    def parse(self) -> None:
        '''
        Parse the markdown file and extract metadata and content
        '''
        with open(self.md_path, 'r') as md_file:
            # use markupsafe to escape html content 
            md_content = Markup(escape(md_file.read()))
            html_content = markdown.markdown(md_content,extensions=['pymdownx.tilde'])
            self.content = html_content
            self.title = md_content.split("\n")[0].strip()[2:]
            # get the link for page and post domain name + html path
            self.link = meta_data["link"] + self.html_path[4:]
            self.author = meta_data["author"]
            # get modification date and time of the md file in MM-DD-YYYY HH:MM:SS format
            # self.date = time.ctime(os.path.getmtime(self.md_path))
            self.date = self.get_modification_date()
            # no need to parse metadata for now. 
            # for line in md_content.split("\n"):
            #    if line.startswith("title:"):
            #        self.title = line.split("title:")[1].strip()
            #    elif line.startswith("date:"):
            #        self.date = line.split("date:")[1].strip()
            #    elif line.startswith("author:"):
            #        self.author = line.split("author:")[1].strip()
            #    elif line.startswith("tags:"):
            #        self.tags = line.split("tags:")[1].strip()
            #    elif line.startswith("read_time:"):
            #        self.read_time = line.split("read_time:")[1].strip()
    def get_modification_date(self):
        mod_time = os.path.getmtime(self.md_path)
        mod_date = datetime.fromtimestamp(mod_time).strftime('%m-%d-%Y %H:%M')
        return mod_date
    
    def render(self) -> None:
        ''' Render the post to HTML
        '''
        rendered_html = template.render(
            title=self.title,
            author=self.author,
            date=self.date,
            content=self.content
        )
        with open(self.html_path, "w") as html_file:
            html_file.write(rendered_html)
    

class INDEX:
    '''
    Class to represent the index page
    '''
    def __init__(self, meta_data, posts, pages) -> None:
        '''
        Initialize the index page, read meta data (dictionary) and HTML directory (list of string)
        '''
        self.meta_data = meta_data
        self.posts = posts
        self.pages = pages

    def render(self) -> None:
        '''
        Render the index page
        '''
        rendered_html = index_template.render(
            title=self.meta_data["title"],
            author=self.meta_data["author"],
            date=self.meta_data["date"],
            content=self.meta_data["content"],
            posts=self.posts,
            pages=self.pages
        )
        with open("docs/index.html", "w") as html_file:
            html_file.write(rendered_html)

# Function to convert Markdown files to HTML
def generate_html() -> None:
    '''
    Generate HTML files from Markdown files,
    only for files in source/page and source/post, does not include index.md
    to the docs directory
    '''
    directories = ["source/page", "source/post"]

    for directory in directories:
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith(".md"):
                    md_path = os.path.join(root, file)
                    html_path = os.path.join("docs", os.path.relpath(md_path, "source")).replace(".md", ".html")
                    os.makedirs(os.path.dirname(html_path), exist_ok=True)
                    post = POST(md_path, html_path)   
                    post.parse()
                    #posts.append([post.title, post.link])
                    if directory == "source/post":
                        posts.append(post)
                    else:
                        pages.append(post)
                    post.render()
    # reverse the order of posts to show the latest post first
    posts.reverse() 
    index = INDEX(meta_data, posts, pages)
    index.render()
                

def clean_old_files() -> None:
    '''
    Clean old HTML files
    '''
    for root, dirs, files in os.walk("docs"):
        for file in files:
            if file.endswith(".html"):
                os.remove(os.path.join(root, file))
    try:
        os.remove("docs/styles.css")
    except FileNotFoundError:
        pass
    


if __name__ == "__main__":
    clean_old_files()
    generate_html()
    build_css()
