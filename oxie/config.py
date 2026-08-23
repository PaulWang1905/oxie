'''
Site configuration for the oxie static site generator.

A SiteConfig describes one site: where its content, templates and output
live, and which optional features (photography page, thumbnails, extra
template pages, CSS pipeline) are enabled. The defaults match the classic
oxie layout:

    source/          markdown content (index.md, post/, page/, image/, static/)
    src/             Jinja2 templates + meta_data.json + styles.css
    docs/            generated output

All relative paths are resolved against the current working directory,
so a build is normally run from the site's root folder.
'''
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence
from zoneinfo import ZoneInfo

#: Bound here because SiteConfig has a field called `timezone`.
UTC = timezone.utc

DEFAULT_MARKDOWN_EXTENSIONS = [
    'pymdownx.tilde', 'pymdownx.emoji', 'tables', 'meta', 'footnotes',
    'md_in_html', 'extra',
    'pymdownx.arithmatex', 'pymdownx.highlight', 'pymdownx.superfences',
]

DEFAULT_MARKDOWN_EXTENSION_CONFIGS = {
    'pymdownx.arithmatex': {
        'generic': True
    },
    'pymdownx.highlight': {
        'use_pygments': True,
        'noclasses': False,
    },
}


@dataclass
class SiteConfig:
    # Core layout
    source_dir: Path = Path('source')
    template_dir: Path = Path('src')
    output_dir: Path = Path('docs')
    # Site metadata JSON (title, link, phrases, default image, ...)
    meta_data_file: Path = Path('src/meta_data.json')

    # Fall back to the templates bundled with oxie for any template the site
    # does not define itself. Set False to fail loudly on a missing template.
    use_bundled_templates: bool = True

    # Markdown pipeline
    markdown_extensions: List[str] = field(
        default_factory=lambda: list(DEFAULT_MARKDOWN_EXTENSIONS))
    markdown_extension_configs: Dict[str, dict] = field(
        default_factory=lambda: dict(DEFAULT_MARKDOWN_EXTENSION_CONFIGS))

    # Static assets: source directory -> output directory. None means the
    # classic default: source/image -> docs/image, source/static -> docs/page.
    collect_dirs: Optional[Dict[str, str]] = None

    # Dates. A front matter date written without an offset is read in this
    # timezone, and one written without a time of day is placed at
    # default_post_time. Noon rather than midnight: midnight is still the
    # previous calendar day for every reader west of the site, so a post
    # dated the 22nd would be shown as the 21st.
    timezone: str = 'UTC'
    default_post_time: time = time(12, 0)

    # Page titles excluded from the index page listing
    index_excluded_titles: Sequence[str] = ('Terms of Service', 'Privacy Policy')

    # Extra standalone pages rendered once with the site context:
    # template file name -> output file name (relative to output_dir)
    simple_pages: Dict[str, str] = field(default_factory=dict)

    # Photography page: parses photos_md into albums and renders
    # photography_template.html to photography.html
    photography: bool = False
    photos_md: Optional[Path] = None      # default: source_dir/photo/photos.md
    thumbnails: bool = False
    thumbnail_dir: Optional[Path] = None  # default: output_dir/image/photo
    thumbnail_width: int = 600

    # Discovery files. All are built from meta_data["link"], so that must be
    # the site's real base URL for the generated URLs to be correct.
    sitemap: bool = True
    sitemap_file: str = 'sitemap.xml'
    robots_txt: bool = True
    robots_file: str = 'robots.txt'
    feed: bool = True
    feed_file: str = 'feed.xml'
    feed_max_items: int = 20
    # Render 404.html, which GitHub Pages serves for unknown paths
    error_page: bool = True
    error_page_template: str = '404.html'

    # CSS pipeline: command run from the site root, or None to skip
    css_build_command: Optional[Sequence[str]] = ('npm', 'run', 'build:css')
    # Pygments highlight style written to output_dir/pygments.css, None to skip
    pygments_style: Optional[str] = None

    def __post_init__(self) -> None:
        self.source_dir = Path(self.source_dir)
        self.template_dir = Path(self.template_dir)
        self.output_dir = Path(self.output_dir)
        self.meta_data_file = Path(self.meta_data_file)
        if self.collect_dirs is None:
            self.collect_dirs = {
                str(self.source_dir / 'image'): str(self.output_dir / 'image'),
                str(self.source_dir / 'static'): str(self.output_dir / 'page'),
            }
        if self.photos_md is None:
            self.photos_md = self.source_dir / 'photo' / 'photos.md'
        if self.thumbnail_dir is None:
            self.thumbnail_dir = self.output_dir / 'image' / 'photo'

    @property
    def tzinfo(self):
        '''
        The site timezone as a tzinfo. The UTC default is short-circuited,
        so an ordinary site needs no timezone database installed.
        '''
        return UTC if self.timezone.upper() == 'UTC' else ZoneInfo(self.timezone)

    def to_datetime(self, value) -> Optional[datetime]:
        '''
        Normalise one front matter date into a timezone-aware datetime.

        Front matter yields whatever YAML made of the value: a date for
        `Date: 2026-08-22`, a naive datetime for `Date: 2026-08-22
        09:30:00`, an aware one when an offset is written, and a string
        from index.md, which the Markdown meta extension reads as text.
        Those types do not compare with each other, so a site holding a
        mix of them cannot be sorted — every date is converted here, on
        the way in, and everything downstream works on the one type.

        A date-only value is placed at default_post_time and a value with
        no offset is read in the site timezone; an aware value keeps the
        offset its author wrote. None passes through, so an optional field
        such as Last_modified needs no checking first.
        '''
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip()
            # Tried as a date first: fromisoformat would otherwise read a
            # date-only string as midnight, skipping default_post_time.
            try:
                value = date.fromisoformat(text)
            except ValueError:
                value = datetime.fromisoformat(text)
        if isinstance(value, datetime):     # datetime subclasses date
            moment = value
        elif isinstance(value, date):
            moment = datetime.combine(value, self.default_post_time)
        else:
            raise TypeError('Expected a date, datetime or ISO 8601 string, '
                            f'got {type(value).__name__}: {value!r}')
        return moment if moment.tzinfo else moment.replace(tzinfo=self.tzinfo)
