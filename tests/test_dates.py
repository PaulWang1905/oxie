'''
Date and time handling: front matter normalisation, and the RFC 822 /
ISO 8601 / W3C output the feed, JSON-LD and sitemap depend on.
'''
import json
import os
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

# Make the repo root importable when running with unittest
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from oxie import Site, SiteConfig
from oxie.seo import iso8601_date, rfc822_date, w3c_date

INDEX_MD = """Title:   Home
Summary: Welcome.
Authors: Test Author
Date:    2026-08-22

Index content.
"""

POST_MD = """---
Title: {title}
Authors: Test Author
Date: {date}
Category: Notes
Tags: [alpha]
Summary: A summary.
---

Body text.
"""

# The three shapes YAML produces, which a real site holds all at once:
# old date-only posts, new dated-and-timed ones, and any with an offset.
DATE_ONLY = '2026-08-22'
NAIVE = '2026-08-22 09:30:00'
AWARE = '2026-08-22 09:30:00+01:00'


class TestToDatetime(unittest.TestCase):
    '''SiteConfig.to_datetime, the one place dates are normalised.'''

    def setUp(self):
        self.config = SiteConfig()

    def test_date_only_gets_the_default_time(self):
        '''Noon, so the calendar day survives conversion westwards.'''
        self.assertEqual(self.config.to_datetime(date(2026, 8, 22)),
                         datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc))

    def test_naive_datetime_is_read_in_the_site_timezone(self):
        self.config.timezone = 'Europe/London'
        moment = self.config.to_datetime(datetime(2026, 8, 22, 9, 30))
        self.assertEqual(moment.utcoffset(), timedelta(hours=1))  # BST
        self.assertEqual(moment.hour, 9)

    def test_aware_datetime_keeps_its_own_offset(self):
        written = datetime(2026, 8, 22, 9, 30,
                           tzinfo=timezone(timedelta(hours=1)))
        self.assertEqual(self.config.to_datetime(written), written)

    def test_strings_parse_in_both_shapes(self):
        '''index.md goes through the meta extension, which yields text.'''
        self.assertEqual(self.config.to_datetime('2026-08-22').hour, 12)
        timed = self.config.to_datetime('2026-08-22 09:30:00')
        self.assertEqual((timed.hour, timed.minute), (9, 30))
        self.assertEqual(self.config.to_datetime('2026-08-22T09:30:00+01:00'),
                         datetime(2026, 8, 22, 9, 30,
                                  tzinfo=timezone(timedelta(hours=1))))

    def test_none_passes_through(self):
        '''So an optional Last_modified needs no checking first.'''
        self.assertIsNone(self.config.to_datetime(None))

    def test_everything_comes_back_aware(self):
        for value in (date(2026, 8, 22), datetime(2026, 8, 22, 9, 30),
                      '2026-08-22', '2026-08-22 09:30:00'):
            self.assertIsNotNone(self.config.to_datetime(value).tzinfo, value)

    def test_default_post_time_is_configurable(self):
        self.config.default_post_time = time(8, 15)
        self.assertEqual(self.config.to_datetime(date(2026, 8, 22)).hour, 8)

    def test_unreadable_values_are_rejected(self):
        with self.assertRaises(ValueError):
            self.config.to_datetime('22/08/2026')
        with self.assertRaises(TypeError):
            self.config.to_datetime(20260822)

    def test_utc_default_needs_no_timezone_database(self):
        self.assertIs(self.config.tzinfo, timezone.utc)


