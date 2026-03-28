# Scheeper Art

Static art portfolio site built with plain HTML, CSS, JavaScript, and a small Python generator.

## Project structure

```text
artworks/
  00001/
    artwork.json
    image files...
  00002/
    artwork.json
    image files...
static/
  css/site.css
  js/gallery.js
templates/
  base.html
  index.html
  artwork.html
  about.html
site.json
build.py
artwork_entry_qt.py
requirements-gui.txt
dist/
```

## Local build

```bash
python build.py
```

The generated site is written to `dist/`.

## Desktop entry tool

Install the desktop dependency once:

```bash
pip install -r requirements-gui.txt
```

Start the Qt artwork entry tool with:

```bash
python artwork_entry_qt.py
```

The tool lets you:

- fill in the artwork fields
- select one or more images from Windows Explorer
- drag and drop image files into the image list
- choose which image should be the main gallery image
- switch to the existing-artworks tab to open an artwork by folder id, title, and added date
- edit the loaded artwork in the same form and save the changes back to its folder
- save everything directly into a new folder under `artworks/`

## Adding a new artwork manually

1. Create a new folder inside `artworks/`.
2. Add the artwork images to that folder.
3. Add an `artwork.json` file in the same folder.
4. Run `python build.py`.

Example `artwork.json`:

```json
{
  "title": "Morning Light",
  "slug": "morning-light",
  "type": "painting",
  "price": 240,
  "price_label": "",
  "dimensions": "60 x 80 cm",
  "description": "Acrylic on canvas.",
  "cover_image": "cover.jpg",
  "additional_images": ["detail.jpg"],
  "featured": false,
  "availability": "available",
  "date_added": "2026-03-28T14:30:00",
  "sort_order": 10
}
```

`date_added` is required and may be either `YYYY-MM-DD` or a full ISO date-time like `YYYY-MM-DDTHH:MM:SS`.

## Site settings

Edit `site.json` for artist-wide content:

- `artist_name`
- `tagline`
- `about`
- `atelier_location`
- `email`
- `phone`
- `instagram`
- `custom_domain`
- `base_path`

Use `base_path` only when the site is served from a repository subpath such as `/repo-name`. If you use a custom domain, leave `base_path` empty.

If `custom_domain` is set, the build writes a `CNAME` file into `dist/`.

## Deployment

The GitHub Actions workflow in `.github/workflows/deploy.yml` builds the site and deploys `dist/` to GitHub Pages.

In the repository settings, set GitHub Pages to use **GitHub Actions** as the source.

If Pages has not been enabled for the repository yet, you have two options:

1. Enable GitHub Pages manually in the repository settings, then keep using the default workflow.
2. Add a repository secret named `PAGES_ENABLEMENT_TOKEN` and let the workflow enable Pages automatically.

For automatic enablement, the token must be something other than the default `GITHUB_TOKEN`. According to `actions/configure-pages`, a Personal Access Token needs `repo` scope or Pages write permission.
