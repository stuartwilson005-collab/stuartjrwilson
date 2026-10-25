#!/usr/bin/env python3
"""Render shared page regions and search metadata using only Python's standard library."""

import argparse
import html
import json
from pathlib import Path
import re
import sys
from xml.sax.saxutils import escape as xml_escape

ROOT = Path(__file__).resolve().parents[1]


def region(source, name, content):
    start, end = f'<!-- site:{name} -->', f'<!-- /site:{name} -->'
    pattern = re.escape(start) + r'.*?' + re.escape(end)
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError(f'Expected exactly one {name} region')
    return re.sub(pattern, lambda _: f'{start}\n{content.strip()}\n{end}', source, flags=re.S)


def navigation(config, current):
    return '\n'.join(
        f'<a href="{html.escape(page["path"], quote=True)}"'
        + (' aria-current="page"' if page['path'] == current else '')
        + f'>{html.escape(page["label"])}</a>'
        for page in config['pages']
    )


def metadata(config, page):
    base = config['url'].rstrip('/')
    canonical = base + page['path']
    image = base + '/assets/stuart-wilson.png'
    person_id = base + '/#person'
    site_id = base + '/#website'
    graph = [
        {'@type': 'Person', '@id': person_id, 'name': config['name'],
         'url': base + '/', 'image': image, 'sameAs': [config['linkedin']]},
        {'@type': 'WebSite', '@id': site_id, 'url': base + '/',
         'name': config['name'], 'inLanguage': 'en-GB',
         'publisher': {'@id': person_id}},
        {'@type': page['schema_type'], '@id': canonical + '#webpage',
         'url': canonical, 'name': page['title'], 'description': page['description'],
         'inLanguage': 'en-GB', 'isPartOf': {'@id': site_id},
         'about': {'@id': person_id}, 'author': {'@id': person_id}},
    ]
    if page['schema_type'] == 'ProfilePage':
        graph[-1]['mainEntity'] = {'@id': person_id}
    if page['path'] != '/':
        graph[-1]['breadcrumb'] = {'@id': canonical + '#breadcrumb'}
        graph.append({
            '@type': 'BreadcrumbList', '@id': canonical + '#breadcrumb',
            'itemListElement': [
                {'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': base + '/'},
                {'@type': 'ListItem', 'position': 2, 'name': page['label'], 'item': canonical},
            ],
        })
    escaped = lambda value: html.escape(value, quote=True)
    tags = [
        f'<title>{html.escape(page["title"])}</title>',
        f'<meta name="description" content="{escaped(page["description"])}">',
        '<meta name="theme-color" content="#213f56">',
        f'<link rel="canonical" href="{escaped(canonical)}">',
        '<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">',
        '<link rel="stylesheet" href="/assets/site.css">',
        '<meta property="og:type" content="website">',
        '<meta property="og:locale" content="en_GB">',
        f'<meta property="og:site_name" content="{escaped(config["name"])}">',
        f'<meta property="og:title" content="{escaped(page["title"])}">',
        f'<meta property="og:description" content="{escaped(page["description"])}">',
        f'<meta property="og:url" content="{escaped(canonical)}">',
        f'<meta property="og:image" content="{escaped(image)}">',
        '<meta property="og:image:type" content="image/png">',
        '<meta property="og:image:width" content="934">',
        '<meta property="og:image:height" content="785">',
        '<meta property="og:image:alt" content="Illustration of Stuart Wilson in a navy suit and teal tie">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{escaped(page["title"])}">',
        f'<meta name="twitter:description" content="{escaped(page["description"])}">',
        f'<meta name="twitter:image" content="{escaped(image)}">',
        '<meta name="twitter:image:alt" content="Illustration of Stuart Wilson in a navy suit and teal tie">',
        '<script type="application/ld+json">',
        json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False, indent=2).replace('<', '\\u003c'),
        '</script>',
    ]
    return '\n'.join(tags)


def build(check=False):
    config = json.loads((ROOT / 'site.json').read_text())
    outputs = {}
    for page in config['pages']:
        path = ROOT / page['path'].lstrip('/') / 'index.html'
        source = path.read_text()
        source = region(source, 'meta', metadata(config, page))
        for name in ('header', 'footer'):
            template = (ROOT / 'templates' / f'{name}.html').read_text()
            template = template.replace('{{navigation}}', navigation(config, page['path']))
            for field in ('email', 'linkedin'):
                template = template.replace('{{' + field + '}}', html.escape(config[field], quote=True))
            source = region(source, name, template)
        source = region(source, 'scripts', '<script src="/assets/site.js" defer></script>')
        outputs[path] = source
    urls = '\n'.join(
        f'  <url><loc>{xml_escape(config["url"].rstrip("/") + page["path"])}</loc></url>'
        for page in config['pages']
    )
    outputs[ROOT / 'sitemap.xml'] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + urls + '\n</urlset>\n'
    )
    outputs[ROOT / 'robots.txt'] = f'User-agent: *\nAllow: /\n\nSitemap: {config["url"].rstrip("/")}/sitemap.xml\n'
    stale = []
    for path, content in outputs.items():
        if not path.exists() or path.read_text() != content:
            stale.append(str(path.relative_to(ROOT)))
            if not check:
                path.write_text(content)
    if check and stale:
        print('Out of date: ' + ', '.join(stale) + '. Run python3 tools/build_site.py.', file=sys.stderr)
        return 1
    print(f'{"Checked" if check else "Rendered"} {len(config["pages"])} pages, sitemap.xml and robots.txt.')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if generated regions are out of date; do not write files.')
    sys.exit(build(parser.parse_args().check))
