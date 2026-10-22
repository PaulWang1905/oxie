'''
Recent updates read from a YAML file in the site repo (0.5.0), and the
file -> Google Sheet -> none order that keeps existing sites unchanged.
'''
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

# Make the repo root importable when running with unittest
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from oxie import Site, SiteConfig, UpdateReader, load_updates_file

INDEX_MD = """Title:   Home
Summary: Welcome.
Authors: Test Author
Date:    2026-08-22

Index content.
"""

POST_MD = """---
Title: A Post
Authors: Test Author
Date: 2026-08-22
Category: Notes
Tags: [alpha]
Summary: A summary.
---

Body text.
"""

THREE_OUT_OF_ORDER = """\
- date: 2025-05-20
  content: middle
- date: 2026-05-01
  content: newest
- date: 2024-01-15
  content: oldest
"""


def entries(count: int) -> str:
    '''count well-formed entries, one per day of January 2026.'''
    return ''.join(f"- date: 2026-01-{day:02d}\n  content: update {day}\n"
                   for day in range(1, count + 1))


class UpdatesTestCase(unittest.TestCase):
    '''A miniature site with no templates of its own, so the bundled
    index.html renders the updates.'''

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        for sub in ('source/post', 'source/page', 'src', 'docs'):
            (self.test_dir / sub).mkdir(parents=True)
        self.meta_data = {
            "title": "Test Site",
            "author": "Test Author",
            "description": "Test Description",
            "link": "https://example.com",
            "image": "image/default.png",
            "phrases": ["Only phrase"],
        }
        self.write_meta_data()
        (self.test_dir / 'source/index.md').write_text(INDEX_MD)
        (self.test_dir / 'source/post/a-post.md').write_text(POST_MD)
        self.updates_path = self.test_dir / 'source/updates.yaml'

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def write_meta_data(self):
        (self.test_dir / 'src/meta_data.json').write_text(
            json.dumps(self.meta_data))

    def make_site(self, **overrides) -> Site:
        config = SiteConfig(
            source_dir=self.test_dir / 'source',
            template_dir=self.test_dir / 'src',
            output_dir=self.test_dir / 'docs',
            meta_data_file=self.test_dir / 'src/meta_data.json',
            css_build_command=None,
            **overrides,
        )
        return Site(config)

    def write_updates(self, text: str) -> Path:
        self.updates_path.write_text(text, encoding='utf-8')
        return self.updates_path


class TestUpdatesFile(UpdatesTestCase):

    def test_default_path_is_derived_from_source_dir(self):
        site = self.make_site()
        self.assertEqual(site.config.updates_file, self.updates_path)
        self.assertEqual(site.config.updates_limit, 5)

    def test_newest_first(self):
        self.write_updates(THREE_OUT_OF_ORDER)
        updates = self.make_site().get_recent_updates()
        self.assertEqual([u.content for u in updates],
                         ['newest', 'middle', 'oldest'])

    def test_same_day_keeps_file_order(self):
        self.write_updates("- date: 2026-01-01\n  content: first\n"
                           "- date: 2026-01-01\n  content: second\n")
        updates = self.make_site().get_recent_updates()
        self.assertEqual([u.content for u in updates], ['first', 'second'])

    def test_limit(self):
        self.write_updates(entries(7))
        updates = self.make_site().get_recent_updates()
        self.assertEqual(len(updates), 5)
        self.assertEqual(updates[0].content, 'update 7')
        self.assertEqual(len(self.make_site(updates_limit=2).get_recent_updates()), 2)

    def test_noon_in_site_timezone(self):
        '''A date-only entry is placed like a date-only post: noon, local.'''
        self.write_updates("- date: 2025-07-01\n  content: summer\n")
        update, = self.make_site(timezone='Europe/London').get_recent_updates()
        self.assertEqual(update.date.isoformat(), '2025-07-01T12:00:00+01:00')
        self.assertEqual(update.date.strftime('%b %d, %Y'), 'Jul 01, 2025')

    def test_dates_with_time_and_offset(self):
        self.write_updates(
            "- date: 2026-03-01 09:30:00\n  content: naive\n"
            "- date: 2026-03-01T08:00:00+01:00\n  content: aware\n"
            "- date: '2026-03-02'\n  content: quoted\n")
        updates = load_updates_file(self.updates_path, self.make_site().config)
        self.assertEqual([u.content for u in updates], ['quoted', 'naive', 'aware'])
        self.assertTrue(all(u.date.tzinfo for u in updates))
        self.assertEqual(updates[0].date,
                         datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc))

    def test_capitalised_keys(self):
        '''The sheet's column names, and the front matter style, also work.'''
        self.write_updates("- Date: 2026-05-01\n  Content: capitalised\n")
        update, = self.make_site().get_recent_updates()
        self.assertEqual(update.content, 'capitalised')
        self.assertEqual(update.date.date().isoformat(), '2026-05-01')

    def test_other_keys_are_ignored(self):
        self.write_updates("- date: 2026-05-01\n  content: x\n  link: /y\n")
        self.assertEqual(len(self.make_site().get_recent_updates()), 1)

    def test_colon_in_folded_block(self):
        self.write_updates(
            "- date: 2025-05-20\n"
            "  content: >-\n"
            "    A talk at the coffee morning.\n"
            "    Time: 10:30 AM. Venue: Weston Library.\n")
        update, = self.make_site().get_recent_updates()
        self.assertEqual(update.content, 'A talk at the coffee morning. '
                                         'Time: 10:30 AM. Venue: Weston Library.')

    def test_literal_block_keeps_line_breaks_and_strips_whitespace(self):
        self.write_updates(
            "- date: 2025-05-20\n"
            "  content: |\n"
            "    line one\n"
            "    line two\n\n")
        update, = self.make_site().get_recent_updates()
        self.assertEqual(update.content, 'line one\nline two')

    def test_empty_file(self):
        self.write_updates('')
        self.assertEqual(self.make_site().get_recent_updates(), [])
        self.write_updates('# just a comment\n')
        self.assertEqual(self.make_site().get_recent_updates(), [])

    def test_custom_path_relative_to_working_directory(self):
        (self.test_dir / 'data').mkdir()
        (self.test_dir / 'data/news.yml').write_text(
            "- date: 2026-05-01\n  content: from news.yml\n")
        cwd = os.getcwd()
        os.chdir(self.test_dir)
        try:
            site = self.make_site(updates_file='data/news.yml')
            self.assertIsInstance(site.config.updates_file, Path)
            updates = site.get_recent_updates()
        finally:
            os.chdir(cwd)
        self.assertEqual([u.content for u in updates], ['from news.yml'])

    def test_html_passes_through_to_index_page(self):
        '''No autoescape: links in content keep working, as with the sheet.'''
        self.write_updates(
            "- date: 2026-05-01\n"
            "  content: >-\n"
            "    Read <a href=\"https://example.org/x?a=1&b=2\">the notes</a>.\n")
        self.make_site().build()
        html = (self.test_dir / 'docs/index.html').read_text()
        self.assertIn('Recent updates', html)
        self.assertIn('Read <a href="https://example.org/x?a=1&b=2">the notes</a>.',
                      html)
        self.assertIn('<time datetime="2026-05-01T12:00:00+00:00"', html)
        self.assertIn('01 May 2026', html)