class TestFormatters(unittest.TestCase):
    '''The three output formats, one canonical input type.'''

    def test_rfc822_converts_a_non_utc_offset(self):
        '''usegmt rejects anything but UTC; this used to raise ValueError.'''
        moment = datetime(2026, 8, 22, 9, 30,
                          tzinfo=timezone(timedelta(hours=1)))
        self.assertEqual(rfc822_date(moment), 'Sat, 22 Aug 2026 08:30:00 GMT')

    def test_rfc822_handles_a_bare_date(self):
        '''Kept usable on its own, outside the normalised pipeline.'''
        self.assertEqual(rfc822_date(date(2024, 3, 9)),
                         'Sat, 09 Mar 2024 00:00:00 GMT')

    def test_iso8601_keeps_the_offset(self):
        moment = datetime(2026, 8, 22, 9, 30,
                          tzinfo=timezone(timedelta(hours=1)))
        self.assertEqual(iso8601_date(moment), '2026-08-22T09:30:00+01:00')

    def test_w3c_uses_the_local_calendar_day(self):
        moment = datetime(2026, 8, 22, 9, 30,
                          tzinfo=timezone(timedelta(hours=1)))
        self.assertEqual(w3c_date(moment), '2026-08-22')

    def test_none_in_none_out(self):
        for fn in (rfc822_date, iso8601_date, w3c_date):
            self.assertIsNone(fn(None), fn.__name__)


class DateSiteTestCase(unittest.TestCase):
    '''A site whose posts use every date shape at once.'''

    posts = {'dated': DATE_ONLY, 'timed': NAIVE, 'offset': AWARE}
    timezone_name = 'UTC'

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        for sub in ['source/post', 'source/page', 'source/image',
                    'source/static', 'docs', 'src']:
            (self.test_dir / sub).mkdir(parents=True, exist_ok=True)

        (self.test_dir / 'src/meta_data.json').write_text(json.dumps({
            "title": "Test Site",
            "author": "Test Author",
            "description": "The full site description.",
            "link": "https://example.com",
            "image": "image/default.png",
            # One phrase: base.html picks at random, which would otherwise
            # make every page differ between builds
            "phrases": ["One fixed phrase."],
        }))
        (self.test_dir / 'source/index.md').write_text(INDEX_MD)
        for name, value in self.posts.items():
            (self.test_dir / f'source/post/{name}.md').write_text(
                POST_MD.format(title=name.title(), date=value))

        self.config = SiteConfig(
            source_dir=self.test_dir / 'source',
            template_dir=self.test_dir / 'src',
            output_dir=self.test_dir / 'docs',
            meta_data_file=self.test_dir / 'src/meta_data.json',
            timezone=self.timezone_name,
            css_build_command=None,
        )
        self.site = Site(self.config)
        self.site.build()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def read(self, name):
        return (self.test_dir / 'docs' / name).read_text()

    def items(self):
        channel = ET.fromstring(self.read('feed.xml')).find('channel')
        return channel.findall('item')


class TestMixedShapesBuild(DateSiteTestCase):
    def test_a_mixed_site_builds(self):
        '''Comparing a date with a datetime used to raise TypeError.'''
        for name in ('feed.xml', 'sitemap.xml', 'posts_metadata.jsonld',
                     'index.html', 'blog_index.html'):
            self.assertTrue((self.test_dir / 'docs' / name).exists(), name)

    def test_generated_xml_is_well_formed(self):
        for name in ('feed.xml', 'sitemap.xml'):
            ET.fromstring(self.read(name))

    def test_json_ld_parses(self):
        data = json.loads(self.read('posts_metadata.jsonld'))
        self.assertEqual(data['numberOfItems'], 3)

    def test_every_pubdate_round_trips(self):
        '''A weekday name disagreeing with the date breaks strict readers.'''
        for item in self.items():
            text = item.find('pubDate').text
            parsed = parsedate_to_datetime(text)
            self.assertEqual(text[:3], parsed.strftime('%a'), text)
            self.assertTrue(text.endswith('GMT'), text)

    def test_json_ld_dates_are_iso_8601(self):
        for entry in json.loads(self.read('posts_metadata.jsonld'))['itemListElement']:
            for key in ('datePublished', 'dateModified'):
                parsed = datetime.fromisoformat(entry[key])
                self.assertIsNotNone(parsed.tzinfo, entry[key])

    def test_the_offset_post_is_converted_to_gmt(self):
        '''09:30+01:00 is 08:30 GMT, and must not be printed as +01:00.'''
        published = {item.find('title').text: item.find('pubDate').text
                     for item in self.items()}
        self.assertEqual(published['Offset'], 'Sat, 22 Aug 2026 08:30:00 GMT')

    def test_the_date_only_post_lands_at_noon(self):
        published = {item.find('title').text: item.find('pubDate').text
                     for item in self.items()}
        self.assertEqual(published['Dated'], 'Sat, 22 Aug 2026 12:00:00 GMT')

    def test_sitemap_lastmod_stays_a_calendar_day(self):
        root = ET.fromstring(self.read('sitemap.xml'))
        ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        for el in root.findall('s:url/s:lastmod', ns):
            self.assertRegex(el.text, r'^\d{4}-\d{2}-\d{2}$')

    def test_time_elements_carry_a_valid_datetime_attribute(self):
        '''A bare interpolation would emit a space instead of a T.'''
        html = self.read('blog_index.html')
        self.assertIn('<time datetime="2026-08-22T12:00:00+00:00"', html)
        self.assertNotIn('<time datetime="2026-08-22 ', html)

    def test_rebuild_is_byte_identical(self):
        '''No clock reaches an output file.'''
        before = {name: self.read(name)
                  for name in ('feed.xml', 'sitemap.xml',
                               'posts_metadata.jsonld', 'blog_index.html')}
        Site(self.config).build()
        for name, content in before.items():
            self.assertEqual(content, self.read(name), name)


