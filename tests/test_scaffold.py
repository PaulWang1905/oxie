import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Make the repo root importable when running with unittest
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from oxie import Site, SiteConfig, init_site
from oxie.cli import main as cli_main


class TestScaffold(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_init_creates_a_complete_site(self):
        result = init_site(str(self.test_dir), title="Test Blog", author="Puyu")

        expected = [
            "build.py", "package.json", "requirements.txt", ".gitignore",
            "src/meta_data.json", "src/styles.css",
            "src/base.html", "src/index.html", "src/template.html",
            "src/blog_template.html", "src/category_template.html",
            "source/index.md", "source/post/hello-world.md",
            "source/page/about.md",
        ]
        for rel in expected:
            self.assertTrue((self.test_dir / rel).exists(), f"missing {rel}")

        # content directories exist even though they are empty
        for rel in ("source/image", "source/static", "docs"):
            self.assertTrue((self.test_dir / rel).is_dir(), f"missing dir {rel}")

        self.assertEqual(result["skipped"], [])
        self.assertTrue(result["created"])

    def test_init_substitutes_metadata(self):
        init_site(str(self.test_dir), title="Test Blog", author="Puyu",
                  link="https://blog.example.org/", description="Hello there")

        meta = json.loads((self.test_dir / "src/meta_data.json").read_text())
        self.assertEqual(meta["title"], "Test Blog")
        self.assertEqual(meta["author"], "Puyu")
        self.assertEqual(meta["description"], "Hello there")
        # trailing slash stripped so link + "/post/x.html" stays well formed
        self.assertEqual(meta["link"], "https://blog.example.org")

        self.assertIn("Title:   Test Blog", (self.test_dir / "source/index.md").read_text())
        self.assertIn("Puyu", (self.test_dir / "source/post/hello-world.md").read_text())

    def test_scaffold_uses_tailwind_v4(self):
        init_site(str(self.test_dir), title="Test Blog")

        styles = (self.test_dir / "src/styles.css").read_text()
        self.assertIn('@import "tailwindcss"', styles)
        self.assertIn('@plugin "@tailwindcss/typography"', styles)

        package = json.loads((self.test_dir / "package.json").read_text())
        self.assertIn("@tailwindcss/cli", package["devDependencies"])
        self.assertIn("build:css", package["scripts"])
        # npm package names may not contain spaces or capitals
        self.assertEqual(package["name"], "test-blog")

    def test_init_does_not_overwrite_without_force(self):
        init_site(str(self.test_dir), title="First")
        (self.test_dir / "source/index.md").write_text("MINE\n")

        result = init_site(str(self.test_dir), title="Second")
        self.assertEqual((self.test_dir / "source/index.md").read_text(), "MINE\n")
        self.assertIn(str(self.test_dir / "source/index.md"), result["skipped"])
        self.assertEqual(result["created"], [])

    def test_init_force_overwrites(self):
        init_site(str(self.test_dir), title="First")
        (self.test_dir / "source/index.md").write_text("MINE\n")

        init_site(str(self.test_dir), title="Second", force=True)
        self.assertIn("Second", (self.test_dir / "source/index.md").read_text())

    def test_scaffolded_site_builds(self):
        '''The headline promise: init then build produces a working site.'''
        init_site(str(self.test_dir), title="Test Blog", author="Puyu",
                  link="https://blog.example.org")

        cwd = os.getcwd()
        os.chdir(self.test_dir)
        try:
            config = SiteConfig(
                collect_dirs={"source/image": "docs/image", "source/static": "docs"},
                pygments_style="github-dark",
                css_build_command=None,   # offline: no npm in the test env
            )
            Site(config).build()
        finally:
            os.chdir(cwd)

        docs = self.test_dir / "docs"
        for rel in ["index.html", "blog_index.html", "blog_Blog.html",
                    "post/hello-world.html", "page/about.html",
                    "posts_metadata.jsonld", "pygments.css"]:
            self.assertTrue((docs / rel).exists(), f"missing {rel}")

        index = (docs / "index.html").read_text()
        self.assertIn("Test Blog", index)
        self.assertIn("Hello World", index)          # the sample post is listed
        self.assertIn('href="/post/hello-world.html"', index)

        post = (docs / "post/hello-world.html").read_text()
        self.assertIn("<h1", post)
        self.assertIn("prose", post)                 # Tailwind typography applied
        self.assertIn("highlight", post)             # pygments code block

    def test_cli_init(self):
        rc = cli_main(["init", str(self.test_dir), "--title", "CLI Site"])
        self.assertEqual(rc, 0)
        meta = json.loads((self.test_dir / "src/meta_data.json").read_text())
        self.assertEqual(meta["title"], "CLI Site")

    def test_cli_no_command_shows_help(self):
        self.assertEqual(cli_main([]), 1)

    def test_cli_version(self):
        with self.assertRaises(SystemExit) as cm:
            cli_main(["--version"])
        self.assertEqual(cm.exception.code, 0)


class TestBundledTemplateFallback(unittest.TestCase):
    '''A site with no templates of its own still renders.'''

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        for sub in ("source/post", "source/page", "src", "docs"):
            (self.test_dir / sub).mkdir(parents=True)
        (self.test_dir / "src/meta_data.json").write_text(json.dumps({
            "title": "Bare Site", "description": "d", "author": "a",
            "link": "https://example.com", "image": "image/default.png",
            "phrases": ["a phrase"],
        }))
        (self.test_dir / "source/index.md").write_text(
            "Title:   Bare Site\nAuthors: A\nDate:    2026-08-16\n\n## Hi\n")
        (self.test_dir / "source/post/p.md").write_text(
            "---\nTitle: P\nSummary: s\nAuthors: A\nDate: 2026-08-16\n"
            "Category: Blog\nTags: [t]\n---\n\nBody.\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_renders_without_site_templates(self):
        cwd = os.getcwd()
        os.chdir(self.test_dir)
        try:
            Site(SiteConfig(css_build_command=None)).build()
        finally:
            os.chdir(cwd)
        self.assertIn("Bare Site", (self.test_dir / "docs/index.html").read_text())

    def test_can_be_disabled(self):
        cwd = os.getcwd()
        os.chdir(self.test_dir)
        try:
            config = SiteConfig(css_build_command=None, use_bundled_templates=False)
            with self.assertRaises(Exception):
                Site(config).build()
        finally:
            os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
