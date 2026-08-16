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
from pathlib import Path
from typing import Dict, List, Optional, Sequence

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

    # Markdown pipeline
    markdown_extensions: List[str] = field(
        default_factory=lambda: list(DEFAULT_MARKDOWN_EXTENSIONS))
    markdown_extension_configs: Dict[str, dict] = field(
        default_factory=lambda: dict(DEFAULT_MARKDOWN_EXTENSION_CONFIGS))

    # Static assets: source directory -> output directory. None means the
    # classic default: source/image -> docs/image, source/static -> docs/page.
    collect_dirs: Optional[Dict[str, str]] = None

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