class TestSiteTimezone(DateSiteTestCase):
    '''The same content read in a timezone west of Greenwich.'''

    posts = {'dated': DATE_ONLY}
    timezone_name = 'America/New_York'

    def test_noon_local_keeps_the_intended_calendar_day(self):
        '''Midnight local would have been 04:00 GMT; midnight GMT the 21st.'''
        published = self.items()[0].find('pubDate').text
        self.assertEqual(published, 'Sat, 22 Aug 2026 16:00:00 GMT')

    def test_json_ld_carries_the_site_offset(self):
        entry = json.loads(self.read('posts_metadata.jsonld'))['itemListElement'][0]
        self.assertEqual(entry['datePublished'], '2026-08-22T12:00:00-04:00')


class TestOrdering(DateSiteTestCase):
    '''Same-day posts, deliberately named against chronological order.'''

    posts = {
        'alpha': '2026-08-22 08:00:00',     # first alphabetically, earliest
        'zulu': '2026-08-22 18:00:00',      # last alphabetically, latest
        'mike': '2026-08-22 13:00:00',
    }

    def test_same_day_posts_sort_chronologically(self):
        '''The old key dropped the time, leaving these in title order.'''
        self.assertEqual([post.title for post in self.site.posts],
                         ['Zulu', 'Mike', 'Alpha'])

    def test_the_feed_follows_the_same_order(self):
        self.assertEqual([item.find('title').text for item in self.items()],
                         ['Zulu', 'Mike', 'Alpha'])


class TestTiedOrdering(DateSiteTestCase):
    '''Identical timestamps still have to produce one stable order.'''

    posts = {'charlie': NAIVE, 'alpha': NAIVE, 'bravo': NAIVE}

    def test_ties_break_on_title(self):
        self.assertEqual([post.title for post in self.site.posts],
                         ['Alpha', 'Bravo', 'Charlie'])


class TestIndexPageDate(DateSiteTestCase):
    '''index.md is read as text, not YAML, so it takes the string path.'''

    def test_index_date_is_normalised(self):
        from oxie.site import IndexPage
        index = IndexPage(self.site, self.site.posts, self.site.pages)
        index.parse()
        self.assertEqual(index.date,
                         datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc))

    def test_a_missing_date_does_not_reach_for_the_clock(self):
        '''today's date in an output file would break reproducibility.'''
        from oxie.site import IndexPage
        (self.test_dir / 'source/index.md').write_text("Title: Home\n\nBody.\n")
        index = IndexPage(self.site, self.site.posts, self.site.pages)
        index.parse()
        self.assertIsNone(index.date)


if __name__ == '__main__':
    unittest.main()
