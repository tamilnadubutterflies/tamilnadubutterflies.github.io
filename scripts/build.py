"""Build the static TNBS website into docs/."""
import hashlib
import json
import os
import re
import shutil
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
NAME = "The Nature and Butterfly Society"
ORIGINAL = "https://sites.google.com/view/tamilnadubutterflies"
CHECKLIST = "https://doi.org/10.13140/RG.2.2.15428.81287"
MAGAZINE = ORIGINAL + "/pattampoochi-magazine"
BUTTERFLY_VISION = "https://butterflyvision.in/"
FACEBOOK_GROUP = "https://www.facebook.com/groups/373700319460990/"
CONTACT = "tamilnadubutterflies@gmail.com"

CONFIG_URL = ROOT / "data" / "site-url.txt"
BASE = os.environ.get("SITE_URL", CONFIG_URL.read_text(encoding="utf-8").strip() if CONFIG_URL.exists() else "").strip()
if BASE:
    parts = urlsplit(BASE)
    if parts.scheme != "https" or not parts.hostname or parts.query or parts.fragment or parts.username or parts.password:
        raise SystemExit("Set SITE_URL to the full public HTTPS address of the site.")
    BASE = BASE.rstrip("/") + "/"


def load(name):
    return json.loads((ROOT / "data" / f"{name}.json").read_text(encoding="utf-8-sig"))


SPECIES = load("species")
PHOTOS = load("photos")
PROFILES = load("profiles")
TAXONOMY = load("taxonomy")
SITE = load("site")
MAGAZINE_INDEX = {item["issue"]: item for item in load("magazine_index")}
BY_SCI = {s["scientific"]: s for s in SPECIES}
BY_FAMILY = {}
for item in SPECIES:
    BY_FAMILY.setdefault(item["family"], []).append(item)

FAMILIES = {
    "Papilionidae": "Swallowtails",
    "Pieridae": "Whites and yellows",
    "Nymphalidae": "Brush-footed butterflies",
    "Lycaenidae": "Blues and hairstreaks",
    "Riodinidae": "Metalmarks",
    "Hesperiidae": "Skippers",
}
EXPECTED_FAMILY_COUNTS = {
    "Papilionidae": 19,
    "Pieridae": 32,
    "Nymphalidae": 97,
    "Riodinidae": 2,
    "Lycaenidae": 96,
    "Hesperiidae": 83,
}
NAV = {
    "": "Home",
    "butterflies/": "Field guide",
    "identify/": "AI Identify",
    "activities/": "Activities",
    "news/": "News & press",
    "magazine/": "Magazine",
    "quiz/": "Quiz",
    "about/": "About us",
}
FEATURED = ["Papilio crino", "Cirrochroa thais", "Troides minos"]
SPOTLIGHT_SPECIES = [
    "Papilio crino",
    "Cirrochroa thais",
    "Troides minos",
    "Tirumala limniace",
    "Talicada nyseus",
    "Cigaritis meghamalaiensis",
]
TAG_LABELS = {
    "state-butterfly": ("State butterfly", "highlight"),
    "wg-endemic": ("Western Ghats endemic", "endemic"),
    "migratory": ("Migratory in TN", "migratory"),
    "wpa-protected": ("WPA protected", "protected"),
    "issue-27-addition": ("Recent addition", "new"),
}
PAGES = []


def h(value):
    return escape(str(value), quote=True)


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def route(species):
    return "butterflies/" + slug(species["scientific"]) + "/"


def link(label, url, style="", external=False):
    cls = f' class="{h(style)}"' if style else ""
    rel = ' target="_blank" rel="noopener noreferrer"' if external or url.startswith("http") else ""
    return f'<a{cls} href="{h(url)}"{rel}>{h(label)}</a>'


def local(prefix, path=""):
    return prefix + path + "index.html"


def license_info(license_id):
    if license_id == "cc0/1.0":
        return ("https://creativecommons.org/publicdomain/zero/1.0/", "CC0 1.0")
    if license_id == "pdm/1.0":
        return ("https://creativecommons.org/publicdomain/mark/1.0/", "Public Domain")
    return (
        "https://creativecommons.org/licenses/" + license_id + "/",
        "CC " + license_id.replace("/", " ").upper(),
    )


def photo_meta(scientific, prefix, thumb=False):
    rec = PHOTOS[scientific]
    if isinstance(rec, dict):
        if rec.get("source") == "local":
            return {
                "src": prefix + rec["file"],
                "alt": rec["alt"],
                "author": rec["author"],
                "url": rec.get("url", ""),
                "license": "",
                "licenseName": rec.get("licenseName", "TNBS Member Archive"),
                "sourceLabel": "",
                "member": bool(rec.get("member", True)),
            }
        lic_url, lic_name = license_info(rec["license"])
        if rec.get("source") == "inaturalist":
            return {
                "src": rec["thumb"] if thumb else rec["full"],
                "alt": rec["alt"],
                "author": rec["author"],
                "url": rec["url"],
                "license": lic_url,
                "licenseName": lic_name,
                "sourceLabel": "iNaturalist observation",
                "member": bool(rec.get("member")),
            }
        filename = rec["file"]
        author = rec["author"]
        alt = rec["alt"]
        width = int(rec.get("width") or 0)
        is_member = bool(rec.get("member"))
    else:
        filename, author, license_id, alt, width = rec
        lic_url, lic_name = license_info(license_id)
        is_member = False

    wiki_name = filename.replace(" ", "_")
    digest = hashlib.md5(wiki_name.encode(), usedforsecurity=False).hexdigest()
    media_path = f"{digest[0]}/{digest[:2]}/{quote(wiki_name)}"
    chosen_width = min(width, 500) if thumb and width else (width if width else 0)
    src = f"https://upload.wikimedia.org/wikipedia/commons/{media_path}"
    if chosen_width:
        src = f"https://upload.wikimedia.org/wikipedia/commons/thumb/{media_path}/{chosen_width}px-{quote(wiki_name)}"
    cached = Path("photos") / (slug(scientific) + ".jpg")
    if (ROOT / "assets" / cached).exists():
        src = prefix + "assets/" + cached.as_posix()
    return {
        "src": src,
        "alt": alt,
        "author": author,
        "url": "https://commons.wikimedia.org/wiki/File:" + quote(wiki_name),
        "license": lic_url,
        "licenseName": lic_name,
        "sourceLabel": "Commons file",
        "member": is_member,
    }


def credit_html(meta, include_source=False):
    parts = [link(meta["author"], meta["url"]) if meta["url"] else h(meta["author"])]
    if meta["licenseName"]:
        parts.append(link(meta["licenseName"], meta["license"]) if meta["license"] else h(meta["licenseName"]))
    if include_source and meta["url"] and meta["sourceLabel"]:
        parts.append(link(meta["sourceLabel"], meta["url"]))
    return " · ".join(parts)


def photo(scientific, prefix, mode="card"):
    if scientific not in PHOTOS:
        return ""
    meta = photo_meta(scientific, prefix, thumb=(mode == "card"))
    species_name = BY_SCI[scientific]["name"]
    if mode == "hero":
        dims = ' width="1024" height="682"' if scientific == "Papilio crino" else ""
        return (
            f'<figure class="hero-media"><img class="hide-on-error" src="{h(meta["src"])}" '
            f'alt="{h(meta["alt"])}" fetchpriority="high" decoding="async"{dims}></figure>'
            f'<span class="hero-credit">{h(species_name)} · {credit_html(meta)}</span>'
        )
    credit = credit_html(meta)
    if mode == "card":
        return (
            f'<div class="media bare"><img class="hide-on-error" src="{h(meta["src"])}" '
            f'alt="{h(meta["alt"])}" loading="lazy" decoding="async"></div>'
            f'<p class="credit">{credit}</p>'
        )
    full_meta = photo_meta(scientific, prefix, thumb=False)
    zoom_btn = (
        f'<button type="button" class="photo-zoom" data-lightbox-src="{h(full_meta["src"])}" '
        f'data-lightbox-title="{h(species_name)} ({h(scientific)})" '
        f'data-lightbox-alt="{h(full_meta["alt"])}" '
        f'data-lightbox-author="{h(full_meta["author"])}" '
        f'data-lightbox-url="{h(full_meta["url"])}" '
        f'data-lightbox-license="{h(full_meta["license"])}" '
        f'data-lightbox-licensename="{h(full_meta["licenseName"])}" '
        f'aria-label="Inspect full-size photograph of {h(species_name)}">'
        f'<img class="hide-on-error" src="{h(meta["src"])}" alt="{h(meta["alt"])}" decoding="async">'
        f'<span class="zoom-hint" aria-hidden="true">Click to enlarge</span></button>'
    )
    return (
        f'<figure class="photo-large">{zoom_btn}'
        f'<figcaption class="credit">{credit_html(meta, include_source=True)}</figcaption></figure>'
    )


def lightbox_button_img(src, alt, title, caption, prefix, width=1200, height=800, img_class=""):
    cls_attr = f' class="{h(img_class)}"' if img_class else ""
    return (
        f'<button type="button" class="photo-zoom gallery-zoom" '
        f'data-lightbox-src="{h(prefix + src)}" '
        f'data-lightbox-title="{h(title)}" '
        f'data-lightbox-alt="{h(alt)}" '
        f'data-lightbox-caption="{h(caption)}" '
        f'aria-label="Enlarge photograph: {h(title)}">'
        f'<img{cls_attr} src="{h(prefix + src)}" alt="{h(alt)}" width="{width}" height="{height}" loading="lazy" decoding="async">'
        f'</button>'
    )


def identity(prefix, is_footer=False):
    lazy_attr = ' loading="lazy"' if is_footer else ""
    return (
        f'<a class="identity" href="{local(prefix)}">'
        f'<img class="brand-logo" src="{prefix}assets/tnbs-logo.png" alt="" width="48" height="48"{lazy_attr}>'
        '<span><strong>The Nature and Butterfly Society</strong><small>TNBS · TAMIL NADU, INDIA</small></span></a>'
    )


def lightbox_dialog():
    return """<dialog id="lightbox" class="lightbox" closedby="any" aria-labelledby="lightbox-title">
<div class="lightbox-frame"><div class="lightbox-head">
<div><h1 id="lightbox-title" class="lightbox-heading">Butterfly photograph</h1>
<p id="lightbox-sub" class="caption"></p></div>
<form method="dialog"><button type="submit" class="button outline lightbox-close" aria-label="Close enlarged photograph">Close</button></form>
</div><div class="lightbox-stage"><img id="lightbox-img" src="" alt=""></div>
<p id="lightbox-credit" class="credit"></p></div></dialog>"""


