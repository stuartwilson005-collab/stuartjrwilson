# Stuart Wilson website

A static site published at https://stuartjrwilson.com. No package installation or build service is required to serve the checked-in pages.

## Local development

From the repository root:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

The public pages are `/`, `/cs/` and `/ai-account-planning/`. Use `?analytics=off` to disable the existing Cloudflare analytics in your browser during development; `?analytics=on` re-enables it.

## Standard page setup

The homepage sets the visual direction: navy and teal, system typography and a dark footer. Every page uses the same header, navigation and footer, rendered into the HTML so they also work without JavaScript.

- Edit `templates/header.html` or `templates/footer.html` to change the shared layout.
- Edit `assets/site.css` for shared header and footer styling, and `assets/site.js` for shared copyright and analytics behaviour.
- Edit `site.json` for page labels, unique titles, descriptions and the production domain.
- Edit page content and page-specific styles in each `index.html`, outside the `site:*` comment regions.

After changing templates or configuration, regenerate and validate the pages:

```sh
python3 tools/build_site.py
python3 tools/build_site.py --check
python3 -m unittest discover -s tests
```

Commit the rendered HTML along with template/configuration changes. GitHub Pages serves these files directly; there is no runtime template engine. `--check` exits unsuccessfully when generated regions or crawl files need updating.

To add a page, create its directory with an `index.html` based on an existing page, retain the four `site:meta`, `site:header`, `site:footer` and `site:scripts` comment regions, use one main landmark with `id="main-content"` and one descriptive H1, then add its trailing-slash path, label, title, description and Schema.org page type to `site.json`. Regenerate so navigation and the sitemap include it everywhere.

## Search and sharing

The generator provides unique titles/descriptions, HTTPS canonical URLs, Open Graph and Twitter sharing metadata, Person/WebSite/page structured data, and breadcrumbs for subpages. It also maintains `sitemap.xml` and `robots.txt`. The existing homepage portrait is a separate cacheable asset and the sharing image; there is a shared SVG favicon.

After deployment, verify the production URLs and submit `https://stuartjrwilson.com/sitemap.xml` in the domain's Google Search Console property. Search engine indexing and rankings depend on deployment, crawling and content; local validation does not confirm indexing.
