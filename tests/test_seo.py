import json
import os
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

# Make the repo root importable when running with unittest
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from oxie import Site, SiteConfig
from oxie.seo import absolute_url, rfc822_date, render_robots_txt, w3c_date

RSS_CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
RSS_DC_NS = "http://purl.org/dc/elements/1.1/"

INDEX_MD = """Title:   Home
Summary: Welcome to my website.
Authors: Test Author
Date:    2024-01-01

## About

Index content here.
"""

POST_MD = """---
Title: {title}
Authors: Test Author
Date: {date}
Category: {category}
Tags: [alpha, beta]
Summary: {summary}
Image: cover.png
---

# Heading

Body text.
"""

PAGE_MD = """---
Title: About
Authors: Test Author
Date: 2024-01-05
Category: Page
Tags: [about]
Summary: About the site.
---

About body.
"""


class SeoTestCase(unittest.TestCase):
    '''A miniature site with three posts across two categories.'''

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        for sub in ['source/post', 'source/page', 'source/image',
                    'source/static', 'docs', 'src']:
            (self.test_dir / sub).mkdir(parents=True, exist_ok=True)

        meta_data = {
            "title": "Test Site",
            "author": "Test Author",
            "description": "The full site description.",
            "link": "https://example.com",
            "image": "image/default.png",
            # One phrase only: base.html picks a random one, which would
            # otherwise make every page differ between builds.
            "phrases": ["One fixed phrase."],
        }
        (self.test_dir / 'src/meta_data.json').write_text(json.dumps(meta_data))

        (self.test_dir / 'source/index.md').write_text(INDEX_MD)
        (self.test_dir / 'source/page/about.md').write_text(PAGE_MD)
        (self.test_dir / 'source/post/first.md').write_text(POST_MD.format(
            title="First Post", date="2024-01-01", category="Notes",
            summary="The first summary."))
        (self.test_dir / 'source/post/second.md').write_text(POST_MD.format(
            title="Second Post", date="2024-03-01", category="Essays",
            summary="The second summary."))
        # Ampersands and angle brackets must survive into XML and JSON-LD
        (self.test_dir / 'source/post/third.md').write_text(POST_MD.format(
            title="Tools & Tips <2024>", date="2024-02-01", category="Notes",
            summary="Sarah & co. on <em>tooling</em>."))

        self.config = SiteConfig(
            source_dir=self.test_dir / 'source',
            template_dir=self.test_dir / 'src',
            output_dir=self.test_dir / 'docs',
            meta_data_file=self.test_dir / 'src/meta_data.json',
            css_build_command=None,
        )
        # No templates in src/, so the bundled defaults are exercised
        Site(self.config).build()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def read(self, name):
        return (self.test_dir / 'docs' / name).read_text()


class TestHelpers(unittest.TestCase):
    def test_absolute_url_normalises_both_sides(self):
        '''Post.link has a leading slash, Category.link does not.'''
        self.assertEqual(absolute_url('https://example.com', '/post/a.html'),
                         'https://example.com/post/a.html')
        self.assertEqual(absolute_url('https://example.com/', 'blog_x.html'),
                         'https://example.com/blog_x.html')

    def test_dates_are_locale_independent(self):
        from datetime import date
        self.assertEqual(w3c_date(date(2024, 3, 9)), '2024-03-09')
        self.assertEqual(rfc822_date(date(2024, 3, 9)),
                         'Sat, 09 Mar 2024 00:00:00 GMT')

    def test_robots_omits_sitemap_line_when_disabled(self):
        self.assertNotIn('Sitemap:', render_robots_txt(None))
        self.assertIn('Sitemap: https://example.com/sitemap.xml',
                      render_robots_txt('https://example.com/sitemap.xml'))


class TestSitemap(SeoTestCase):
    def test_lists_every_indexable_page(self):
        root = ET.fromstring(self.read('sitemap.xml'))
        ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        locs = [el.text for el in root.findall('s:url/s:loc', ns)]

        self.assertIn('https://example.com/index.html', locs)
        self.assertIn('https://example.com/blog_index.html', locs)
        self.assertIn('https://example.com/post/first.html', locs)
        self.assertIn('https://example.com/page/about.html', locs)
        # Category links carry no leading slash internally
        self.assertIn('https://example.com/blog_Notes.html', locs)
        self.assertIn('https://example.com/blog_Essays.html', locs)

    def test_urls_are_absolute_and_well_formed(self):
        root = ET.fromstring(self.read('sitemap.xml'))
        ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        for el in root.findall('s:url/s:loc', ns):
            self.assertTrue(el.text.startswith('https://example.com/'), el.text)
            self.assertNotIn('//', el.text[len('https://'):], el.text)

    def test_excludes_the_404_page(self):
        self.assertNotIn('404.html', self.read('sitemap.xml'))

    def test_lastmod_uses_content_dates(self):
        self.assertIn('<lastmod>2024-03-01</lastmod>', self.read('sitemap.xml'))