def render(path, title, description, body, active=None, image_key=None, schema=None):
    prefix = "../" * path.count("/") if path.endswith("/") else ""
    display_title = title + " | TNBS" if path else title
    url = BASE + path if BASE else ""
    canonical = f'<link rel="canonical" href="{h(url)}"><meta property="og:url" content="{h(url)}">' if url else ""
    cover = ""
    if image_key and image_key in PHOTOS:
        media = photo_meta(image_key, prefix)
        img = media["src"]
        if not img.startswith("https://") and BASE:
            img = BASE + img.removeprefix(prefix)
        if img.startswith("https://"):
            cover = f'<meta property="og:image" content="{h(img)}"><meta property="og:image:alt" content="{h(media["alt"])}">'
    structured = ""
    if schema:
        data = {"@context": "https://schema.org", **schema}
        if url:
            data["url"] = url
        if BASE and data.get("@type") == "Organization":
            data["logo"] = BASE + "assets/tnbs-logo.png"
        structured = '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False).replace("<", "\\u003c") + "</script>"
    nav_links = []
    for dest, label in NAV.items():
        current = ' aria-current="page"' if dest == (path if active is None else active) else ""
        nav_links.append(f'<a href="{local(prefix, dest)}"{current}>{h(label)}</a>')
    nav_links.append(link("Get involved", local(prefix, "about/") + "#get-involved", "small-button"))
    crawl = '<meta name="robots" content="noindex">' if path == "404.html" else ""
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{h(display_title)}</title><meta name="description" content="{h(description)}">
<meta property="og:site_name" content="{NAME}"><meta property="og:type" content="website">
<meta property="og:title" content="{h(display_title)}"><meta property="og:description" content="{h(description)}">{canonical}{cover}{crawl}
<meta name="twitter:card" content="{'summary_large_image' if cover else 'summary'}">
<link rel="icon" href="{prefix}assets/tnbs-logo.png" type="image/png">
<link rel="apple-touch-icon" href="{prefix}assets/tnbs-logo.png">
<link rel="stylesheet" href="{prefix}assets/site.css"><script defer src="{prefix}assets/site.js"></script>{structured}
</head><body id="top">
<a class="skip" href="#main">Skip to content</a>
<header class="masthead"><div class="wrap">{identity(prefix)}
<button type="button" class="nav-toggle" aria-expanded="false" aria-controls="primary">Menu</button>
<nav id="primary" class="nav" aria-label="Main navigation">{"".join(nav_links)}</nav></div></header>
<main id="main">{body}</main>
<footer class="footer"><div class="wrap"><div class="footer-cols"><div>{identity(prefix, is_footer=True)}<p>Documenting butterflies across Tamil Nadu since 2014.</p></div>
<nav aria-label="Explore">{link("Field guide", local(prefix, "butterflies/"))}{link("Butterfly Vision AI", local(prefix, "identify/"))}{link("Interactive quiz", local(prefix, "quiz/"))}{link("Pattampoochi magazine", local(prefix, "magazine/"))}</nav>
<nav aria-label="Society">{link("About us", local(prefix, "about/"))}{link("Activities & fieldwork", local(prefix, "activities/"))}{link("News & press", local(prefix, "news/"))}{link("Sources & photo credits", local(prefix, "sources/"))}</nav>
<nav aria-label="Connect">{link("Get involved", local(prefix, "about/") + "#get-involved")}{link(CONTACT, "mailto:" + CONTACT)}{link("Tamil Nadu Butterflies Facebook", FACEBOOK_GROUP)}{link("Original Google Site", ORIGINAL)}</nav></div>
<div class="footer-bottom"><small>© <span data-year>{date.today().year}</span> {NAME} · Reg. No. 259/2018 · Coimbatore, Tamil Nadu</small></div></div></footer>
<a class="back-top" href="#top" data-back-top hidden aria-label="Back to top">↑ Top</a>
{lightbox_dialog()}
</body></html>"""
    target = OUT / (path if path == "404.html" else path + "index.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    if path != "404.html":
        PAGES.append(path)


def heading(title, description, kicker=""):
    label = f'<p class="kicker">{h(kicker)}</p>' if kicker else ""
    return f'<header class="page-head"><div class="wrap">{label}<h1>{h(title)}</h1><p class="lede">{h(description)}</p></div></header>'


def species_badges_html(entry, compact=False):
    pills = []
    for tag in entry.get("tags", []):
        if tag in TAG_LABELS:
            label, cls = TAG_LABELS[tag]
            if compact and len(pills) >= 2:
                break
            pills.append(f'<span class="tag tag-{cls}">{h(label)}</span>')
    if not compact:
        if entry.get("validated", True):
            pills.append('<span class="tag tag-valid">Validated in TN</span>')
        else:
            pills.append('<span class="tag tag-pending">Awaiting TN validation</span>')
        for m in entry.get("butterflyVision", []):
            pills.append(f'<span class="tag tag-bv">BV: {"WG" if m == "wg" else "India"}</span>')
    elif entry.get("butterflyVision") and len(pills) < 2:
        pills.append('<span class="tag tag-bv">AI ID</span>')
    return '<div class="tag-row">' + "".join(pills) + "</div>" if pills else ""


def is_member_photo(scientific):
    rec = PHOTOS.get(scientific)
    return isinstance(rec, dict) and bool(rec.get("member"))


def species_card(entry, prefix, include_spot_btn=False):
    name, scientific, family, subfamily = (entry[key] for key in ("name", "scientific", "family", "subfamily"))
    prof = PROFILES.get(scientific, {})
    host_terms = " ".join(prof.get("hostPlants", [])) if isinstance(prof, dict) else ""
    tag_terms = " ".join(entry.get("tags", []))
    bv_terms = " ".join(entry.get("butterflyVision", []))
    val_term = "validated" if entry.get("validated", True) else "unvalidated pending"
    member_flag = int(is_member_photo(scientific))
    author_term = PHOTOS[scientific].get("author", "") if isinstance(PHOTOS.get(scientific), dict) else (PHOTOS[scientific][1] if scientific in PHOTOS else "")
    terms = " ".join([name, scientific, family, FAMILIES[family], subfamily, *entry["aliases"], host_terms, tag_terms, bv_terms, val_term, author_term])
    has_photo = int(scientific in PHOTOS)
    has_profile = int(scientific in PROFILES)
    spot_btn = ""
    if include_spot_btn:
        spot_btn = (
            f'<div class="card-foot"><button type="button" class="spot-btn" data-spot-btn data-sci="{h(scientific)}" '
            f'aria-pressed="false" aria-label="Mark {h(name)} as spotted in Tamil Nadu">+ Spotted</button></div>'
        )
    return (
        f'<article class="card reveal" data-species data-id="{entry["id"]}" data-name="{h(name.casefold())}" '
        f'data-sci="{h(scientific.casefold())}" data-family="{h(family)}" data-subfamily="{h(subfamily)}" '
        f'data-terms="{h(terms)}" data-photo="{has_photo}" data-member="{member_flag}" data-profile="{has_profile}" '
        f'data-validated="{int(entry.get("validated", True))}" data-tags="{h(tag_terms)}" data-bv="{h(bv_terms)}">'
        f'{photo(scientific, prefix)}<div class="card-body">'
        f'<p class="card-meta">{h(family)} · {h(subfamily)}</p>'
        f'<h3>{link(name, local(prefix, route(entry)))}</h3>'
        f'<p class="scientific">{h(scientific)}</p>'
        f'{species_badges_html(entry, compact=True)}'
        f'{spot_btn}'
        f'</div></article>'
    )


def issue_url(number):
    key, separator, query = SITE["issues"][number - 1].partition("?")
    return f"https://drive.google.com/file/d/{key}/view{separator}{query}"


def cover():
    return (
        '<div class="issue-cover" aria-hidden="true"><div><p class="cover-tamil" lang="ta">பட்டாம்பூச்சி</p>'
        '<p class="cover-title">Pattampoochi</p></div>'
        '<p class="cover-details">Issue 27 · Wings 9 · Veins 1<br>January-March 2025</p></div>'
    )


def press_card(story, prefix=""):
    day = story["date"]
    when = date.fromisoformat(day).strftime("%d %b %Y").lstrip("0")
    sp_badge = ""
    if story.get("species") and story["species"] in BY_SCI:
        sp = BY_SCI[story["species"]]
        sp_badge = f' · {link(sp["name"], local(prefix, route(sp)), "press-species")}'
    terms = " ".join([story["title"], story["summary"], story["source"], story["category"], story.get("species", "")])
    return (
        f'<li class="news-card reveal" data-record data-kind="Press" data-category="{h(story["category"])}" '
        f'data-source="{h(story["source"])}" data-year="{day[:4]}" data-terms="{h(terms)}">'
        f'<div class="news-card-meta"><span class="tag tag-bv">{h(story["category"])}</span>'
        f'<span class="card-meta">{h(story["source"])} · <time datetime="{day}">{when}</time></span></div>'
        f'<h3>{link(story["title"], story["url"])}</h3>'
        f'<p>{h(story["summary"])}</p>'
        f'<p class="news-card-foot">{link("Read full article ↗", story["url"])}{sp_badge}</p></li>'
    )


def home_spotlight_section():
    payload = []
    buttons = []
    for idx, sci in enumerate(SPOTLIGHT_SPECIES):
        sp = BY_SCI[sci]
        prof = PROFILES.get(sci, {})
        meta = photo_meta(sci, "", thumb=False)
        payload.append({
            "name": sp["name"],
            "scientific": sci,
            "family": f'{sp["family"]} ({sp["subfamily"]})',
            "headline": prof.get("headline", ""),
            "wingspan": prof.get("wingspan", "Field guide entry"),
            "hosts": ", ".join(prof.get("hostPlants", [])[:2]) or "Tamil Nadu checklist species",
            "range": prof.get("tnDistribution", "Recorded across Tamil Nadu habitats."),
            "url": local("", route(sp)),
            "src": meta["src"],
            "alt": meta["alt"],
            "author": meta["author"],
            "authorUrl": meta["url"],
            "licenseName": meta["licenseName"],
            "licenseUrl": meta["license"],
        })
        pressed = "true" if idx == 0 else "false"
        buttons.append(
            f'<button type="button" class="choice" data-spot-idx="{idx}" aria-pressed="{pressed}">{h(sp["name"])}</button>'
        )
    first = payload[0]
    return f"""<section class="spotlight-band"><div class="wrap section">
<div class="section-head"><div><p class="kicker">Interactive Species Explorer</p>
<h2>Flagship butterflies of Tamil Nadu</h2></div>
<div class="choices" role="group" aria-label="Choose a flagship species">{"".join(buttons)}</div></div>
<div class="spotlight-card" data-spotlight="{h(json.dumps(payload, ensure_ascii=False))}">
<div class="spotlight-media">
<button type="button" class="photo-zoom" data-spot-zoom data-lightbox-src="{h(first["src"])}" data-lightbox-title="{h(first["name"])} ({h(first["scientific"])})" data-lightbox-alt="{h(first["alt"])}" data-lightbox-author="{h(first["author"])}" data-lightbox-url="{h(first["authorUrl"])}" data-lightbox-license="{h(first["licenseUrl"])}" data-lightbox-licensename="{h(first["licenseName"])}" aria-label="Enlarge spotlight photograph">
<img data-spot-img src="{h(first["src"])}" alt="{h(first["alt"])}" loading="lazy" decoding="async">
<span class="zoom-hint" aria-hidden="true">Zoom</span></button>
<p class="credit" data-spot-credit>{credit_html({"author": first["author"], "url": first["authorUrl"], "licenseName": first["licenseName"], "license": first["licenseUrl"]})}</p></div>
<div class="spotlight-copy">
<p class="card-meta" data-spot-family>{h(first["family"])}</p>
<h3 data-spot-name>{h(first["name"])}</h3>
<p class="scientific" data-spot-sci>{h(first["scientific"])}</p>
<p class="lede" data-spot-headline>{h(first["headline"])}</p>
<dl class="mini-stats"><div><dt>Wingspan</dt><dd data-spot-wingspan>{h(first["wingspan"])}</dd></div>
<div><dt>Larval host plants</dt><dd data-spot-hosts>{h(first["hosts"])}</dd></div></dl>
<p class="spot-range" data-spot-range>{h(first["range"])}</p>
<div class="actions"><a class="button" data-spot-link href="{h(first["url"])}">Open full species profile →</a>
{link("Explore all 329 species", "butterflies/index.html", "button outline")}</div>
</div></div></div></section>"""


def home_hotspots_tabs():
    tab_buttons = []
    tab_panels = []
    for idx, region in enumerate(SITE["hotspots"]):
        tid = f'tab-{region["id"]}'
        selected = "true" if idx == 0 else "false"
        hidden_attr = "" if idx == 0 else ' hidden="until-found"'
        tabindex_attr = ' tabindex="0"' if idx == 0 else ""
        tab_buttons.append(
            f'<button type="button" role="tab" id="{tid}" aria-selected="{selected}">{h(region["label"])}</button>'
        )
        cards_html = []
        for card in region["cards"]:
            sp_link = ""
            if card.get("species") and card["species"] in BY_SCI:
                sp = BY_SCI[card["species"]]
                sp_link = link(f'{sp["name"]} profile', local("", route(sp)), "tag tag-bv")
            cards_html.append(
                f'<article class="card"><div class="card-body">'
                f'<p class="card-meta">{h(card["stat"])}</p>'
                f'<h3>{h(card["place"])}</h3>'
                f'<p>{h(card["summary"])}</p>'
                f'<div class="actions-inline">{sp_link}{link("Read press coverage ↗", card["pressUrl"])}</div>'
                f'</div></article>'
            )
        tab_panels.append(
            f'<div role="tabpanel" aria-labelledby="{tid}"{tabindex_attr}{hidden_attr}>'
            f'<div class="tabpanel-inner"><div class="tabpanel-head"><h3>{h(region["headline"])}</h3>'
            f'<p class="lede">{h(region["intro"])}</p></div>'
            f'<div class="grid">{"".join(cards_html)}</div></div></div>'
        )
    return f"""<section class="wrap section" data-tabs>
