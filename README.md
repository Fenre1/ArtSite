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
dist/
```

## Local build

```bash
python build.py
```

The generated site is written to `dist/`.

## Adding a new artwork

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
  "sort_order": 10
}
```

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
