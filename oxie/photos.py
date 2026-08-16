'''
Photography support for the oxie static site generator: parsing a
photos.md album file and generating thumbnails for the photo gallery.
'''
import re
from pathlib import Path

from PIL import Image


def resolve_photo_src(src: str, md_filepath: str, source_root) -> str:
    '''
    Resolve an image path written relative to the .md file into a path
    relative to the web root (the output directory).
    e.g. ../image/photo/file.jpg (relative to source/photo/) → image/photo/file.jpg
    '''
    md_dir = Path(md_filepath).parent
    resolved = (md_dir / src).resolve()
    return str(resolved.relative_to(Path(source_root).resolve()))


def parse_photos_md(filepath: str, source_root) -> list:
    '''
    Parse photos.md into a list of albums.
    Each album has a name and a list of photos with src, alt, and description.

    Supported format:
        ## Album Name

        ![alt text](image/path.jpg)
        Optional description paragraph on the next line.
    '''
    albums = []
    current_album = {'name': None, 'photos': []}
    current_photo = None

    with open(filepath, 'r') as f:
        lines = f.readlines()

    for line in lines:
        line = line.rstrip('\n')

        # Album heading
        if line.startswith('## '):
            if current_photo:
                current_album['photos'].append(current_photo)
                current_photo = None
            if current_album['photos'] or current_album['name']:
                albums.append(current_album)
            current_album = {'name': line[3:].strip(), 'photos': []}

        # Image line
        elif line.startswith('!['):
            if current_photo:
                current_album['photos'].append(current_photo)
            m = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line)
            if m:
                web_src = resolve_photo_src(m.group(2), filepath, source_root)
                current_photo = {'alt': m.group(1), 'src': web_src, 'description': ''}

        # Description: non-empty line after an image, not a heading or image itself
        elif current_photo and line.strip() and not line.startswith('#') and not line.startswith('!['):
            current_photo['description'] = line.strip()

        # Blank line flushes the current photo
        elif not line.strip() and current_photo:
            current_album['photos'].append(current_photo)
            current_photo = None

    # Flush remaining
    if current_photo:
        current_album['photos'].append(current_photo)
    if current_album['photos'] or current_album['name']:
        albums.append(current_album)

    return albums


def generate_thumbnails(photo_dir, thumb_width: int = 600) -> None:
    '''
    Generate thumbnails for all images in photo_dir.
    Thumbnails are written to photo_dir/thumb/ at thumb_width pixels wide,
    preserving aspect ratio. Skips non-image files.
    '''
    photo_path = Path(photo_dir)
    thumb_path = photo_path / 'thumb'
    thumb_path.mkdir(parents=True, exist_ok=True)

    image_exts = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    for img_file in photo_path.iterdir():
        if img_file.suffix.lower() not in image_exts:
            continue
        dest = thumb_path / img_file.name
        with Image.open(img_file) as img:
            img = img.convert('RGB')
            ratio = thumb_width / img.width
            new_size = (thumb_width, int(img.height * ratio))
            thumb = img.resize(new_size, Image.LANCZOS)
            thumb.save(dest, quality=80, optimize=True)
    print(f"Thumbnails written to {thumb_path}")
