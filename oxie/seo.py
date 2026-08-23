'''
SEO and syndication artifacts for the oxie static site generator.

Pure functions that turn already-parsed content into the standard discovery
files: an XML sitemap, robots.txt, an RSS 2.0 feed, and the JSON-LD that
templates embed inline. Nothing here touches the filesystem — Site owns the
writing, these functions just return strings.

Everything is deterministic: given the same content these produce the same
bytes. No build timestamps are used anywhere, so rebuilding an unchanged
site leaves the output untouched instead of generating a spurious diff.
'''
import json
from datetime import datetime, time, timezone
from email.utils import format_datetime
from typing import Iterable, List, NamedTuple, Optional
from xml.sax.saxutils import escape, quoteattr

RSS_NAMESPACES = {
    'xmlns:atom': 'http://www.w3.org/2005/Atom',
    'xmlns:content': 'http://purl.org/rss/1.0/modules/content/',
    'xmlns:dc': 'http://purl.org/dc/elements/1.1/',
}


class SitemapEntry(NamedTuple):
    '''One <url> in the sitemap: an absolute URL and an optional W3C date.'''
    loc: str
    lastmod: Optional[str] = None


# ---- small helpers -----------------------------------------------------

def absolute_url(base: str, path: str) -> str:
    '''
    Join a site base URL and a site-relative path.

    Post.link carries a leading slash and Category.link does not, so both
    sides are trimmed before joining rather than concatenated blindly.
    '''
    return '{}/{}'.format(base.rstrip('/'), str(path).lstrip('/'))


def w3c_date(day) -> Optional[str]:
    '''
    A YYYY-MM-DD date, as <lastmod> wants it.

    Formatted numerically rather than through a locale-aware strftime code,
    so the output does not depend on the builder's LC_TIME. A datetime keeps
    the calendar day of its own offset, which is the day its author wrote,
    not the UTC day the feed's pubDate converts to.
    '''
    if day is None:
        return None
    return '{:04d}-{:02d}-{:02d}'.format(day.year, day.month, day.day)


def rfc822_date(day) -> Optional[str]:
    '''
    An RFC 822 date in GMT, as RSS <pubDate> requires.

    Post dates arrive from SiteConfig.to_datetime already timezone-aware,
    and are converted to UTC here because usegmt rejects any other offset.
    A bare date is still read as midnight GMT, so the helper stays usable on
    its own. email.utils does the formatting because the equivalent strftime
    codes emit localised day and month names.
    '''
    if day is None:
        return None
    moment = day if isinstance(day, datetime) else datetime.combine(day, time.min)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return format_datetime(moment.astimezone(timezone.utc), usegmt=True)


def iso8601_date(moment) -> Optional[str]:
    '''
    An ISO 8601 timestamp, as Schema.org dates want them.

    isoformat() rather than strftime, so the output holds no locale-dependent
    names and keeps the offset the date was written with. Google's structured
    data guidance asks for the time and offset, not a bare calendar date.
    '''
    if moment is None:
        return None
    return moment.isoformat()


def last_modified_of(post):
    '''
    A post's last-modified date, falling back to its publication date.

    Post.last_modified is only assigned inside the metadata try block, so a
    post with malformed frontmatter has no such attribute at all.
    '''
    return getattr(post, 'last_modified', None) or getattr(post, 'date', None)


def _tag(name: str, text, indent: str = '    ') -> str:
    '''One escaped XML element on its own line.'''
    return '{}<{}>{}</{}>'.format(indent, name, escape(str(text)), name)


# ---- sitemap and robots ------------------------------------------------

def render_sitemap(entries: Iterable[SitemapEntry]) -> str:
    '''
    Render a sitemap.xml body from an ordered sequence of entries.
    '''
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for entry in entries:
        lines.append('  <url>')
        lines.append(_tag('loc', entry.loc))
        if entry.lastmod:
            lines.append(_tag('lastmod', entry.lastmod))
        lines.append('  </url>')
    lines.append('</urlset>')
    return '\n'.join(lines) + '\n'


def render_robots_txt(sitemap_url: Optional[str] = None) -> str:
    '''
    Render a permissive robots.txt, pointing at the sitemap when there is one.
    '''
    lines = ['User-agent: *', 'Allow: /']
    if sitemap_url:
        lines.extend(['', 'Sitemap: {}'.format(sitemap_url)])
    return '\n'.join(lines) + '\n'