class TestUpdateSources(UpdatesTestCase):
    '''File first, then the sheet, then nothing.'''

    def test_file_wins_over_spreadsheet(self):
        self.meta_data['update_spreedsheet_id'] = 'sheet-id'
        self.write_meta_data()
        self.write_updates(THREE_OUT_OF_ORDER)
        with patch.object(UpdateReader, 'load_from_spreadsheet') as load:
            updates = self.make_site().get_recent_updates()
        load.assert_not_called()
        self.assertEqual(len(updates), 3)

    def test_spreadsheet_still_used_without_file(self):
        '''Backward compatibility: a site with no file reads its sheet.'''
        self.meta_data['update_spreedsheet_id'] = 'sheet-id'
        self.write_meta_data()
        rows = [object() for _ in range(7)]

        def fake_load(reader, *args, **kwargs):
            reader.updates = rows
            return len(rows)

        with patch.object(UpdateReader, 'load_from_spreadsheet',
                          autospec=True, side_effect=fake_load) as load:
            updates = self.make_site(updates_limit=3).get_recent_updates()
        load.assert_called_once()
        self.assertEqual(updates, rows[:3])     # updates_limit applies here too

    def test_none_without_file_or_spreadsheet(self):
        with patch.object(UpdateReader, 'load_from_spreadsheet') as load:
            self.assertEqual(self.make_site().get_recent_updates(), [])
        load.assert_not_called()


class TestUpdatesFileErrors(UpdatesTestCase):
    '''The file is the author's own, so a bad entry fails the build loudly.'''

    def assert_fails(self, text: str, *fragments: str):
        path = self.write_updates(text)
        config = self.make_site().config
        with self.assertRaises(ValueError) as caught:
            load_updates_file(path, config)
        message = str(caught.exception)
        self.assertIn('updates.yaml', message)
        for fragment in fragments:
            self.assertIn(fragment, message)
        return message

    def test_invalid_yaml(self):
        # A plain scalar with ": " in it, the mistake the docs warn about
        self.assert_fails("- date: 2025-05-20\n  content: Time: 10:30\n",
                          'not valid YAML', 'line 2', "'>-' block")

    def test_top_level_not_a_list(self):
        self.assert_fails("date: 2026-05-01\ncontent: x\n",
                          'expected a list', 'dict')

    def test_entry_not_a_mapping(self):
        self.assert_fails(entries(1) + "- just some text\n", 'update 2',
                          'not a mapping')

    def test_missing_content(self):
        self.assert_fails(entries(2) + "- date: 2026-05-01\n", 'update 3',
                          'needs a date and content')

    def test_empty_content(self):
        self.assert_fails("- date: 2026-05-01\n  content: '   '\n", 'update 1',
                          'needs a date and content')

    def test_missing_date(self):
        self.assert_fails("- content: undated\n", 'update 1',
                          'needs a date and content')
        self.assert_fails("- date:\n  content: blank\n", 'update 1',
                          'needs a date and content')

    def test_unparseable_dates(self):
        for bad in ('next week', '16/03/2025', '2025'):
            with self.subTest(date=bad):
                self.assert_fails(entries(1) + f"- date: {bad}\n  content: x\n",
                                  'update 2', 'bad date', 'YYYY-MM-DD')

    def test_error_fails_the_build(self):
        self.write_updates("- content: undated\n")
        with self.assertRaises(ValueError):
            self.make_site().build()


if __name__ == '__main__':
    unittest.main()
