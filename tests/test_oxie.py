import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Make the repo root importable when running with unittest
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from oxie import Site, SiteConfig, Post, Category, BlogIndex, IndexPage


POST_MD = """---
Title: Test Post
Authors: Test Author
Date: 2024-01-01
Category: test
Tags: [test, unit-test]
Summary: This is a test post
Last_modified: 2024-01-02
Image: test-image.jpg
---

# Test Header

This is a test post content.
"""

INDEX_MD = """Title:   Test Post
Summary: A test index page
Authors: Test Author
Date:    2024-01-01
Category: Index
Tags: Index

## About

Index content here.
"""


class TestOxie(unittest.TestCase):
    def setUp(self):
        """Build a complete miniature site in a temp directory."""
        self.test_dir = Path(tempfile.mkdtemp())

        for sub in ['source/post', 'source/page', 'source/image',
                    'source/static', 'docs', 'src']:
            (self.test_dir / sub).mkdir(parents=True, exist_ok=True)

        meta_data = {
            "title": "Test Site",
            "author": "Test Author",
            "description": "Test Description",
            "link": "https://example.com",
            "image": "default-image.jpg",
            "phrases": ["Test Phrase 1", "Test Phrase 2"]
        }
        (self.test_dir / 'src/meta_data.json').write_text(json.dumps(meta_data))

        (self.test_dir / 'src/template.html').write_text(
            "<html><head><title>{{ title }}</title></head><body>{{ content }}</body></html>")
        (self.test_dir / 'src/index.html').write_text(
            "<html><head><title>{{ title }}</title></head><body>{{ content }}</body></html>")
        (self.test_dir / 'src/category_template.html').write_text(
            "<html><head><title>{{ category }}</title></head><body>Category: {{ category }}</body></html>")
        (self.test_dir / 'src/blog_template.html').write_text(
            "<html><head><title>Blog</title></head><body>Blog content</body></html>")
        (self.test_dir / 'src/extra_template.html').write_text(
            "<html><body>Extra page for {{ meta_data.title }}</body></html>")

        (self.test_dir / 'source/post/test-post.md').write_text(POST_MD)
        (self.test_dir / 'source/page/test-page.md').write_text(POST_MD)
        (self.test_dir / 'source/index.md').write_text(INDEX_MD)
        (self.test_dir / 'source/image/test-image.jpg').write_text("test image content")

        self.config = SiteConfig(
            source_dir=self.test_dir / 'source',
            template_dir=self.test_dir / 'src',
            output_dir=self.test_dir / 'docs',
            meta_data_file=self.test_dir / 'src/meta_data.json',
            css_build_command=None,
        )
        self.site = Site(self.config)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def make_post(self, md='source/post/test-post.md', html='docs/test-post.html'):
        post = Post(str(self.test_dir / md), str(self.test_dir / html), self.site)
        post.parse()
        return post

    def test_config_defaults_derived(self):
        """collect_dirs, photos_md and thumbnail_dir derive from the layout."""
        self.assertEqual(self.config.collect_dirs, {
            str(self.test_dir / 'source/image'): str(self.test_dir / 'docs/image'),
            str(self.test_dir / 'source/static'): str(self.test_dir / 'docs/page'),
        })
        self.assertEqual(self.config.photos_md,
                         self.test_dir / 'source/photo/photos.md')
        self.assertEqual(self.config.thumbnail_dir,
                         self.test_dir / 'docs/image/photo')

    def test_post_init(self):
        post = Post('a.md', 'b.html', self.site)
        self.assertEqual(post.md_path, 'a.md')
        self.assertEqual(post.html_path, 'b.html')
        self.assertEqual(post.image, self.site.meta_data["image"])

    def test_post_parse(self):
        post = self.make_post()
        self.assertEqual(post.title, 'Test Post')
        self.assertEqual(post.author, 'Test Author')
        self.assertEqual(post.summary, 'This is a test post')
        self.assertEqual(post.category, 'test')
        self.assertEqual(post.date.strftime('%Y-%m-%d'), '2024-01-01')
        self.assertEqual(post.last_modified.strftime('%Y-%m-%d'), '2024-01-02')
        self.assertEqual(post.image, 'test-image.jpg')
        self.assertEqual(post.tags, ['test', 'unit-test'])
        self.assertEqual(post.link, '/test-post.html')
        self.assertEqual(post.full_link, 'https://example.com/test-post.html')

    def test_post_render(self):
        post = self.make_post()
        post.render()
        html = (self.test_dir / 'docs/test-post.html').read_text()
        self.assertIn('<title>Test Post</title>', html)

    def test_category(self):
        post = self.make_post()
        category = Category(self.site, [post], 'test')
        self.assertEqual(category.category, 'test')
        self.assertEqual(category.tags, ['test', 'unit-test'])
        self.assertEqual(category.link, 'blog_test.html')
        self.assertEqual(category.count, 1)
        self.assertEqual(category.last_post, post)

        category.render()
        html = (self.test_dir / 'docs/blog_test.html').read_text()
        self.assertIn('<title>test</title>', html)

    def test_blog_index(self):
        post = self.make_post()
        blog_index = BlogIndex(self.site, [post])
        self.assertEqual(blog_index.category_list, {'test'})
        self.assertEqual(blog_index.tags, {'test', 'unit-test'})

        blog_index.render()
        self.assertTrue((self.test_dir / 'docs/blog_index.html').exists())
        self.assertTrue((self.test_dir / 'docs/blog_test.html').exists())
        self.assertEqual(len(self.site.categories), 1)

    def test_index_page(self):
        post = self.make_post()
        page = self.make_post('source/page/test-page.md', 'docs/test-page.html')

        index = IndexPage(self.site, [post], [page])
        index.parse()
        self.assertEqual(self.site.meta_data['title'], 'Test Post')

        index.render()
        html = (self.test_dir / 'docs/index.html').read_text()
        self.assertIn('<title>Test Post</title>', html)

    def test_index_excludes_configured_titles(self):
        page = self.make_post('source/page/test-page.md', 'docs/test-page.html')
        page.title = 'Privacy Policy'
        index = IndexPage(self.site, [], [page])
        self.assertEqual(index.pages, [])

    def test_recent_updates_empty_without_spreadsheet(self):
        self.assertEqual(self.site.get_recent_updates(), [])

    def test_clean_old_files(self):
        docs = self.test_dir / 'docs'
        (docs / 'subdir').mkdir()
        (docs / 'test.html').write_text('Test HTML')
        (docs / 'subdir/deep.html').write_text('Deep HTML')
        (docs / 'styles.css').write_text('Test CSS')
        (docs / 'image').mkdir()
        (docs / 'image/test.jpg').write_text('Test Image')

        self.site.clean_old_files()

        self.assertFalse((docs / 'test.html').exists())
        self.assertFalse((docs / 'subdir/deep.html').exists())
        self.assertFalse((docs / 'styles.css').exists())
        self.assertFalse((docs / 'image').exists())

    def test_collect_static_files(self):
        self.site.collect_static_files()
        copied = self.test_dir / 'docs/image/test-image.jpg'
        self.assertTrue(copied.exists())
        self.assertEqual(copied.read_text(), 'test image content')

    def test_generate_html(self):
        self.site.generate_html()
        docs = self.test_dir / 'docs'
        for name in ['post/test-post.html', 'page/test-page.html',
                     'blog_test.html', 'blog_index.html', 'index.html',
                     'posts_metadata.jsonld']:
            self.assertTrue((docs / name).exists(), f"missing {name}")
        self.assertEqual(len(self.site.posts), 1)
        self.assertEqual(len(self.site.pages), 1)
        self.assertEqual(len(self.site.categories), 1)

    def test_jsonld_content(self):
        self.site.generate_html()
        data = json.loads((self.test_dir / 'docs/posts_metadata.jsonld').read_text())
        self.assertEqual(data['numberOfItems'], 1)
        entry = data['itemListElement'][0]
        self.assertEqual(entry['headline'], 'Test Post')
        self.assertEqual(entry['datePublished'], '2024-01-01')
        self.assertEqual(entry['dateModified'], '2024-01-02')

    def test_simple_pages(self):
        self.site.config.simple_pages = {'extra_template.html': 'extra.html'}
        self.site.render_simple_pages()
        html = (self.test_dir / 'docs/extra.html').read_text()
        self.assertIn('Extra page for Test Site', html)

    def test_build_css_runs_configured_command(self):
        self.site.config.css_build_command = ('npm', 'run', 'build:css')
        with patch('oxie.site.subprocess.run') as mock_run:
            self.site.build_css()
        mock_run.assert_called_once_with(['npm', 'run', 'build:css'], check=True)

    def test_full_build_pipeline(self):
        """build() with optional features disabled runs offline end to end."""
        self.site.build()
        docs = self.test_dir / 'docs'
        self.assertTrue((docs / 'index.html').exists())
        self.assertTrue((docs / 'blog_index.html').exists())
        self.assertTrue((docs / 'image/test-image.jpg').exists())
        # disabled features produced no output
        self.assertFalse((docs / 'photography.html').exists())
        self.assertFalse((docs / 'pygments.css').exists())


if __name__ == '__main__':
    unittest.main()