# ---- RSS ---------------------------------------------------------------

def render_rss_feed(
    title: str,
    link: str,
    description: str,
    feed_url: str,
    posts: Iterable,
    language: str = 'en',
) -> str:
    '''
    Render an RSS 2.0 feed for the given posts, newest first.

    The channel's lastBuildDate is the newest post date rather than the
    current time, so an unchanged site rebuilds to an identical file.
    '''
    posts = list(posts)
    dates = [p.date for p in posts if getattr(p, 'date', None)]
    build_date = rfc822_date(max(dates)) if dates else None

    namespaces = ' '.join(
        '{}={}'.format(key, quoteattr(value))
        for key, value in RSS_NAMESPACES.items()
    )
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" {}>'.format(namespaces),
        '  <channel>',
        _tag('title', title),
        _tag('link', link),
        _tag('description', description),
        _tag('language', language),
        '    <atom:link href={} rel="self" type="application/rss+xml"/>'.format(
            quoteattr(feed_url)),
    ]
    if build_date:
        lines.append(_tag('lastBuildDate', build_date))

    for post in posts:
        lines.append('    <item>')
        lines.append(_tag('title', post.title or 'Untitled', '      '))
        lines.append(_tag('link', post.full_link, '      '))
        lines.append('      <guid isPermaLink="true">{}</guid>'.format(
            escape(str(post.full_link))))
        published = rfc822_date(getattr(post, 'date', None))
        if published:
            lines.append(_tag('pubDate', published, '      '))
        if post.author:
            lines.append(_tag('dc:creator', post.author, '      '))
        if post.category:
            lines.append(_tag('category', post.category, '      '))
        if post.summary:
            lines.append(_tag('description', post.summary, '      '))
        if post.content:
            lines.append(_tag('content:encoded', post.content, '      '))
        lines.append('    </item>')

    lines.extend(['  </channel>', '</rss>'])
    return '\n'.join(lines) + '\n'


# ---- JSON-LD -----------------------------------------------------------

def post_jsonld(post, meta_data) -> dict:
    '''
    Schema.org BlogPosting for one post.

    Returned without an "@context" key so it can be dropped straight into the
    ItemList in posts_metadata.jsonld; use jsonld_script() to emit it on its
    own inside a page.
    '''
    published = iso8601_date(post.date)
    modified = iso8601_date(last_modified_of(post)) or published
    data = {
        "@type": "BlogPosting",
        "@id": post.full_link,
        "headline": post.title,
        "author": {
            "@type": "Person",
            "name": post.author
        },
        "datePublished": published,
        "dateModified": modified,
        "description": post.summary,
        "about": {
            "@type": "DefinedTerm",
            "name": post.category,
            "inDefinedTermSet": {
                "@type": "DefinedTermSet",
                "name": "Blog Categories"
            }
        },
        "keywords": post.tags,
        "url": post.full_link,
        "publisher": {
            "@type": "Organization",
            "name": meta_data["title"],
            "url": meta_data["link"]
        },
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": post.full_link
        }
    }
    if published is None:
        # A post whose frontmatter has no Date at all. Dropping the keys
        # beats emitting nulls that no consumer can read, and beats the
        # AttributeError this used to raise.
        del data["datePublished"]
        del data["dateModified"]
    return data


def posts_jsonld(posts: List, meta_data) -> dict:
    '''
    Schema.org ItemList wrapping every post, for posts_metadata.jsonld and
    for the home page's inline structured data.
    '''
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"{meta_data['title']} - Blog Posts",
        "description": f"Collection of blog posts from {meta_data['title']}",
        "numberOfItems": len(posts),
        "itemListElement": [post_jsonld(post, meta_data) for post in posts]
    }


def jsonld_script(data: Optional[dict]) -> Optional[str]:
    '''
    Serialise JSON-LD for embedding in a <script> tag.

    Every '<' becomes an escape sequence so a stray "</script>" inside a
    title or summary cannot close the tag early.
    '''
    if data is None:
        return None
    return json.dumps(data, indent=2, ensure_ascii=False).replace('<', '\\u003c')


def post_jsonld_script(post, meta_data) -> Optional[str]:
    '''
    Inline JSON-LD for a single post, or None when the post has no date and
    the structured data would be incomplete.
    '''
    if getattr(post, 'date', None) is None:
        return None
    data = {"@context": "https://schema.org"}
    data.update(post_jsonld(post, meta_data))
    return jsonld_script(data)