class TestFeed(SeoTestCase):
    def channel(self):
        return ET.fromstring(self.read('feed.xml')).find('channel')

    def test_channel_uses_site_metadata_not_the_index_page(self):
        '''index.md must not overwrite the site title or description.'''
        channel = self.channel()
        self.assertEqual(channel.find('title').text, 'Test Site')
        self.assertEqual(channel.find('description').text,
                         'The full site description.')

    def test_items_are_newest_first(self):
        titles = [item.find('title').text for item in self.channel().findall('item')]
        self.assertEqual(titles,
                         ['Second Post', 'Tools & Tips <2024>', 'First Post'])

    def test_item_fields(self):
        item = self.channel().findall('item')[0]
        self.assertEqual(item.find('link').text,
                         'https://example.com/post/second.html')
        self.assertEqual(item.find('guid').text,
                         'https://example.com/post/second.html')
        self.assertEqual(item.find('pubDate').text,
                         'Fri, 01 Mar 2024 00:00:00 GMT')
        self.assertEqual(item.find('category').text, 'Essays')
        self.assertEqual(item.find('{%s}creator' % RSS_DC_NS).text, 'Test Author')
        self.assertIn('<h1', item.find('{%s}encoded' % RSS_CONTENT_NS).text)

    def test_special_characters_round_trip(self):
        '''An unescaped & or < would make the feed unparseable.'''
        item = self.channel().findall('item')[1]
        self.assertEqual(item.find('title').text, 'Tools & Tips <2024>')
        self.assertEqual(item.find('description').text,
                         'Sarah & co. on <em>tooling</em>.')

    def test_respects_feed_max_items(self):
        self.config.feed_max_items = 2
        Site(self.config).build()
        self.assertEqual(len(self.channel().findall('item')), 2)


class TestRobots(SeoTestCase):
    def test_points_at_the_sitemap(self):
        robots = self.read('robots.txt')
        self.assertIn('User-agent: *', robots)
        self.assertIn('Sitemap: https://example.com/sitemap.xml', robots)


class TestPageMarkup(SeoTestCase):
    def test_post_has_canonical_and_social_tags(self):
        html = self.read('post/first.html')
        self.assertIn('<link rel="canonical" href="https://example.com/post/first.html">', html)
        self.assertIn('<meta property="og:url" content="https://example.com/post/first.html">', html)
        self.assertIn('<meta property="og:image" content="https://example.com/cover.png">', html)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', html)

    def test_pages_advertise_the_feed(self):
        self.assertIn('type="application/rss+xml" title="Test Site" '
                      'href="https://example.com/feed.xml"',
                      self.read('index.html'))

    def test_post_embeds_parseable_jsonld(self):
        html = self.read('post/first.html')
        start = html.index('<script type="application/ld+json">')
        body = html[start + len('<script type="application/ld+json">'):]
        data = json.loads(body[:body.index('</script>')])

        self.assertEqual(data['@type'], 'BlogPosting')
        self.assertEqual(data['headline'], 'First Post')
        # publisher is the site, not the home page's own title
        self.assertEqual(data['publisher']['name'], 'Test Site')

    def test_jsonld_cannot_break_out_of_its_script_tag(self):
        '''< is escaped, so a title containing </script> stays inert.'''
        html = self.read('post/third.html')
        script = html[html.index('<script type="application/ld+json">'):]
        script = script[:script.index('</script>')]
        self.assertNotIn('<2024>', script)
        self.assertIn('\\u003c2024>', script)

    def test_error_page_is_rendered_and_noindex(self):
        html = self.read('404.html')
        self.assertIn('<meta name="robots" content="noindex">', html)
        self.assertIn('404', html)

    def test_home_page_description_is_not_truncated(self):
        '''The old code indexed [0] into the string and rendered just "W".'''
        self.assertIn('<meta name="description" content="Welcome to my website.">',
                      self.read('index.html'))

    def test_categories_render_in_sorted_order(self):
        html = self.read('blog_index.html')
        self.assertLess(html.index('blog_Essays.html'), html.index('blog_Notes.html'))


class TestDeterminism(SeoTestCase):
    def test_rebuild_is_byte_identical(self):
        '''No build timestamps: an unchanged site must rebuild identically.'''
        before = {name: self.read(name)
                  for name in ('sitemap.xml', 'feed.xml', 'robots.txt',
                               'blog_index.html', 'index.html')}
        Site(self.config).build()
        for name, content in before.items():
            self.assertEqual(content, self.read(name), name)


class TestFeatureSwitches(SeoTestCase):
    def test_disabling_removes_stale_files(self):
        for name in ('sitemap.xml', 'feed.xml', 'robots.txt'):
            self.assertTrue((self.test_dir / 'docs' / name).exists())

        self.config.sitemap = False
        self.config.feed = False
        self.config.robots_txt = False
        self.config.error_page = False
        Site(self.config).build()

        for name in ('sitemap.xml', 'feed.xml', 'robots.txt', '404.html'):
            self.assertFalse((self.test_dir / 'docs' / name).exists(), name)

    def test_static_robots_txt_wins_over_the_generated_one(self):
        (self.test_dir / 'source/static/robots.txt').write_text("User-agent: *\nDisallow: /\n")
        self.config.collect_dirs = {
            str(self.test_dir / 'source/static'): str(self.test_dir / 'docs'),
        }
        Site(self.config).build()
        self.assertEqual(self.read('robots.txt'), "User-agent: *\nDisallow: /\n")


if __name__ == '__main__':
    unittest.main()
