"""Regression checks for the actual HTML served by GitHub Pages; no dependencies."""

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'site.json').read_text())


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.schemas = []
        self.schema_text = None
        self.navigation = {}
        self.current_nav = None
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == 'nav':
            self.current_nav = attrs.get('aria-label')
            self.navigation[self.current_nav] = []
        if tag == 'a' and self.current_nav:
            self.navigation[self.current_nav].append(attrs)
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.schema_text = ''

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag == 'nav':
            self.current_nav = None
        if tag == 'script' and self.schema_text is not None:
            self.schemas.append(json.loads(self.schema_text))
            self.schema_text = None

    def handle_data(self, data):
        if self.schema_text is not None:
            self.schema_text += data

    def select(self, tag, **attrs):
        return [a for t, a in self.tags if t == tag and all(a.get(k) == v for k, v in attrs.items())]


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {page['path']: (ROOT / page['path'].lstrip('/') / 'index.html').read_text() for page in CONFIG['pages']}
        cls.docs = {path: Document(source) for path, source in cls.sources.items()}

    def test_all_public_pages_use_the_standard(self):
        configured = {ROOT / page['path'].lstrip('/') / 'index.html' for page in CONFIG['pages']}
        self.assertEqual(configured, set(ROOT.rglob('index.html')))
        for path, doc in self.docs.items():
            with self.subTest(page=path):
                for tag in ('html', 'head', 'body', 'header', 'main', 'footer', 'h1', 'title'):
                    self.assertEqual(len(doc.select(tag)), 1, tag)
                self.assertEqual(len(re.findall(r'<!doctype html>', self.sources[path], re.I)), 1)
                self.assertEqual(len(doc.select('main', id='main-content')), 1)
                self.assertEqual(len(doc.select('a', href='#main-content')), 1)
                self.assertEqual(len(doc.select('link', rel='stylesheet', href='/assets/site.css')), 1)
                self.assertEqual(len(doc.select('script', src='/assets/site.js')), 1)
                self.assertEqual(len(doc.select('link', rel='icon', href='/assets/favicon.svg')), 1)
                self.assertNotIn('data:image/', self.sources[path])
                ids = [attrs['id'] for _, attrs in doc.tags if 'id' in attrs]
                self.assertEqual(len(ids), len(set(ids)), 'IDs must be unique')

    def test_navigation_is_consistent_and_marks_the_current_page(self):
        paths = [page['path'] for page in CONFIG['pages']]
        headers, footers = [], []
        for path, doc in self.docs.items():
            with self.subTest(page=path):
                for label in ('Main navigation', 'Footer navigation'):
                    links = doc.navigation[label]
                    # Header also has the clickable site brand before the page links.
                    page_links = [a for a in links if a.get('class') != 'site-brand']
                    self.assertEqual([a['href'] for a in page_links], paths)
                    self.assertEqual([a['href'] for a in page_links if a.get('aria-current') == 'page'], [path])
                self.assertGreaterEqual(len(doc.select('a', href='mailto:' + CONFIG['email'])), 1)
                normalise = lambda s: re.sub(r' aria-current="page"', '', s)
                headers.append(normalise(re.search(r'<!-- site:header -->(.*?)<!-- /site:header -->', self.sources[path], re.S)[1]))
                footers.append(normalise(re.search(r'<!-- site:footer -->(.*?)<!-- /site:footer -->', self.sources[path], re.S)[1]))
        self.assertEqual(len(set(headers)), 1)
        self.assertEqual(len(set(footers)), 1)

    def test_metadata_and_structured_data(self):
        titles, descriptions = [], []
        for page in CONFIG['pages']:
            path = page['path']
            doc = self.docs[path]
            canonical = CONFIG['url'] + path
            with self.subTest(page=path):
                descriptions.append(doc.select('meta', name='description')[0]['content'])
                titles.append(doc.select('meta', property='og:title')[0]['content'])
                self.assertEqual(len(doc.select('meta', name='description')), 1)
                self.assertEqual(doc.select('link', rel='canonical'), [{'rel': 'canonical', 'href': canonical}])
                self.assertEqual(doc.select('meta', property='og:url')[0]['content'], canonical)
                self.assertEqual(doc.select('meta', name='twitter:card')[0]['content'], 'summary_large_image')
                image = doc.select('meta', property='og:image')[0]['content']
                self.assertTrue((ROOT / urlsplit(image).path.lstrip('/')).is_file())
                self.assertEqual(len(doc.schemas), 1)
                graph = doc.schemas[0]['@graph']
                self.assertEqual(doc.schemas[0]['@context'], 'https://schema.org')
                self.assertTrue(any(node['@type'] == 'Person' for node in graph))
                self.assertTrue(any(node['@type'] == page['schema_type'] and node.get('url') == canonical for node in graph))
        self.assertEqual(len(set(titles)), len(self.docs))
        self.assertEqual(len(set(descriptions)), len(self.docs))

    def test_local_resources_links_and_fragments_resolve(self):
        for path, doc in self.docs.items():
            for tag, attrs in doc.tags:
                if tag == 'img':
                    self.assertIn('alt', attrs)
                for ref in [attrs.get('href'), attrs.get('src')]:
                    if not ref or urlsplit(ref).scheme or ref.startswith('//'):
                        continue
                    target = urlsplit(urljoin(path, ref))
                    file = ROOT / unquote(target.path).lstrip('/')
                    if file.is_dir():
                        file /= 'index.html'
                    with self.subTest(page=path, resource=ref):
                        self.assertTrue(file.is_file(), str(file))
                        if target.fragment and file.suffix == '.html':
                            ids = {a.get('id') for _, a in Document(file.read_text()).tags}
                            self.assertIn(unquote(target.fragment), ids)

    def test_crawl_files_include_every_page(self):
        root = ET.parse(ROOT / 'sitemap.xml').getroot()
        urls = [node.text for node in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        self.assertEqual(urls, [CONFIG['url'] + page['path'] for page in CONFIG['pages']])
        robots = (ROOT / 'robots.txt').read_text()
        self.assertIn('Allow: /', robots)
        self.assertIn('Sitemap: ' + CONFIG['url'] + '/sitemap.xml', robots)


if __name__ == '__main__':
    unittest.main()
