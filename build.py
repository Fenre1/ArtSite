from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote


ROOT = Path(__file__).parent
SITE_FILE = ROOT / "site.json"
ARTWORKS_DIR = ROOT / "artworks"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
DIST_DIR = ROOT / "dist"
PLACEHOLDER_PATTERN = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
TYPE_LABELS = {
    "painting": "Painting",
    "mosaic": "Mosaic",
    "sculpture": "Sculpture",
    "other": "Other",
}
AVAILABILITY_LABELS = {
    "available": ("Available", "is-available"),
    "sold": ("Sold", "is-sold"),
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def render_template(template_name: str, context: dict[str, Any]) -> str:
    template_path = TEMPLATES_DIR / template_name
    template_text = template_path.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise KeyError(f"Missing template value '{key}' for {template_name}")
        return str(context[key])

    return PLACEHOLDER_PATTERN.sub(replace, template_text)


def escape_text(value: Any) -> str:
    return html.escape(str(value), quote=True)


def paragraph_html(text: str, fallback: str = "") -> str:
    blocks = [block.strip() for block in str(text or "").split("\n\n") if block.strip()]
    if not blocks and fallback:
        blocks = [fallback]
    return "".join(
        f"<p>{html.escape(block).replace(chr(10), '<br>')}</p>" for block in blocks
    )


def excerpt(text: str, limit: int = 140) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "..."


def meta_description(text: str) -> str:
    return " ".join(str(text or "").split())


def split_url_segments(path_value: str) -> list[str]:
    return [
        quote(segment)
        for segment in str(PurePosixPath(path_value)).replace("\\", "/").split("/")
        if segment and segment != "."
    ]


def build_url(base_path: str, relative_path: str = "", trailing_slash: bool = False) -> str:
    base_segments = split_url_segments(base_path.strip("/"))
    relative_segments = split_url_segments(relative_path.strip("/"))
    segments = base_segments + relative_segments

    if not segments:
        return "/"

    url = "/" + "/".join(segments)
    if trailing_slash:
        return url + "/"
    return url


def format_currency(value: float) -> str:
    amount = f"{value:,.2f}" if not float(value).is_integer() else f"{value:,.0f}"
    amount = amount.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"EUR {amount}"


def format_price(price: Any, price_label: str = "") -> str:
    if price is None:
        return escape_text(price_label) if price_label else "Price on request"
    return format_currency(float(price))


def price_band(price: Any) -> str:
    if price is None:
        return "unknown"
    amount = float(price)
    if amount < 100:
        return "under-100"
    if amount < 300:
        return "100-300"
    if amount < 700:
        return "300-700"
    return "700-plus"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "artwork"


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    ensure_directory(path.parent)
    path.write_text(content, encoding="utf-8")


def load_site() -> dict[str, Any]:
    site = load_json(SITE_FILE)
    defaults = {
        "site_name": "Art Portfolio",
        "artist_name": "Artist Name",
        "tagline": "Original paintings, mosaics, sculptures, and mixed-media works.",
        "intro": "Browse the catalogue and contact the artist directly for availability.",
        "about": "Add a short artist bio here.",
        "atelier_location": "",
        "email": "",
        "phone": "",
        "instagram": "",
        "custom_domain": "",
        "base_path": "",
    }

    merged = {**defaults, **site}
    merged["copyright_name"] = merged["artist_name"]
    return merged


def discover_images(folder: Path) -> list[str]:
    return sorted(
        [
            item.name
            for item in folder.iterdir()
            if item.is_file()
            and item.suffix.lower() in IMAGE_EXTENSIONS
            and item.name.lower() != "artwork.json"
        ],
        key=str.lower,
    )


def copy_artwork_images(
    folder: Path, slug: str, image_names: list[str], base_path: str
) -> list[str]:
    destination = DIST_DIR / "images" / "art" / slug
    ensure_directory(destination)

    copied_urls: list[str] = []

    for index, image_name in enumerate(image_names, start=1):
        source = folder / image_name
        extension = source.suffix.lower()
        target_name = f"image-{index}{extension}"
        shutil.copy2(source, destination / target_name)
        copied_urls.append(build_url(base_path, f"images/art/{slug}/{target_name}"))

    return copied_urls


def normalize_artwork(folder: Path, raw: dict[str, Any], base_path: str) -> dict[str, Any]:
    images = discover_images(folder)
    if not images:
        raise SystemExit(f"No artwork images found in {folder}")

    title = str(raw.get("title") or f"Untitled {folder.name}").strip()
    slug = slugify(str(raw.get("slug") or title or folder.name))
    type_key = str(raw.get("type") or "other").strip().lower()
    if type_key not in TYPE_LABELS:
        raise SystemExit(f"Unsupported artwork type '{type_key}' in {folder / 'artwork.json'}")

    availability_key = str(raw.get("availability") or "available").strip().lower()
    if availability_key not in AVAILABILITY_LABELS:
        raise SystemExit(
            f"Unsupported availability '{availability_key}' in {folder / 'artwork.json'}"
        )

    cover_image = str(raw.get("cover_image") or images[0]).strip()
    if cover_image not in images:
        raise SystemExit(f"Cover image '{cover_image}' not found in {folder}")

    if raw.get("additional_images") is None:
        additional_images = [name for name in images if name != cover_image]
    else:
        additional_images = []
        for image_name in raw["additional_images"]:
            image_name = str(image_name).strip()
            if image_name not in images:
                raise SystemExit(f"Additional image '{image_name}' not found in {folder}")
            additional_images.append(image_name)

    ordered_images: list[str] = []
    for image_name in [cover_image, *additional_images]:
        if image_name not in ordered_images:
            ordered_images.append(image_name)

    price = raw.get("price")
    if isinstance(price, str) and price.strip():
        price = float(price)
    if price is not None and not isinstance(price, (int, float)):
        raise SystemExit(f"Price must be a number or null in {folder / 'artwork.json'}")

    copied_urls = copy_artwork_images(folder, slug, ordered_images, base_path)
    availability_label, availability_class = AVAILABILITY_LABELS[availability_key]
    price_label = str(raw.get("price_label") or "").strip()
    description = str(raw.get("description") or "").strip()
    dimensions = str(raw.get("dimensions") or "").strip() or "Dimensions on request"

    return {
        "title": title,
        "slug": slug,
        "type_key": type_key,
        "type_label": TYPE_LABELS[type_key],
        "price": price,
        "price_display": format_price(price, price_label),
        "price_preview": format_price(price, price_label) if price is not None or price_label else "",
        "price_band": price_band(price),
        "dimensions": dimensions,
        "description": description or "Description coming soon.",
        "description_html": paragraph_html(description, "Description coming soon."),
        "featured": bool(raw.get("featured", False)),
        "availability_key": availability_key,
        "availability_label": availability_label,
        "availability_class": availability_class,
        "sort_order": int(raw.get("sort_order", 999)),
        "url": build_url(base_path, f"art/{slug}", trailing_slash=True),
        "output_path": DIST_DIR / "art" / slug / "index.html",
        "cover_url": copied_urls[0],
        "gallery_urls": copied_urls[1:],
    }


def load_artworks(base_path: str) -> list[dict[str, Any]]:
    artworks: list[dict[str, Any]] = []
    slugs: set[str] = set()

    for folder in sorted(ARTWORKS_DIR.iterdir(), key=lambda item: item.name.lower()):
        if not folder.is_dir():
            continue

        metadata_file = folder / "artwork.json"
        if not metadata_file.exists():
            raise SystemExit(f"Missing artwork metadata: {metadata_file}")

        artwork = normalize_artwork(folder, load_json(metadata_file), base_path)
        if artwork["slug"] in slugs:
            raise SystemExit(f"Duplicate artwork slug: {artwork['slug']}")

        slugs.add(artwork["slug"])
        artworks.append(artwork)

    artworks.sort(key=lambda item: (item["sort_order"], item["title"].lower()))
    return artworks


def nav_links(site: dict[str, Any], current_page: str) -> str:
    links = [
        ("Gallery", build_url(site["base_path"], "", trailing_slash=True), current_page == "home"),
        (
            "About / Contact",
            build_url(site["base_path"], "about", trailing_slash=True),
            current_page == "about",
        ),
    ]

    rendered: list[str] = []
    for label, href, is_active in links:
        class_name = "site-nav__link is-active" if is_active else "site-nav__link"
        rendered.append(f'<a class="{class_name}" href="{href}">{escape_text(label)}</a>')
    return "".join(rendered)


def render_footer(site: dict[str, Any]) -> str:
    links: list[str] = []

    if site["email"]:
        address = escape_text(site["email"])
        links.append(f'<a href="mailto:{address}">{address}</a>')

    if site["phone"]:
        links.append(f"<span>{escape_text(site['phone'])}</span>")

    if site["instagram"]:
        handle = str(site["instagram"]).strip().lstrip("@")
        links.append(
            f'<a href="https://instagram.com/{quote(handle)}" target="_blank" rel="noreferrer">@{escape_text(handle)}</a>'
        )

    if site["atelier_location"]:
        links.append(f"<span>{escape_text(site['atelier_location'])}</span>")

    year = datetime.now().year
    footer_links = "".join(f"<div>{item}</div>" for item in links)

    return (
        f'<div class="footer-links">{footer_links}</div>'
        f'<div class="footer-meta">(c) {year} {escape_text(site["copyright_name"])}. All rights reserved.</div>'
    )


def render_contact_details(site: dict[str, Any]) -> str:
    rows: list[str] = []

    if site["email"]:
        address = escape_text(site["email"])
        rows.append(
            f'<div class="contact-list__row"><span class="contact-list__label">Email</span>'
            f'<div class="contact-list__value"><a href="mailto:{address}">{address}</a></div></div>'
        )

    if site["phone"]:
        rows.append(
            f'<div class="contact-list__row"><span class="contact-list__label">Phone</span>'
            f'<div class="contact-list__value">{escape_text(site["phone"])}</div></div>'
        )

    if site["instagram"]:
        handle = str(site["instagram"]).strip().lstrip("@")
        rows.append(
            f'<div class="contact-list__row"><span class="contact-list__label">Instagram</span>'
            f'<div class="contact-list__value"><a href="https://instagram.com/{quote(handle)}" target="_blank" rel="noreferrer">@{escape_text(handle)}</a></div></div>'
        )

    if site["atelier_location"]:
        rows.append(
            f'<div class="contact-list__row"><span class="contact-list__label">Atelier</span>'
            f'<div class="contact-list__value">{escape_text(site["atelier_location"])}</div></div>'
        )

    return f'<div class="contact-list">{"".join(rows)}</div>'


def render_featured_cards(artworks: list[dict[str, Any]]) -> str:
    featured = [artwork for artwork in artworks if artwork["featured"]]
    featured = featured[:2] if len(featured) >= 2 else artworks[:2]

    cards: list[str] = []
    for artwork in featured:
        price_html = (
            f'<p class="featured-card__price">{escape_text(artwork["price_preview"])}</p>'
            if artwork["price_preview"]
            else ""
        )
        cards.append(
            "<article class=\"featured-card\">"
            f'<a class="featured-card__link" href="{artwork["url"]}">'
            f'<div class="featured-card__image"><img src="{artwork["cover_url"]}" alt="{escape_text(artwork["title"])}" loading="eager" decoding="async"></div>'
            '<div class="featured-card__content">'
            f'<h3 class="featured-card__title">{escape_text(artwork["title"])}</h3>'
            f'<p class="featured-card__meta">{escape_text(artwork["type_label"])} / {escape_text(artwork["availability_label"])}</p>'
            f'<p class="featured-card__excerpt">{escape_text(excerpt(artwork["description"]))}</p>'
            f"{price_html}"
            "</div></a></article>"
        )

    return "".join(cards)


def render_gallery_cards(artworks: list[dict[str, Any]]) -> str:
    cards: list[str] = []

    for artwork in artworks:
        price_html = (
            f'<p class="art-card__price">{escape_text(artwork["price_preview"])}</p>'
            if artwork["price_preview"]
            else ""
        )
        cards.append(
            f'<article class="art-card" data-art-card data-type="{artwork["type_key"]}" data-price-band="{artwork["price_band"]}">'
            f'<a class="art-card__link" href="{artwork["url"]}">'
            f'<div class="art-card__image"><img src="{artwork["cover_url"]}" alt="{escape_text(artwork["title"])}" loading="lazy" decoding="async"></div>'
            '<div class="art-card__meta"><div>'
            f'<h3 class="art-card__title">{escape_text(artwork["title"])}</h3>'
            f'<p class="art-card__type">{escape_text(artwork["type_label"])}</p>'
            f'<p class="art-card__availability">{escape_text(artwork["availability_label"])}</p>'
            "</div>"
            f"{price_html}"
            "</div></a></article>"
        )

    return "".join(cards)


def render_filter_controls() -> str:
    type_buttons = [
        ("all", "All"),
        ("painting", "Painting"),
        ("mosaic", "Mosaic"),
        ("sculpture", "Sculpture"),
        ("other", "Other"),
    ]
    price_buttons = [
        ("all", "All prices"),
        ("under-100", "Under EUR 100"),
        ("100-300", "EUR 100-300"),
        ("300-700", "EUR 300-700"),
        ("700-plus", "EUR 700+"),
    ]

    def button_group(group_name: str, label: str, options: list[tuple[str, str]]) -> str:
        buttons = "".join(
            (
                f'<button class="filter-button" type="button" data-filter-button '
                f'data-filter-group="{group_name}" data-filter-value="{value}" '
                f'aria-pressed="{str(value == "all").lower()}">{escape_text(text)}</button>'
            )
            for value, text in options
        )
        return (
            f'<div class="filter-row"><div class="filter-label">{escape_text(label)}</div>'
            f'<div class="filter-buttons">{buttons}</div></div>'
        )

    return (
        '<div class="filter-panel">'
        f"{button_group('type', 'Type', type_buttons)}"
        f"{button_group('price', 'Price', price_buttons)}"
        "</div>"
    )


def render_additional_gallery(artwork: dict[str, Any]) -> str:
    if not artwork["gallery_urls"]:
        return ""

    images = "".join(
        f'<div class="detail-gallery__item"><img src="{image_url}" alt="{escape_text(artwork["title"])} detail view" loading="lazy" decoding="async"></div>'
        for image_url in artwork["gallery_urls"]
    )

    return (
        '<section class="detail-gallery" aria-labelledby="detail-gallery-heading">'
        '<div class="section-heading">'
        '<p class="section-kicker">Additional Images</p>'
        '<h2 id="detail-gallery-heading">More views of the artwork</h2>'
        "</div>"
        f'<div class="detail-gallery__grid">{images}</div>'
        "</section>"
    )


def wrap_page(
    site: dict[str, Any],
    *,
    current_page: str,
    page_title: str,
    page_description: str,
    body_class: str,
    page_content: str,
) -> str:
    return render_template(
        "base.html",
        {
            "page_title": page_title,
            "page_description": escape_text(meta_description(page_description)),
            "css_url": build_url(site["base_path"], "static/css/site.css"),
            "js_url": build_url(site["base_path"], "static/js/gallery.js"),
            "body_class": escape_text(body_class),
            "home_url": build_url(site["base_path"], "", trailing_slash=True),
            "site_name": escape_text(site["site_name"]),
            "nav_links": nav_links(site, current_page),
            "page_content": page_content,
            "footer_content": render_footer(site),
        },
    )


def build_homepage(site: dict[str, Any], artworks: list[dict[str, Any]]) -> None:
    index_content = render_template(
        "index.html",
        {
            "artist_name": escape_text(site["artist_name"]),
            "tagline": escape_text(site["tagline"]),
            "intro": escape_text(site["intro"]),
            "featured_cards": render_featured_cards(artworks),
            "filter_controls": render_filter_controls(),
            "gallery_cards": render_gallery_cards(artworks),
        },
    )

    write_text(
        DIST_DIR / "index.html",
        wrap_page(
            site,
            current_page="home",
            page_title=site["site_name"],
            page_description=site["tagline"],
            body_class="page-home",
            page_content=index_content,
        ),
    )


def build_artwork_pages(site: dict[str, Any], artworks: list[dict[str, Any]]) -> None:
    for artwork in artworks:
        contact_subject = quote(f"Artwork enquiry: {artwork['title']}")
        detail_content = render_template(
            "artwork.html",
            {
                "home_url": build_url(site["base_path"], "", trailing_slash=True),
                "artwork_title": escape_text(artwork["title"]),
                "main_image_url": artwork["cover_url"],
                "artwork_type": escape_text(artwork["type_label"]),
                "availability_class": artwork["availability_class"],
                "availability_label": escape_text(artwork["availability_label"]),
                "artwork_price": escape_text(artwork["price_display"]),
                "artwork_dimensions": escape_text(artwork["dimensions"]),
                "artwork_description": artwork["description_html"],
                "contact_url": f"mailto:{escape_text(site['email'])}?subject={contact_subject}",
                "contact_label": "Contact about this artwork"
                if artwork["availability_key"] == "available"
                else "Ask about similar work",
                "additional_gallery_section": render_additional_gallery(artwork),
            },
        )

        write_text(
            artwork["output_path"],
            wrap_page(
                site,
                current_page="artwork",
                page_title=f"{artwork['title']} | {site['site_name']}",
                page_description=artwork["description"],
                body_class="page-artwork",
                page_content=detail_content,
            ),
        )


def build_about_page(site: dict[str, Any]) -> None:
    about_content = render_template(
        "about.html",
        {
            "tagline": escape_text(site["tagline"]),
            "about_content": paragraph_html(site["about"], "Add a short artist bio here."),
            "contact_details": render_contact_details(site),
        },
    )

    write_text(
        DIST_DIR / "about" / "index.html",
        wrap_page(
            site,
            current_page="about",
            page_title=f"About | {site['site_name']}",
            page_description=site["about"],
            body_class="page-about",
            page_content=about_content,
        ),
    )


def copy_static_assets() -> None:
    shutil.copytree(STATIC_DIR, DIST_DIR / "static", dirs_exist_ok=True)


def build_site() -> None:
    site = load_site()

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    ensure_directory(DIST_DIR)

    copy_static_assets()

    artworks = load_artworks(site["base_path"])
    build_homepage(site, artworks)
    build_artwork_pages(site, artworks)
    build_about_page(site)

    write_text(DIST_DIR / ".nojekyll", "")

    if site["custom_domain"]:
        write_text(DIST_DIR / "CNAME", str(site["custom_domain"]).strip() + "\n")

    print(f"Built {len(artworks)} artworks into {DIST_DIR}")


if __name__ == "__main__":
    build_site()