<div class="section-head"><div><p class="kicker">Biodiversity &amp; Migration</p>
<h2>Tamil Nadu butterfly hotspots &amp; corridors</h2>
<p class="lede">Switch tabs to inspect Western Ghats sanctuaries, Eastern Ghats surveys, urban Coimbatore wetlands, and seasonal Danainae migration routes.</p></div>
{link("View all fieldwork", "activities/index.html", "button outline")}</div>
<div class="tablist" role="tablist" aria-label="Tamil Nadu butterfly hotspots and migration corridors">{"".join(tab_buttons)}</div>
<div class="tabpanels">{"".join(tab_panels)}</div>
</section>"""


def home():
    validated_count = sum(1 for s in SPECIES if s.get("validated", True))
    hero_media = (
        '<figure class="hero-media"><img class="hide-on-error" src="assets/photos/home-hero-crino.jpg" '
        'alt="Common Banded Peacock (Papilio crino) basking with open emerald-green and turquoise-banded wings on green foliage, photographed by Pavendhan A" '
        'fetchpriority="high" decoding="async" width="1024" height="682"></figure>'
        '<span class="hero-credit">Common Banded Peacock (<i>Papilio crino</i>) · Photo: Pavendhan A (TNBS)</span>'
    )
    hero = f"""<section class="hero"><div class="wrap hero-inner">{hero_media}
<div class="hero-copy"><p class="kicker">The Nature and Butterfly Society · Tamil Nadu</p><h1>Butterflies of<br><em>Tamil Nadu</em></h1>
<p>Explore Tamil Nadu's {len(SPECIES)}-species butterfly field guide with detailed profiles and verified photos, identify sightings with Butterfly Vision AI, and follow conservation fieldwork across the state.</p>
<search class="hero-search"><form action="butterflies/index.html" method="get" class="hero-search-form">
<label for="hero-q" class="visually-hidden">Search 329 Tamil Nadu butterflies</label>
<input id="hero-q" type="search" name="q" placeholder="Quick search: Peacock, Yeoman, Blue Tiger, Papilio...">
<button type="submit" class="button light">Find butterfly</button>
</form></search>
<div class="actions">{link("Explore field guide","butterflies/index.html","button outline")}{link("Identify with AI","identify/index.html","button outline")}{link("Take interactive quiz","quiz/index.html","button outline")}</div></div></div></section>
<div class="band"><div class="wrap"><ul class="stats stats-4">
<li><strong>{len(SPECIES)}</strong><span>Butterfly species recorded in Tamil Nadu ({validated_count} validated)</span></li>
<li><strong>{len(FAMILIES)}</strong><span>Butterfly families across {len(TAXONOMY["subfamilies"])} subfamilies</span></li>
<li><strong>{len(SITE["issues"])}</strong><span>Pattampoochi magazine issues</span></li>
<li><strong>{h(SITE["butterflyVision"]["supportedTotal"])}</strong><span>Species covered on Butterfly Vision AI</span></li></ul></div></div>"""

    family_chips = "".join(
        f'<a class="chip-link" href="butterflies/index.html?family={h(fam)}">{h(fam)} <span>({EXPECTED_FAMILY_COUNTS[fam]})</span></a>'
        for fam in FAMILIES
    )
    member_photo_count = sum(1 for s in SPECIES if is_member_photo(s["scientific"]))
    guide_sec = f"""<section class="wrap section"><div class="section-head"><div><p class="kicker">Tamil Nadu field guide</p>
<h2>Which butterfly did you see?</h2><p class="lede">Search {len(SPECIES)} species by common name, scientific name, subfamily, host plant, or photographer, complete with detailed species profiles and {len(PHOTOS)} verified photos (including {member_photo_count} by TNBS members).</p></div>{link("Browse all 329 species","butterflies/index.html","button outline")}</div>
<div class="chip-row" aria-label="Browse by family">{family_chips}</div>
<div class="grid">{"".join(species_card(BY_SCI[x], "") for x in FEATURED)}</div></section>"""

    spotlight_sec = home_spotlight_section()
    hotspots_sec = home_hotspots_tabs()

    bv_meta = SITE["butterflyVision"]
    bv_sec = f"""<section class="ai-spotlight"><div class="wrap section split">
<div><p class="kicker">AI Butterfly Identification</p><h2>Butterfly Vision integration</h2>
<p class="lede">Upload a field photograph to identify Indian butterflies in seconds using deep convolutional neural networks developed by TNBS member Theivaprakasham Hari.</p>
<ul class="bullet-list">
<li><strong>Western Ghats Model:</strong> {h(bv_meta["wgCount"])} regional species including {sum(1 for s in SPECIES if "wg" in s.get("butterflyVision", []))} species on the Tamil Nadu checklist.</li>
<li><strong>All India Model:</strong> {h(bv_meta["indiaCount"])} Indian species ({h(bv_meta["supportedTotal"])} total taxa) with {h(bv_meta["accuracy"])} average accuracy.</li>
<li><strong>Interactive crop &amp; feedback loop:</strong> Fine-tune framing before re-identifying and help improve accuracy toward 95%+.</li></ul>
<div class="actions">{link("Launch AI identifier","identify/index.html","button")}{link("Visit butterflyvision.in",BUTTERFLY_VISION,"button outline")}</div></div>
<div class="ai-card reveal"><p class="card-meta">Deep Learning × Citizen Science</p>
<h3>Snap. Upload. Identify.</h3>
<p>Every TNBS field guide species card links directly to Butterfly Vision model coverage, helping newcomers, students, and survey volunteers verify sightings faster in the field.</p>
<dl class="mini-stats"><div><dt>TN species covered</dt><dd>{sum(1 for s in SPECIES if s.get("butterflyVision"))} / {len(SPECIES)}</dd></div>
<div><dt>Published science</dt><dd>5 peer-reviewed papers &amp; repos</dd></div></dl>
</div></div></section>"""

    about_photos = SITE["about"]["photos"][:3]
    about_gallery = "".join(
        f'<figure class="gallery-card reveal">{lightbox_button_img(p["src"], p["caption"], p["title"], p["caption"], "", p["width"], p["height"])}'
        f'<figcaption><strong>{h(p["title"])}</strong> · <span>{h(p["when"])}</span><br><small>{h(p["caption"])}</small></figcaption></figure>'
        for p in about_photos
    )
    about_sec = f"""<section id="about-us" class="section about-home"><div class="wrap">
<div class="section-head"><div><p class="kicker">Who we are</p><h2>About us</h2>
<p class="lede">The Nature and Butterfly Society (TNBS) is a registered Coimbatore-based citizen-science society ({h(SITE["about"]["registration"])}) uniting naturalists, researchers, students, and forest partners to document butterflies across Tamil Nadu.</p></div>
<div class="about-emblem"><img src="assets/tnbs-logo.png" alt="Official emblem of The Nature and Butterfly Society featuring the Common Banded Peacock" width="96" height="96" loading="lazy"></div></div>
<div class="split about-story"><div>
<p>What began in 2012-2014 as an effort to build Tamil Nadu's first dedicated state checklist has grown into a thriving community of {h(SITE["about"]["facebookGroup"])}.</p>
<p>From joint monsoon surveys in Mudumalai Tiger Reserve and Pachamalai Hills to tracking cross-state tiger and crow migrations and distributing free Tamil butterfly posters to government schools, TNBS turns careful field observations into open conservation knowledge.</p>
<div class="actions">{link("Read our full story & team","about/index.html","button")}{link("Explore fieldwork & surveys","activities/index.html","button outline")}</div></div>
<ul class="milestone-compact">{"".join(f'<li><strong>{h(yr)}</strong><span>{h(desc)}</span></li>' for yr, desc in SITE["about"]["milestones"][:4])}</ul></div>
<div class="grid gallery-grid">{about_gallery}</div></div></section>"""

    total_indexed = sum(len(MAGAZINE_INDEX[n]["articles"]) for n in MAGAZINE_INDEX)
    journal = f"""<section class="journal"><div class="wrap section split">{cover()}<div>
<p class="kicker">The society's quarterly magazine</p><h2>Pattampoochi</h2>
<p class="lede">Browse 27 quarterly issues and {total_indexed} indexed articles covering the 2024 Danainae migration report, Mudumalai and Pachamalai Forest Division surveys, life-cycle studies, school outreach, and state butterfly updates.</p>
<div class="actions">{link("Browse all 27 issues & article index","magazine/index.html","button")}{link("Read latest issue (No. 27) PDF",issue_url(27),"button outline")}</div></div></div></section>"""

    # Top 6 diverse recent press & magazine reports
    press_preview = "".join(press_card(s, "") for s in SITE["press"][:6])
    elsewhere_cards = "".join(
        f'<article class="card community-card reveal"><div class="card-body"><p class="card-meta">{h(c["badge"])}</p>'
        f'<h3>{link(c["title"], c["url"])}</h3><p>{h(c["summary"])}</p>'
        f'<p>{link(c["cta"] + " ↗", c["url"], "small-button")}</p></div></article>'
        for c in SITE["community"][:3]
    )
    updates = f"""<section class="wrap section"><div class="section-head"><div><p class="kicker">News, magazine reports &amp; press ({len(SITE["press"])} entries)</p><h2>Recently in the press</h2></div>
{link(f"Explore all {len(SITE['press'])} reports","news/index.html","button outline")}</div>
<ul class="news-grid">{press_preview}</ul>
<div class="elsewhere-block"><div class="section-head"><div><p class="kicker">Community &amp; External Portals</p><h3>Elsewhere on the web</h3></div>
{link("See all community links","news/index.html#elsewhere","button outline")}</div>
<div class="grid">{elsewhere_cards}</div></div></section>"""

    cta = f"""<section class="dark"><div class="wrap compact"><p class="kicker">Get involved</p><h2>Share a butterfly sighting</h2>
<p class="lede">A photograph, a date, and a locality turn a casual observation into scientific data, especially for the four checklist species still awaiting validated Tamil Nadu photographic records.</p>
<div class="actions">{link("How to contribute","about/index.html#get-involved","button light")}{link("Test yourself in the quiz","quiz/index.html","button outline")}</div></div></section>"""

    render(
        "",
        "Butterflies of Tamil Nadu | The Nature and Butterfly Society",
        "Official website of The Nature and Butterfly Society (TNBS). Explore Tamil Nadu's 329-species butterfly field guide with full profiles, Butterfly Vision AI identification, interactive quiz, hotspots, and TNBS press & magazine reports.",
        hero + guide_sec + spotlight_sec + hotspots_sec + bv_sec + about_sec + journal + updates + cta,
        image_key="Papilio crino",
        schema={"@type": "Organization", "name": NAME, "alternateName": "TNBS", "email": CONTACT, "sameAs": [ORIGINAL, BUTTERFLY_VISION, FACEBOOK_GROUP]},
    )


def guide():
    family_options = "".join(f'<option value="{f}">{f} · {h(common)} ({EXPECTED_FAMILY_COUNTS[f]})</option>' for f, common in FAMILIES.items())
    subfamilies = sorted({s["subfamily"] for s in SPECIES})
    subfamily_options = "".join(f'<option value="{sf}">{h(sf)}: {h(TAXONOMY["subfamilies"][sf]["group"])}</option>' for sf in subfamilies)
    cards = sorted(SPECIES, key=lambda x: (x["scientific"] not in PHOTOS, not is_member_photo(x["scientific"]), x["scientific"] not in PROFILES, x["name"].casefold()))
    photo_count = sum(1 for s in SPECIES if s["scientific"] in PHOTOS)
    member_count = sum(1 for s in SPECIES if is_member_photo(s["scientific"]))
    profile_count = sum(1 for s in SPECIES if s["scientific"] in PROFILES)

    family_pills = ['<button type="button" class="choice" data-family-pill="" aria-pressed="true">All 329</button>']
    for fam in FAMILIES:
        family_pills.append(
            f'<button type="button" class="choice" data-family-pill="{h(fam)}" aria-pressed="false">{h(fam)} ({EXPECTED_FAMILY_COUNTS[fam]})</button>'
        )

    body = heading(
        "Butterflies of Tamil Nadu",
        f"{len(SPECIES)} Tamil Nadu butterfly species across {len(FAMILIES)} families and {len(subfamilies)} subfamilies ({photo_count} with verified photographs, {member_count} by TNBS members, {profile_count} with detailed field profiles).",
        "Field guide",
    )
    body += f"""<div class="wrap section" data-guide>
<div class="lifelist-bar" data-lifelist-bar data-enhancement hidden>
<div class="lifelist-info"><strong>My Tamil Nadu Life List:</strong> <span data-lifelist-count>0 / {len(SPECIES)} spotted (0%)</span>
<progress class="lifelist-progress" max="{len(SPECIES)}" value="0" aria-label="Spotted species progress"></progress></div>
<div class="actions-inline">
<button type="button" class="choice" data-spotted-filter aria-pressed="false">My spotted only</button>
<button type="button" class="choice" data-copy-lifelist>Copy life list</button>
<button type="button" class="button compact-btn" data-surprise-btn>Surprise me</button>
</div></div>
<p role="status" aria-live="polite" class="caption" data-lifelist-status></p>

<div class="guide-banner">
<div><strong>Got a butterfly photo you can't match yet?</strong> <span>Identify it in seconds with Butterfly Vision's Western Ghats &amp; All India AI models ({sum(1 for s in SPECIES if s.get("butterflyVision"))}/{len(SPECIES)} TN species supported).</span></div>
<div class="actions-inline">{link("Open AI Identify tool","../identify/index.html","small-button")}{link("butterflyvision.in",BUTTERFLY_VISION,"button outline compact-btn")}</div>
</div>

<div data-enhancement hidden>
<div class="choices family-pills" role="group" aria-label="Quick filter by butterfly family">{"".join(family_pills)}</div>
<search><form class="filters">
<div class="field grow"><label for="guide-q">Search butterflies</label><input id="guide-q" type="search" name="q" placeholder="Name, scientific name, subfamily, host plant, photographer..."></div>
<div class="field"><label for="guide-family">Family</label><select id="guide-family" name="family"><option value="">All families (329)</option>{family_options}</select></div>
<div class="field"><label for="guide-subfamily">Subfamily</label><select id="guide-subfamily" name="subfamily"><option value="">All subfamilies (21)</option>{subfamily_options}</select></div>
<div class="field"><label for="guide-tag">Highlight / Filter</label><select id="guide-tag" name="tag">
<option value="">All entries</option>
<option value="spotted">My spotted butterflies</option>
<option value="member">Photographed by TNBS members ({member_count})</option>
<option value="photo">With verified photo ({photo_count})</option>
<option value="wg-endemic">Western Ghats endemic</option>
<option value="migratory">Migratory in Tamil Nadu</option>
<option value="wpa-protected">WPA protected species</option>
<option value="issue-27-addition">Recent state additions (2)</option>
<option value="unvalidated">Awaiting TN validation (4)</option>
<option value="bv">Butterfly Vision AI supported</option>
</select></div>
<div class="field"><label for="guide-sort">Sort by</label><select id="guide-sort" name="sort">
<option value="featured">Photos &amp; TNBS members first</option>
<option value="name">Common name (A-Z)</option>
<option value="sci">Scientific name (A-Z)</option>
<option value="id">Checklist order (#1-329)</option>
</select></div>
<button type="reset" class="button outline">Clear filters</button></form></search>
<div class="guide-tools"><p role="status" aria-live="polite" data-results></p><div class="choices" aria-label="View options">
<button class="choice" type="button" data-view="grid" aria-pressed="true">Cards</button>
<button class="choice" type="button" data-view="list" aria-pressed="false">List</button></div></div></div>
<noscript><p class="notice">All {len(SPECIES)} butterflies of Tamil Nadu are listed below. Use your browser's find command to search names.</p></noscript>
<p class="notice" data-empty hidden>No butterflies match those filters. Try clearing a filter or searching another name.</p>
<div class="grid guide-grid" data-cards>{"".join(species_card(s, "../", include_spot_btn=True) for s in cards)}</div>
<button type="button" class="button outline more" data-more hidden>Show more species</button>
<p class="caption actions">Checklist history, family counts, research papers, and photo credits are listed on the {link("sources page","../sources/index.html")}.</p></div>"""
    render(
        "butterflies/",
        "Butterflies of Tamil Nadu field guide",
        f"Search all {len(SPECIES)} Tamil Nadu butterflies, track your personal Life List, filter by family, subfamily, or TNBS member photographs, and read detailed field profiles.",
        body,
        image_key="Papilio crino",
    )


def species_press_mentions(scientific, name):
    matches = []
    for story in SITE["press"]:
        if story.get("species") == scientific or name.lower() in (story["title"] + " " + story["summary"]).lower():
            when = date.fromisoformat(story["date"]).strftime("%d %b %Y").lstrip("0")
            matches.append(f'<li><strong>{h(story["source"])} ({when}):</strong> {link(story["title"], story["url"])}</li>')
    return matches


def detail(entry):
    path = route(entry)
    prefix = "../../"
    scientific, name, family, subfamily, genus = (entry[k] for k in ("scientific", "name", "family", "subfamily", "genus"))
    aliases = entry.get("aliases", [])
    query = quote(scientific)
    wiki = "https://commons.wikimedia.org/w/index.php?title=Special:MediaSearch&type=image&search=" + query
    inat = "https://www.inaturalist.org/observations?taxon_name=" + query
    search_ifb = "https://www.ifoundbutterflies.org/search/node?keys=" + query
    gbif = "https://www.gbif.org/species/search?q=" + query
    family_url = local(prefix, "butterflies/") + "?family=" + quote(family)
    subfamily_url = local(prefix, "butterflies/") + "?subfamily=" + quote(subfamily)

    figure = photo(scientific, prefix, "detail")
    if not figure:
        taxon_names = [scientific] + [alias for alias in aliases if re.fullmatch(r"[A-Z][a-z]+ [a-z]+(?: [a-z]+)?", alias)]
        figure = f"""<div class="notice" data-photo-lookup="{h(json.dumps(taxon_names))}">
<strong>No pre-cached photo yet: look up Wikimedia Commons</strong>
<p>Check live Wikimedia Commons records for <i>{h(scientific)}</i>, or share your verified field photograph with TNBS to include it in the guide.</p>
<div class="actions"><button type="button" class="button" data-enhancement hidden>Look up Wikimedia photo</button>{link("Search Wikimedia Commons",wiki,"button outline")}</div>
<p role="status" aria-live="polite" data-lookup-status class="caption"></p><div data-lookup-result></div></div>"""

    bv_models = entry.get("butterflyVision", [])
    if bv_models:
        model_text = " & ".join("Western Ghats (300+)" if m == "wg" else "All India (800+)" for m in bv_models)
        bv_card = f"""<div class="bv-species-card">
<p class="card-meta">Butterfly Vision AI Support</p>
<h3>Identify a photo of {h(name)}</h3>
<p>Recognised by the <strong>{h(model_text)}</strong> model on Butterfly Vision ({h(SITE["butterflyVision"]["accuracy"])} average accuracy).</p>
<div class="actions">{link("Open AI Identifier", local(prefix, "identify/"), "button")}{link("Open butterflyvision.in", BUTTERFLY_VISION, "button outline")}</div></div>"""
    else:
        bv_card = f"""<div class="bv-species-card">
<p class="card-meta">Butterfly Vision AI</p>
<h3>Contribute training photos</h3>
<p><i>{h(scientific)}</i> is a rare or recently recognised Tamil Nadu taxon not yet listed separately on Butterfly Vision. Clear field photos (&gt;600x600px) help expand AI recognition.</p>
<div class="actions">{link("How to contribute", local(prefix, "identify/") + "#contribute-ai", "button outline")}</div></div>"""

    prof = PROFILES.get(scientific)
    fam_tax = TAXONOMY["families"][family]
    sub_tax = TAXONOMY["subfamilies"][subfamily]

    fact_rows = [
        f'<div><dt>Checklist ID</dt><dd>#{entry["id"]} of {len(SPECIES)}</dd></div>',
        f'<div><dt>Common name</dt><dd>{h(name)}</dd></div>',
    ]
    if isinstance(prof, dict) and prof.get("tamilName"):
        fact_rows.append(f'<div><dt>Tamil name</dt><dd lang="ta">{h(prof["tamilName"])}</dd></div>')
    fact_rows.extend([
        f'<div><dt>Scientific name</dt><dd><i>{h(scientific)}</i></dd></div>',
        f'<div><dt>Taxonomy</dt><dd>Family {link(family, family_url)} ({h(FAMILIES[family])}) → Subfamily {link(subfamily, subfamily_url)} → Genus <i>{h(genus)}</i></dd></div>',
    ])
    if aliases:
        fact_rows.append(f'<div><dt>Alternate names</dt><dd>{h("; ".join(aliases))}</dd></div>')
    if isinstance(prof, dict) and prof.get("wingspan"):
        fact_rows.append(f'<div><dt>Typical wingspan</dt><dd>{h(prof["wingspan"])}</dd></div>')
    val_label = "Validated presence in Tamil Nadu (one of 325 confirmed taxa)" if entry.get("validated", True) else "Target checklist entry awaiting validated TNBS sighting confirmation (1 of 4 priority target species)"
    fact_rows.append(f'<div><dt>TN validation status</dt><dd>{h(val_label)}</dd></div>')
    if isinstance(prof, dict) and prof.get("wpaStatus"):
        fact_rows.append(f'<div><dt>Legal protection</dt><dd>{h(prof["wpaStatus"])}</dd></div>')

    profile_html = ""
    if isinstance(prof, dict):
        hosts = "".join(f'<span class="host-pill">{h(hp)}</span>' for hp in prof.get("hostPlants", []))
        refs = "".join(f'<li>{link(lbl, ref)}</li>' for lbl, ref in prof.get("sources", []))
        profile_html = f"""<section class="profile-section" aria-label="Species identification and ecology">
<div class="profile-lead"><h2>{h(prof["headline"])}</h2></div>
<div class="profile-grid">
<div class="profile-card"><h3>Identification marks</h3>
<p><strong>Upperwing:</strong> {h(prof["upperwing"])}</p>
<p><strong>Underwing:</strong> {h(prof["underwing"])}</p>
<p><strong>Lookalikes:</strong> {h(prof["similarSpecies"])}</p></div>
<div class="profile-card"><h3>Habitat &amp; Tamil Nadu range</h3>
<p><strong>Habitats:</strong> {h(prof["habitat"])}</p>
<p><strong>Tamil Nadu distribution:</strong> {h(prof["tnDistribution"])}</p>
<p><strong>Seasonality:</strong> {h(prof["season"])}</p></div>
<div class="profile-card"><h3>Flight &amp; behaviour</h3>
<p>{h(prof["behavior"])}</p>
{f'<p><strong>Field note:</strong> {h(prof["notes"])}</p>' if prof.get("notes") else ""}</div>
<div class="profile-card"><h3>Caterpillar host plants</h3>
{f'<div class="host-pills">{hosts}</div>' if hosts else '<p>Host plants recorded under family associations.</p>'}
{f'<h4>Field references</h4><ul class="compact-list">{refs}</ul>' if refs else ""}</div>
</div></section>"""

    subfamily_card = f"""<details class="taxonomy-disclosure">
<summary>Field guide notes for {h(family)} · {h(subfamily)} ({h(sub_tax["group"])})</summary>
<div class="disclosure-body">
<p><strong>Family overview ({h(family)}, {h(fam_tax["common"])}):</strong> {h(fam_tax["description"])}</p>
<p><strong>Subfamily traits ({h(subfamily)}):</strong> {h(sub_tax["traits"])}</p>
<p><strong>Typical habitats:</strong> {h(sub_tax["habitat"])}</p>
<p><strong>Field photography tip:</strong> {h(sub_tax["photoTip"])} {h(fam_tax["photoTip"])}</p>
</div></details>"""

    mentions = species_press_mentions(scientific, name)
    mentions_html = f'<h2>In TNBS news &amp; press</h2><ul>{"".join(mentions)}</ul>' if mentions else ""

    idx = entry["id"] - 1
    prev_entry = SPECIES[(idx - 1) % len(SPECIES)]
    next_entry = SPECIES[(idx + 1) % len(SPECIES)]
    siblings = [s for s in BY_FAMILY[family] if s["scientific"] != scientific]
    siblings.sort(key=lambda s: (s["scientific"] not in PHOTOS, s["subfamily"] != subfamily, s["id"]))
    related_cards = "".join(species_card(s, prefix) for s in siblings[:3])

    spot_action = (
        f'<div class="actions" data-enhancement hidden>'
        f'<button type="button" class="button outline spot-btn" data-spot-btn data-sci="{h(scientific)}" aria-pressed="false">+ Mark as spotted in Tamil Nadu</button>'
        f'<a class="button outline" href="{local(prefix, "butterflies/")}?tag=spotted">View my life list</a></div>'
    )

    body = f"""<header class="page-head"><div class="wrap">
<p class="breadcrumb">{link("Field guide",local(prefix,"butterflies/"))} / {link(family,family_url)} / {link(subfamily,subfamily_url)}</p>
<h1>{h(name)}</h1><p class="lede"><i>{h(scientific)}</i> · {h(sub_tax["group"])}</p>
{species_badges_html(entry, compact=False)}{spot_action}</div></header>
<section class="wrap section species-main"><div class="species-media-col">{figure}{bv_card}</div>
<div class="species-info-col"><h2>Structured checklist record</h2><dl class="facts">{"".join(fact_rows)}</dl>
{subfamily_card}{mentions_html}
<h2>Explore external databases</h2><ul class="explore-links">
<li>{link("Identify similar photos on Butterfly Vision AI", BUTTERFLY_VISION)}</li>
<li>{link("Search Butterflies of India (IFoundButterflies)", search_ifb)}</li>
<li>{link("Browse iNaturalist observations", inat)}</li>
<li>{link("Search Wikimedia Commons media", wiki)}</li>
<li>{link("Lookup taxonomic record on GBIF", gbif)}</li></ul></div></section>
{f'<section class="journal"><div class="wrap compact">{profile_html}</div></section>' if profile_html else ""}
<section class="wrap section">
<nav class="species-pager" aria-label="Adjacent checklist species">
<a class="pager-link" href="{local(prefix, route(prev_entry))}"><small>← Previous (#{prev_entry["id"]})</small><strong>{h(prev_entry["name"])}</strong></a>
<a class="pager-link pager-next" href="{local(prefix, route(next_entry))}"><small>Next (#{next_entry["id"]}) →</small><strong>{h(next_entry["name"])}</strong></a>
</nav>
{f'<div class="related-block"><h2>More in {h(family)} ({h(FAMILIES[family])})</h2><div class="grid">{related_cards}</div></div>' if related_cards else ""}
</section>"""

    render(
        path,
        f"{name} ({scientific})",
        f"{name} ({scientific}) in the Butterflies of Tamil Nadu field guide. Explore taxonomy, identification marks, host plants, Butterfly Vision support, and verified photographs.",
        body,
        active="butterflies/",
        image_key=scientific,
        schema={
            "@type": "WebPage",
            "name": f"{name} ({scientific})",
            "about": [{"@type": "Thing", "name": scientific}, {"@type": "Place", "name": "Tamil Nadu"}],
        },
    )


def identify():
    bv = SITE["butterflyVision"]
    wg_covered = sum(1 for s in SPECIES if "wg" in s.get("butterflyVision", []))
    india_covered = sum(1 for s in SPECIES if "india" in s.get("butterflyVision", []))
    total_covered = sum(1 for s in SPECIES if s.get("butterflyVision"))

    lookup_map = {}
    for s in SPECIES:
        target = route(s)
        lookup_map[s["scientific"].lower()] = [s["name"], s["scientific"], target]
        lookup_map[s["name"].lower()] = [s["name"], s["scientific"], target]
        for alias in s.get("aliases", []):
            lookup_map.setdefault(alias.lower(), [s["name"], s["scientific"], target])

    pubs_html = "".join(
        f'<li class="reveal"><h3>{h(title)}</h3><p class="card-meta">{h(venue)}</p><p>{link("Read publication / repository", url)}</p></li>'
        for title, venue, url in bv["publications"]
    )
    body = heading(
        "Identify butterflies with Butterfly Vision AI",
        f"Direct integration with butterflyvision.in: an instant deep-learning butterfly identification platform developed by TNBS member {bv['developer']} covering {bv['supportedTotal']} Indian and Western Ghats species.",
        "AI Butterfly Identifier",
    )
    body += f"""<div class="band"><div class="wrap"><ul class="stats stats-4">
<li><strong>{bv['supportedTotal']}</strong><span>Total species supported on Butterfly Vision</span></li>
<li><strong>{bv['accuracy']}</strong><span>Average deep learning accuracy</span></li>
<li><strong>{wg_covered} / {len(SPECIES)}</strong><span>TN checklist species in Western Ghats model</span></li>
<li><strong>{india_covered} / {len(SPECIES)}</strong><span>TN checklist species in All India model</span></li></ul></div></div>

<section class="wrap section">
<div class="bv-widget" data-bv-widget data-species-index="{h(json.dumps(lookup_map, separators=(',', ':'), ensure_ascii=False))}">
<div class="bv-header"><div><p class="kicker">Step 1 · Choose recognition model</p><h2>Upload &amp; prepare a butterfly photo</h2></div>
<div class="choices" role="group" aria-label="Butterfly Vision model selection">
<button type="button" class="choice" data-bv-model="wg" aria-pressed="true">Western Ghats ({bv['wgCount']} species)</button>
<button type="button" class="choice" data-bv-model="india" aria-pressed="false">All India ({bv['indiaCount']} species)</button></div></div>
<p class="caption" data-bv-model-desc>Recommended for Tamil Nadu hills, forests, and Western Ghats surveys ({total_covered} of 329 TN checklist species covered).</p>

<div class="bv-dropzone" data-bv-drop>
<label for="bv-file" class="bv-file-label">Choose butterfly photo (JPG, PNG, or WebP)</label>
<input id="bv-file" name="butterfly_photo" type="file" accept="image/jpeg,image/png,image/webp" class="bv-file-input" aria-describedby="bv-file-help">
<p id="bv-file-help" class="caption">Use Browse / Choose File above or drag and drop a photo here. Clear, cropped photos above 600x600px give the best species predictions.</p>
<div class="actions">{link("Open butterflyvision.in directly", BUTTERFLY_VISION, "button outline")}</div>
</div>

<div class="bv-preview" data-bv-preview hidden>
<div class="bv-preview-grid">
<figure class="photo-large"><img id="bv-preview-img" src="" alt="Selected butterfly image preview"><figcaption id="bv-file-meta" class="credit"></figcaption></figure>
<div class="bv-result-col">
<p role="status" aria-live="polite" data-bv-status class="quiz-feedback"></p>
<div data-bv-results></div>
<div class="actions" data-bv-actions>
<button type="button" class="button" data-bv-run>Run AI identification</button>
<a class="button outline" href="{BUTTERFLY_VISION}" target="_blank" rel="noopener noreferrer">Open on butterflyvision.in ↗</a>
</div></div></div></div>
<noscript><p class="notice">JavaScript is off, so please {link("identify directly on butterflyvision.in", BUTTERFLY_VISION)}.</p></noscript>
</div></section>

<section class="journal"><div class="wrap section split">
<div><p class="kicker">How it works</p><h2>Tips for high-accuracy AI &amp; expert ID</h2>
<ul class="bullet-list">
<li><strong>Fill the frame cleanly:</strong> Crop close around the butterfly so wing spots, bands, and margins stand out clearly (Butterfly Vision includes a built-in cropper on its site too!).</li>
<li><strong>Capture both surfaces when possible:</strong> Underwing patterns are vital for grass blues, bushbrowns, silverlines, and skippers.</li>
<li><strong>Use Western Ghats vs All India strategically:</strong> For Coimbatore, Nilgiris, Anamalai, or KMTR photos, try the Western Ghats model first to narrow lookalike northern taxa; switch to All India for coastal plains or Eastern Ghats surprises.</li>
<li><strong>Cross-verify in the TNBS Field Guide:</strong> Always confirm seasonal morphs, location, and host-plant clues on the species page before logging a sighting.</li></ul></div>
<div id="contribute-ai" class="ai-card"><p class="card-meta">Community Data Flywheel</p>
<h3>Help train Butterfly Vision toward 95%+ accuracy</h3>
<p>Do you have crisp, verified butterfly photographs taken in India (&gt;600x600px, JPG or PNG)? Share them with the Butterfly Vision research team to strengthen rare species recognition across Tamil Nadu.</p>
<p><strong>Email:</strong> {link(bv["contributeEmail"], "mailto:" + bv["contributeEmail"] + "?subject=Photo%20contribution%20to%20Butterfly%20Vision")}</p>
<div class="actions">{link("Browse supported TN species", local("../", "butterflies/") + "?tag=bv", "button outline")}</div></div>
</div></section>

<section class="wrap section">
<p class="kicker">Peer-reviewed research</p><h2>Scientific foundation behind Butterfly Vision</h2>
<ul class="news-list">{pubs_html}</ul></section>"""

    render(
        "identify/",
        "Butterfly Vision AI Identification",
        "Identify Tamil Nadu and Indian butterflies instantly with Butterfly Vision AI (butterflyvision.in), integrated directly with TNBS's 329-species field guide.",
        body,
        image_key="Papilio crino",
    )


def magazine():
    rows = []
    total_indexed = sum(len(MAGAZINE_INDEX[n]["articles"]) for n in MAGAZINE_INDEX)
    for number in range(len(SITE["issues"]), 0, -1):
        if number <= 18:
            year, quarter = 2017 + (number - 1) // 4, (number - 1) % 4 + 1
        elif number <= 22:
            year, quarter = 2022, number - 18
        elif number <= 25:
            year, quarter = 2023, number - 22
        else:
            year, quarter = 2024 + number - 26, 1
        months = ("January-March", "April-June", "July-September", "October-December")[quarter - 1]
        articles = MAGAZINE_INDEX.get(number, {}).get("articles", [])
        terms = " ".join([f"Issue {number}", months, str(year), *articles])
        articles_html = ""
        if articles:
            li_items = "".join(f'<li>{h(a)}</li>' for a in articles)
            articles_html = (
                f'<details class="mag-articles"><summary>Browse {len(articles)} featured articles</summary>'
                f'<ul class="compact-list">{li_items}</ul></details>'
            )
        rows.append(
            f'<li class="issue-card reveal" data-record data-year="{year}" data-terms="{h(terms)}" id="issue-{number}">'
            f'<div class="issue-row"><div><strong>Issue {number} · {months} {year}</strong>'
            f'<p class="meta">Wings {year-2016} · Veins {quarter}</p></div>'
            f'{link(f"Open issue {number} PDF",issue_url(number),"button outline")}</div>{articles_html}</li>'
        )
    body = heading(
        "Pattampoochi",
        f"The quarterly e-magazine of The Nature and Butterfly Society: 27 issues and {total_indexed} indexed articles covering surveys, migration, host plants, and Tamil Nadu checklist revisions.",
        "Publications",
    )
    body += f"""<section class="journal"><div class="wrap compact split">{cover()}<div><p class="kicker">Issue 27 · January-March 2025</p><h2>Latest issue highlights</h2>
<p>Issue 27 presents the 2024 Danainae migration update, Mudumalai Tiger Reserve (185+ spp.) and Pachamalai Hills (126 spp.) surveys, school Tamil poster outreach across 13+ districts, a full back-issues article index (2017-2024), and the updated 329-species Tamil Nadu checklist.</p>
{link("Open issue 27 PDF",issue_url(27),"button")}</div></div></section>
<section class="wrap section" data-records><h2>All {len(SITE["issues"])} issues &amp; searchable article index</h2>
<div data-enhancement hidden><search><form class="filters">
<div class="field grow"><label for="mag-q">Search articles, places &amp; authors</label><input id="mag-q" type="search" name="q" placeholder="Try Siruvani, Kallar, migration, Pavendhan, life cycle..."></div>
<div class="field"><label for="mag-year">Year</label><select id="mag-year" name="year"><option value="">All years</option>{"".join(f'<option>{y}</option>' for y in range(2025,2016,-1))}</select></div>
<button type="reset" class="button outline">Clear</button></form></search></div>
<p data-status role="status" aria-live="polite"></p><ul class="issue-list">{"".join(rows)}</ul><div class="actions">{link("Original magazine archive",MAGAZINE)} ·
{link("Send a contribution","mailto:"+CONTACT+"?subject=Pattampoochi%20contribution")}</div></section>"""
    render(
        "magazine/",
        "Pattampoochi magazine archive",
        f"Browse all 27 issues and search {total_indexed} indexed articles in Pattampoochi, The Nature and Butterfly Society's quarterly magazine on Tamil Nadu butterflies.",
        body,
    )


def news():
    updates = [
        ("2025", "Society Updates", "TNBS", "Tamil Nadu butterfly checklist reaches 329 species", "Confirmed 325 validated species and 4 priority targets across 6 families, adding Common Palmfly and Cloud Forest Silverline.", local("../", "butterflies/")),
        ("2025", "Society Updates", "TNBS", "Free Tamil butterfly posters reach 13+ districts", "TNBS government school outreach expanded across Chennai, Salem, Krishnagiri, Tiruppur, Dharmapuri, Cuddalore, and The Nilgiris.", local("../", "about/") + "#outreach"),
        ("2024", "Society Updates", "TNBS", "Tamilnadu Butterflies Facebook group marks 10 years", "Launched on 02 October 2014, TNBS's flagship citizen-science forum now connects 2,340+ contributors across all 38 districts of Tamil Nadu and Puducherry.", FACEBOOK_GROUP),
        ("2024", "Society Updates", "TNBS", "Butterfly Vision surpasses 923+ supported Indian species", "TNBS member Theivaprakasham Hari's AI identification tool covers 319 of Tamil Nadu's 329 checklist species.", local("../", "identify/")),
    ]
    lead = SITE["press"][0]
    lead_when = date.fromisoformat(lead["date"]).strftime("%d %b %Y").lstrip("0")
    lead_html = f"""<article class="featured-news">
<p class="kicker">Latest Lead Report · <time datetime="{lead["date"]}">{lead_when}</time></p>
<h2>{h(lead["title"])}</h2>
<p class="card-meta">{h(lead["source"])} · {h(lead["category"])}</p>
<p class="lede">{h(lead["summary"])}</p>
<div class="actions">{link("Read full article ↗", lead["url"], "button")}{link("Browse Blue Tiger species profile", local("../", route(BY_SCI[lead["species"]])), "button outline")}</div>
</article>"""

    categories = sorted({s["category"] for s in SITE["press"]} | {"Society Updates"})
    cat_pills = ['<button type="button" class="choice" data-cat-pill="" aria-pressed="true">All coverage</button>']
    for cat in categories:
        cat_pills.append(f'<button type="button" class="choice" data-cat-pill="{h(cat)}" aria-pressed="false">{h(cat)}</button>')

    sources_opts = "".join(f'<option>{h(src)}</option>' for src in sorted({s["source"] for s in SITE["press"]} | {"TNBS"}))
    year_opts = "".join(f'<option>{y}</option>' for y in sorted({s["date"][:4] for s in SITE["press"]} | {u[0] for u in updates}, reverse=True))

    update_rows = "".join(
        f'<li class="news-card reveal" data-record data-kind="Society" data-category="{h(cat)}" data-source="{h(src)}" data-year="{year}" data-terms="{h(title + " " + summary)}">'
        f'<div class="news-card-meta"><span class="tag tag-highlight">{h(cat)}</span><span class="card-meta">{h(src)} · {year}</span></div>'
        f'<h3>{link(title, url)}</h3><p>{h(summary)}</p>'
        f'<p class="news-card-foot">{link("Open update →", url)}</p></li>'
        for year, cat, src, title, summary, url in updates
    )

    elsewhere_cards = "".join(
        f'<article class="card community-card reveal"><div class="card-body"><p class="card-meta">{h(c["badge"])}</p>'
        f'<h3>{link(c["title"], c["url"])}</h3><p>{h(c["summary"])}</p>'
        f'<p>{link(c["cta"] + " ↗", c["url"], "small-button")}</p></div></article>'
        for c in SITE["community"]
    )

    body = heading(
        "News, press & community archive",
        f"{len(SITE['press'])} verified newspaper articles, peer-reviewed research papers, and Pattampoochi magazine feature reports alongside TNBS updates and community links across the web.",
    )
    body += f"""<section class="wrap section" data-records>
{lead_html}
<div data-enhancement hidden>
<div class="choices" role="group" aria-label="Filter coverage by topic">{"".join(cat_pills)}</div>
<search><form class="filters">
<div class="field grow"><label for="news-q">Search headlines, places &amp; species</label><input id="news-q" type="search" name="q" placeholder="Try Mudumalai, Pachamalai, Pattampoochi, Ypthima, Singanallur, Vellalore..."></div>
<div class="field"><label for="news-source">Publication</label><select id="news-source" name="source"><option value="">All publications</option>{sources_opts}</select></div>
<div class="field"><label for="news-year">Year</label><select id="news-year" name="year"><option value="">All years</option>{year_opts}</select></div>
<input type="hidden" name="category" value="">
<button type="reset" class="button outline">Clear</button></form></search></div>
<p data-status role="status" aria-live="polite"></p>
<ul class="news-grid">{"".join(press_card(story, "../") for story in SITE["press"])}{update_rows}</ul>
</section>

<section id="elsewhere" class="journal"><div class="wrap section">
<p class="kicker">Facebook, YouTube, ResearchGate &amp; Partner Apps</p>
<h2>Elsewhere on the web</h2>
<p class="lede">Connect with Tamil Nadu's active butterfly community, watch public lectures, request free school materials, and explore published checklist citations.</p>
<div class="grid">{elsewhere_cards}</div>
</div></section>"""

    render(
        "news/",
        "News, press & community archive",
        f"Explore {len(SITE['press'])} verified press articles, Pattampoochi magazine reports, Journal of Threatened Taxa research, and Tamil Nadu butterfly community links.",
        body,
        image_key="Tirumala limniace",
    )


def activities():
    cards = ""
    for act in SITE["activities"]:
        origin, number = act["ref"].split(":")
        url = issue_url(int(number)) if origin == "issue" else SITE["press"][int(number)]["url"]
        media_html = ""
        if act.get("photo"):
            media_html = f'<div class="media">{lightbox_button_img(act["photo"], act["photoAlt"], act["title"], act["summary"], "../")}</div>'
        cards += (
            f'<article class="card reveal">{media_html}<div class="card-body">'
            f'<p class="card-meta">{h(act["kind"])} · {h(act["when"])}</p>'
            f'<h3>{h(act["title"])}</h3><p>{h(act["summary"])}</p>'
            f'<p>{link("Open field report" if origin == "issue" else "Read the coverage", url)}</p></div></article>'
        )
    body = heading(
        "Activities and fieldwork",
        "From Mudumalai and Pachamalai Forest Division butterfly surveys to school outreach, City Nature Challenge walks, and statewide migration tracking.",
    )
    body += f'<section class="wrap section"><h2>Surveys, walks &amp; outreach</h2><div class="grid">{cards}</div><div class="actions">{link("Ask about future activities", "mailto:"+CONTACT+"?subject=TNBS%20activities", "button")}</div></section>'
    render(
        "activities/",
        "Activities and fieldwork",
        "Explore TNBS butterfly surveys, walks, Tamil school poster distribution, and migration monitoring across Tamil Nadu.",
        body,
    )


def about():
    ab = SITE["about"]
    gallery = "".join(
        f'<figure class="gallery-card reveal">{lightbox_button_img(p["src"], p["caption"], p["title"], p["caption"], "../", p["width"], p["height"])}'
        f'<figcaption><strong>{h(p["title"])}</strong> · <span>{h(p["when"])}</span><br><small>{h(p["caption"])}</small></figcaption></figure>'
        for p in ab["photos"]
    )
    milestones = "".join(f'<li><strong>{h(yr)}</strong><p>{h(desc)}</p></li>' for yr, desc in ab["milestones"])
    team_items = "".join(f'<li>{h(member)}</li>' for member in ab["leadership"])
    papers_cards = []
    for paper in SITE.get("researchPapers", []):
        sp_link = ""
        if paper.get("species") and paper["species"] in BY_SCI:
            sp = BY_SCI[paper["species"]]
            sp_link = link(f'View {sp["name"]} profile →', local("../", route(sp)), "press-species")
        doi_link = link("DOI", paper["doiUrl"]) if paper.get("doiUrl") and paper["doiUrl"] != paper["url"] else ""
        links_row = " · ".join(x for x in [link("Read article / record ↗", paper["url"]), doi_link, sp_link] if x)
        papers_cards.append(
            f'<li class="news-card reveal"><p class="card-meta">{h(paper["authors"])} · {h(paper["venue"])}</p>'
            f'<h3>{link(paper["title"], paper["url"])}</h3><p>{h(paper["summary"])}</p>'
            f'<p class="news-card-foot">{links_row}</p></li>'
        )
    papers_html = "".join(papers_cards)

    body = heading(
        "About The Nature and Butterfly Society",
        "A Coimbatore-based conservation & citizen-science society systematically documenting Tamil Nadu's butterflies across the Western Ghats, Eastern Ghats, wetlands, plains, and schools.",
        "About us",
    )
    body += f"""<section class="wrap section split">
<div><p class="kicker">Society story &amp; mission</p><h2>Built by field naturalists across 38 districts</h2>
<p>Geographically, Tamil Nadu spans a remarkable meeting ground where the Western Ghats and Eastern Ghats converge at the Nilgiri hills alongside fertile coastal plains and arid interior scrub. Yet before TNBS began compiling systematic records in 2012-2014, Tamil Nadu lacked an exclusive validated state checklist.</p>
<p>Registered formally in Coimbatore ({h(ab["registration"])}), TNBS coordinates field walks, Tamil Nadu Forest Department surveys, seasonal Danainae migration monitoring, school poster outreach, and the quarterly journal <em>Pattampoochi</em>.</p>
<dl class="facts">
<div><dt>Registration</dt><dd>{h(ab["registration"])}</dd></div>
<div><dt>Headquarters</dt><dd>{h(ab["address"])}</dd></div>
<div><dt>Community network</dt><dd>{link(ab["facebookGroup"], ab["facebookUrl"])}</dd></div>
<div><dt>Video lecture</dt><dd>{link("TNBS President talk on Tamil Nadu Butterflies (YouTube)", ab["youtubeUrl"])}</dd></div>
<div><dt>Official contact</dt><dd>{link(CONTACT, "mailto:" + CONTACT)}</dd></div></dl></div>
<div class="emblem-panel"><img src="../assets/tnbs-logo.png" alt="Official logo of The Nature and Butterfly Society featuring Papilio crino" width="173" height="173">
<p><strong>Official TNBS Emblem</strong></p><p class="caption">Featuring the emerald Common Banded Peacock (<i>Papilio crino</i>) encircled by The Nature and Butterfly Society seal.</p></div></section>

<section class="journal"><div class="wrap section">
<p class="kicker">In the field &amp; classroom</p><h2>TNBS in action</h2>
<p class="lede">Highlights from Forest Division butterfly surveys, community biodiversity counts, and school education programmes across Tamil Nadu. Click any photograph to inspect it full-size.</p>
<div class="grid gallery-grid">{gallery}</div></div></section>

<section id="outreach" class="wrap section split">
<div><p class="kicker">Milestones (2012-2025)</p><h2>How the society grew</h2>
<ol class="timeline">{milestones}</ol></div>
<div><p class="kicker">People &amp; leadership</p><h2>Editorial &amp; survey core team</h2>
<p>TNBS thrives through collaborative voluntary contributions by dozens of field naturalists, photographers, and researchers across Tamil Nadu and Puducherry.</p>
<ul class="bullet-list">{team_items}</ul>
<div class="ai-card"><h3>TNBS Government School Poster Project</h3>
<p>TNBS prints and distributes free Tamil butterfly awareness posters and beginner booklets to government school teachers across Tamil Nadu (and English posters at nominal cost for nature clubs).</p>
<div class="actions">{link("Request free Tamil school posters", ab["posterFormUrl"], "button")}{link("Browse activities", "../activities/index.html", "button outline")}</div></div></div></section>

<section id="research" class="journal"><div class="wrap section">
<p class="kicker">Scientific Contributions</p><h2>Peer-reviewed research &amp; publications</h2>
<p class="lede">Original life-cycle discoveries, state checklist datasets, and computer-vision research authored by TNBS members.</p>
<ul class="news-grid">{papers_html}</ul></div></section>

<section class="dark" id="get-involved"><div class="wrap section content"><p class="kicker">Join the effort</p><h2>Get involved with TNBS</h2>
<h3>Report a sighting</h3><p>Send a clear photo, date, location, and habitat notes, especially for the four checklist entries awaiting validated Tamil Nadu confirmation (Palni Sailer, Tamil Oakblue, Common Awl, and Coorg Forest Hopper).</p>
<h3>Identify &amp; learn with AI</h3><p>Try {link("Butterfly Vision AI", "../identify/index.html")} for quick species suggestions and cross-check field traits in our {link("329-species field guide", "../butterflies/index.html")}.</p>
<h3>Join a walk, survey, or write for Pattampoochi</h3><p>Write to TNBS or join our {link("Tamil Nadu Butterflies Facebook Group", ab["facebookUrl"])} to ask about regional butterfly walks, school awareness sessions, or submitting articles and photo stories to <em>Pattampoochi</em>.</p>
<div class="actions">{link("Email TNBS", "mailto:" + CONTACT, "button light")}{link("Visit original Google Site archive", ORIGINAL, "button outline")}</div></div></section>"""
    render(
        "about/",
        "About us · The Nature and Butterfly Society",
        "Learn about The Nature and Butterfly Society (TNBS), its Coimbatore history, leadership, 2024-2025 Forest Department surveys, Tamil school poster outreach, and how to contribute.",
        body,
    )


def sources():
    photos_list = "".join(
        f'<li><i>{h(s)}</i> · {credit_html(meta)}</li>'
        for s in sorted(PHOTOS)
        for meta in [photo_meta(s, "../")]
    )
    unvalidated_list = "".join(
        f'<li>{link(BY_SCI[s]["name"], local("../", route(BY_SCI[s])))} (<i>{h(s)}</i>)</li>'
        for s in ["Neptis palnica", "Arhopala bazaloides", "Hasora badra", "Arnetta mercara"]
    )
    table_rows = "".join(
        f'<tr><th scope="row">{h(fam)} ({h(FAMILIES[fam])})</th><td>{v1}</td><td><strong>{EXPECTED_FAMILY_COUNTS[fam]}</strong></td></tr>'
        for fam, v1 in [("Papilionidae", 19), ("Pieridae", 32), ("Nymphalidae", 96), ("Riodinidae", 2), ("Lycaenidae", 91), ("Hesperiidae", 83)]
    )
    member_counts = {}
    for s in sorted(PHOTOS):
        if is_member_photo(s):
            author = PHOTOS[s]["author"]
            member_counts[author] = member_counts.get(author, 0) + 1
    member_summary = ", ".join(f"{h(k)}: {v} species" for k, v in sorted(member_counts.items()))
    research_items = "".join(
        f'<li>{link(p["title"], p["url"])} ({h(p["authors"])}, {h(p["venue"])})</li>'
        for p in SITE.get("researchPapers", [])
    )
    body = heading("Sources and photo credits", "Tamil Nadu checklist provenance, peer-reviewed research publications, taxonomy notes, and Creative Commons photo attributions.")
    body += f"""<section class="wrap section content">
<h2>Tamil Nadu Butterfly Checklist</h2>
<p>This website presents TNBS's <strong>{len(SPECIES)}-species Tamil Nadu Butterfly Checklist across {len(FAMILIES)} families</strong> (compiled and updated through <em>Pattampoochi</em>, with <strong>325 validated species</strong> and 4 priority species awaiting validated photographic records in Tamil Nadu).</p>
<p>Recent state additions highlighted in the field guide include {link("Common Palmfly", local("../", route(BY_SCI["Elymnias hypermnestra"])))} (<i>Elymnias hypermnestra</i>) and {link("Cloud Forest Silverline", local("../", route(BY_SCI["Cigaritis meghamalaiensis"])))} (<i>Cigaritis meghamalaiensis</i>, Naicker et al. 2023).</p>

<table class="data-table"><caption>Tamil Nadu Butterfly Checklist family counts: 2015 v1 vs. 2025 (329 species)</caption>
<thead><tr><th scope="col">Family</th><th scope="col">2015 v1</th><th scope="col">2025</th></tr></thead>
<tbody>{table_rows}</tbody>
<tfoot><tr><th scope="row">Total species</th><td>323</td><td><strong>329 (325 validated)</strong></td></tr></tfoot></table>

<h3>Four checklist species awaiting validated Tamil Nadu confirmation</h3>
<ul>{unvalidated_list}</ul>

<h3>Peer-reviewed research &amp; checklist references</h3>
<ul>{research_items}
<li>{link("Latest Pattampoochi checklist issue PDF", issue_url(27))}</li>
<li>{link("Original TNBS checklist archive page", ORIGINAL + "/butterfly-checklist-of-tamil-nadu")}</li>
<li>{link("Butterfly Vision AI species registry", BUTTERFLY_VISION)}</li></ul>

<h2>Photographs &amp; open licenses ({len(PHOTOS)} species illustrated)</h2>
<p>Field guide photographs combine Creative Commons licensed field observations contributed by TNBS members ({member_summary}) with verified open-licensed Wikimedia Commons images, paired with photographer credits and license links. Activities and About Us photographs come from TNBS fieldwork and outreach archives.</p>
<details class="taxonomy-disclosure"><summary>Show all {len(PHOTOS)} species photo attributions</summary>
<div class="disclosure-body"><ul class="credit-list">{photos_list}</ul></div></details>
</section>"""
    render(
        "sources/",
        "Checklist sources and photo credits",
        "Read the Tamil Nadu Butterfly Checklist history, peer-reviewed publications including Journal of Threatened Taxa #6656, and complete photographer attributions.",
        body,
    )


def quiz():
    body = heading(
        "Interactive Butterfly Quiz",
        f"Challenge yourself with four interactive modes: Photo ID across {len(PHOTOS)} species, Mixed Field Facts, Timed Rapid Fire, or Scientific Name Match, with streaks, lifelines, personal bests, and shareable score cards.",
    )
    body += """<section class="wrap section"><div class="quiz" data-quiz>
<div data-quiz-start>
<div class="quiz-lobby-head"><div><p class="kicker">Choose your challenge</p><h2>Start a quiz session</h2></div>
<div class="quiz-best" data-quiz-best hidden></div></div>

<div class="quiz-mode-grid" role="group" aria-label="Quiz mode">
<button type="button" class="mode-card" data-mode="photo" aria-pressed="true"><strong>Photo ID Challenge</strong><span>Identify real field photographs of butterflies from Tamil Nadu.</span></button>
<button type="button" class="mode-card" data-mode="mixed" aria-pressed="false"><strong>Mixed Field Quiz</strong><span>Blend butterfly photos with TNBS migration, host-plant, and ecology questions.</span></button>
<button type="button" class="mode-card" data-mode="rapid" aria-pressed="false"><strong>Timed Rapid Fire</strong><span>20 seconds per question: build streaks and earn speed bonus points!</span></button>
<button type="button" class="mode-card" data-mode="scientific" aria-pressed="false"><strong>Scientific Name Match</strong><span>Match Tamil Nadu common names to their binomial scientific names.</span></button>
</div>

<div class="quiz-settings">
<div class="field"><label for="quiz-family">Focus family</label><select id="quiz-family">
<option value="">All 6 families</option>
<option value="Papilionidae">Papilionidae (Swallowtails)</option>
<option value="Pieridae">Pieridae (Whites &amp; yellows)</option>
<option value="Nymphalidae">Nymphalidae (Brush-footed)</option>
<option value="Lycaenidae">Lycaenidae (Blues &amp; hairstreaks)</option>
<option value="Hesperiidae">Hesperiidae (Skippers)</option>
</select></div>
<div class="field"><label for="quiz-difficulty">Difficulty</label><select id="quiz-difficulty">
<option value="standard">Standard (Mixed distractors)</option>
<option value="expert">Expert (Same-family lookalikes)</option>
</select></div>
<div class="field"><label for="quiz-count">Questions</label><select id="quiz-count">
<option value="8" selected>8 questions</option>
<option value="12">12 questions</option>
<option value="15">15 questions</option>
</select></div></div>

<div class="actions" data-enhancement hidden><button type="button" class="button" data-start-btn>Start quiz →</button></div>
<p role="status" aria-live="polite" data-start-status class="caption"></p>
<noscript><p>The interactive quiz requires JavaScript. You can still <a href="../butterflies/index.html">browse all 329 species in the field guide</a>.</p></noscript>
</div>

<div data-quiz-game hidden>
<div class="quiz-hud">
<span class="hud-chip" data-step>Question 1 of 8</span>
<span class="hud-chip hud-score" data-hud-score>Score: 0</span>
<span class="hud-chip hud-streak" data-hud-streak>Streak: 0 🔥</span>
<span class="hud-chip hud-timer" data-hud-timer hidden>20s</span>
</div>
<progress class="quiz-progress" max="100" value="0" aria-label="Quiz progress" style="--quiz-hue: 145;"></progress>

<div class="quiz-lifelines">
<button type="button" class="choice" data-lifeline-5050>50:50 Eliminate two</button>
<button type="button" class="choice" data-lifeline-hint>Field hint (H)</button>
<span class="caption keyboard-tip">Keys: <kbd>1</kbd>-<kbd>4</kbd> answer · <kbd>H</kbd> hint · <kbd>Enter</kbd> next</span>
</div>

<h2 tabindex="-1" data-question></h2>
<p class="quiz-hint-box" data-hint-box hidden></p>
<div data-quiz-photo hidden></div>
<div class="quiz-options" data-options></div>
<div class="quiz-feedback" role="status" aria-live="polite" data-feedback></div>
<div class="actions"><button class="button" type="button" data-next hidden>Next question</button></div>
</div>

<div data-finish hidden>
<div class="rank-card">
<p class="kicker">Session complete</p>
<h2 tabindex="-1" data-score></h2>
<p class="rank-badge" data-rank></p>
<p data-summary></p>
<dl class="mini-stats quiz-end-stats" data-end-stats></dl>
</div>
<div class="quiz-review-tools">
<div class="choices" role="group" aria-label="Filter review answers">
<button type="button" class="choice" data-review-filter="all" aria-pressed="true">All answers</button>
<button type="button" class="choice" data-review-filter="missed" aria-pressed="false">Missed only</button>
</div>
<div class="actions-inline">
<button type="button" class="button outline" data-retry-missed hidden>Retry missed questions</button>
<button type="button" class="button outline" data-share-score>Copy score summary</button>
</div>
</div>
<p role="status" aria-live="polite" data-share-status class="caption"></p>
<ol class="review-list" data-review></ol>
<div class="actions">
<button type="button" class="button" data-restart>Play another round</button>
<a class="button outline" href="../butterflies/index.html">Browse the field guide</a>
<a class="button outline" href="../identify/index.html">Try Butterfly Vision AI</a>
</div></div></div></section>"""
    render(
        "quiz/",
        "Interactive Tamil Nadu Butterfly Quiz",
        "Test your butterfly identification skills across four interactive quiz modes using verified Tamil Nadu butterfly photos, family lookalikes, streaks, and field facts.",
        body,
        image_key="Papilio crino",
    )


def build_quiz_data():
    photo_bank = []
    for entry in SPECIES:
        sci = entry["scientific"]
        if sci not in PHOTOS:
            continue
        card_meta = photo_meta(sci, "../", thumb=True)
        full_meta = photo_meta(sci, "../", thumb=False)
        prof = PROFILES.get(sci, {})
        clue = f"Family {entry['family']} ({entry['subfamily']})."
        if isinstance(prof, dict) and prof.get("headline"):
            clue = prof["headline"]
        photo_bank.append({
            "id": entry["id"],
            "name": entry["name"],
            "scientific": sci,
            "family": entry["family"],
            "subfamily": entry["subfamily"],
            "slug": slug(sci),
            "clue": clue,
            "src": card_meta["src"],
            "fullSrc": full_meta["src"],
            "author": card_meta["author"],
            "license": card_meta["license"],
            "licenseName": card_meta["licenseName"],
            "url": card_meta["url"],
        })
    species_bank = [
        {"name": s["name"], "scientific": s["scientific"], "family": s["family"], "subfamily": s["subfamily"], "slug": slug(s["scientific"])}
        for s in SPECIES
    ]
    facts = [
        ["Which butterfly is Tamil Nadu's official State Butterfly (தமிழ் மறவன்)?", ["Tamil Yeoman", "Common Banded Peacock", "Southern Birdwing", "Red Pierrot"], "Tamil Nadu adopted the Tamil Yeoman (Cirrochroa thais) in 2019.", "cirrochroa-thais", "Nymphalidae", "Look for orange wings crossed by dark markings and a silvery-pale underside band."],
        ["Which butterfly species appears at the heart of The Nature and Butterfly Society (TNBS) emblem?", ["Common Banded Peacock", "Blue Mormon", "Tamil Yeoman", "Lime Butterfly"], "Papilio crino, the Common Banded Peacock, features emerald-green wings with a turquoise median band and serves as TNBS's emblem.", "papilio-crino", "Papilionidae", "An emerald-green swallowtail whose caterpillars feed on East Indian Satinwood."],
        ["How many butterfly species are documented in Tamil Nadu's state butterfly checklist?", ["329 species", "285 species", "312 species", "410 species"], "TNBS records 329 species across 6 families (325 validated in Tamil Nadu, with 4 awaiting confirmation).", "", "All", "The count increased from 323 in 2015 and 328 in 2022 to 329 in 2025."],
        ["Which two recent species additions expanded the Tamil Nadu checklist to 329 species?", ["Common Palmfly & Cloud Forest Silverline", "Blue Mormon & Painted Lady", "Crimson Rose & Yamfly", "Peacock Pansy & Rice Swift"], "Elymnias hypermnestra and Cigaritis meghamalaiensis (described from Meghamalai in 2023) brought the state list to 329.", "cigaritis-meghamalaiensis", "Lycaenidae", "One feeds on palms around Chennai and Sirumalai; the other is a newly described Theni hill silverline."],
        ["Which butterfly has a white underside with black markings and a bold orange hindwing border?", ["Red Pierrot", "Common Pierrot", "Banded Blue Pierrot", "Common Grass Yellow"], "The Red Pierrot (Talicada nyseus) breeds inside succulent Kalanchoe leaves.", "talicada-nyseus", "Lycaenidae", "Often seen fluttering gently near courtyard Kalanchoe plants."],
        ["Which large swallowtail is Tamil Nadu's largest butterfly and a Western Ghats endemic?", ["Southern Birdwing", "Blue Mormon", "Clipper", "Malabar Banded Peacock"], "Troides minos reaches up to 190 mm wingspan with golden-yellow hindwings.", "troides-minos", "Papilionidae", "Also known as the Sahyadri Birdwing."],
        ["Which species was observed migrating in thousands during the June 2024 Mudumalai survey?", ["Common Grass Yellow", "Tamil Yeoman", "Blue Pansy", "Crimson Rose"], "TNBS and Forest Department teams documented thousands of Common Grass Yellows (Eurema hecabe) moving in Mudumalai.", "eurema-hecabe", "Pieridae", "A small yellow pierid with two dark spots inside its underside forewing cell."],
        ["Which two Danainae groups make up the vast directional butterfly migrations between Yercaud and Coimbatore?", ["Tigers and Crows", "Pansies and Sailers", "Swifts and Darts", "Oakblues and Royals"], "Blue Tigers, Dark Blue Tigers, Common Crows, and Double-branded Crows drive Tamil Nadu's biannual migrations.", "tirumala-limniace", "Nymphalidae", "Monitored by TNBS since 2013 across Salem, Tiruppur, and Coimbatore."],
        ["What AI identification platform created by a TNBS member identifies 923+ Indian butterfly species from photos?", ["Butterfly Vision", "WikiWings", "GhatsLens", "MothScan"], "Butterfly Vision (butterflyvision.in), built by Theivaprakasham Hari, runs Western Ghats and All India deep learning models.", "", "All", "Integrated right into our AI Identify page!"],
        ["Which Schedule II mistletoe butterfly was a highlight of the Dec 2024 Pachamalai Hills survey?", ["Banded Royal", "Tiny Grass Blue", "Common Mormon", "Lemon Pansy"], "Rachana jalindra was recorded in healthy numbers in thick Pachamalai forest.", "rachana-jalindra", "Lycaenidae", "Its underside is cleanly split between snow-white outer half and golden-brown inner half."],
        ["Which skipper featured in Pattampoochi has pale yellow-green caterpillars feeding on Urena lobata?", ["Golden Angle", "Grass Demon", "Rice Swift", "Brown Awl"], "Caprona ransonnetti rests with spread wings and contrasts a mottled brown upperside with a chalky-white underside.", "caprona-ransonnetti", "Hesperiidae", "Belongs to Pyrginae, spread-winged flats and angles."],
        ["Which butterfly's early stages and Cynodon dactylon (Bermuda grass) host plant were first documented in India by TNBS authors in 2021?", ["White Four-ring", "Common Four-ring", "Common Five-ring", "Redeye"], "Hari Theivaprakasham, Hari Ramanasaran, and Appavu Pavendhan published Ypthima ceylonica's immature stages in Journal of Threatened Taxa.", "ypthima-ceylonica", "Nymphalidae", "A bright white-hindwinged ringlet common on short lawn grasses."],
        ["Which member of Lycaenidae in Tamil Nadu has carnivorous caterpillars that prey on mealybugs?", ["Apefly", "Monkey Puzzle", "Indian Sunbeam", "Pea Blue"], "Spalgis epius larvae eat mealybugs instead of plant leaves, and its pupa resembles a miniature monkey face.", "spalgis-epius", "Lycaenidae", "Its silvery-grey underside is scribbled with fine wavy brown lines."],
        ["How many walking legs does a brush-footed butterfly (Nymphalidae) use when perching?", ["Four", "Six", "Two", "Eight"], "Nymphalid forelegs are reduced to short brush-like structures, so they stand on their middle and hind pairs.", "", "Nymphalidae", "That anatomical quirk gives brush-footed butterflies their English family name."],
        ["Which mimicry pair involves a distasteful red-bodied swallowtail and a harmless female morph?", ["Crimson Rose & Common Mormon", "Blue Tiger & Plain Tiger", "Common Jezebel & Psyche", "Lime Butterfly & Common Jay"], "Female Common Mormons (romulus form) mimic the distasteful Crimson Rose (Pachliopta hector).", "papilio-polytes", "Papilionidae", "True Rose swallowtails have bright crimson-red bodies; mimics keep black bodies."],
        ["What host plant do caterpillars of the Grass Demon (Udaspes folus) feed on?", ["Turmeric and ginger", "Crown flower (Calotropis)", "Curry leaf", "Coconut palm"], "Grass Demon larvae roll leaves of turmeric (Curcuma) and ginger (Zingiber) plants.", "udaspes-folus", "Hesperiidae", "Look for a dark skipper with a big white central patch on the hindwing."],
        ["Which detail turns a butterfly photograph into a reliable scientific sighting record?", ["Date, exact locality & habitat notes", "Camera brand & megapixel count", "Image file format alone", "Zoom lens focal length"], "Date and locality allow citizen-science records to track seasonality, range shifts, and migrations.", "", "All", "TNBS's checklist relies on verified place-and-date observations."],
        ["Which Nilgiri Biosphere tiger reserve recorded 185+ butterfly species across 8 ranges during the June 2024 monsoon survey?", ["Mudumalai Tiger Reserve", "Point Calimere", "Vandalur Park", "Yelagiri Lake"], "Sixteen teams covering 8 ranges recorded 185+ butterfly species in Mudumalai Tiger Reserve in June 2024.", "", "All", "Located at the Tamil Nadu-Kerala-Karnataka tri-junction."],
        ["Which family is Tamil Nadu's smallest butterfly family with just two Plum Judy species?", ["Riodinidae (Metalmarks)", "Papilionidae (Swallowtails)", "Pieridae (Whites & yellows)", "Hesperiidae (Skippers)"], "Riodinidae has 2 entries in Tamil Nadu: Straight Plum Judy (Abisara echerius) and Plum Judy (Abisara bifasciata).", "abisara-echerius", "Riodinidae", "Shade-loving maroon-brown butterflies that turn abruptly right after landing."],
        ["Which butterfly's female closely mimics the orange-and-black Plain Tiger while its male is jet-black with violet-white ovals?", ["Danaid Eggfly", "Common Baron", "Blue Admiral", "Painted Lady"], "Hypolimnas misippus displays dramatic sexual dimorphism and Batesian mimicry.", "hypolimnas-misippus", "Nymphalidae", "Females lack the cluster of tiny black dots at the hindwing centre found on true Plain Tigers."],
        ["Which migratory painted nymphalid was spotted near Sivaganga in June 2026 press reports?", ["Painted Lady", "Indian Red Admiral", "Blue Pansy", "Grey Count"], "Vanessa cardui is a celebrated long-distance migrant tracked in Tamil Nadu hills and plains.", "vanessa-cardui", "Nymphalidae", "Orange-pink wings with black, white-spotted forewing tips."]
    ]
    payload = {"photos": photo_bank, "species": species_bank, "facts": facts}
    (OUT / "assets" / "quiz-data.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_redirect(old_path, target_rel, title):
    target_file = OUT / old_path / "index.html"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0; url={h(target_rel)}">
<link rel="canonical" href="{h(target_rel)}">
<title>Moved: {h(title)} | TNBS</title></head>
<body><p>This species record moved to <a href="{h(target_rel)}">{h(title)}</a>.</p></body></html>""",
        encoding="utf-8",
    )


def main():
    if len(SPECIES) != 329 or len({route(s) for s in SPECIES}) != len(SPECIES):
        raise SystemExit("Expected 329 distinct species routes.")
    for fam, expected in EXPECTED_FAMILY_COUNTS.items():
        actual = len(BY_FAMILY.get(fam, []))
        if actual != expected:
            raise SystemExit(f"Expected {expected} species in {fam}, found {actual}.")
    if any(not entry["name"] or entry["subfamily"] not in TAXONOMY["subfamilies"] for entry in SPECIES):
        raise SystemExit("Every species needs a common name and valid subfamily in data/taxonomy.json.")
    if not set(PHOTOS).issubset(BY_SCI) or any(
        not (item.get("author") if isinstance(item, dict) else item[1]) for item in PHOTOS.values()
    ):
        raise SystemExit("Every photo needs a checklist match and author credit.")

    shutil.copytree(ROOT / "assets", OUT / "assets", dirs_exist_ok=True)
    home()
    guide()
    for entry in SPECIES:
        detail(entry)
    identify()
    magazine()
    news()
    activities()
    about()
    sources()
    quiz()
    render(
        "404.html",
        "Page not found",
        "Find the TNBS home page, butterfly field guide, or Butterfly Vision AI tool.",
        heading("Page not found", "Use the navigation menu to return to the TNBS home page or 329-species field guide."),
    )
    write_redirect("butterflies/cigaritis-meghamaleinsis", "../cigaritis-meghamalaiensis/index.html", "Cloud Forest Silverline (Cigaritis meghamalaiensis)")
    (OUT / ".nojekyll").touch()
    build_quiz_data()
    (OUT / "assets" / "quiz-photos.json").write_text(json.dumps({s: photo_meta(s, "../") for s in PHOTOS}, ensure_ascii=False), encoding="utf-8")

    sitemap = OUT / "sitemap.xml"
    if BASE:
        urls = "".join(f"<url><loc>{h(BASE + path)}</loc></url>\n" for path in PAGES)
        sitemap.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n", encoding="utf-8")
    elif sitemap.exists():
        sitemap.unlink()
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\n" + (f"Sitemap: {BASE}sitemap.xml\n" if BASE else ""), encoding="utf-8")
    print(f"Built {len(PAGES)} public pages, 1 redirect, and 404.html in {OUT}")


if __name__ == "__main__":
    main()
