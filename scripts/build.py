"""Build the static bilingual (EN + TA) TNBS website into docs/."""
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
INAT_PROJECT_URL = "https://www.inaturalist.org/projects/butterflies-of-tamil-nadu"
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
HOST_PLANTS = (
    load("host_plants")
    if (ROOT / "data" / "host_plants.json").exists()
    else {"plants": {}, "bySpecies": {}}
)
def load_opt(name, default):
    path = ROOT / "data" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


GALLERIES = load_opt("galleries", {})
INAT = load_opt("inat_project", {"project": {}, "months": [0] * 12, "topSpecies": [], "topObservers": [], "recent": [], "bySpecies": {}})
TAMIL_NAMES = load_opt("tamil_names", {})
I18N_TA = load_opt("i18n_ta", {})
PROFILES_TA = load_opt("profiles_ta", {})
SITE_TA = load_opt("site_ta", {})
TAXONOMY_TA = load_opt("taxonomy_ta", {})
MAGAZINE_TA = {item["issue"]: item for item in load_opt("magazine_index_ta", [])}
TA_UI = I18N_TA.get("ui", {})

TAXONOMY = load("taxonomy")
SITE = load("site")
MAGAZINE_INDEX = {item["issue"]: item for item in load("magazine_index")}
BY_SCI = {s["scientific"]: s for s in SPECIES}
BY_FAMILY = {}
for item in SPECIES:
    BY_FAMILY.setdefault(item["family"], []).append(item)

MONTHS_TA_SHORT = {
    "01": "ஜன",
    "02": "பிப்",
    "03": "மார்",
    "04": "ஏப்",
    "05": "மே",
    "06": "ஜூன்",
    "07": "ஜூலை",
    "08": "ஆக",
    "09": "செப்",
    "10": "அக்",
    "11": "நவ",
    "12": "டிச",
}


def fmt_date(day_str, lang="en"):
    d = date.fromisoformat(day_str)
    if lang == "ta":
        m_ta = MONTHS_TA_SHORT.get(f"{d.month:02d}", d.strftime("%b"))
        return f"{d.day} {m_ta} {d.year}"
    return d.strftime("%d %b %Y").lstrip("0")


def press_cat(category, lang="en"):
    if lang == "ta":
        return SITE_TA.get("pressCategories", {}).get(category, category)
    return category


def press_src(source, lang="en"):
    if lang == "ta":
        return SITE_TA.get("pressSources", {}).get(source, source)
    return source

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
    "sightings/": "Sightings",
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
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
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


def paths_for(path, lang="en"):
    out_path = ("ta/" + path) if lang == "ta" else path
    asset_prefix = "../" * out_path.count("/")
    lang_prefix = "../" * (path.count("/") if path.endswith("/") else 0)
    en_rel = path if path == "404.html" else local("", path)
    ta_rel = ("ta/" + path) if path == "404.html" else local("ta/", path)
    mirror_href = asset_prefix + (ta_rel if lang == "en" else en_rel)
    return out_path, asset_prefix, lang_prefix, en_rel, ta_rel, mirror_href


def tamil_name(scientific):
    rec = TAMIL_NAMES.get(scientific)
    if isinstance(rec, dict) and rec.get("ta"):
        return rec["ta"]
    prof = PROFILES.get(scientific)
    if isinstance(prof, dict) and prof.get("tamilName"):
        return prof["tamilName"].split("(")[0].strip()
    return ""


def fam_name(family, lang="en"):
    if lang == "ta":
        return I18N_TA.get("families", {}).get(family, {}).get("name", family)
    return family


def fam_desc(family, lang="en"):
    if lang == "ta":
        return I18N_TA.get("families", {}).get(family, {}).get("desc", FAMILIES[family])
    return FAMILIES[family]


def sub_desc(subfamily, lang="en"):
    if lang == "ta":
        return I18N_TA.get("subfamilies", {}).get(subfamily, TAXONOMY["subfamilies"][subfamily]["group"])
    return TAXONOMY["subfamilies"][subfamily]["group"]


def nav_text(key, lang="en"):
    if lang == "ta":
        return I18N_TA.get("nav", {}).get(key, NAV[key])
    return NAV[key]


def license_info(license_id):
    if license_id == "cc0/1.0":
        return ("https://creativecommons.org/publicdomain/zero/1.0/", "CC0 1.0")
    if license_id == "pdm/1.0":
        return ("https://creativecommons.org/publicdomain/mark/1.0/", "Public Domain")
    return (
        "https://creativecommons.org/licenses/" + license_id + "/",
        "CC " + license_id.replace("/", " ").upper(),
    )


def resolve_license(license_id, default_name="TNBS Member Archive"):
    if license_id:
        return license_info(license_id)
    return ("", default_name)


def commons_src(filename, width, prefix, thumb=False, allow_cached_sci=None):
    wiki_name = filename.replace(" ", "_")
    digest = hashlib.md5(wiki_name.encode(), usedforsecurity=False).hexdigest()
    media_path = f"{digest[0]}/{digest[:2]}/{quote(wiki_name)}"
    chosen_width = min(width, 500) if thumb and width else (width if width else 0)
    src = f"https://upload.wikimedia.org/wikipedia/commons/{media_path}"
    if chosen_width:
        src = f"https://upload.wikimedia.org/wikipedia/commons/thumb/{media_path}/{chosen_width}px-{quote(wiki_name)}"
    if allow_cached_sci:
        cached = Path("photos") / (slug(allow_cached_sci) + ".jpg")
        if (ROOT / "assets" / cached).exists():
            src = prefix + "assets/" + cached.as_posix()
    return src


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
        lic_url, lic_name = resolve_license(rec.get("license") or "", rec.get("licenseName") or "TNBS Member Archive")
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
    return {
        "src": commons_src(filename, width, prefix, thumb=thumb, allow_cached_sci=scientific),
        "alt": alt,
        "author": author,
        "url": "https://commons.wikimedia.org/wiki/File:" + quote(wiki_name),
        "license": lic_url,
        "licenseName": lic_name,
        "sourceLabel": "Commons file",
        "member": is_member,
    }


def gallery_item_meta(scientific, item, prefix, thumb=False, is_primary=False):
    src_type = item.get("source")
    if src_type == "local":
        return {
            "src": prefix + item["file"],
            "alt": item["alt"],
            "author": item["author"],
            "url": item.get("url", ""),
            "license": "",
            "licenseName": item.get("licenseName", "TNBS Member Archive"),
            "sourceLabel": "",
            "note": item.get("note", ""),
            "member": bool(item.get("member", True)),
        }
    lic_url, lic_name = resolve_license(item.get("license") or "", item.get("licenseName") or "TNBS Member Archive")
    if src_type == "inaturalist":
        return {
            "src": item["thumb"] if thumb else item["full"],
            "alt": item["alt"],
            "author": item["author"],
            "url": item["url"],
            "license": lic_url,
            "licenseName": lic_name,
            "sourceLabel": "iNaturalist observation",
            "note": item.get("note", ""),
            "member": bool(item.get("member", True)),
        }
    filename = item["file"]
    wiki_name = filename.replace(" ", "_")
    return {
        "src": commons_src(filename, int(item.get("width") or 0), prefix, thumb=thumb, allow_cached_sci=scientific if is_primary else None),
        "alt": item["alt"],
        "author": item["author"],
        "url": "https://commons.wikimedia.org/wiki/File:" + quote(wiki_name),
        "license": lic_url,
        "licenseName": lic_name,
        "sourceLabel": "Commons file",
        "note": item.get("note", ""),
        "member": bool(item.get("member")),
    }


def credit_html(meta, include_source=False):
    parts = [link(meta["author"], meta["url"]) if meta["url"] else h(meta["author"])]
    if meta["licenseName"]:
        parts.append(link(meta["licenseName"], meta["license"]) if meta["license"] else h(meta["licenseName"]))
    if include_source and meta["url"] and meta["sourceLabel"]:
        parts.append(link(meta["sourceLabel"], meta["url"]))
    return " · ".join(parts)


def photo(scientific, asset_prefix, mode="card", lang="en"):
    if scientific not in PHOTOS:
        return ""
    meta = photo_meta(scientific, asset_prefix, thumb=(mode == "card"))
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
        g_count = len(GALLERIES.get(scientific, []))
        unit = TA_UI.get("photosUnit", "படங்கள்") if lang == "ta" else "photos"
        badge = (
            f'<span class="photo-count-badge" aria-label="{g_count} {h(unit)}">{g_count} {h(unit)}</span>'
            if g_count >= 2
            else ""
        )
        return (
            f'<div class="media bare"><img class="hide-on-error" src="{h(meta["src"])}" '
            f'alt="{h(meta["alt"])}" loading="lazy" decoding="async">{badge}</div>'
            f'<p class="credit">{credit}</p>'
        )
    full_meta = photo_meta(scientific, asset_prefix, thumb=False)
    zoom_txt = "பெரிதாக்கச் சொடுக்கவும்" if lang == "ta" else "Click to enlarge"
    zoom_btn = (
        f'<button type="button" class="photo-zoom" data-lightbox-src="{h(full_meta["src"])}" '
        f'data-lightbox-title="{h(species_name)} ({h(scientific)})" '
        f'data-lightbox-alt="{h(full_meta["alt"])}" '
        f'data-lightbox-author="{h(full_meta["author"])}" '
        f'data-lightbox-url="{h(full_meta["url"])}" '
        f'data-lightbox-license="{h(full_meta["license"])}" '
        f'data-lightbox-licensename="{h(full_meta["licenseName"])}" '
        f'aria-label="Inspect full-size photograph of {h(species_name)}">'
        f'<img class="hide-on-error" src="{h(meta["src"])}" alt="{h(meta["alt"])}" fetchpriority="high" decoding="async">'
        f'<span class="zoom-hint" aria-hidden="true">{h(zoom_txt)}</span></button>'
    )
    return (
        f'<figure class="photo-large">{zoom_btn}'
        f'<figcaption class="credit">{credit_html(meta, include_source=True)}</figcaption></figure>'
    )


def species_gallery(scientific, asset_prefix, lang="en"):
    raw_items = GALLERIES.get(scientific, [])
    if len(raw_items) < 2:
        return photo(scientific, asset_prefix, "detail", lang=lang)
    species_name = BY_SCI[scientific]["name"]
    ta_sp = tamil_name(scientific)
    display_title = f"{ta_sp} · {species_name} ({scientific})" if (lang == "ta" and ta_sp) else f"{species_name} ({scientific})"
    zoom_txt = "பெரிதாக்கச் சொடுக்கவும்" if lang == "ta" else "Click to enlarge"
    slides = []
    thumb_btns = []
    total = len(raw_items)
    for idx, raw in enumerate(raw_items):
        full_meta = gallery_item_meta(scientific, raw, asset_prefix, thumb=False, is_primary=(idx == 0))
        thumb_meta = gallery_item_meta(scientific, raw, asset_prefix, thumb=True, is_primary=(idx == 0))
        slide = {
            "src": full_meta["src"],
            "thumbSrc": thumb_meta["src"],
            "title": display_title,
            "alt": full_meta["alt"],
            "author": full_meta["author"],
            "url": full_meta["url"],
            "license": full_meta["license"],
            "licenseName": full_meta["licenseName"],
            "sourceLabel": full_meta["sourceLabel"],
            "note": full_meta["note"],
        }
        slides.append(slide)
        cur = "true" if idx == 0 else "false"
        t_label = (
            f"படம் {idx + 1} / {total}" if lang == "ta" else f"View photo {idx + 1} of {total}"
        ) + (f": {slide['note']}" if slide["note"] else f" ({slide['author']})")
        thumb_btns.append(
            f'<button type="button" class="gallery-thumb" data-gallery-idx="{idx}" '
            f'aria-current="{cur}" aria-label="{h(t_label)}">'
            f'<img src="{h(slide["thumbSrc"])}" alt="" loading="lazy" decoding="async">'
            f'<span class="thumb-idx" aria-hidden="true">{idx + 1}</span></button>'
        )
    first = slides[0]
    note_attr = "" if first["note"] else " hidden"
    payload = json.dumps(slides, ensure_ascii=False, separators=(",", ":"))
    prev_lbl = "முந்தைய படம்" if lang == "ta" else "Previous photograph"
    next_lbl = "அடுத்த படம்" if lang == "ta" else "Next photograph"
    return (
        f'<section class="species-gallery" aria-roledescription="carousel" '
        f'aria-label="Field photographs of {h(species_name)}" data-species-gallery="{h(payload)}">'
        f'<figure class="photo-large gallery-stage">'
        f'<div class="gallery-nav">'
        f'<button type="button" class="gallery-arrow gallery-prev" data-gallery-dir="-1" aria-label="{h(prev_lbl)}">‹</button>'
        f'<button type="button" class="gallery-arrow gallery-next" data-gallery-dir="1" aria-label="{h(next_lbl)}">›</button>'
        f'</div>'
        f'<button type="button" class="photo-zoom gallery-main-btn" data-gallery-zoom data-gallery-current="0" '
        f'data-lightbox-src="{h(first["src"])}" '
        f'data-lightbox-title="{h(first["title"])}" '
        f'data-lightbox-alt="{h(first["alt"])}" '
        f'data-lightbox-author="{h(first["author"])}" '
        f'data-lightbox-url="{h(first["url"])}" '
        f'data-lightbox-license="{h(first["license"])}" '
        f'data-lightbox-licensename="{h(first["licenseName"])}" '
        f'aria-label="{h(zoom_txt)}: {h(species_name)}">'
        f'<img data-gallery-img class="hide-on-error" src="{h(first["src"])}" alt="{h(first["alt"])}" fetchpriority="high" decoding="async">'
        f'<span class="gallery-counter" data-gallery-counter aria-hidden="true">1 / {total}</span>'
        f'<span class="zoom-hint" aria-hidden="true">{h(zoom_txt)}</span></button>'
        f'<figcaption class="gallery-caption">'
        f'<span class="gallery-note" data-gallery-note{note_attr}>{h(first["note"])}</span>'
        f'<span class="credit" data-gallery-credit>{credit_html(first, include_source=True)}</span>'
        f'</figcaption></figure>'
        f'<p class="visually-hidden" role="status" aria-live="polite" data-gallery-status></p>'
        f'<div class="gallery-thumbs" role="group" aria-label="Choose a photograph of {h(species_name)}">{"".join(thumb_btns)}</div>'
        f'</section>'
    )


HOST_STANDALONE_GENERA = {
    "Arundinella", "Themeda", "Oplismenus", "Ochlandra", "Panicum",
    "Millettia", "Callerya", "Dendrophthoe", "Loranthus", "Planococcus",
    "Ferrisia", "Chrysopogon", "Cymbopogon", "Bryophyllum", "Caprona",
    "Microcos", "Helicteres", "Crematogaster",
}
HOST_NON_GENUS = {
    "All", "Bamboo", "Bermuda", "Cane", "Carpet", "Chinese", "Coconut",
    "Common", "Creeping", "Crown", "Custard", "Dry", "East", "Eastern",
    "Eeta", "Elephant", "False", "Fishtail", "Flame", "Foothill", "Forest",
    "Garden", "Ghat", "Golden", "Grass", "Guinea", "Hill", "Hyacinth",
    "Indian", "Jackal", "Kamala", "Key", "King", "Lalang", "Life", "Mango",
    "Mistletoe", "Montane", "Mung", "Myrmecophilous", "Native", "Orangeberry",
    "Ornamental", "Paddy", "Palmyra", "Para", "Pigeon", "Pomegranate",
    "Pongam", "Predatory", "Puncture", "Queen", "Rattan", "Red", "Rice",
    "Satinwood", "Shaded", "Shamrock", "South", "Stinking", "Terrestrial",
    "Thorny", "Tiger", "Toothbrush", "Various", "Wet", "White", "Wild",
    "Woodsorrel",
}
HOST_NON_EPITHET = (
    "species|spp\\.?|sp\\.?|and|or|grasses|reeds|herbs|clovers|shrubs|trees|"
    "climbers|palms|mistletoes|legumes|bamboo|vines|plants|leaves|flowers|"
    "fruits|ants|associations|feed|on|of|in|as|such|syn|rattans|yams|banana|"
    "palm|tree|grass|pea|bean|apple|leaf|vine|orchid|reed|flower|creeper|"
    "passionflower|knotweed|leadwort|beech|jujube|bead|nettle|sago|lime|host|"
    "woody|dryland|meadow|undergrowth|forest|montane|shola"
)
HOST_TAXON_RE = re.compile(
    r"\b([A-Z][a-z]+)(?=\s+(?:species|spp\.?|sp\.?)\b)"
    r"|\b([A-Z][a-z]+)\s+(?!(?:" + HOST_NON_EPITHET + r")\b)([a-z][a-z-]+)\b"
    r"|\b(" + "|".join(sorted(HOST_STANDALONE_GENERA, key=len, reverse=True)) + r")\b"
)


def tokenize_host_plant(text):
    parts = []
    pos = 0
    for m in HOST_TAXON_RE.finditer(text):
        start, end = m.span()
        g_sp, g_bi, ep_bi, g_solo = m.groups()
        italic_seg = None
        if g_sp:
            if g_sp not in HOST_NON_GENUS and not g_sp.endswith(("aceae", "oideae")):
                italic_seg = g_sp
        elif g_bi:
            if g_bi not in HOST_NON_GENUS and not g_bi.endswith(("aceae", "oideae")):
                italic_seg = f"{g_bi} {ep_bi}"
        elif g_solo:
            italic_seg = g_solo
        if italic_seg is None:
            continue
        if start > pos:
            parts.append([text[pos:start], False])
        parts.append([italic_seg, True])
        pos = end
    if pos < len(text):
        parts.append([text[pos:], False])
    return parts


def format_host_plant_html(text):
    return "".join(f"<i>{h(seg)}</i>" if is_it else h(seg) for seg, is_it in tokenize_host_plant(text))


def host_plant_gallery(scientific, lang="en"):
    entries = HOST_PLANTS.get("bySpecies", {}).get(scientific, [])
    plants = HOST_PLANTS.get("plants", {})
    if not entries:
        return ""
    species_name = BY_SCI[scientific]["name"]
    cards = []
    for item in entries:
        plant = plants.get(item.get("plantKey", ""))
        if not plant:
            continue
        taxon = plant["taxon"]
        is_genus = plant.get("rank") == "genus"
        plain_taxon = f"{taxon} sp." if is_genus else taxon
        taxon_html = f"<i>{h(taxon)}</i> sp." if is_genus else f"<i>{h(taxon)}</i>"
        common = plant.get("commonName") or ""
        host_base = re.split(r"\s*\(", item.get("hostLabel", ""))[0].strip()
        match_kind = item.get("matchKind", "exact")
        if match_kind == "synonym" and host_base and host_base.lower() != taxon.lower():
            prefix_txt = f"{h(common)} · " if common else ""
            meta_html = f'<span class="host-meta">{prefix_txt}syn. <i>{h(host_base)}</i></span>'
        elif match_kind == "genus" and not re.search(r"\b(species|spp|sp\.?)\b", host_base, re.I):
            prefix_txt = f"{h(common)} · " if common else ""
            rel_txt = "ஒரே பேரினத் தாவரம்" if lang == "ta" else "Related genus host"
            meta_html = f'<span class="host-meta">{prefix_txt}{rel_txt}</span>'
        elif common:
            meta_html = f'<span class="host-meta">{h(common)}</span>'
        else:
            meta_html = ""
        lic_url, lic_name = resolve_license(plant.get("license") or "", plant.get("licenseName") or "TNBS Member Archive")
        author_short = plant["author"].replace(" (TNBS)", "")
        common_paren = f" ({common})" if common else ""
        alt = f"{plain_taxon}{common_paren}, larval host plant of {species_name}, photographed by {author_short}"
        credit = credit_html(
            {
                "author": plant["author"],
                "url": plant["url"],
                "license": lic_url,
                "licenseName": lic_name,
            }
        )
        btn = (
            f'<button type="button" class="photo-zoom host-photo-btn" '
            f'data-lightbox-src="{h(plant["full"])}" '
            f'data-lightbox-title="{h(plain_taxon)}{h(common_paren)}" '
            f'data-lightbox-alt="{h(alt)}" '
            f'data-lightbox-author="{h(plant["author"])}" '
            f'data-lightbox-url="{h(plant["url"])}" '
            f'data-lightbox-license="{h(lic_url)}" '
            f'data-lightbox-licensename="{h(lic_name)}" '
            f'aria-label="Enlarge host plant photograph: {h(plain_taxon)}">'
            f'<img class="hide-on-error" src="{h(plant["thumb"])}" alt="{h(alt)}" loading="lazy" decoding="async">'
            f'</button>'
        )
        cards.append(
            f'<figure class="host-card">{btn}'
            f'<figcaption><strong class="host-name">{taxon_html}</strong>{meta_html}'
            f'<span class="host-credit">{credit}</span></figcaption></figure>'
        )
    if not cards:
        return ""
    head = TA_UI.get("hostGalleryHead", "உணவூட்டும் தாவரப் படங்கள் (பெரிதாக்கச் சொடுக்கவும்)") if lang == "ta" else "Host plant field photos (click to enlarge)"
    return (
        '<div class="host-gallery-block">'
        f'<p class="host-gallery-head">{h(head)}</p>'
        f'<div class="host-gallery">{"".join(cards)}</div>'
        '</div>'
    )


def lightbox_button_img(src, alt, title, caption, asset_prefix, width=1200, height=800, img_class=""):
    cls_attr = f' class="{h(img_class)}"' if img_class else ""
    return (
        f'<button type="button" class="photo-zoom gallery-zoom" '
        f'data-lightbox-src="{h(asset_prefix + src)}" '
        f'data-lightbox-title="{h(title)}" '
        f'data-lightbox-alt="{h(alt)}" '
        f'data-lightbox-caption="{h(caption)}" '
        f'aria-label="Enlarge photograph: {h(title)}">'
        f'<img{cls_attr} src="{h(asset_prefix + src)}" alt="{h(alt)}" width="{width}" height="{height}" loading="lazy" decoding="async">'
        f'</button>'
    )


def phenology_chart_html(months, lang="en", caption=""):
    if not months or len(months) != 12 or sum(months) == 0:
        return ""
    names = I18N_TA.get("months", MONTHS_EN) if lang == "ta" else MONTHS_EN
    max_val = max(months) or 1
    bars = []
    for idx, val in enumerate(months):
        pct = round((val / max_val) * 100) if val else 0
        bar_h = max(pct, 6) if val else 2
        val_txt = f"{val:,}" if val < 10000 else f"{val / 1000:.1f}k"
        zero_cls = " is-zero" if val == 0 else ""
        bars.append(
            f'<li class="pheno-col{zero_cls}" title="{h(names[idx])}: {val:,}">'
            f'<span class="pheno-val">{h(val_txt)}</span>'
            f'<span class="pheno-track" aria-hidden="true"><span class="pheno-bar" style="--bar-h:{bar_h}%;"></span></span>'
            f'<span class="pheno-month">{h(names[idx])}</span>'
            f'</li>'
        )
    cap_html = f'<p class="caption pheno-caption">{h(caption)}</p>' if caption else ""
    region_lbl = caption or ("மாதாந்திர அவதானிப்பு வரைபடம்" if lang == "ta" else "Monthly observations chart")
    return f'{cap_html}<div class="pheno-scroll" role="region" tabindex="0" aria-label="{h(region_lbl)}"><ol class="phenology-chart" aria-label="{h(region_lbl)}">{"".join(bars)}</ol></div>'


def inat_map_html(project_id, taxon_id=0, lang="en", lazy=False, direct_url=""):
    is_ta = lang == "ta"
    hm_lbl = TA_UI.get("heatmapBtn", "வெப்ப வரைபடம் (Heatmap)") if is_ta else "Density Heatmap"
    pt_lbl = TA_UI.get("pointsBtn", "புள்ளிப் பதிவுகள்") if is_ta else "Observation Points"
    load_lbl = TA_UI.get("loadMapBtn", "தமிழ்நாடு பரவல் வரைபடத்தைத் திற") if is_ta else "Load interactive Tamil Nadu sightings map"
    browse_lbl = TA_UI.get("browseInatProject", "திட்டம் #47280-இல் அனைத்து பதிவுகளையும் பார் ↗") if is_ta else "Open observations on iNaturalist ↗"
    taxon_attr = f' data-taxon-id="{int(taxon_id)}"' if taxon_id else ""
    lazy_attr = ' data-lazy-map="true"' if lazy else ""
    launch_btn = (
        f'<div class="inat-map-placeholder"><button type="button" class="button outline" data-load-map>{h(load_lbl)}</button></div>'
        if lazy
        else ""
    )
    canvas_hidden = " hidden" if lazy else ""
    return (
        f'<div class="inat-map-box" data-inat-map data-project="{int(project_id)}"{taxon_attr} data-map-mode="heatmap"{lazy_attr}>'
        f'<div class="inat-map-toolbar">'
        f'<div class="choices" role="group" aria-label="Map layer mode">'
        f'<button type="button" class="choice" data-map-layer="heatmap" aria-pressed="true">{h(hm_lbl)}</button>'
        f'<button type="button" class="choice" data-map-layer="points" aria-pressed="false">{h(pt_lbl)}</button>'
        f'</div>'
        f'{link(browse_lbl, direct_url or INAT_PROJECT_URL, "caption")}'
        f'</div>'
        f'{launch_btn}'
        f'<div class="inat-map-canvas" data-map-canvas{canvas_hidden}></div>'
        f'<p role="status" aria-live="polite" class="caption" data-map-status></p>'
        f'</div>'
    )


def identity(asset_prefix, lang_prefix, lang="en", is_footer=False):
    lazy_attr = ' loading="lazy"' if is_footer else ""
    title = I18N_TA["brand"] if lang == "ta" else NAME
    sub = I18N_TA["brandSub"] if lang == "ta" else "TNBS · TAMIL NADU, INDIA"
    return (
        f'<a class="identity" href="{local(lang_prefix)}">'
        f'<img class="brand-logo" src="{asset_prefix}assets/tnbs-logo.png" alt="" width="48" height="48"{lazy_attr}>'
        f'<span><strong>{h(title)}</strong><small>{h(sub)}</small></span></a>'
    )


def lightbox_dialog(lang="en"):
    is_ta = lang == "ta"
    close_lbl = "மூடு" if is_ta else "Close"
    prev_lbl = "← முந்தையது" if is_ta else "← Prev"
    next_lbl = "அடுத்தது →" if is_ta else "Next →"
    heading_txt = "பட்டாம்பூச்சி புகைப்படம்" if is_ta else "Butterfly photograph"
    return f"""<dialog id="lightbox" class="lightbox" closedby="any" aria-labelledby="lightbox-title">
<div class="lightbox-frame"><div class="lightbox-head">
<div><h1 id="lightbox-title" class="lightbox-heading">{h(heading_txt)}</h1>
<p id="lightbox-sub" class="caption"></p></div>
<form method="dialog"><button type="submit" class="button outline lightbox-close" aria-label="{h(close_lbl)}">{h(close_lbl)}</button></form>
</div><div class="lightbox-stage"><img id="lightbox-img" src="" alt=""></div>
<div class="lightbox-nav" data-lightbox-nav hidden>
<button type="button" class="button outline lightbox-step" data-lightbox-dir="-1" aria-label="{h(prev_lbl)}">{h(prev_lbl)}</button>
<span class="lightbox-counter" data-lightbox-counter></span>
<button type="button" class="button outline lightbox-step" data-lightbox-dir="1" aria-label="{h(next_lbl)}">{h(next_lbl)}</button>
</div>
<p id="lightbox-credit" class="credit"></p></div></dialog>"""


def render(path, title, description, body, active=None, image_key=None, schema=None, lang="en"):
    out_path, asset_prefix, lang_prefix, en_rel, ta_rel, mirror_href = paths_for(path, lang=lang)
    is_ta = lang == "ta"
    other_lang = "en" if is_ta else "ta"
    lang_label = "English" if is_ta else "தமிழ்"
    brand_title = I18N_TA["brand"] if is_ta else NAME
    display_title = title + " | TNBS" if path else title
    url = BASE + out_path if BASE else ""
    canonical = f'<link rel="canonical" href="{h(url)}"><meta property="og:url" content="{h(url)}">' if url else ""
    alternates = ""
    if path != "404.html":
        en_alt = (BASE + path) if BASE else (asset_prefix + en_rel)
        ta_alt = (BASE + "ta/" + path) if BASE else (asset_prefix + ta_rel)
        alternates = (
            f'<link rel="alternate" hreflang="en" href="{h(en_alt)}">'
            f'<link rel="alternate" hreflang="ta" href="{h(ta_alt)}">'
        )
    cover = ""
    if image_key and image_key in PHOTOS:
        media = photo_meta(image_key, asset_prefix)
        img = media["src"]
        if not img.startswith("https://") and BASE:
            img = BASE + img.removeprefix(asset_prefix)
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

    nav_items = []
    current_key = path if active is None else active
    for dest in NAV:
        current = ' aria-current="page"' if dest == current_key else ""
        nav_items.append(f'<li><a href="{local(lang_prefix, dest)}"{current}>{h(nav_text(dest, lang))}</a></li>')
    get_inv_lbl = I18N_TA["nav"]["getInvolved"] if is_ta else "Get involved"
    nav_items.append(f'<li>{link(get_inv_lbl, local(lang_prefix, "about/") + "#get-involved", "small-button")}</li>')

    menu_lbl = I18N_TA["nav"]["menu"] if is_ta else "Menu"
    nav_aria = "முதன்மை வழிசெலுத்தல்" if is_ta else "Main navigation"
    nav_html = (
        f'<nav id="primary" class="site-nav" aria-label="{h(nav_aria)}">'
        f'<button type="button" class="nav-toggle menu-button" popovertarget="primary-menu" popovertargetaction="toggle" aria-controls="primary-menu">{h(menu_lbl)}</button>'
        f'<ul id="primary-menu" class="site-menu" popover="auto">{"".join(nav_items)}</ul>'
        f'</nav>'
    )

    to_dark = TA_UI.get("themeToDark", "இருண்ட தோற்றத்திற்கு மாற்று") if is_ta else "Switch to dark theme"
    to_light = TA_UI.get("themeToLight", "வெளிர் தோற்றத்திற்கு மாற்று") if is_ta else "Switch to light theme"
    header_tools = (
        f'<div class="header-tools">'
        f'<a class="lang-switch" href="{h(mirror_href)}" lang="{other_lang}" hreflang="{other_lang}">{h(lang_label)}</a>'
        f'<button type="button" class="theme-toggle" data-theme-toggle>'
        f'<span class="if-light"><span aria-hidden="true">🌙</span><span class="visually-hidden">{h(to_dark)}</span></span>'
        f'<span class="if-dark"><span aria-hidden="true">☀️</span><span class="visually-hidden">{h(to_light)}</span></span>'
        f'</button>'
        f'</div>'
    )

    tagline = I18N_TA["tagline"] if is_ta else "Documenting butterflies across Tamil Nadu since 2014."
    sources_lbl = I18N_TA["nav"]["sources"] if is_ta else "Sources & photo credits"
    skip_lbl = I18N_TA["nav"]["skip"] if is_ta else "Skip to content"
    top_lbl = I18N_TA["nav"]["top"] if is_ta else "↑ Top"
    inat_footer_lbl = "iNaturalist திட்டம் #47280" if is_ta else "iNaturalist Project #47280"
    reg_footer = "பதிவு எண் 259/2018 · கோயம்புத்தூர், தமிழ்நாடு" if is_ta else "Reg. No. 259/2018 · Coimbatore, Tamil Nadu"
    f_nav1 = "ஆராய்க" if is_ta else "Explore"
    f_nav2 = "சங்கம்" if is_ta else "Society"
    f_nav3 = "தொடர்பு" if is_ta else "Connect"
    top_aria = "மேலே செல்லவும்" if is_ta else "Back to top"
    crawl = '<meta name="robots" content="noindex">' if path == "404.html" else ""

    html = f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<script>try{{var c=localStorage.getItem("color-scheme");if(c==="light"||c==="dark")document.querySelector('meta[name="color-scheme"]').content=c;}}catch(e){{}}</script>
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{h(display_title)}</title><meta name="description" content="{h(description)}">
<meta property="og:site_name" content="{h(brand_title)}"><meta property="og:type" content="website">
<meta property="og:title" content="{h(display_title)}"><meta property="og:description" content="{h(description)}">{canonical}{alternates}{cover}{crawl}
<meta name="twitter:card" content="{'summary_large_image' if cover else 'summary'}">
<link rel="icon" href="{asset_prefix}assets/tnbs-logo.png" type="image/png">
<link rel="apple-touch-icon" href="{asset_prefix}assets/tnbs-logo.png">
<link rel="stylesheet" href="{asset_prefix}assets/site.css"><script defer src="{asset_prefix}assets/site.js"></script>{structured}
</head><body id="top">
<a class="skip" href="#main">{h(skip_lbl)}</a>
<header class="masthead"><div class="wrap header-inner">{identity(asset_prefix, lang_prefix, lang=lang)}
{nav_html}{header_tools}</div></header>
<main id="main">{body}</main>
<footer class="footer"><div class="wrap"><div class="footer-cols"><div>{identity(asset_prefix, lang_prefix, lang=lang, is_footer=True)}<p>{h(tagline)}</p></div>
<nav aria-label="{h(f_nav1)}">{link(nav_text("butterflies/", lang), local(lang_prefix, "butterflies/"))}{link(nav_text("sightings/", lang), local(lang_prefix, "sightings/"))}{link(nav_text("identify/", lang), local(lang_prefix, "identify/"))}{link(nav_text("quiz/", lang), local(lang_prefix, "quiz/"))}</nav>
<nav aria-label="{h(f_nav2)}">{link(nav_text("about/", lang), local(lang_prefix, "about/"))}{link(nav_text("activities/", lang), local(lang_prefix, "activities/"))}{link(nav_text("magazine/", lang), local(lang_prefix, "magazine/"))}{link(sources_lbl, local(lang_prefix, "sources/"))}</nav>
<nav aria-label="{h(f_nav3)}">{link(nav_text("news/", lang), local(lang_prefix, "news/"))}{link(get_inv_lbl, local(lang_prefix, "about/") + "#get-involved")}{link(inat_footer_lbl, INAT_PROJECT_URL)}{link(CONTACT, "mailto:" + CONTACT)}</nav></div>
<div class="footer-bottom"><small>© <span data-footer-year>{date.today().year}</span> {h(brand_title)} · {h(reg_footer)} · {link(lang_label, mirror_href)}</small></div></div></footer>
<a class="back-top" href="#top" data-back-top hidden aria-label="{h(top_aria)}">{h(top_lbl)}</a>
{lightbox_dialog(lang)}
</body></html>"""
    target = OUT / (out_path if path == "404.html" else out_path + "index.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    if path != "404.html":
        PAGES.append(out_path)


def heading(title, description, kicker=""):
    label = f'<p class="kicker">{h(kicker)}</p>' if kicker else ""
    return f'<header class="page-head"><div class="wrap">{label}<h1>{h(title)}</h1><p class="lede">{h(description)}</p></div></header>'


def species_badges_html(entry, compact=False, lang="en"):
    pills = []
    ta_tags = I18N_TA.get("tags", {})
    for tag in entry.get("tags", []):
        if tag in TAG_LABELS:
            label_en, cls = TAG_LABELS[tag]
            label = ta_tags.get(tag, label_en) if lang == "ta" else label_en
            if compact and len(pills) >= 2:
                break
            pills.append(f'<span class="tag tag-{cls}">{h(label)}</span>')
    if not compact:
        if entry.get("validated", True):
            val_txt = ta_tags.get("validated", "Validated in TN") if lang == "ta" else "Validated in TN"
            pills.append(f'<span class="tag tag-valid">{h(val_txt)}</span>')
        else:
            unval_txt = ta_tags.get("unvalidated", "Awaiting TN validation") if lang == "ta" else "Awaiting TN validation"
            pills.append(f'<span class="tag tag-pending">{h(unval_txt)}</span>')
        for m in entry.get("butterflyVision", []):
            bv_txt = f'AI: {"WG" if m == "wg" else "India"}' if lang == "ta" else f'BV: {"WG" if m == "wg" else "India"}'
            pills.append(f'<span class="tag tag-bv">{bv_txt}</span>')
    elif entry.get("butterflyVision") and len(pills) < 2:
        pills.append(f'<span class="tag tag-bv">{"AI" if lang == "ta" else "AI ID"}</span>')
    return '<div class="tag-row">' + "".join(pills) + "</div>" if pills else ""


def is_member_photo(scientific):
    rec = PHOTOS.get(scientific)
    return isinstance(rec, dict) and bool(rec.get("member"))


def species_card(entry, asset_prefix, lang_prefix, include_spot_btn=False, lang="en"):
    name, scientific, family, subfamily = (entry[key] for key in ("name", "scientific", "family", "subfamily"))
    ta_sp = tamil_name(scientific)
    prof = PROFILES.get(scientific, {})
    host_terms = " ".join(prof.get("hostPlants", [])) if isinstance(prof, dict) else ""
    tag_terms = " ".join(entry.get("tags", []))
    bv_terms = " ".join(entry.get("butterflyVision", []))
    val_term = "validated" if entry.get("validated", True) else "unvalidated pending"
    member_flag = int(is_member_photo(scientific))
    author_term = PHOTOS[scientific].get("author", "") if isinstance(PHOTOS.get(scientific), dict) else (PHOTOS[scientific][1] if scientific in PHOTOS else "")
    terms = " ".join([name, ta_sp, scientific, family, FAMILIES[family], fam_name(family, "ta"), subfamily, *entry["aliases"], host_terms, tag_terms, bv_terms, val_term, author_term])
    has_photo = int(scientific in PHOTOS)
    gallery_count = len(GALLERIES.get(scientific, []))
    has_profile = int(scientific in PROFILES)
    spot_btn = ""
    if include_spot_btn:
        spot_txt = TA_UI.get("spottedMark", "+ பார்த்தேன்") if lang == "ta" else "+ Spotted"
        spot_btn = (
            f'<div class="card-foot"><button type="button" class="spot-btn" data-spot-btn data-sci="{h(scientific)}" '
            f'aria-pressed="false" aria-label="Mark {h(name)} as spotted in Tamil Nadu">{h(spot_txt)}</button></div>'
        )
    target_href = local(lang_prefix, route(entry))
    if lang == "ta":
        card_meta = f"{fam_name(family, 'ta')} · {sub_desc(subfamily, 'ta')}"
        title_txt = ta_sp if ta_sp else name
        sub_txt = f'<p class="en-subname">{h(name)}</p>' if ta_sp else ""
    else:
        card_meta = f"{family} · {subfamily}"
        title_txt = name
        sub_txt = f'<p class="tamil-name" lang="ta">{h(ta_sp)}</p>' if ta_sp else ""

    return (
        f'<article class="card reveal" data-species data-id="{entry["id"]}" data-name="{h((ta_sp + " " + name).casefold() if lang == "ta" and ta_sp else name.casefold())}" '
        f'data-sci="{h(scientific.casefold())}" data-family="{h(family)}" data-subfamily="{h(subfamily)}" '
        f'data-terms="{h(terms)}" data-photo="{has_photo}" data-gallery="{gallery_count}" data-member="{member_flag}" data-profile="{has_profile}" '
        f'data-validated="{int(entry.get("validated", True))}" data-tags="{h(tag_terms)}" data-bv="{h(bv_terms)}">'
        f'{photo(scientific, asset_prefix, mode="card", lang=lang)}<div class="card-body">'
        f'<p class="card-meta">{h(card_meta)}</p>'
        f'<h3>{link(title_txt, target_href)}</h3>'
        f'{sub_txt}'
        f'<p class="scientific">{h(scientific)}</p>'
        f'{species_badges_html(entry, compact=True, lang=lang)}'
        f'{spot_btn}'
        f'</div></article>'
    )


def issue_url(number):
    key, separator, query = SITE["issues"][number - 1].partition("?")
    return f"https://drive.google.com/file/d/{key}/view{separator}{query}"


def cover(lang="en"):
    details = "இதழ் 27 · சிறகு 9 · நரம்பு 1<br>ஜனவரி-மார்ச் 2025" if lang == "ta" else "Issue 27 · Wings 9 · Veins 1<br>January-March 2025"
    return (
        '<div class="issue-cover" aria-hidden="true"><div><p class="cover-tamil" lang="ta">பட்டாம்பூச்சி</p>'
        '<p class="cover-title">Pattampoochi</p></div>'
        f'<p class="cover-details">{details}</p></div>'
    )


def press_card(story, idx=0, lang_prefix="", lang="en"):
    day = story["date"]
    when = fmt_date(day, lang)
    is_ta = lang == "ta"
    ta_press = SITE_TA.get("press") or []
    t_story = ta_press[idx] if (is_ta and idx < len(ta_press)) else {}
    cat_disp = press_cat(story["category"], lang)
    src_disp = press_src(story["source"], lang)
    title_txt = t_story.get("title") or story["title"]
    summary_txt = t_story.get("summary") or story["summary"]
    sp_badge = ""
    sp_terms = []
    if story.get("species") and story["species"] in BY_SCI:
        sp = BY_SCI[story["species"]]
        ta_sp_name = tamil_name(sp["scientific"])
        sp_terms.extend(x for x in [sp["name"], ta_sp_name] if x)
        sp_lbl = (ta_sp_name or sp["name"]) if is_ta else sp["name"]
        sp_badge = f' · {link(sp_lbl, local(lang_prefix, route(sp)), "press-species")}'
    terms = " ".join([story["title"], title_txt, story["summary"], summary_txt, story["source"], src_disp, story["category"], cat_disp, day, day[:4], when, story.get("species", ""), *sp_terms])
    read_lbl = "முழுக் கட்டுரையைப் படி ↗" if is_ta else "Read full article ↗"
    return (
        f'<li class="news-card reveal" data-record data-kind="Press" data-category="{h(cat_disp)}" '
        f'data-source="{h(src_disp)}" data-year="{day[:4]}" data-terms="{h(terms)}">'
        f'<div class="news-card-meta"><span class="tag tag-bv">{h(cat_disp)}</span>'
        f'<span class="card-meta">{h(src_disp)} · <time datetime="{day}">{when}</time></span></div>'
        f'<h3>{link(title_txt, story["url"])}</h3>'
        f'<p>{h(summary_txt)}</p>'
        f'<p class="news-card-foot">{link(read_lbl, story["url"])}{sp_badge}</p></li>'
    )


def home_spotlight_section(asset_prefix, lang_prefix, lang="en"):
    is_ta = lang == "ta"
    payload = []
    buttons = []
    ta_spots = SITE_TA.get("spotlights", {}) if is_ta else {}
    for idx, sci in enumerate(SPOTLIGHT_SPECIES):
        sp = BY_SCI[sci]
        prof = PROFILES.get(sci, {})
        t_spot = ta_spots.get(sci, {}) if is_ta else {}
        t_prof = PROFILES_TA.get(sci, {}) if is_ta else {}
        meta = photo_meta(sci, asset_prefix, thumb=False)
        ta_sp = tamil_name(sci)
        disp_name = f"{ta_sp} ({sp['name']})" if (is_ta and ta_sp) else sp["name"]
        btn_name = ta_sp if (is_ta and ta_sp) else sp["name"]
        hosts_en = ", ".join(prof.get("hostPlants", [])[:2]) or "Tamil Nadu checklist species"
        hosts_raw = t_spot.get("hosts") or (hosts_en if not is_ta else (f"உணவூட்டும் தாவரம்: {hosts_en}" if prof.get("hostPlants") else "தமிழ்நாடு பட்டாம்பூச்சிப் பட்டியல் இனம்"))
        payload.append({
            "name": disp_name,
            "scientific": sci,
            "family": f'{fam_name(sp["family"], lang)} ({sub_desc(sp["subfamily"], lang)})' if is_ta else f'{sp["family"]} ({sp["subfamily"]})',
            "headline": t_spot.get("headline") or t_prof.get("headline") or prof.get("headline", ""),
            "wingspan": t_spot.get("wingspan") or t_prof.get("wingspan") or prof.get("wingspan", "தமிழ்நாடு பதிவு" if is_ta else "Field guide entry"),
            "hosts": hosts_raw,
            "hostsParts": tokenize_host_plant(hosts_raw),
            "range": t_spot.get("range") or t_prof.get("tnDistribution") or prof.get("tnDistribution", "தமிழ்நாடு முழுவதும் பதிவானது." if is_ta else "Recorded across Tamil Nadu habitats."),
            "url": local(lang_prefix, route(sp)),
            "src": meta["src"],
            "alt": meta["alt"],
            "author": meta["author"],
            "authorUrl": meta["url"],
            "licenseName": meta["licenseName"],
            "licenseUrl": meta["license"],
        })
        pressed = "true" if idx == 0 else "false"
        buttons.append(
            f'<button type="button" class="choice" data-spot-idx="{idx}" aria-pressed="{pressed}">{h(btn_name)}</button>'
        )
    first = payload[0]
    kicker = TA_UI.get("homeSpotlightKicker", "முதன்மை இனங்கள் அறிமுகம்") if is_ta else "Interactive Species Explorer"
    title = TA_UI.get("homeSpotlightTitle", "தமிழ்நாட்டின் சிறப்புப் பட்டாம்பூச்சிகள்") if is_ta else "Flagship butterflies of Tamil Nadu"
    open_btn = TA_UI.get("openProfileBtn", "முழு இனக் குறிப்பைப் பார் →") if is_ta else "Open full species profile →"
    all_btn = TA_UI.get("browseAll", "அனைத்து 329 இனங்களையும் பார்") if is_ta else "Explore all 329 species"
    wing_dt = TA_UI.get("wingspanLabel", "இறக்கை அகலம்") if is_ta else "Wingspan"
    host_dt = TA_UI.get("hostPlantsTitle", "உணவூட்டும் தாவரங்கள்") if is_ta else "Larval host plants"
    zoom_lbl = "பெரிதாக்கு" if is_ta else "Zoom"
    group_aria = "சிறப்பு இனத்தைத் தேர்ந்தெடுக்கவும்" if is_ta else "Choose a flagship species"
    enlarge_aria = "படத்தைப் பெரிதாக்கவும்" if is_ta else "Enlarge spotlight photograph"
    return f"""<section class="spotlight-band"><div class="wrap section">
<div class="section-head"><div><p class="kicker">{h(kicker)}</p>
<h2>{h(title)}</h2></div>
<div class="choices" role="group" aria-label="{h(group_aria)}">{"".join(buttons)}</div></div>
<div class="spotlight-card" data-spotlight="{h(json.dumps(payload, ensure_ascii=False))}">
<div class="spotlight-media">
<button type="button" class="photo-zoom" data-spot-zoom data-lightbox-src="{h(first["src"])}" data-lightbox-title="{h(first["name"])} ({h(first["scientific"])})" data-lightbox-alt="{h(first["alt"])}" data-lightbox-author="{h(first["author"])}" data-lightbox-url="{h(first["authorUrl"])}" data-lightbox-license="{h(first["licenseUrl"])}" data-lightbox-licensename="{h(first["licenseName"])}" aria-label="{h(enlarge_aria)}">
<img data-spot-img src="{h(first["src"])}" alt="{h(first["alt"])}" loading="lazy" decoding="async">
<span class="zoom-hint" aria-hidden="true">{h(zoom_lbl)}</span></button>
<p class="credit" data-spot-credit>{credit_html({"author": first["author"], "url": first["authorUrl"], "licenseName": first["licenseName"], "license": first["licenseUrl"]})}</p></div>
<div class="spotlight-copy">
<p class="card-meta" data-spot-family>{h(first["family"])}</p>
<h3 data-spot-name>{h(first["name"])}</h3>
<p class="scientific" data-spot-sci>{h(first["scientific"])}</p>
<p class="lede" data-spot-headline>{h(first["headline"])}</p>
<dl class="mini-stats"><div><dt>{h(wing_dt)}</dt><dd data-spot-wingspan>{h(first["wingspan"])}</dd></div>
<div><dt>{h(host_dt)}</dt><dd data-spot-hosts>{format_host_plant_html(first["hosts"])}</dd></div></dl>
<p class="spot-range" data-spot-range>{h(first["range"])}</p>
<div class="actions"><a class="button" data-spot-link href="{h(first["url"])}">{h(open_btn)}</a>
{link(all_btn, local(lang_prefix, "butterflies/"), "button outline")}</div>
</div></div></div></section>"""


def home_hotspots_tabs(lang_prefix, lang="en"):
    is_ta = lang == "ta"
    ta_hotspots = {r["id"]: r for r in SITE_TA.get("hotspots", [])} if is_ta else {}
    tab_buttons = []
    tab_panels = []
    for idx, region in enumerate(SITE["hotspots"]):
        t_reg = ta_hotspots.get(region["id"], {})
        tid = f'tab-{region["id"]}'
        selected = "true" if idx == 0 else "false"
        hidden_attr = "" if idx == 0 else ' hidden="until-found"'
        tabindex_attr = ' tabindex="0"' if idx == 0 else ""
        tab_buttons.append(
            f'<button type="button" role="tab" id="{tid}" aria-selected="{selected}">{h(t_reg.get("label") or region["label"])}</button>'
        )
        t_cards = t_reg.get("cards", [])
        cards_html = []
        for c_idx, card in enumerate(region["cards"]):
            t_card = t_cards[c_idx] if c_idx < len(t_cards) else {}
            sp_link = ""
            if card.get("species") and card["species"] in BY_SCI:
                sp = BY_SCI[card["species"]]
                lbl = (tamil_name(sp["scientific"]) or sp["name"]) if is_ta else f'{sp["name"]} profile'
                sp_link = link(lbl, local(lang_prefix, route(sp)), "tag tag-bv")
            press_lbl = "செய்தியைப் படி ↗" if is_ta else "Read press coverage ↗"
            cards_html.append(
                f'<article class="card"><div class="card-body">'
                f'<p class="card-meta">{h(t_card.get("stat") or card["stat"])}</p>'
                f'<h3>{h(t_card.get("place") or card["place"])}</h3>'
                f'<p>{h(t_card.get("summary") or card["summary"])}</p>'
                f'<div class="actions-inline">{sp_link}{link(press_lbl, card["pressUrl"])}</div>'
                f'</div></article>'
            )
        tab_panels.append(
            f'<div role="tabpanel" aria-labelledby="{tid}"{tabindex_attr}{hidden_attr}>'
            f'<div class="tabpanel-inner"><div class="tabpanel-head"><h3>{h(t_reg.get("headline") or region["headline"])}</h3>'
            f'<p class="lede">{h(t_reg.get("intro") or region["intro"])}</p></div>'
            f'<div class="grid">{"".join(cards_html)}</div></div></div>'
        )
    kicker_txt = "பல்லுயிர் & வலசை" if is_ta else "Biodiversity & Migration"
    sec_title = TA_UI.get("homeHotspotsTitle", "தமிழ்நாட்டின் பட்டாம்பூச்சி மையங்கள் & வலசைப் பாதைகள்") if is_ta else "Tamil Nadu butterfly hotspots & corridors"
    sec_desc = TA_UI.get("homeHotspotsDesc", "") if is_ta else "Switch tabs to inspect Western Ghats sanctuaries, Eastern Ghats surveys, urban Coimbatore wetlands, and seasonal Danainae migration routes."
    sec_btn = TA_UI.get("homeFieldworkBtn", "கள ஆய்வுகளைப் பார்") if is_ta else "View all fieldwork"
    tabs_aria = "தமிழ்நாடு பட்டாம்பூச்சி மையங்கள் மற்றும் வலசைப் பாதைகள்" if is_ta else "Tamil Nadu butterfly hotspots and migration corridors"
    return f"""<section class="wrap section" data-tabs>
<div class="section-head"><div><p class="kicker">{h(kicker_txt)}</p>
<h2>{h(sec_title)}</h2>
<p class="lede">{h(sec_desc)}</p></div>
{link(sec_btn, local(lang_prefix, "activities/"), "button outline")}</div>
<div class="tablist" role="tablist" aria-label="{h(tabs_aria)}">{"".join(tab_buttons)}</div>
<div class="tabpanels">{"".join(tab_panels)}</div>
</section>"""


def home(lang="en"):
    _, asset_prefix, lang_prefix, _, _, _ = paths_for("", lang=lang)
    is_ta = lang == "ta"
    validated_count = sum(1 for s in SPECIES if s.get("validated", True))
    proj = INAT.get("project") or {}

    hero_alt = (
        "பச்சை இலை மீது விரிந்த மரகதப் பச்சை மற்றும் நீலப் பட்டைச் சிறகுகளுடன் அமர்ந்திருக்கும் மயில் அழகி (Papilio crino), புகைப்படம்: அ. பாவேந்தன்"
        if is_ta
        else "Common Banded Peacock (Papilio crino) basking with open emerald-green and turquoise-banded wings on green foliage, photographed by Pavendhan A"
    )
    hero_credit_txt = (
        "மயில் அழகி (<i>Papilio crino</i>) · புகைப்படம்: அ. பாவேந்தன் (TNBS)"
        if is_ta
        else "Common Banded Peacock (<i>Papilio crino</i>) · Photo: Pavendhan A (TNBS)"
    )
    hero_media = (
        f'<figure class="hero-media"><img class="hide-on-error" src="{asset_prefix}assets/photos/home-hero-crino.jpg" '
        f'alt="{h(hero_alt)}" fetchpriority="high" decoding="async" width="1024" height="682"></figure>'
        f'<span class="hero-credit">{hero_credit_txt}</span>'
    )
    if is_ta:
        hero_kicker = TA_UI["heroKicker"]
        hero_title = TA_UI["heroTitle"]
        hero_desc = TA_UI["heroDesc"]
        ph_search = TA_UI["heroSearchPlaceholder"]
        btn_search = TA_UI["heroSearchBtn"]
        cta1, cta2, cta3 = TA_UI["exploreGuide"], TA_UI["identifyAi"], TA_UI["takeQuiz"]
        stat_labels = TA_UI["homeStats"]
    else:
        hero_kicker = "The Nature and Butterfly Society · Tamil Nadu"
        hero_title = "Butterflies of<br><em>Tamil Nadu</em>"
        hero_desc = f"Explore Tamil Nadu's {len(SPECIES)}-species butterfly field guide with detailed profiles, multi-photo variation galleries, Tamil names, Butterfly Vision AI, and live iNaturalist sightings."
        ph_search = "Quick search: Peacock, Yeoman, மயில் அழகி, Papilio..."
        btn_search = "Find butterfly"
        cta1, cta2, cta3 = "Explore field guide", "Identify with AI", "Take interactive quiz"
        stat_labels = [
            f"Butterfly species recorded in Tamil Nadu ({validated_count} validated)",
            f"Butterfly families across {len(TAXONOMY['subfamilies'])} subfamilies",
            "Pattampoochi magazine issues",
            "Species covered on Butterfly Vision AI",
        ]

    hero = f"""<section class="hero"><div class="wrap hero-inner">{hero_media}
<div class="hero-copy"><p class="kicker">{h(hero_kicker)}</p><h1>{hero_title}</h1>
<p>{h(hero_desc)}</p>
<search class="hero-search"><form action="{local(lang_prefix, "butterflies/")}" method="get" class="hero-search-form">
<label for="hero-q" class="visually-hidden">{h(ph_search)}</label>
<input id="hero-q" type="search" name="q" placeholder="{h(ph_search)}">
<button type="submit" class="button light">{h(btn_search)}</button>
</form></search>
<div class="actions">{link(cta1, local(lang_prefix, "butterflies/"), "button outline")}{link(cta2, local(lang_prefix, "identify/"), "button outline")}{link(cta3, local(lang_prefix, "quiz/"), "button outline")}</div></div></div></section>
<div class="band"><div class="wrap"><ul class="stats stats-4">
<li><strong>{len(SPECIES)}</strong><span>{h(stat_labels[0])}</span></li>
<li><strong>{len(FAMILIES)}</strong><span>{h(stat_labels[1])}</span></li>
<li><strong>{len(SITE["issues"])}</strong><span>{h(stat_labels[2])}</span></li>
<li><strong>{h(SITE["butterflyVision"]["supportedTotal"])}</strong><span>{h(stat_labels[3])}</span></li></ul></div></div>"""

    family_chips = "".join(
        f'<a class="chip-link" href="{local(lang_prefix, "butterflies/")}?family={h(fam)}">{h(fam_name(fam, lang))} <span>({EXPECTED_FAMILY_COUNTS[fam]})</span></a>'
        for fam in FAMILIES
    )
    member_photo_count = sum(1 for s in SPECIES if is_member_photo(s["scientific"]))
    g_kicker = TA_UI["homeFeaturedKicker"] if is_ta else "Tamil Nadu field guide"
    g_title = TA_UI["homeFeaturedTitle"] if is_ta else "Which butterfly did you see?"
    g_desc = TA_UI["homeFeaturedDesc"] if is_ta else f"Search {len(SPECIES)} species by common name, Tamil name, scientific name, host plant, or photographer across {len(PHOTOS)} pictured species and {len(GALLERIES)} multi-photo variation galleries ({member_photo_count} TNBS member primary records)."
    g_btn = TA_UI["browseAll"] if is_ta else "Browse all 329 species"
    chip_aria = "குடும்ப வாரியாகத் தேடுக" if is_ta else "Browse by family"

    guide_sec = f"""<section class="wrap section"><div class="section-head"><div><p class="kicker">{h(g_kicker)}</p>
<h2>{h(g_title)}</h2><p class="lede">{h(g_desc)}</p></div>{link(g_btn, local(lang_prefix, "butterflies/"), "button outline")}</div>
<div class="chip-row" aria-label="{h(chip_aria)}">{family_chips}</div>
<div class="grid">{"".join(species_card(BY_SCI[x], asset_prefix, lang_prefix, lang=lang) for x in FEATURED)}</div></section>"""

    inat_sec = ""
    if proj.get("observations"):
        s_kicker = TA_UI["homeSightingsKicker"] if is_ta else "Citizen Science · iNaturalist Project #47280"
        s_title = TA_UI["homeSightingsTitle"] if is_ta else "Live Tamil Nadu Butterfly Sightings"
        s_desc = TA_UI["homeSightingsDesc"] if is_ta else f"Powered by the Butterflies of Tamil Nadu collection project on iNaturalist: explore {proj['observations']:,}+ community sightings across Tamil Nadu districts, seasonal charts, and distribution maps."
        s_btn = TA_UI["openSightingsHub"] if is_ta else "Explore Live Sightings Hub →"
        obs_lbl = "மொத்த பதிவுகள்" if is_ta else "Total sightings"
        rg_lbl = "ஆராய்ச்சித் தரம்" if is_ta else "Research Grade"
        usr_lbl = "பங்களிப்பாளர்கள்" if is_ta else "Contributors"
        inat_ext_lbl = "iNaturalist #47280 ↗"
        inat_sec = f"""<section class="wrap section"><div class="guide-banner inat-home-banner">
<div><p class="kicker">{h(s_kicker)}</p><h2>{h(s_title)}</h2><p class="lede">{h(s_desc)}</p>
<p class="meta"><strong>{proj['observations']:,}</strong> {h(obs_lbl)} · <strong>{proj['researchGrade']:,}</strong> {h(rg_lbl)} · <strong>{proj['observersCount']:,}</strong> {h(usr_lbl)}</p></div>
<div class="actions">{link(s_btn, local(lang_prefix, "sightings/"), "button")}{link(inat_ext_lbl, INAT_PROJECT_URL, "button outline")}</div>
</div></section>"""

    spotlight_sec = home_spotlight_section(asset_prefix, lang_prefix, lang=lang)
    hotspots_sec = home_hotspots_tabs(lang_prefix, lang=lang)

    bv_meta = SITE["butterflyVision"]
    wg_covered = sum(1 for s in SPECIES if "wg" in s.get("butterflyVision", []))
    bv_total_covered = sum(1 for s in SPECIES if s.get("butterflyVision"))
    if is_ta:
        bv_bullets = (
            f'<li><strong>மேற்குத் தொடர்ச்சி மலை மாதிரி:</strong> {h(bv_meta["wgCount"])} மண்டல இனங்கள் (தமிழ்நாடு பட்டியலில் {wg_covered} இனங்கள் உட்பட).</li>'
            f'<li><strong>அகில இந்திய மாதிரி:</strong> {h(bv_meta["indiaCount"])} இந்திய இனங்கள் (மொத்தம் {h(bv_meta["supportedTotal"])} உயிரினப் பிரிவுகள்), சராசரி {h(bv_meta["accuracy"])} துல்லியம்.</li>'
            '<li><strong>படச் செதுக்கல் &amp; பின்னூட்ட வசதி:</strong> படத்தைச் சரியாக வெட்டி (crop) மீண்டும் அடையாளம் காணவும்; 95%+ துல்லியத்தை அடைய உதவவும்.</li>'
        )
        bv_visit = "butterflyvision.in தளம் ↗"
        bv_card_meta = "ஆழ்கற்றல் × குடிமை அறிவியல்"
        bv_card_title = "படம் எடு. பதிவேற்று. அடையாளம் காண்."
        bv_card_body = "TNBS கள வழிகாட்டியின் ஒவ்வொரு இன அட்டையும் Butterfly Vision AI ஆதரவுடன் இணைக்கப்பட்டுள்ளது; மாணவர்கள் மற்றும் கள ஆர்வலர்கள் இனங்களை விரைந்து உறுதிசெய்ய இது உதவுகிறது."
        bv_stat1_dt, bv_stat2_dt, bv_stat2_dd = "இணைந்த தமிழ்நாடு இனங்கள்", "வெளியிடப்பட்ட ஆய்வுகள்", "5 ஆய்வுக் கட்டுரைகள் & தொகுப்புகள்"
    else:
        bv_bullets = (
            f'<li><strong>Western Ghats Model:</strong> {h(bv_meta["wgCount"])} regional species including {wg_covered} species on the Tamil Nadu checklist.</li>'
            f'<li><strong>All India Model:</strong> {h(bv_meta["indiaCount"])} Indian species ({h(bv_meta["supportedTotal"])} total taxa) with {h(bv_meta["accuracy"])} average accuracy.</li>'
            '<li><strong>Interactive crop &amp; feedback loop:</strong> Fine-tune framing before re-identifying and help improve accuracy toward 95%+.</li>'
        )
        bv_visit = "Visit butterflyvision.in"
        bv_card_meta = "Deep Learning × Citizen Science"
        bv_card_title = "Snap. Upload. Identify."
        bv_card_body = "Every TNBS field guide species card links directly to Butterfly Vision model coverage, helping newcomers, students, and survey volunteers verify sightings faster in the field."
        bv_stat1_dt, bv_stat2_dt, bv_stat2_dd = "TN species covered", "Published science", "5 peer-reviewed papers & repos"

    bv_sec = f"""<section class="ai-spotlight"><div class="wrap section split">
<div><p class="kicker">{"AI அடையாள உதவி" if is_ta else "AI Butterfly Identification"}</p><h2>{"Butterfly Vision AI ஒருங்கிணைப்பு" if is_ta else "Butterfly Vision integration"}</h2>
<p class="lede">{"TNBS உறுப்பினர் தெய்வபிரகாசம் ஹரி உருவாக்கிய Butterfly Vision ஆழ்கற்றல் AI தளத்தில் இந்தியப் பட்டாம்பூச்சிகளை நொடிகளில் அடையாளம் காணலாம்." if is_ta else "Upload a field photograph to identify Indian butterflies in seconds using deep convolutional neural networks developed by TNBS member Theivaprakasham Hari."}</p>
<ul class="bullet-list">{bv_bullets}</ul>
<div class="actions">{link(TA_UI["identifyAi"] if is_ta else "Launch AI identifier", local(lang_prefix, "identify/"), "button")}{link(bv_visit, BUTTERFLY_VISION, "button outline")}</div></div>
<div class="ai-card reveal"><p class="card-meta">{h(bv_card_meta)}</p>
<h3>{h(bv_card_title)}</h3>
<p>{h(bv_card_body)}</p>
<dl class="mini-stats"><div><dt>{h(bv_stat1_dt)}</dt><dd>{bv_total_covered} / {len(SPECIES)}</dd></div>
<div><dt>{h(bv_stat2_dt)}</dt><dd>{h(bv_stat2_dd)}</dd></div></dl>
</div></div></section>"""

    ta_about = SITE_TA.get("about", {}) if is_ta else {}
    about_photos_en = SITE["about"]["photos"][:3]
    about_photos_ta = ta_about.get("photos", [])[:3] if is_ta else []
    about_gallery_parts = []
    for p_idx, p in enumerate(about_photos_en):
        tp = about_photos_ta[p_idx] if p_idx < len(about_photos_ta) else {}
        t_title = tp.get("title") or p["title"]
        t_when = tp.get("when") or p["when"]
        t_cap = tp.get("caption") or p["caption"]
        about_gallery_parts.append(
            f'<figure class="gallery-card reveal">{lightbox_button_img(p["src"], t_cap, t_title, t_cap, asset_prefix, p["width"], p["height"])}'
            f'<figcaption><strong>{h(t_title)}</strong> · <span>{h(t_when)}</span><br><small>{h(t_cap)}</small></figcaption></figure>'
        )
    about_gallery = "".join(about_gallery_parts)
    milestones_src = ta_about.get("milestones", SITE["about"]["milestones"])[:4] if is_ta else SITE["about"]["milestones"][:4]
    emblem_alt = (
        "மயில் அழகி (Papilio crino) பொறிக்கப்பட்ட இயற்கை மற்றும் பட்டாம்பூச்சி சங்கத்தின் (TNBS) அதிகாரப்பூர்வ இலச்சினை"
        if is_ta
        else "Official emblem of The Nature and Butterfly Society featuring the Common Banded Peacock"
    )
    if is_ta:
        about_lede = f"இயற்கை மற்றும் பட்டாம்பூச்சி சங்கம் (TNBS), கோயம்புத்தூரைத் தலைமையிடமாகக் கொண்டு பதிவு செய்யப்பட்ட ({h(ta_about.get('registration') or SITE['about']['registration'])}) குடிமை அறிவியல் அமைப்பாகும். தமிழ்நாடு முழுவதும் இயற்கை ஆர்வலர்கள், ஆய்வாளர்கள், மாணவர்கள் மற்றும் வனத்துறையினரை இணைத்துப் பட்டாம்பூச்சிகளை ஆவணப்படுத்தி வருகிறோம்."
        about_p1 = f"2012-2014 காலகட்டத்தில் தமிழ்நாட்டின் முதல் பிரத்யேக மாநிலப் பட்டாம்பூச்சிப் பட்டியலை உருவாக்கும் முயற்சியாகத் தொடங்கிய இப்பணி, இன்று {h(ta_about.get('facebookGroup') or SITE['about']['facebookGroup'])} கொண்ட பெருங்குழுமமாக வளர்ந்துள்ளது."
        about_p2 = "முதுமலை புலிகள் காப்பகம் மற்றும் பச்சைமலைக் காடுகளில் இணைந்து நடத்தும் பருவகாலப் பட்டாம்பூச்சி ஆய்வுகள், நீல வரியன் & கருப்பன் வலசைப் பயணக் கண்காணிப்பு, மற்றும் அரசுப் பள்ளிகளுக்கு இலவசத் தமிழ் பட்டாம்பூச்சிச் சுவரொட்டிகள் வழங்குதல் ஆகிய பணிகள் மூலம் களத் தரவுகளைப் பொதுப் பாதுகாப்பு அறிவாக மாற்றி வருகிறோம்."
    else:
        about_lede = f"The Nature and Butterfly Society (TNBS) is a registered Coimbatore-based citizen-science society ({h(SITE['about']['registration'])}) uniting naturalists, researchers, students, and forest partners to document butterflies across Tamil Nadu."
        about_p1 = f"What began in 2012-2014 as an effort to build Tamil Nadu's first dedicated state checklist has grown into a thriving community of {h(SITE['about']['facebookGroup'])}."
        about_p2 = "From joint monsoon surveys in Mudumalai Tiger Reserve and Pachamalai Hills to tracking cross-state tiger and crow migrations and distributing free Tamil butterfly posters to government schools, TNBS turns careful field observations into open conservation knowledge."

    about_sec = f"""<section id="about-us" class="section about-home"><div class="wrap">
<div class="section-head"><div><p class="kicker">{h(TA_UI["homeAboutKicker"] if is_ta else "Who we are")}</p><h2>{h(TA_UI["homeAboutTitle"] if is_ta else "About us")}</h2>
<p class="lede">{about_lede}</p></div>
<div class="about-emblem"><img src="{asset_prefix}assets/tnbs-logo.png" alt="{h(emblem_alt)}" width="96" height="96" loading="lazy"></div></div>
<div class="split about-story"><div>
<p>{about_p1}</p>
<p>{h(about_p2)}</p>
<div class="actions">{link(TA_UI["homeAboutBtn"] if is_ta else "Read our full story & team", local(lang_prefix, "about/"), "button")}{link(TA_UI["homeFieldworkBtn"] if is_ta else "Explore fieldwork & surveys", local(lang_prefix, "activities/"), "button outline")}</div></div>
<ul class="milestone-compact">{"".join(f'<li><strong>{h(yr)}</strong><span>{h(desc)}</span></li>' for yr, desc in milestones_src)}</ul></div>
<div class="grid gallery-grid">{about_gallery}</div></div></section>"""

    total_indexed = sum(len(MAGAZINE_INDEX[n]["articles"]) for n in MAGAZINE_INDEX)
    journal_desc = (
        f"27 காலாண்டிதழ்கள் மற்றும் {total_indexed} பட்டியலிடப்பட்ட கட்டுரைகளை வாசியுங்கள்: 2024 Danainae வலசை அறிக்கை, முதுமலை & பச்சைமலை வன ஆய்வுகள், வாழ்க்கைச் சுழற்சி ஆய்வுகள், பள்ளி விழிப்புணர்வுத் திட்டங்கள் மற்றும் மாநிலப் பட்டியல் புதுப்பிப்புகள்."
        if is_ta
        else f"Browse 27 quarterly issues and {total_indexed} indexed articles covering the 2024 Danainae migration report, Mudumalai and Pachamalai Forest Division surveys, life-cycle studies, school outreach, and state butterfly updates."
    )
    issue27_btn = "இதழ் 27 PDF" if is_ta else "Issue 27 PDF"
    journal = f"""<section class="journal"><div class="wrap section split">{cover(lang)}<div>
<p class="kicker">{h(TA_UI["homeMagazineKicker"] if is_ta else "The society's quarterly magazine")}</p><h2>{h(TA_UI["homeMagazineTitle"] if is_ta else "Pattampoochi")}</h2>
<p class="lede">{h(journal_desc)}</p>
<div class="actions">{link(TA_UI["homeMagazineBtn"] if is_ta else "Browse all 27 issues & article index", local(lang_prefix, "magazine/"), "button")}{link(issue27_btn, issue_url(27), "button outline")}</div></div></div></section>"""

    press_preview = "".join(press_card(s, i, lang_prefix, lang=lang) for i, s in enumerate(SITE["press"][:6]))
    ta_comm = SITE_TA.get("community", []) if is_ta else []
    elsewhere_cards_parts = []
    for c_idx, c in enumerate(SITE["community"][:3]):
        tc = ta_comm[c_idx] if c_idx < len(ta_comm) else {}
        elsewhere_cards_parts.append(
            f'<article class="card community-card reveal"><div class="card-body"><p class="card-meta">{h(tc.get("badge") or c["badge"])}</p>'
            f'<h3>{link(tc.get("title") or c["title"], c["url"])}</h3><p>{h(tc.get("summary") or c["summary"])}</p>'
            f'<p>{link((tc.get("cta") or c["cta"]) + " ↗", c["url"], "small-button")}</p></div></article>'
        )
    elsewhere_cards = "".join(elsewhere_cards_parts)
    updates = f"""<section class="wrap section"><div class="section-head"><div><p class="kicker">{h(TA_UI["homePressKicker"] if is_ta else f"News, magazine reports & press ({len(SITE['press'])} entries)")}</p><h2>{h(TA_UI["homePressTitle"] if is_ta else "Recently in the press")}</h2></div>
{link(TA_UI["homeNewsBtn"] if is_ta else f"Explore all {len(SITE['press'])} reports", local(lang_prefix, "news/"), "button outline")}</div>
<ul class="news-grid">{press_preview}</ul>
<div class="elsewhere-block"><div class="section-head"><div><p class="kicker">{"சமூகம் & வெளிப்புறத் தளங்கள்" if is_ta else "Community & External Portals"}</p><h3>{"இணையத்தில் TNBS" if is_ta else "Elsewhere on the web"}</h3></div>
{link("அனைத்து இணைப்புகளையும் பார்" if is_ta else "See all community links", local(lang_prefix, "news/") + "#elsewhere", "button outline")}</div>
<div class="grid">{elsewhere_cards}</div></div></section>"""

    cta = f"""<section class="dark"><div class="wrap compact"><p class="kicker">{h(I18N_TA["nav"]["getInvolved"] if is_ta else "Get involved")}</p><h2>{h(TA_UI["homeJoinTitle"] if is_ta else "Share a butterfly sighting")}</h2>
<p class="lede">{h(TA_UI["homeJoinDesc"] if is_ta else "A photograph, a date, and a locality turn a casual observation into scientific data, especially for the four checklist species still awaiting validated Tamil Nadu photographic records.")}</p>
<div class="actions">{link(I18N_TA["nav"]["getInvolved"] if is_ta else "How to contribute", local(lang_prefix, "about/") + "#get-involved", "button light")}{link(TA_UI["takeQuiz"] if is_ta else "Test yourself in the quiz", local(lang_prefix, "quiz/"), "button outline")}</div></div></section>"""

    page_title = f"{TA_UI['heroTitle'].replace('<br>', ' ').replace('<em>', '').replace('</em>', '')} | {I18N_TA['brand']}" if is_ta else "Butterflies of Tamil Nadu | The Nature and Butterfly Society"
    page_desc = TA_UI["heroDesc"] if is_ta else "Official website of The Nature and Butterfly Society (TNBS). Explore Tamil Nadu's 329-species butterfly field guide with Tamil names, multi-photo galleries, Butterfly Vision AI, live iNaturalist sightings, and TNBS reports."

    render(
        "",
        page_title,
        page_desc,
        hero + guide_sec + inat_sec + spotlight_sec + hotspots_sec + bv_sec + about_sec + journal + updates + cta,
        image_key="Papilio crino",
        schema={"@type": "Organization", "name": NAME, "alternateName": "TNBS", "email": CONTACT, "sameAs": [ORIGINAL, BUTTERFLY_VISION, FACEBOOK_GROUP, INAT_PROJECT_URL]},
        lang=lang,
    )


def sightings(lang="en"):
    _, asset_prefix, lang_prefix, _, _, _ = paths_for("sightings/", lang=lang)
    is_ta = lang == "ta"
    proj = INAT.get("project") or {}
    months = INAT.get("months") or [0] * 12

    species_index = {}
    for s in SPECIES:
        sci = s["scientific"]
        ta_sp = tamil_name(sci)
        species_index[sci.lower()] = {
            "name": ta_sp if (is_ta and ta_sp) else s["name"],
            "sub": s["name"] if (is_ta and ta_sp) else ta_sp,
            "scientific": sci,
            "href": local(lang_prefix, route(s)),
        }

    recent_cards = []
    for obs in INAT.get("recent") or []:
        sci = obs.get("scientific") or ""
        ta_sp = tamil_name(sci) if sci else ""
        disp = ta_sp if (is_ta and ta_sp) else (obs.get("commonName") or obs.get("taxonName"))
        sp_href = local(lang_prefix, route(BY_SCI[sci])) if sci in BY_SCI else ""
        title_html = link(disp, sp_href) if sp_href else link(disp, obs["url"])
        img_html = (
            f'<div class="media"><img src="{h(obs["thumb"])}" alt="{h(disp)}" loading="lazy" decoding="async">'
            f'<span class="photo-count-badge">{h(obs.get("observedOn", ""))}</span></div>'
            if obs.get("thumb")
            else ""
        )
        obs_place = obs.get("place") or ("தமிழ்நாடு" if is_ta else "Tamil Nadu")
        obs_user = obs.get("user") or ("iNaturalist ஆர்வலர்" if is_ta else "iNaturalist observer")
        recent_cards.append(
            f'<article class="card sighting-card">{img_html}<div class="card-body">'
            f'<p class="card-meta">{h(obs_place)}</p>'
            f'<h3>{title_html}</h3>'
            f'<p class="scientific">{h(obs.get("taxonName", ""))}</p>'
            f'<p class="caption">{link(obs_user + " · iNaturalist ↗", obs["url"])}</p>'
            f'</div></article>'
        )

    top_species_rows = []
    for rank_i, sp_item in enumerate(INAT.get("topSpecies") or [], 1):
        sci = sp_item["scientific"]
        ta_sp = tamil_name(sci)
        label = f"{ta_sp} ({sp_item['name']})" if (is_ta and ta_sp) else (f"{sp_item['name']} · {ta_sp}" if ta_sp else sp_item["name"])
        top_species_rows.append(
            f'<li><span class="lb-rank">{rank_i}</span>'
            f'<span class="lb-main">{link(label, local(lang_prefix, route(BY_SCI[sci])))} <i>{h(sci)}</i></span>'
            f'<strong class="lb-val">{sp_item["count"]:,}</strong></li>'
        )

    spp_unit = "இனங்கள்" if is_ta else "spp."
    top_observer_rows = []
    for rank_i, ob in enumerate(INAT.get("topObservers") or [], 1):
        u_url = f"https://www.inaturalist.org/observations?project_id=butterflies-of-tamil-nadu&user_id={quote(ob['login'])}"
        top_observer_rows.append(
            f'<li><span class="lb-rank">{rank_i}</span>'
            f'<span class="lb-main">{link(ob["name"], u_url)} <small class="caption">({ob["species"]} {h(spp_unit)})</small></span>'
            f'<strong class="lb-val">{ob["observations"]:,}</strong></li>'
        )

    s_stats = TA_UI["sightingsStats"] if is_ta else [
        "Total Tamil Nadu observations",
        "Research Grade verified records",
        "Butterfly taxa documented",
        "Citizen-science contributors",
    ]
    kicker = TA_UI["sightingsKicker"] if is_ta else "Citizen Science · iNaturalist Project #47280"
    title = TA_UI["sightingsTitle"] if is_ta else "Butterflies of Tamil Nadu Live Sightings"
    desc = TA_UI["sightingsDesc"] if is_ta else "Live citizen-science observations, seasonal flight patterns, top species, and an interactive distribution map from TNBS's official iNaturalist collection project."
    snapshot_note = (
        f"தரவுப் புதுப்பிப்பு: {proj.get('fetchedAt', '')[:10]} · நேரடி iNaturalist விவரங்கள் சரிபார்க்கப்படுகின்றன..."
        if is_ta
        else f"Snapshot updated: {proj.get('fetchedAt', '')[:10]} · Checking live iNaturalist API..."
    )
    pheno_cap = (
        "தமிழ்நாட்டில் அனைத்து பட்டாம்பூச்சி இனங்களின் மாதாந்திரப் பதிவுகள்"
        if is_ta
        else "Monthly Tamil Nadu sightings across all species"
    )
    open_proj_btn = "iNaturalist திட்டத்தைத் திற ↗" if is_ta else "Open iNaturalist project ↗"
    upload_inat_btn = "iNaturalist-இல் பதிவேற்றவும் ↗" if is_ta else "Upload to iNaturalist ↗"

    body = heading(title, desc, kicker)
    body += f"""<div class="band"><div class="wrap"><ul class="stats stats-4" data-inat-live data-species-index="{h(json.dumps(species_index, separators=(',', ':'), ensure_ascii=False))}">
<li><strong data-inat-obs>{proj.get('observations', 0):,}</strong><span>{h(s_stats[0])}</span></li>
<li><strong data-inat-rg>{proj.get('researchGrade', 0):,}</strong><span>{h(s_stats[1])}</span></li>
<li><strong data-inat-spp>{proj.get('speciesCount', 0):,}</strong><span>{h(s_stats[2])}</span></li>
<li><strong data-inat-observers>{proj.get('observersCount', 0):,}</strong><span>{h(s_stats[3])}</span></li>
</ul></div></div>

<section class="wrap section">
<p class="caption" role="status" aria-live="polite" data-inat-status>{h(snapshot_note)}</p>
<div class="split sightings-top">
<div>
<h2>{"தமிழ்நாட்டில் பட்டாம்பூச்சி பரவல்" if is_ta else "Statewide observation map"}</h2>
<p class="lede">{"திட்டம் #47280-இல் பதிவான தமிழ்நாடு பட்டாம்பூச்சி அவதானிப்புகளை வெப்ப வரைபடமாகவோ புள்ளிப் பதிவுகளாகவோ காண்க." if is_ta else "Toggle between Observation Density Heatmap and individual Point markers across Tamil Nadu from iNaturalist Project #47280."}</p>
{inat_map_html(47280, lang=lang, lazy=False, direct_url=INAT_PROJECT_URL)}
</div>
<div>
<h2>{h(TA_UI["sightingsPhenologyHeading"] if is_ta else "Seasonal butterfly activity (Jan to Dec)")}</h2>
<p class="lede">{"69,500+ பதிவுகளின் அடிப்படையில் தமிழ்நாட்டின் பருவகாலப் பட்டாம்பூச்சி எண்ணிக்கை (செப்டம்பர் உச்சம்)." if is_ta else "Aggregate monthly observation rhythm across all recorded Tamil Nadu sightings, showing peak abundance through monsoon months."}</p>
{phenology_chart_html(months, lang=lang, caption=pheno_cap)}
</div>
</div>
</section>

<section class="journal"><div class="wrap section">
<div class="section-head"><div><h2>{h(TA_UI["sightingsRecentHeading"] if is_ta else "Latest Tamil Nadu sightings")}</h2>
<p class="lede">{"அண்மையில் தமிழ்நாடு முழுவதும் ஆர்வலர்கள் பதிவேற்றிய படங்களுடன் கூடிய பட்டாம்பூச்சி பதிவுகள்." if is_ta else "Recent photographed observations uploaded to iNaturalist from Tamil Nadu, refreshed live in your browser."}</p></div>
{link(open_proj_btn, INAT_PROJECT_URL, "button outline")}</div>
<div class="grid sightings-grid" data-inat-recent>{"".join(recent_cards)}</div>
</div></section>

<section class="wrap section">
<div class="leaderboard-grid">
<div class="profile-card"><h3>{h(TA_UI["sightingsTopSpeciesHeading"] if is_ta else "Most observed species in Tamil Nadu")}</h3>
<ol class="leaderboard-list">{"".join(top_species_rows)}</ol></div>
<div class="profile-card"><h3>{h(TA_UI["sightingsTopObserversHeading"] if is_ta else "Top citizen-science observers")}</h3>
<ol class="leaderboard-list">{"".join(top_observer_rows)}</ol></div>
</div>
<div class="guide-banner" style="margin-top:1.75rem;">
<div><h3>{h(TA_UI["sightingsContributeTitle"] if is_ta else "Contribute your sighting automatically")}</h3>
<p>{h(TA_UI["sightingsContributeBody"] if is_ta else "Because Project #47280 is an automated iNaturalist Collection Project, every butterfly photograph you upload with a Tamil Nadu location joins the dataset automatically.")}</p></div>
<div class="actions-inline">{link(upload_inat_btn, INAT_PROJECT_URL, "button")}{link(TA_UI["browseAll"] if is_ta else "Explore 329 species guide", local(lang_prefix, "butterflies/"), "button outline")}</div>
</div>
</section>"""

    render("sightings/", title, desc, body, image_key="Danaus chrysippus", lang=lang)


def guide(lang="en"):
    _, asset_prefix, lang_prefix, _, _, _ = paths_for("butterflies/", lang=lang)
    is_ta = lang == "ta"
    family_options = "".join(
        f'<option value="{f}">{h(fam_name(f, lang))} · {h(fam_desc(f, lang))} ({EXPECTED_FAMILY_COUNTS[f]})</option>'
        for f in FAMILIES
    )
    subfamilies = sorted({s["subfamily"] for s in SPECIES})
    subfamily_options = "".join(
        f'<option value="{sf}">{h(sub_desc(sf, lang))} ({h(sf)})</option>' if is_ta else f'<option value="{sf}">{h(sf)}: {h(sub_desc(sf, lang))}</option>'
        for sf in subfamilies
    )
    cards = sorted(SPECIES, key=lambda x: (x["scientific"] not in PHOTOS, not is_member_photo(x["scientific"]), x["scientific"] not in PROFILES, x["name"].casefold()))
    photo_count = sum(1 for s in SPECIES if s["scientific"] in PHOTOS)
    gallery_count = sum(1 for s in SPECIES if len(GALLERIES.get(s["scientific"], [])) >= 2)
    member_count = sum(1 for s in SPECIES if is_member_photo(s["scientific"]))
    profile_count = sum(1 for s in SPECIES if s["scientific"] in PROFILES)
    ta_count = sum(1 for s in SPECIES if tamil_name(s["scientific"]))

    all_pill = "அனைத்தும் 329" if is_ta else "All 329"
    family_pills = [f'<button type="button" class="choice" data-family-pill="" aria-pressed="true">{h(all_pill)}</button>']
    for fam in FAMILIES:
        family_pills.append(
            f'<button type="button" class="choice" data-family-pill="{h(fam)}" aria-pressed="false">{h(fam_name(fam, lang))} ({EXPECTED_FAMILY_COUNTS[fam]})</button>'
        )

    title = TA_UI["guideTitle"] if is_ta else "Butterflies of Tamil Nadu"
    kicker = TA_UI["guideKicker"] if is_ta else "Field guide"
    lede = (
        f"{len(SPECIES)} தமிழ்நாடு பட்டாம்பூச்சி இனங்கள் ({photo_count} இனங்களுக்குப் படங்கள், {gallery_count} பல-புகைப்படத் தொகுப்புகள், {ta_count} தமிழ்ப் பெயர்கள்)."
        if is_ta
        else f"{len(SPECIES)} Tamil Nadu butterfly species across {len(FAMILIES)} families ({photo_count}/329 photographed, {gallery_count} with multi-photo variation galleries, {ta_count} with Tamil names, {member_count} TNBS member primary records, {profile_count} detailed field profiles)."
    )
    bv_cov = sum(1 for s in SPECIES if s.get("butterflyVision"))
    bv_banner_sub = f"Butterfly Vision AI ({bv_cov} / {len(SPECIES)} தமிழ்நாடு இனங்கள்)" if is_ta else f"Butterfly Vision AI ({bv_cov}/{len(SPECIES)} TN species)"
    noscript_txt = f"தமிழ்நாட்டின் அனைத்து {len(SPECIES)} பட்டாம்பூச்சி இனங்களும் கீழே பட்டியலிடப்பட்டுள்ளன." if is_ta else f"All {len(SPECIES)} butterflies of Tamil Nadu are listed below."
    pills_aria = "குடும்ப வாரியாக விரைவுத் தேர்வு" if is_ta else "Quick filter by butterfly family"
    view_aria = "காட்சி வடிவம்" if is_ta else "View options"
    prog_aria = "பார்த்த இனங்களின் எண்ணிக்கை" if is_ta else "Spotted species progress"

    body = heading(title, lede, kicker)
    body += f"""<div class="wrap section" data-guide>
<div class="lifelist-bar" data-lifelist-bar data-enhancement hidden>
<div class="lifelist-info"><strong>{h(TA_UI["guideMyLifeList"] if is_ta else "My Tamil Nadu Life List:")}</strong> <span data-lifelist-count>0 / {len(SPECIES)}</span>
<progress class="lifelist-progress" max="{len(SPECIES)}" value="0" aria-label="{h(prog_aria)}"></progress></div>
<div class="actions-inline">
<button type="button" class="choice" data-spotted-filter aria-pressed="false">{h(TA_UI["guideSpottedOnly"] if is_ta else "My spotted only")}</button>
<button type="button" class="choice" data-copy-lifelist>{h(TA_UI["guideCopyList"] if is_ta else "Copy life list")}</button>
<button type="button" class="button compact-btn" data-surprise-btn>{h(TA_UI["guideSurprise"] if is_ta else "Surprise me")}</button>
</div></div>
<p role="status" aria-live="polite" class="caption" data-lifelist-status></p>

<div class="guide-banner">
<div><strong>{h(TA_UI["guideBannerTitle"] if is_ta else "Got a butterfly photo you can't match yet?")}</strong> <span>{h(bv_banner_sub)}</span></div>
<div class="actions-inline">{link(TA_UI["guideBannerBtn"] if is_ta else "Open AI Identify tool", local(lang_prefix, "identify/"), "small-button")}{link("butterflyvision.in", BUTTERFLY_VISION, "button outline compact-btn")}</div>
</div>

<div data-enhancement hidden>
<div class="choices family-pills" role="group" aria-label="{h(pills_aria)}">{"".join(family_pills)}</div>
<search><form class="filters">
<div class="field grow"><label for="guide-q">{h(TA_UI["guideSearchLabel"] if is_ta else "Search butterflies")}</label><input id="guide-q" type="search" name="q" placeholder="{h(TA_UI["guideSearchPlaceholder"] if is_ta else "Name, Tamil name, scientific name, host plant, photographer...")}"></div>
<div class="field"><label for="guide-family">{h(TA_UI["guideFamily"] if is_ta else "Family")}</label><select id="guide-family" name="family"><option value="">{h(TA_UI["guideAllFamilies"] if is_ta else "All families (329)")}</option>{family_options}</select></div>
<div class="field"><label for="guide-subfamily">{h(TA_UI["guideSubfamily"] if is_ta else "Subfamily")}</label><select id="guide-subfamily" name="subfamily"><option value="">{h(TA_UI["guideAllSubfamilies"] if is_ta else "All subfamilies (21)")}</option>{subfamily_options}</select></div>
<div class="field"><label for="guide-tag">{h(TA_UI["guideFilter"] if is_ta else "Highlight / Filter")}</label><select id="guide-tag" name="tag">
<option value="">{"அனைத்து இனங்களும்" if is_ta else "All entries"}</option>
<option value="spotted">{"நான் பார்த்த பட்டாம்பூச்சிகள்" if is_ta else "My spotted butterflies"}</option>
<option value="tamil">{"தமிழ்ப் பெயர் கொண்டவை" if is_ta else f"With Tamil name ({ta_count})"}</option>
<option value="member">{"TNBS உறுப்பினர் படங்கள்" if is_ta else f"Photographed by TNBS members ({member_count})"}</option>
<option value="gallery">{"பல-புகைப்படத் தொகுப்பு" if is_ta else f"Multi-photo gallery ({gallery_count})"}</option>
<option value="photo">{"புகைப்படம் உள்ளவை" if is_ta else f"With verified photo ({photo_count})"}</option>
<option value="wg-endemic">{h(I18N_TA["tags"]["wg-endemic"] if is_ta else "Western Ghats endemic")}</option>
<option value="migratory">{h(I18N_TA["tags"]["migratory"] if is_ta else "Migratory in Tamil Nadu")}</option>
<option value="wpa-protected">{h(I18N_TA["tags"]["wpa-protected"] if is_ta else "WPA protected species")}</option>
<option value="issue-27-addition">{h(I18N_TA["tags"]["issue-27-addition"] if is_ta else "Recent state additions (2)")}</option>
<option value="unvalidated">{h(I18N_TA["tags"]["unvalidated"] if is_ta else "Awaiting TN validation (4)")}</option>
<option value="bv">{h(I18N_TA["tags"]["bv"] if is_ta else "Butterfly Vision AI supported")}</option>
</select></div>
<div class="field"><label for="guide-sort">{h(TA_UI["guideSort"] if is_ta else "Sort by")}</label><select id="guide-sort" name="sort">
<option value="featured">{"படங்கள் & TNBS முதலில்" if is_ta else "Photos & TNBS members first"}</option>
<option value="name">{"பெயர் வரிசை (A-Z)" if is_ta else "Common name (A-Z)"}</option>
<option value="sci">{"அறிவியல் பெயர் (A-Z)" if is_ta else "Scientific name (A-Z)"}</option>
<option value="id">{"பட்டியல் எண் (#1-329)" if is_ta else "Checklist order (#1-329)"}</option>
</select></div>
<button type="reset" class="button outline">{h(TA_UI["guideReset"] if is_ta else "Clear filters")}</button></form></search>
<div class="guide-tools"><p role="status" aria-live="polite" data-results></p><div class="choices" aria-label="{h(view_aria)}">
<button class="choice" type="button" data-view="grid" aria-pressed="true">{h(TA_UI["guideCardsView"] if is_ta else "Cards")}</button>
<button class="choice" type="button" data-view="list" aria-pressed="false">{h(TA_UI["guideListView"] if is_ta else "List")}</button></div></div></div>
<noscript><p class="notice">{h(noscript_txt)}</p></noscript>
<p class="notice" data-empty hidden>{h(TA_UI["guideEmpty"] if is_ta else "No butterflies match those filters. Try clearing a filter or searching another name.")}</p>
<div class="grid guide-grid" data-cards>{"".join(species_card(s, asset_prefix, lang_prefix, include_spot_btn=True, lang=lang) for s in cards)}</div>
<button type="button" class="button outline more" data-more hidden>{h(TA_UI["guideMore"] if is_ta else "Show more species")}</button>
<p class="caption actions">{link(I18N_TA["nav"]["sources"] if is_ta else "Checklist sources & photo credits", local(lang_prefix, "sources/"))}</p></div>"""
    render(
        "butterflies/",
        title + (" · கள வழிகாட்டி" if is_ta else " field guide"),
        lede,
        body,
        image_key="Papilio crino",
        lang=lang,
    )


def species_press_mentions(scientific, name, lang="en"):
    is_ta = lang == "ta"
    ta_press = SITE_TA.get("press") or []
    matches = []
    for idx, story in enumerate(SITE["press"]):
        if story.get("species") == scientific or name.lower() in (story["title"] + " " + story["summary"]).lower():
            when = fmt_date(story["date"], lang)
            t_story = ta_press[idx] if (is_ta and idx < len(ta_press)) else {}
            src_disp = press_src(story["source"], lang)
            title_txt = t_story.get("title") or story["title"]
            matches.append(f'<li><strong>{h(src_disp)} ({when}):</strong> {link(title_txt, story["url"])}</li>')
    return matches


def detail(entry, lang="en"):
    path = route(entry)
    _, asset_prefix, lang_prefix, _, _, _ = paths_for(path, lang=lang)
    is_ta = lang == "ta"
    scientific, name, family, subfamily, genus = (entry[k] for k in ("scientific", "name", "family", "subfamily", "genus"))
    ta_sp = tamil_name(scientific)
    aliases = entry.get("aliases", [])
    query = quote(scientific)
    wiki = "https://commons.wikimedia.org/w/index.php?title=Special:MediaSearch&type=image&search=" + query
    inat = "https://www.inaturalist.org/observations?taxon_name=" + query
    search_ifb = "https://www.ifoundbutterflies.org/search/node?keys=" + query
    gbif = "https://www.gbif.org/species/search?q=" + query
    family_url = local(lang_prefix, "butterflies/") + "?family=" + quote(family)
    subfamily_url = local(lang_prefix, "butterflies/") + "?subfamily=" + quote(subfamily)

    figure = species_gallery(scientific, asset_prefix, lang=lang)
    if not figure:
        taxon_names = [scientific] + [alias for alias in aliases if re.fullmatch(r"[A-Z][a-z]+ [a-z]+(?: [a-z]+)?", alias)]
        lookup_head = "படம் இன்னும் இல்லை: Wikimedia Commons-இல் தேடு" if is_ta else "No pre-cached photo yet: look up Wikimedia Commons"
        lookup_p = f"<i>{h(scientific)}</i> இனத்திற்கு Wikimedia Commons படங்கள் உள்ளதா எனச் சரிபார்க்கவும்." if is_ta else f"Check live Wikimedia Commons records for <i>{h(scientific)}</i>, or share your verified field photograph with TNBS to include it in the guide."
        lookup_btn = "Wikimedia படத்தைத் தேடு" if is_ta else "Look up Wikimedia photo"
        lookup_ext = "Wikimedia Commons தேடல்" if is_ta else "Search Wikimedia Commons"
        figure = f"""<div class="notice" data-photo-lookup="{h(json.dumps(taxon_names))}">
<strong>{h(lookup_head)}</strong>
<p>{lookup_p}</p>
<div class="actions"><button type="button" class="button" data-enhancement hidden>{h(lookup_btn)}</button>{link(lookup_ext, wiki, "button outline")}</div>
<p role="status" aria-live="polite" data-lookup-status class="caption"></p><div data-lookup-result></div></div>"""

    bv_models = entry.get("butterflyVision", [])
    if bv_models:
        if is_ta:
            model_text = " & ".join("மேற்குத் தொடர்ச்சி மலை (300+)" if m == "wg" else "அகில இந்தியா (800+)" for m in bv_models)
            bv_body = f"Butterfly Vision தளத்தில் (சராசரி {SITE['butterflyVision']['accuracy']} துல்லியம்) <strong>{h(model_text)}</strong> AI மாதிரி வழியாக அடையாளம் காணப்படும் இனம்."
        else:
            model_text = " & ".join("Western Ghats (300+)" if m == "wg" else "All India (800+)" for m in bv_models)
            bv_body = f"Recognised by the <strong>{h(model_text)}</strong> model on Butterfly Vision ({SITE['butterflyVision']['accuracy']} average accuracy)."
        bv_card = f"""<div class="bv-species-card">
<p class="card-meta">{"Butterfly Vision AI ஆதரவு" if is_ta else "Butterfly Vision AI Support"}</p>
<h3>{h(f"{ta_sp or name} AI அடையாளம்" if is_ta else f"Identify a photo of {name}")}</h3>
<p>{bv_body}</p>
<div class="actions">{link(TA_UI["identifyAi"] if is_ta else "Open AI Identifier", local(lang_prefix, "identify/"), "button")}{link("butterflyvision.in", BUTTERFLY_VISION, "button outline")}</div></div>"""
    else:
        un_cov = (
            f"<i>{h(scientific)}</i> இன்னும் Butterfly Vision AI பட்டியலில் தனியாகச் சேர்க்கப்படவில்லை. 600x600px மேல் உள்ள தெளிவான படங்கள் AI பயிற்சிக்கு உதவும்."
            if is_ta
            else f"<i>{h(scientific)}</i> is not yet listed separately on Butterfly Vision. Clear field photos (&gt;600x600px) help expand AI recognition."
        )
        bv_card = f"""<div class="bv-species-card">
<p class="card-meta">Butterfly Vision AI</p>
<h3>{"பயிற்சிப் படங்கள் பகிர்க" if is_ta else "Contribute training photos"}</h3>
<p>{un_cov}</p>
<div class="actions">{link("பங்களிக்கும் முறை" if is_ta else "How to contribute", local(lang_prefix, "identify/") + "#contribute-ai", "button outline")}</div></div>"""

    prof = PROFILES.get(scientific)
    t_prof = PROFILES_TA.get(scientific, {}) if (is_ta and isinstance(PROFILES_TA, dict)) else {}

    def view_prof(key):
        if is_ta and isinstance(t_prof, dict) and t_prof.get(key):
            return t_prof[key]
        return prof.get(key, "") if isinstance(prof, dict) else ""

    fam_tax = TAXONOMY_TA.get("families", {}).get(family, TAXONOMY["families"][family]) if is_ta else TAXONOMY["families"][family]
    sub_tax = TAXONOMY_TA.get("subfamilies", {}).get(subfamily, TAXONOMY["subfamilies"][subfamily]) if is_ta else TAXONOMY["subfamilies"][subfamily]
    sp_inat = (INAT.get("bySpecies") or {}).get(scientific)
    inat_proj_url = (
        f"https://www.inaturalist.org/observations?project_id=butterflies-of-tamil-nadu&taxon_id={sp_inat['taxonId']}"
        if sp_inat and sp_inat.get("taxonId")
        else f"https://www.inaturalist.org/observations?project_id=butterflies-of-tamil-nadu&taxon_name={query}"
    )

    tax_dd = (
        f'{link(fam_name(family, lang), family_url)} ({h(fam_desc(family, lang))}) → {link(sub_desc(subfamily, lang), subfamily_url)} ({h(subfamily)}) → <i>{h(genus)}</i>'
        if is_ta
        else f'{link(fam_name(family, lang), family_url)} ({h(fam_desc(family, lang))}) → {link(subfamily, subfamily_url)} ({h(sub_desc(subfamily, lang))}) → <i>{h(genus)}</i>'
    )
    fact_rows = [
        f'<div><dt>{h(TA_UI["checklistId"] if is_ta else "Checklist ID")}</dt><dd>#{entry["id"]} / {len(SPECIES)}</dd></div>',
    ]
    if ta_sp:
        fact_rows.append(f'<div><dt>{h(TA_UI["tamilNameLabel"] if is_ta else "Tamil name")}</dt><dd lang="ta">{h(ta_sp)}</dd></div>')
    fact_rows.extend([
        f'<div><dt>{h(TA_UI["commonNameLabel"] if is_ta else "Common name")}</dt><dd>{h(name)}</dd></div>',
        f'<div><dt>{h(TA_UI["scientificNameLabel"] if is_ta else "Scientific name")}</dt><dd><i>{h(scientific)}</i></dd></div>',
        f'<div><dt>{h(TA_UI["taxonomyLabel"] if is_ta else "Taxonomy")}</dt><dd>{tax_dd}</dd></div>',
    ])
    if aliases:
        fact_rows.append(f'<div><dt>{h(TA_UI["aliasesLabel"] if is_ta else "Alternate names")}</dt><dd>{h("; ".join(aliases))}</dd></div>')
    if view_prof("wingspan"):
        fact_rows.append(f'<div><dt>{h(TA_UI["wingspanLabel"] if is_ta else "Typical wingspan")}</dt><dd>{h(view_prof("wingspan"))}</dd></div>')
    if sp_inat:
        obs_cnt = sp_inat.get("count", 0)
        inat_txt = f"{obs_cnt:,} பதிவுகள் (திட்டம் #47280)" if is_ta else f"{obs_cnt:,} observations (Project #47280)"
        fact_rows.append(f'<div><dt>{h(TA_UI["inatCountLabel"] if is_ta else "TN iNaturalist records")}</dt><dd>{link(inat_txt, inat_proj_url)}</dd></div>')
    val_label = (
        ("தமிழ்நாட்டில் உறுதிப்படுத்தப்பட்ட இனம் (325 உறுதிப்படுத்தப்பட்ட இனங்களில் ஒன்று)" if is_ta else "Validated presence in Tamil Nadu (one of 325 confirmed taxa)")
        if entry.get("validated", True)
        else ("தமிழ்நாடு உறுதிப்படுத்தல் காத்திருப்பில் உள்ள இனம் (4 முன்னுரிமை இனங்களில் ஒன்று)" if is_ta else "Target checklist entry awaiting validated TNBS sighting confirmation (1 of 4 priority target species)")
    )
    fact_rows.append(f'<div><dt>{h(TA_UI["validationLabel"] if is_ta else "TN validation status")}</dt><dd>{h(val_label)}</dd></div>')
    if view_prof("wpaStatus"):
        fact_rows.append(f'<div><dt>{h(TA_UI["wpaLabel"] if is_ta else "Legal protection")}</dt><dd>{h(view_prof("wpaStatus"))}</dd></div>')

    inat_sec = ""
    if sp_inat and sp_inat.get("taxonId"):
        pheno_html = phenology_chart_html(
            sp_inat.get("months") or [],
            lang=lang,
            caption=TA_UI["phenologyCaption"] if is_ta else f"Monthly Tamil Nadu observations of {name} recorded in iNaturalist Project #47280:",
        )
        map_html = inat_map_html(47280, taxon_id=sp_inat["taxonId"], lang=lang, lazy=True, direct_url=inat_proj_url)
        no_pheno = "மாதாந்திரப் பதிவு விவரங்கள் சேகரிக்கப்படுகின்றன." if is_ta else "Seasonal distribution summary pending more monthly records."
        inat_sec = f"""<section class="wrap section inat-species-section">
<h2>{h(TA_UI["phenologyTitle"] if is_ta else "Tamil Nadu Sightings & Flight Season (iNaturalist Project #47280)")}</h2>
<div class="profile-grid">
<div class="profile-card"><h3>{f"பருவகாலப் பரவல் ({sp_inat.get('count', 0):,} பதிவுகள்)" if is_ta else f"Seasonal flight rhythm ({sp_inat.get('count', 0):,} records)"}</h3>
{pheno_html or f'<p class="caption">{h(no_pheno)}</p>'}</div>
<div class="profile-card"><h3>{h(TA_UI["mapTitle"] if is_ta else "Tamil Nadu Distribution Map")}</h3>
{map_html}</div>
</div></section>"""

    profile_html = ""
    if isinstance(prof, dict):
        hosts = "".join(f'<span class="host-pill">{format_host_plant_html(hp)}</span>' for hp in prof.get("hostPlants", []))
        refs = "".join(f'<li>{link(lbl, ref)}</li>' for lbl, ref in prof.get("sources", []))
        host_photos = host_plant_gallery(scientific, lang=lang)
        sec_aria = "இன அடையாளம் மற்றும் சூழலியல் குறிப்புகள்" if is_ta else "Species identification and ecology"
        id_head = "அடையாளக் குறிகள்" if is_ta else "Identification marks"
        hab_head = "வாழிடம் &amp; தமிழ்நாடு பரவல்" if is_ta else "Habitat &amp; Tamil Nadu range"
        beh_head = "பறக்கும் முறை &amp; நடத்தை" if is_ta else "Flight &amp; behaviour"
        ref_head = "கள ஆதாரங்கள்" if is_ta else "Field references"
        up_lbl = "மேற்சிறகு:" if is_ta else "Upperwing:"
        un_lbl = "கீழ்ச்சிறகு:" if is_ta else "Underwing:"
        sim_lbl = "ஒத்த இனங்கள்:" if is_ta else "Lookalikes:"
        hab_lbl = "வாழிடங்கள்:" if is_ta else "Habitats:"
        tn_lbl = "தமிழ்நாடு பரவல்:" if is_ta else "Tamil Nadu distribution:"
        sea_lbl = "பருவகாலம்:" if is_ta else "Seasonality:"
        note_lbl = "களக் குறிப்பு:" if is_ta else "Field note:"
        no_host = "குடும்பத் தாவரத் தொடர்புகளின் அடிப்படையில் பதிவானது." if is_ta else "Host plants recorded under family associations."
        profile_html = f"""<section class="profile-section" aria-label="{h(sec_aria)}">
<div class="profile-lead"><h2>{h(view_prof("headline"))}</h2></div>
<div class="profile-grid">
<div class="profile-card"><h3>{id_head}</h3>
<p><strong>{h(up_lbl)}</strong> {h(view_prof("upperwing"))}</p>
<p><strong>{h(un_lbl)}</strong> {h(view_prof("underwing"))}</p>
<p><strong>{h(sim_lbl)}</strong> {h(view_prof("similarSpecies"))}</p></div>
<div class="profile-card"><h3>{hab_head}</h3>
<p><strong>{h(hab_lbl)}</strong> {h(view_prof("habitat"))}</p>
<p><strong>{h(tn_lbl)}</strong> {h(view_prof("tnDistribution"))}</p>
<p><strong>{h(sea_lbl)}</strong> {h(view_prof("season"))}</p></div>
<div class="profile-card"><h3>{beh_head}</h3>
<p>{h(view_prof("behavior"))}</p>
{f'<p><strong>{h(note_lbl)}</strong> {h(view_prof("notes"))}</p>' if view_prof("notes") else ""}</div>
<div class="profile-card"><h3>{h(TA_UI["hostPlantsTitle"] if is_ta else "Caterpillar host plants")}</h3>
{f'<div class="host-pills">{hosts}</div>' if hosts else f'<p>{h(no_host)}</p>'}
{host_photos}
{f'<h4>{h(ref_head)}</h4><ul class="compact-list">{refs}</ul>' if refs else ""}</div>
</div></section>"""

    if is_ta:
        sub_sum = f'{fam_name(family, "ta")} · {sub_tax["group"]} ({subfamily}) கள வழிகாட்டிக் குறிப்புகள்'
        subfamily_card = f"""<details class="taxonomy-disclosure">
<summary>{h(sub_sum)}</summary>
<div class="disclosure-body">
<p><strong>குடும்ப அறிமுகம் ({h(fam_name(family, "ta"))}, {h(fam_tax["common"])}):</strong> {h(fam_tax["description"])}</p>
<p><strong>துணைக்குடும்ப இயல்புகள் ({h(subfamily)}):</strong> {h(sub_tax["traits"])}</p>
<p><strong>வழக்கமான வாழிடங்கள்:</strong> {h(sub_tax["habitat"])}</p>
<p><strong>களப் புகைப்படக் குறிப்பு:</strong> {h(sub_tax["photoTip"])} {h(fam_tax["photoTip"])}</p>
</div></details>"""
    else:
        subfamily_card = f"""<details class="taxonomy-disclosure">
<summary>Field guide notes for {h(family)} · {h(subfamily)} ({h(sub_tax["group"])})</summary>
<div class="disclosure-body">
<p><strong>Family overview ({h(family)}, {h(fam_tax["common"])}):</strong> {h(fam_tax["description"])}</p>
<p><strong>Subfamily traits ({h(subfamily)}):</strong> {h(sub_tax["traits"])}</p>
<p><strong>Typical habitats:</strong> {h(sub_tax["habitat"])}</p>
<p><strong>Field photography tip:</strong> {h(sub_tax["photoTip"])} {h(fam_tax["photoTip"])}</p>
</div></details>"""

    mentions = species_press_mentions(scientific, name, lang=lang)
    mentions_html = f'<h2>{"செய்திகள் & இதழ்களில்" if is_ta else "In TNBS news & press"}</h2><ul>{"".join(mentions)}</ul>' if mentions else ""

    idx = entry["id"] - 1
    prev_entry = SPECIES[(idx - 1) % len(SPECIES)]
    next_entry = SPECIES[(idx + 1) % len(SPECIES)]
    prev_disp = (tamil_name(prev_entry["scientific"]) or prev_entry["name"]) if is_ta else prev_entry["name"]
    next_disp = (tamil_name(next_entry["scientific"]) or next_entry["name"]) if is_ta else next_entry["name"]

    siblings = [s for s in BY_FAMILY[family] if s["scientific"] != scientific]
    siblings.sort(key=lambda s: (s["scientific"] not in PHOTOS, s["subfamily"] != subfamily, s["id"]))
    related_cards = "".join(species_card(s, asset_prefix, lang_prefix, lang=lang) for s in siblings[:3])

    spot_action = (
        f'<div class="actions" data-enhancement hidden>'
        f'<button type="button" class="button outline spot-btn" data-spot-btn data-sci="{h(scientific)}" aria-pressed="false">{h(TA_UI["spottedDetailMark"] if is_ta else "+ Mark as spotted in Tamil Nadu")}</button>'
        f'<a class="button outline" href="{local(lang_prefix, "butterflies/")}?tag=spotted">{h(TA_UI["viewLifeList"] if is_ta else "View my life list")}</a></div>'
    )

    h1_txt = ta_sp if (is_ta and ta_sp) else name
    lede_sub = f'<p class="lede"><span lang="en">{h(name)}</span> · <i>{h(scientific)}</i> · {h(sub_desc(subfamily, lang))}</p>' if (is_ta and ta_sp) else (
        f'<p class="lede"><span lang="ta">{h(ta_sp)}</span> · <i>{h(scientific)}</i> · {h(sub_tax["group"])}</p>' if ta_sp else f'<p class="lede"><i>{h(scientific)}</i> · {h(sub_desc(subfamily, lang))}</p>'
    )
    ext_links_html = (
        f'<li>{link("TNBS iNaturalist திட்டம் #47280", inat_proj_url)}</li>'
        f'<li>{link("Butterfly Vision AI", BUTTERFLY_VISION)}</li>'
        f'<li>{link("இந்தியப் பட்டாம்பூச்சிகள் (IFoundButterflies)", search_ifb)}</li>'
        f'<li>{link("iNaturalist அவதானிப்புகள்", inat)}</li>'
        f'<li>{link("விக்கிமீடியா காமன்ஸ் (Wikimedia Commons)", wiki)}</li>'
        f'<li>{link("GBIF உயிரியல் பதிவு", gbif)}</li>'
        if is_ta
        else f'<li>{link("TNBS iNaturalist Project #47280", inat_proj_url)}</li>'
        f'<li>{link("Butterfly Vision AI", BUTTERFLY_VISION)}</li>'
        f'<li>{link("Butterflies of India (IFoundButterflies)", search_ifb)}</li>'
        f'<li>{link("iNaturalist observations", inat)}</li>'
        f'<li>{link("Wikimedia Commons", wiki)}</li>'
        f'<li>{link("GBIF taxonomic record", gbif)}</li>'
    )
    pager_aria = "அடுத்த மற்றும் முந்தைய இனங்கள்" if is_ta else "Adjacent checklist species"

    body = f"""<header class="page-head"><div class="wrap">
<p class="breadcrumb">{link(nav_text("butterflies/", lang), local(lang_prefix, "butterflies/"))} / {link(fam_name(family, lang), family_url)} / {link(sub_desc(subfamily, lang) if is_ta else subfamily, subfamily_url)}</p>
<h1>{h(h1_txt)}</h1>{lede_sub}
{species_badges_html(entry, compact=False, lang=lang)}{spot_action}</div></header>
<section class="wrap section species-main"><div class="species-media-col">{figure}{bv_card}</div>
<div class="species-info-col"><h2>{h(TA_UI["checklistRecordHeading"] if is_ta else "Structured checklist record")}</h2><dl class="facts">{"".join(fact_rows)}</dl>
{subfamily_card}{mentions_html}
<h2>{h(TA_UI["exploreExternalHeading"] if is_ta else "Explore external databases")}</h2><ul class="explore-links">{ext_links_html}</ul></div></section>
{inat_sec}
{f'<section class="journal"><div class="wrap compact">{profile_html}</div></section>' if profile_html else ""}
<section class="wrap section">
<nav class="species-pager" aria-label="{h(pager_aria)}">
<a class="pager-link" href="{local(lang_prefix, route(prev_entry))}"><small>{h(TA_UI["prevSpecies"] if is_ta else "← Previous")} (#{prev_entry["id"]})</small><strong>{h(prev_disp)}</strong></a>
<a class="pager-link pager-next" href="{local(lang_prefix, route(next_entry))}"><small>{h(TA_UI["nextSpecies"] if is_ta else "Next")} (#{next_entry["id"]}) →</small><strong>{h(next_disp)}</strong></a>
</nav>
{f'<div class="related-block"><h2>{h((TA_UI["moreInFamily"] + " " + fam_name(family, "ta")) if is_ta else f"More in {family} ({FAMILIES[family]})")}</h2><div class="grid">{related_cards}</div></div>' if related_cards else ""}
</section>"""

    page_title = f"{ta_sp} ({name}, {scientific})" if (is_ta and ta_sp) else f"{name} ({scientific})"
    page_desc = (
        f"தமிழ்நாடு பட்டாம்பூச்சிகள் கள வழிகாட்டியில் {page_title} பற்றிய அடையாளக் குறிகள், உணவூட்டும் தாவரங்கள், பரவல் மற்றும் புகைப்படங்கள்."
        if is_ta
        else f"{page_title} in the Butterflies of Tamil Nadu field guide."
    )
    render(
        path,
        page_title,
        page_desc,
        body,
        active="butterflies/",
        image_key=scientific,
        schema={
            "@type": "WebPage",
            "name": page_title,
            "about": [{"@type": "Thing", "name": scientific}, {"@type": "Place", "name": "Tamil Nadu"}],
        },
        lang=lang,
    )


def identify(lang="en"):
    _, asset_prefix, lang_prefix, _, _, _ = paths_for("identify/", lang=lang)
    is_ta = lang == "ta"
    bv = SITE["butterflyVision"]
    wg_covered = sum(1 for s in SPECIES if "wg" in s.get("butterflyVision", []))
    india_covered = sum(1 for s in SPECIES if "india" in s.get("butterflyVision", []))
    total_covered = sum(1 for s in SPECIES if s.get("butterflyVision"))

    lookup_map = {}
    for s in SPECIES:
        target = route(s)
        ta_sp = tamil_name(s["scientific"])
        disp = f"{ta_sp} ({s['name']})" if (is_ta and ta_sp) else s["name"]
        lookup_map[s["scientific"].lower()] = [disp, s["scientific"], target]
        lookup_map[s["name"].lower()] = [disp, s["scientific"], target]
        for alias in s.get("aliases", []):
            lookup_map.setdefault(alias.lower(), [disp, s["scientific"], target])

    ta_bv_pubs = SITE_TA.get("bvPublications", []) if is_ta else []
    pubs_parts = []
    for p_idx, (title, venue, url) in enumerate(bv["publications"]):
        t_pair = ta_bv_pubs[p_idx] if p_idx < len(ta_bv_pubs) else None
        p_title = t_pair[0] if t_pair else title
        p_venue = t_pair[1] if t_pair else venue
        read_lbl = "ஆய்வு / தொகுப்பைப் பார்" if is_ta else "Read publication / repository"
        pubs_parts.append(f'<li class="reveal"><h3>{h(p_title)}</h3><p class="card-meta">{h(p_venue)}</p><p>{link(read_lbl, url)}</p></li>')
    pubs_html = "".join(pubs_parts)

    lead_desc = (
        f"butterflyvision.in நேரடி ஒருங்கிணைப்பு: TNBS உறுப்பினர் {bv['developer']} உருவாக்கியது; {bv['supportedTotal']} இந்திய மற்றும் மேற்குத் தொடர்ச்சி மலை இனங்களை அடையாளம் காணும் திறன் கொண்டது."
        if is_ta
        else f"Direct integration with butterflyvision.in: developed by TNBS member {bv['developer']} covering {bv['supportedTotal']} Indian and Western Ghats species."
    )
    body = heading(
        "Butterfly Vision AI மூலம் பட்டாம்பூச்சியை அடையாளம் காண" if is_ta else "Identify butterflies with Butterfly Vision AI",
        lead_desc,
        "AI அடையாளம்" if is_ta else "AI Butterfly Identifier",
    )
    wg_btn = f"மேற்குத் தொடர்ச்சி மலை ({bv['wgCount']})" if is_ta else f"Western Ghats ({bv['wgCount']})"
    in_btn = f"அகில இந்தியா ({bv['indiaCount']})" if is_ta else f"All India ({bv['indiaCount']})"
    model_desc_init = (
        f"தமிழ்நாடு மலைப்பகுதிகள், காடுகள் மற்றும் மேற்குத் தொடர்ச்சி மலை ஆய்வுகளுக்குப் பரிந்துரைக்கப்படுவது (329 தமிழ்நாடு இனங்களில் {total_covered} இனங்கள் உள்ளடக்கம்)."
        if is_ta
        else f"Recommended for Tamil Nadu hills, forests, and Western Ghats surveys ({total_covered} of 329 TN checklist species covered)."
    )
    open_ext_lbl = "butterflyvision.in தளத்தில் திற ↗" if is_ta else "Open on butterflyvision.in ↗"
    noscript_msg = (
        f'JavaScript இயக்கத்தில் இல்லை, எனவே {link("butterflyvision.in தளத்தில் நேரடியாக அடையாளம் காண்க", BUTTERFLY_VISION)}.'
        if is_ta
        else f'JavaScript is off, so please {link("identify directly on butterflyvision.in", BUTTERFLY_VISION)}.'
    )
    if is_ta:
        tips_html = """<div><p class="kicker">செயல்படும் விதம்</p><h2>துல்லியமான AI &amp; கள அடையாளத்திற்கான குறிப்புகள்</h2>
<ul class="bullet-list">
<li><strong>சட்டகத்தைத் தெளிவாக நிரப்புங்கள்:</strong> இறக்கை புள்ளிகள், பட்டைகள் மற்றும் விளிம்புகள் தெளிவாகத் தெரியும்படி பட்டாம்பூச்சியை அருகில் வெட்டி (crop) எடுங்கள்.</li>
<li><strong>இரு பக்கங்களையும் படமெடுக்கவும்:</strong> புல் நீலன்கள், நால்வளையன்கள், வெள்ளிவரையன்கள் மற்றும் தாவிகளுக்குக் கீழ்ச்சிறகு குறிகள் மிகவும் அவசியம்.</li>
<li><strong>சரியான மாதிரியைத் தேர்ந்தெடுக்கவும்:</strong> நீலகிரி, ஆனைமலை, களக்காடு படங்களுக்கு மேற்குத் தொடர்ச்சி மலை மாதிரியும், கடற்கரை/கிழக்குத் தொடர்ச்சி மலைகளுக்கு அகில இந்திய மாதிரியும் சிறந்தது.</li>
<li><strong>TNBS கள வழிகாட்டியில் உறுதிசெய்யவும்:</strong> பருவகால வடிவங்கள், பரவல் வரைபடம் மற்றும் உணவூட்டும் தாவரங்களை இனப் பக்கத்தில் சரிபார்க்கவும்.</li></ul></div>"""
        contrib_html = f"""<div id="contribute-ai" class="ai-card"><p class="card-meta">சமூகத் தரவுப் பங்களிப்பு</p>
<h3>Butterfly Vision AI துல்லியத்தை 95%+ ஆக உயர்த்த உதவுங்கள்</h3>
<p>அரிய இனங்களை அடையாளம் காணும் திறனை வலுப்படுத்த 600x600px மேல் உள்ள தெளிவான பட்டாம்பூச்சிப் படங்களை Butterfly Vision ஆய்வுக் குழுவுடன் பகிருங்கள்.</p>
<p><strong>மின்னஞ்சல்:</strong> {link(bv["contributeEmail"], "mailto:" + bv["contributeEmail"] + "?subject=Photo%20contribution%20to%20Butterfly%20Vision")}</p>
<div class="actions">{link(TA_UI["browseAll"], local(lang_prefix, "butterflies/") + "?tag=bv", "button outline")}</div></div>"""
    else:
        tips_html = """<div><p class="kicker">How it works</p><h2>Tips for high-accuracy AI &amp; expert ID</h2>
<ul class="bullet-list">
<li><strong>Fill the frame cleanly:</strong> Crop close around the butterfly so wing spots, bands, and margins stand out clearly.</li>
<li><strong>Capture both surfaces when possible:</strong> Underwing patterns are vital for grass blues, bushbrowns, silverlines, and skippers.</li>
<li><strong>Use Western Ghats vs All India strategically:</strong> For Nilgiris, Anamalai, or KMTR photos, try Western Ghats first; switch to All India for coastal plains or Eastern Ghats.</li>
<li><strong>Cross-verify in the TNBS Field Guide:</strong> Confirm seasonal morphs, distribution maps, and host plants on the species page.</li></ul></div>"""
        contrib_html = f"""<div id="contribute-ai" class="ai-card"><p class="card-meta">Community Data Flywheel</p>
<h3>Help train Butterfly Vision toward 95%+ accuracy</h3>
<p>Share clear, verified butterfly photographs (&gt;600x600px) with the Butterfly Vision research team to strengthen rare species recognition.</p>
<p><strong>Email:</strong> {link(bv["contributeEmail"], "mailto:" + bv["contributeEmail"] + "?subject=Photo%20contribution%20to%20Butterfly%20Vision")}</p>
<div class="actions">{link("Browse supported TN species", local(lang_prefix, "butterflies/") + "?tag=bv", "button outline")}</div></div>"""

    body += f"""<div class="band"><div class="wrap"><ul class="stats stats-4">
<li><strong>{bv['supportedTotal']}</strong><span>{"மொத்த ஆதரவு இனங்கள்" if is_ta else "Total species supported on Butterfly Vision"}</span></li>
<li><strong>{bv['accuracy']}</strong><span>{"சராசரி துல்லியம்" if is_ta else "Average deep learning accuracy"}</span></li>
<li><strong>{wg_covered} / {len(SPECIES)}</strong><span>{"மேற்குத் தொடர்ச்சி மலை மாதிரி" if is_ta else "TN checklist species in Western Ghats model"}</span></li>
<li><strong>{india_covered} / {len(SPECIES)}</strong><span>{"அகில இந்திய மாதிரி" if is_ta else "TN checklist species in All India model"}</span></li></ul></div></div>

<section class="wrap section">
<div class="bv-widget" data-bv-widget data-lang-prefix="{h(lang_prefix)}" data-species-index="{h(json.dumps(lookup_map, separators=(',', ':'), ensure_ascii=False))}">
<div class="bv-header"><div><p class="kicker">{"படி 1 · மாதிரியைத் தேர்ந்தெடுக்கவும்" if is_ta else "Step 1 · Choose recognition model"}</p><h2>{"பட்டாம்பூச்சி புகைப்படத்தைப் பதிவேற்றவும்" if is_ta else "Upload & prepare a butterfly photo"}</h2></div>
<div class="choices" role="group" aria-label="{"AI மாதிரித் தேர்வு" if is_ta else "Butterfly Vision model selection"}">
<button type="button" class="choice" data-bv-model="wg" aria-pressed="true">{h(wg_btn)}</button>
<button type="button" class="choice" data-bv-model="india" aria-pressed="false">{h(in_btn)}</button></div></div>
<p class="caption" data-bv-model-desc>{h(model_desc_init)}</p>

<div class="bv-dropzone" data-bv-drop>
<label for="bv-file" class="bv-file-label">{"பட்டாம்பூச்சி புகைப்படத்தைத் தேர்ந்தெடுக்கவும் (JPG, PNG, WebP)" if is_ta else "Choose butterfly photo (JPG, PNG, or WebP)"}</label>
<input id="bv-file" name="butterfly_photo" type="file" accept="image/jpeg,image/png,image/webp" class="bv-file-input" aria-describedby="bv-file-help">
<p id="bv-file-help" class="caption">{"மேலே கோப்பைத் தேர்ந்தெடுக்கும் பொத்தானைச் சொடுக்கவும் அல்லது படத்தை இங்கே இழுத்து விடவும் (600x600px மேல் சிறந்தது)." if is_ta else "Use Browse / Choose File above or drag and drop a photo here. Clear, cropped photos above 600x600px give the best species predictions."}</p>
<div class="actions">{link("butterflyvision.in நேரடியாகத் திற", BUTTERFLY_VISION, "button outline") if is_ta else link("Open butterflyvision.in directly", BUTTERFLY_VISION, "button outline")}</div>
</div>

<div class="bv-preview" data-bv-preview hidden>
<div class="bv-preview-grid">
<figure class="photo-large"><img id="bv-preview-img" src="" alt="{"தேர்ந்தெடுக்கப்பட்ட பட்டாம்பூச்சி பட முன்னோட்டம்" if is_ta else "Selected butterfly image preview"}"><figcaption id="bv-file-meta" class="credit"></figcaption></figure>
<div class="bv-result-col">
<p role="status" aria-live="polite" data-bv-status class="quiz-feedback"></p>
<div data-bv-results></div>
<div class="actions" data-bv-actions>
<button type="button" class="button" data-bv-run>{"AI அடையாளம் இயக்கு" if is_ta else "Run AI identification"}</button>
<a class="button outline" href="{BUTTERFLY_VISION}" target="_blank" rel="noopener noreferrer">{h(open_ext_lbl)}</a>
</div></div></div></div>
<noscript><p class="notice">{noscript_msg}</p></noscript>
</div></section>

<section class="journal"><div class="wrap section split">{tips_html}{contrib_html}</div></section>

<section class="wrap section">
<p class="kicker">{"சக மதிப்பாய்வு செய்யப்பட்ட ஆய்வுகள்" if is_ta else "Peer-reviewed research"}</p><h2>{"Butterfly Vision-இன் அறிவியல் அடித்தளம்" if is_ta else "Scientific foundation behind Butterfly Vision"}</h2>
<ul class="news-list">{pubs_html}</ul></section>"""

    render(
        "identify/",
        "Butterfly Vision AI" + (" அடையாளம்" if is_ta else " Identification"),
        "Butterfly Vision AI மூலம் தமிழ்நாடு மற்றும் இந்தியப் பட்டாம்பூச்சிகளை நொடிகளில் அடையாளம் காணுங்கள்." if is_ta else "Identify Tamil Nadu and Indian butterflies instantly with Butterfly Vision AI (butterflyvision.in).",
        body,
        image_key="Papilio crino",
        lang=lang,
    )


def magazine(lang="en"):
    _, _, _, _, _, _ = paths_for("magazine/", lang=lang)
    is_ta = lang == "ta"
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
        months_en = ("January-March", "April-June", "July-September", "October-December")[quarter - 1]
        en_articles = MAGAZINE_INDEX.get(number, {}).get("articles", [])
        ta_entry = MAGAZINE_TA.get(number, {}) if is_ta else {}
        disp_articles = ta_entry.get("articles") or en_articles if is_ta else en_articles
        period_lbl = ta_entry.get("period") or f"{months_en} {year}" if is_ta else f"{months_en} {year}"
        terms = " ".join([f"Issue {number} இதழ் {number}", months_en, period_lbl, str(year), *en_articles, *disp_articles])
        articles_html = ""
        if disp_articles:
            li_items = "".join(f'<li>{h(a)}</li>' for a in disp_articles)
            sum_txt = f"{len(disp_articles)} சிறப்புக் கட்டுரைகளைப் பார்" if is_ta else f"Browse {len(disp_articles)} featured articles"
            articles_html = (
                f'<details class="mag-articles"><summary>{h(sum_txt)}</summary>'
                f'<ul class="compact-list">{li_items}</ul></details>'
            )
        issue_head = f"இதழ் {number} · {period_lbl}" if is_ta else f"Issue {number} · {months_en} {year}"
        issue_meta = f"சிறகு {year - 2016} · நரம்பு {quarter}" if is_ta else f"Wings {year - 2016} · Veins {quarter}"
        pdf_btn = f"இதழ் {number} PDF" if is_ta else f"Open issue {number} PDF"
        rows.append(
            f'<li class="issue-card reveal" data-record data-year="{year}" data-terms="{h(terms)}" id="issue-{number}">'
            f'<div class="issue-row"><div><strong>{h(issue_head)}</strong>'
            f'<p class="meta">{h(issue_meta)}</p></div>'
            f'{link(pdf_btn, issue_url(number), "button outline")}</div>{articles_html}</li>'
        )
    latest_desc = (
        "இதழ் 27-இல் 2024 Danainae வலசை அறிக்கை, முதுமலை புலிகள் காப்பகம் (185+ இனங்கள்) மற்றும் பச்சைமலை (126 இனங்கள்) ஆய்வுகள், 13+ மாவட்டப் பள்ளித் தமிழ் சுவரொட்டி விழிப்புணர்வு, 2017-2024 கட்டுரை அட்டவணை மற்றும் 329 இனங்கள் கொண்ட தமிழ்நாடு பட்டியல் ஆகியவை இடம்பெற்றுள்ளன."
        if is_ta
        else "Issue 27 presents the 2024 Danainae migration update, Mudumalai Tiger Reserve (185+ spp.) and Pachamalai Hills (126 spp.) surveys, school Tamil poster outreach across 13+ districts, a full back-issues article index (2017-2024), and the updated 329-species Tamil Nadu checklist."
    )
    body = heading(
        "பட்டாம்பூச்சி இதழ் (Pattampoochi)" if is_ta else "Pattampoochi",
        f"TNBS காலாண்டிதழ்: {len(SITE['issues'])} இதழ்கள் மற்றும் {total_indexed} கட்டுரைகள்." if is_ta else f"The quarterly e-magazine of The Nature and Butterfly Society: 27 issues and {total_indexed} indexed articles covering surveys, migration, host plants, and Tamil Nadu checklist revisions.",
        "இதழ்கள்" if is_ta else "Publications",
    )
    body += f"""<section class="journal"><div class="wrap compact split">{cover(lang)}<div><p class="kicker">{"இதழ் 27 · ஜனவரி-மார்ச் 2025" if is_ta else "Issue 27 · January-March 2025"}</p><h2>{"அண்மை இதழ் சிறப்புகள்" if is_ta else "Latest issue highlights"}</h2>
<p>{h(latest_desc)}</p>
{link("இதழ் 27 PDF திற" if is_ta else "Open issue 27 PDF", issue_url(27), "button")}</div></div></section>
<section class="wrap section" data-records><h2>{"அனைத்து 27 இதழ்கள் & கட்டுரைத் தேடல்" if is_ta else f"All {len(SITE['issues'])} issues & searchable article index"}</h2>
<div data-enhancement hidden><search><form class="filters">
<div class="field grow"><label for="mag-q">{"கட்டுரைகள், இடங்கள் தேடுக" if is_ta else "Search articles, places & authors"}</label><input id="mag-q" type="search" name="q" placeholder="{"சிறுவாணி, கல்லாறு, வலசை, பாவேந்தன், வாழ்க்கைச் சுழற்சி..." if is_ta else "Try Siruvani, Kallar, migration, Pavendhan, life cycle..."}"></div>
<div class="field"><label for="mag-year">{"ஆண்டு" if is_ta else "Year"}</label><select id="mag-year" name="year"><option value="">{"அனைத்து ஆண்டுகளும்" if is_ta else "All years"}</option>{"".join(f'<option>{y}</option>' for y in range(2025, 2016, -1))}</select></div>
<button type="reset" class="button outline">{"மீட்டமை" if is_ta else "Clear"}</button></form></search></div>
<p data-status role="status" aria-live="polite"></p><ul class="issue-list">{"".join(rows)}</ul><div class="actions">{link("முந்தைய இதழ் காப்பகம்" if is_ta else "Original magazine archive", MAGAZINE)} ·
{link("கட்டுரை அனுப்ப" if is_ta else "Send a contribution", "mailto:" + CONTACT + "?subject=Pattampoochi%20contribution")}</div></section>"""
    render(
        "magazine/",
        "பட்டாம்பூச்சி இதழ் காப்பகம்" if is_ta else "Pattampoochi magazine archive",
        f"பட்டாம்பூச்சி இதழின் 27 இதழ்கள் மற்றும் {total_indexed} கட்டுரைகளைத் தேடிப் படியுங்கள்." if is_ta else f"Browse all 27 issues and search {total_indexed} indexed articles in Pattampoochi.",
        body,
        lang=lang,
    )


def news(lang="en"):
    _, _, lang_prefix, _, _, _ = paths_for("news/", lang=lang)
    is_ta = lang == "ta"
    updates_en = [
        ("2025", "Society Updates", "TNBS", "Tamil Nadu butterfly checklist reaches 329 species", "Confirmed 325 validated species and 4 priority targets across 6 families, adding Common Palmfly and Cloud Forest Silverline.", local(lang_prefix, "butterflies/")),
        ("2025", "Society Updates", "TNBS", "Free Tamil butterfly posters reach 13+ districts", "TNBS government school outreach expanded across Chennai, Salem, Krishnagiri, Tiruppur, Dharmapuri, Cuddalore, and The Nilgiris.", local(lang_prefix, "about/") + "#outreach"),
        ("2024", "Society Updates", "TNBS", "Tamilnadu Butterflies Facebook group marks 10 years", "Launched on 02 October 2014, TNBS's flagship citizen-science forum now connects 2,340+ contributors across all 38 districts of Tamil Nadu and Puducherry.", FACEBOOK_GROUP),
        ("2024", "Society Updates", "TNBS", "Butterfly Vision surpasses 923+ supported Indian species", "TNBS member Theivaprakasham Hari's AI identification tool covers 319 of Tamil Nadu's 329 checklist species.", local(lang_prefix, "identify/")),
    ]
    ta_updates = SITE_TA.get("updates", []) if is_ta else []
    ta_press = SITE_TA.get("press", []) if is_ta else []

    lead = SITE["press"][0]
    t_lead = ta_press[0] if (is_ta and ta_press) else {}
    lead_when = fmt_date(lead["date"], lang)
    lead_kicker = f'{"அண்மை முதன்மை அறிக்கை" if is_ta else "Latest Lead Report"} · <time datetime="{lead["date"]}">{lead_when}</time>'
    lead_btn = "முழுக் கட்டுரையைப் படி ↗" if is_ta else "Read full article ↗"
    lead_sp_lbl = "நீல வரியன் இனக் குறிப்பைப் பார்" if is_ta else "Browse Blue Tiger species profile"
    lead_html = f"""<article class="featured-news">
<p class="kicker">{lead_kicker}</p>
<h2>{h(t_lead.get("title") or lead["title"])}</h2>
<p class="card-meta">{h(press_src(lead["source"], lang))} · {h(press_cat(lead["category"], lang))}</p>
<p class="lede">{h(t_lead.get("summary") or lead["summary"])}</p>
<div class="actions">{link(lead_btn, lead["url"], "button")}{link(lead_sp_lbl, local(lang_prefix, route(BY_SCI[lead["species"]])), "button outline")}</div>
</article>"""

    categories = sorted({press_cat(s["category"], lang) for s in SITE["press"]} | {press_cat("Society Updates", lang)})
    all_cov_lbl = "அனைத்துச் செய்திகளும்" if is_ta else "All coverage"
    cat_pills = [f'<button type="button" class="choice" data-cat-pill="" aria-pressed="true">{h(all_cov_lbl)}</button>']
    for cat in categories:
        cat_pills.append(f'<button type="button" class="choice" data-cat-pill="{h(cat)}" aria-pressed="false">{h(cat)}</button>')

    sources_opts = "".join(
        f'<option>{h(src)}</option>'
        for src in sorted({press_src(s["source"], lang) for s in SITE["press"]} | {press_src("TNBS", lang)})
    )
    year_opts = "".join(f'<option>{y}</option>' for y in sorted({s["date"][:4] for s in SITE["press"]} | {u[0] for u in updates_en}, reverse=True))

    update_rows_parts = []
    for u_idx, (year, cat, src, title, summary, url) in enumerate(updates_en):
        tu = ta_updates[u_idx] if u_idx < len(ta_updates) else {}
        u_cat = press_cat(cat, lang)
        u_src = press_src(src, lang)
        u_title = tu.get("title") or title
        u_sum = tu.get("summary") or summary
        open_lbl = "விவரம் காண்க →" if is_ta else "Open update →"
        u_terms = " ".join([title, u_title, summary, u_sum, year, cat, u_cat, src, u_src])
        update_rows_parts.append(
            f'<li class="news-card reveal" data-record data-kind="Society" data-category="{h(u_cat)}" data-source="{h(u_src)}" data-year="{year}" data-terms="{h(u_terms)}">'
            f'<div class="news-card-meta"><span class="tag tag-highlight">{h(u_cat)}</span><span class="card-meta">{h(u_src)} · {year}</span></div>'
            f'<h3>{link(u_title, url)}</h3><p>{h(u_sum)}</p>'
            f'<p class="news-card-foot">{link(open_lbl, url)}</p></li>'
        )
    update_rows = "".join(update_rows_parts)

    ta_comm = SITE_TA.get("community", []) if is_ta else []
    elsewhere_parts = []
    for c_idx, c in enumerate(SITE["community"]):
        tc = ta_comm[c_idx] if c_idx < len(ta_comm) else {}
        elsewhere_parts.append(
            f'<article class="card community-card reveal"><div class="card-body"><p class="card-meta">{h(tc.get("badge") or c["badge"])}</p>'
            f'<h3>{link(tc.get("title") or c["title"], c["url"])}</h3><p>{h(tc.get("summary") or c["summary"])}</p>'
            f'<p>{link((tc.get("cta") or c["cta"]) + " ↗", c["url"], "small-button")}</p></div></article>'
        )
    elsewhere_cards = "".join(elsewhere_parts)

    news_desc = (
        f"செய்தித்தாள் கட்டுரைகள், ஆய்வுக் கட்டுரைகள், பட்டாம்பூச்சி இதழ் அறிக்கைகள் ({len(SITE['press'])} பதிவுகள்) மற்றும் TNBS சமூக இணைப்புகள்."
        if is_ta
        else f"{len(SITE['press'])} verified newspaper articles, peer-reviewed research papers, and Pattampoochi magazine feature reports alongside TNBS updates and community links across the web."
    )
    body = heading("செய்திகள் & ஊடகப் பதிவுகள்" if is_ta else "News, press & community archive", news_desc)
    body += f"""<section class="wrap section" data-records>
{lead_html}
<div data-enhancement hidden>
<div class="choices" role="group" aria-label="{"தலைப்பு வாரியாக வடிகட்டு" if is_ta else "Filter coverage by topic"}">{"".join(cat_pills)}</div>
<search><form class="filters">
<div class="field grow"><label for="news-q">{"தலைப்புகள், இடங்கள் & இனங்களைத் தேடுக" if is_ta else "Search headlines, places & species"}</label><input id="news-q" type="search" name="q" placeholder="{"முதுமலை, பச்சைமலை, பட்டாம்பூச்சி இதழ், சிங்காநல்லூர்..." if is_ta else "Try Mudumalai, Pachamalai, Pattampoochi, Ypthima, Singanallur, Vellalore..."}"></div>
<div class="field"><label for="news-source">{"வெளியீடு" if is_ta else "Publication"}</label><select id="news-source" name="source"><option value="">{"அனைத்து வெளியீடுகளும்" if is_ta else "All publications"}</option>{sources_opts}</select></div>
<div class="field"><label for="news-year">{"ஆண்டு" if is_ta else "Year"}</label><select id="news-year" name="year"><option value="">{"அனைத்து ஆண்டுகளும்" if is_ta else "All years"}</option>{year_opts}</select></div>
<input type="hidden" name="category" value="">
<button type="reset" class="button outline">{"மீட்டமை" if is_ta else "Clear"}</button></form></search></div>
<p data-status role="status" aria-live="polite"></p>
<ul class="news-grid">{"".join(press_card(story, i, lang_prefix, lang=lang) for i, story in enumerate(SITE["press"]))}{update_rows}</ul>
</section>

<section id="elsewhere" class="journal"><div class="wrap section">
<p class="kicker">{"Facebook, YouTube, ResearchGate & துணைத் தளங்கள்" if is_ta else "Facebook, YouTube, ResearchGate & Partner Apps"}</p>
<h2>{"இணையத்தில் TNBS" if is_ta else "Elsewhere on the web"}</h2>
<p class="lede">{"தமிழ்நாட்டின் பட்டாம்பூச்சி ஆர்வலர்கள் குழுவுடன் இணையுங்கள், காணொளி உரைகளைப் பாருங்கள், பள்ளிச் சுவரொட்டிகளைப் பெறுங்கள் மற்றும் ஆய்வுத் தரவுகளை ஆராயுங்கள்." if is_ta else "Connect with Tamil Nadu's active butterfly community, watch public lectures, request free school materials, and explore published checklist citations."}</p>
<div class="grid">{elsewhere_cards}</div>
</div></section>"""

    render(
        "news/",
        "செய்திகள் & ஊடகப் பதிவுகள்" if is_ta else "News, press & community archive",
        news_desc,
        body,
        image_key="Tirumala limniace",
        lang=lang,
    )


def activities(lang="en"):
    _, asset_prefix, _, _, _, _ = paths_for("activities/", lang=lang)
    is_ta = lang == "ta"
    ta_acts = SITE_TA.get("activities", []) if is_ta else []
    cards = ""
    for a_idx, act in enumerate(SITE["activities"]):
        ta_act = ta_acts[a_idx] if a_idx < len(ta_acts) else {}
        origin, number = act["ref"].split(":")
        url = issue_url(int(number)) if origin == "issue" else SITE["press"][int(number)]["url"]
        a_kind = ta_act.get("kind") or act["kind"]
        a_when = ta_act.get("when") or act["when"]
        a_title = ta_act.get("title") or act["title"]
        a_sum = ta_act.get("summary") or act["summary"]
        a_alt = ta_act.get("photoAlt") or act.get("photoAlt", "")
        media_html = ""
        if act.get("photo"):
            media_html = f'<div class="media">{lightbox_button_img(act["photo"], a_alt, a_title, a_sum, asset_prefix)}</div>'
        link_lbl = ("கள அறிக்கையைப் பார்" if origin == "issue" else "செய்தியைப் படி") if is_ta else ("Open field report" if origin == "issue" else "Read the coverage")
        cards += (
            f'<article class="card reveal">{media_html}<div class="card-body">'
            f'<p class="card-meta">{h(a_kind)} · {h(a_when)}</p>'
            f'<h3>{h(a_title)}</h3><p>{h(a_sum)}</p>'
            f'<p>{link(link_lbl, url)}</p></div></article>'
        )
    act_desc = (
        "முதுமலை மற்றும் பச்சைமலை வன ஆய்வுகள், அரசுப் பள்ளி விழிப்புணர்வுத் திட்டம், நகரப் பல்லுயிர் நடைபயணங்கள் மற்றும் மாநில அளவிலான வலசைக் கண்காணிப்பு."
        if is_ta
        else "From Mudumalai and Pachamalai Forest Division butterfly surveys to school outreach, City Nature Challenge walks, and statewide migration tracking."
    )
    body = heading("TNBS களச் செயல்பாடுகள் & ஆய்வுகள்" if is_ta else "Activities and fieldwork", act_desc)
    cta_btn = "வரும் செயல்பாடுகள் குறித்துக் கேட்க" if is_ta else "Ask about future activities"
    body += f'<section class="wrap section"><h2>{"கள ஆய்வுகள், நடைபயணங்கள் & பள்ளித் திட்டங்கள்" if is_ta else "Surveys, walks & outreach"}</h2><div class="grid">{cards}</div><div class="actions">{link(cta_btn, "mailto:" + CONTACT + "?subject=TNBS%20activities", "button")}</div></section>'
    render(
        "activities/",
        "களச் செயல்பாடுகள்" if is_ta else "Activities and fieldwork",
        act_desc,
        body,
        lang=lang,
    )


def about(lang="en"):
    _, asset_prefix, lang_prefix, _, _, _ = paths_for("about/", lang=lang)
    is_ta = lang == "ta"
    ab = SITE["about"]
    t_ab = SITE_TA.get("about", {}) if is_ta else {}

    t_photos = t_ab.get("photos", []) if is_ta else []
    gallery_parts = []
    for p_idx, p in enumerate(ab["photos"]):
        tp = t_photos[p_idx] if p_idx < len(t_photos) else {}
        p_title = tp.get("title") or p["title"]
        p_when = tp.get("when") or p["when"]
        p_cap = tp.get("caption") or p["caption"]
        gallery_parts.append(
            f'<figure class="gallery-card reveal">{lightbox_button_img(p["src"], p_cap, p_title, p_cap, asset_prefix, p["width"], p["height"])}'
            f'<figcaption><strong>{h(p_title)}</strong> · <span>{h(p_when)}</span><br><small>{h(p_cap)}</small></figcaption></figure>'
        )
    gallery = "".join(gallery_parts)

    milestones_src = t_ab.get("milestones", ab["milestones"]) if is_ta else ab["milestones"]
    milestones = "".join(f'<li><strong>{h(yr)}</strong><p>{h(desc)}</p></li>' for yr, desc in milestones_src)
    leadership_src = t_ab.get("leadership", ab["leadership"]) if is_ta else ab["leadership"]
    team_items = "".join(f'<li>{h(member)}</li>' for member in leadership_src)

    t_papers = SITE_TA.get("researchPapers", []) if is_ta else []
    papers_cards = []
    for p_idx, paper in enumerate(SITE.get("researchPapers", [])):
        tp = t_papers[p_idx] if p_idx < len(t_papers) else {}
        sp_link = ""
        if paper.get("species") and paper["species"] in BY_SCI:
            sp = BY_SCI[paper["species"]]
            sp_disp = (tamil_name(sp["scientific"]) or sp["name"]) if is_ta else sp["name"]
            sp_lbl = f"{sp_disp} இனக் குறிப்பு →" if is_ta else f'View {sp["name"]} profile →'
            sp_link = link(sp_lbl, local(lang_prefix, route(sp)), "press-species")
        doi_link = link("DOI", paper["doiUrl"]) if paper.get("doiUrl") and paper["doiUrl"] != paper["url"] else ""
        read_paper_lbl = "கட்டுரை / பதிவைப் படி ↗" if is_ta else "Read article / record ↗"
        links_row = " · ".join(x for x in [link(read_paper_lbl, paper["url"]), doi_link, sp_link] if x)
        papers_cards.append(
            f'<li class="news-card reveal"><p class="card-meta">{h(tp.get("authors") or paper["authors"])} · {h(tp.get("venue") or paper["venue"])}</p>'
            f'<h3>{link(tp.get("title") or paper["title"], paper["url"])}</h3><p>{h(tp.get("summary") or paper["summary"])}</p>'
            f'<p class="news-card-foot">{links_row}</p></li>'
        )
    papers_html = "".join(papers_cards)

    about_desc = (
        "கோவையை மையமாகக் கொண்டு தமிழ்நாடு முழுவதும் பட்டாம்பூச்சி பாதுகாப்பு மற்றும் குடிமை அறிவியல் பணிகளை முன்னெடுக்கும் சங்கத்தின் வரலாறு, குழு மற்றும் களப் பணிகள்."
        if is_ta
        else "A Coimbatore-based conservation & citizen-science society systematically documenting Tamil Nadu's butterflies across the Western Ghats, Eastern Ghats, wetlands, plains, and schools."
    )
    body = heading(
        "இயற்கை மற்றும் பட்டாம்பூச்சி சங்கம் (TNBS)" if is_ta else "About The Nature and Butterfly Society",
        about_desc,
        I18N_TA["nav"]["about/"] if is_ta else "About us",
    )
    reg_val = t_ab.get("registration") or ab["registration"]
    addr_val = t_ab.get("address") or ab["address"]
    fb_val = t_ab.get("facebookGroup") or ab["facebookGroup"]

    if is_ta:
        body += f"""<section class="wrap section split">
<div><p class="kicker">சங்கத்தின் கதை &amp; நோக்கம்</p><h2>38 மாவட்ட இயற்கை ஆர்வலர்களின் கூட்டு முயற்சி</h2>
<p>புவியியல் ரீதியாக மேற்குத் தொடர்ச்சி மலையும் கிழக்குத் தொடர்ச்சி மலையும் நீலகிரி மலைகளில் சங்கமிக்கும் தமிழ்நாடு, கடற்கரைச் சமவெளிகள் முதல் ஈரப்பதம் மிக்க மழைக்காடுகள் வரை பன்முக வாழிடங்களைக் கொண்டுள்ளது. ஆனால் 2012-2014 காலகட்டத்தில் TNBS பணிகளைத் தொடங்கும் வரை தமிழ்நாட்டிற்கென அதிகாரப்பூர்வ பட்டாம்பூச்சிப் பட்டியல் இல்லை.</p>
<p>கோவையில் பதிவு செய்யப்பட்ட ({h(reg_val)}) TNBS, கள நடைபயணங்கள், தமிழ்நாடு வனத்துறையுடன் இணைந்த ஆய்வுகள், பருவகால வலசைக் கண்காணிப்பு, பள்ளிச் சுவரொட்டி விழிப்புணர்வு மற்றும் <em>பட்டாம்பூச்சி</em> காலாண்டிதழ் வழியே இப்பணியை முன்னெடுக்கிறது.</p>
<dl class="facts">
<div><dt>பதிவு எண்</dt><dd>{h(reg_val)}</dd></div>
<div><dt>தலைமையகம்</dt><dd>{h(addr_val)}</dd></div>
<div><dt>சமூக வலைப்பின்னல்</dt><dd>{link(fb_val, ab["facebookUrl"])}</dd></div>
<div><dt>iNaturalist திட்டம்</dt><dd>{link("Butterflies of Tamil Nadu (#47280)", INAT_PROJECT_URL)}</dd></div>
<div><dt>காணொளி உரை</dt><dd>{link("தமிழ்நாட்டின் பட்டாம்பூச்சிகள் உரை (YouTube)", ab["youtubeUrl"])}</dd></div>
<div><dt>அதிகாரப்பூர்வ மின்னஞ்சல்</dt><dd>{link(CONTACT, "mailto:" + CONTACT)}</dd></div></dl></div>
<div class="emblem-panel"><img src="{asset_prefix}assets/tnbs-logo.png" alt="மயில் அழகி (Papilio crino) பொறிக்கப்பட்ட TNBS இலச்சினை" width="173" height="173">
<p><strong>அதிகாரப்பூர்வ TNBS இலச்சினை</strong></p><p class="caption">இயற்கை மற்றும் பட்டாம்பூச்சி சங்க முத்திரைக்குள் மரகதப் பச்சை மயில் அழகி (<i>Papilio crino</i>).</p></div></section>

<section class="journal"><div class="wrap section">
<p class="kicker">களத்திலும் வகுப்பறையிலும்</p><h2>செயல்பாட்டில் TNBS</h2>
<p class="lede">வனக் கோட்டப் பட்டாம்பூச்சி ஆய்வுகள், குடிமை அறிவியல் எண்ணிக்கைகள் மற்றும் பள்ளி விழிப்புணர்வுத் திட்டங்களின் சிறப்புப் படங்கள். பெரிதாக்கப் படத்தைச் சொடுக்கவும்.</p>
<div class="grid gallery-grid">{gallery}</div></div></section>

<section id="outreach" class="wrap section split">
<div><p class="kicker">மைல்கற்கள் (2012-2025)</p><h2>சங்கம் வளர்ந்த வரலாறு</h2>
<ol class="timeline">{milestones}</ol></div>
<div><p class="kicker">குழு &amp; பொறுப்பாளர்கள்</p><h2>பதிப்பு &amp; கள ஆய்வுக் குழு</h2>
<p>தமிழ்நாடு மற்றும் புதுச்சேரி முழுவதும் உள்ள ஆர்வலர்கள், புகைப்படக் கலைஞர்கள் மற்றும் ஆய்வாளர்களின் தன்னார்வப் பங்களிப்பால் TNBS இயங்குகிறது.</p>
<ul class="bullet-list">{team_items}</ul>
<div class="ai-card"><h3>TNBS அரசுப் பள்ளி சுவரொட்டித் திட்டம்</h3>
<p>தமிழ்நாட்டில் உள்ள அரசுப் பள்ளி ஆசிரியர்களுக்கும் மாணவர்களுக்கும் இலவசத் தமிழ் பட்டாம்பூச்சி சுவரொட்டிகள் மற்றும் அறிமுகக் கையேடுகளை TNBS அச்சிட்டு வழங்குகிறது.</p>
<div class="actions">{link("இலவசப் பள்ளிச் சுவரொட்டி கோர", ab["posterFormUrl"], "button")}{link("கள ஆய்வுகளைப் பார்", local(lang_prefix, "activities/"), "button outline")}</div></div></div></section>

<section id="research" class="journal"><div class="wrap section">
<p class="kicker">அறிவியல் பங்களிப்புகள்</p><h2>ஆய்வுக் கட்டுரைகள் &amp; வெளியீடுகள்</h2>
<p class="lede">TNBS உறுப்பினர்களால் வெளியிடப்பட்ட இளம்பருவ வாழ்க்கை சுழற்சி கண்டுபிடிப்புகள், மாநிலப் பட்டியல் தரவுகள் மற்றும் AI ஆய்வுகள்.</p>
<ul class="news-grid">{papers_html}</ul></div></section>

<section class="dark" id="get-involved"><div class="wrap section content"><p class="kicker">{h(I18N_TA["nav"]["getInvolved"])}</p><h2>TNBS பணிகளில் இணையுங்கள்</h2>
<h3>பட்டாம்பூச்சி பதிவைப் பகிருங்கள்</h3><p>தமிழ்நாட்டின் எந்தப் பகுதியிலிருந்தும் எடுத்த பட்டாம்பூச்சிப் படங்களை {link("iNaturalist திட்டம் #47280", INAT_PROJECT_URL)}-இல் பதிவேற்றுங்கள் அல்லது உறுதிப்படுத்தப்படாத 4 இனங்கள் குறித்த பதிவுகளை மின்னஞ்சலில் அனுப்புங்கள்.</p>
<h3>AI வழியே அடையாளம் காணுங்கள்</h3><p>உடனடி இனக் கணிப்புக்கு {link("Butterfly Vision AI", local(lang_prefix, "identify/"))} கருவியையும், {link("329 இனங்கள் கள வழிகாட்டியையும்", local(lang_prefix, "butterflies/"))} பயன்படுத்துங்கள்.</p>
<h3>நடைபயணம், ஆய்வு அல்லது இதழில் இணைந்திடுங்கள்</h3><p>மாவட்ட அளவிலான பட்டாம்பூச்சி நடைபயணங்கள், பள்ளி நிகழ்ச்சிகள் அல்லது <em>பட்டாம்பூச்சி</em> இதழில் எழுதுவதற்கு எங்களைத் தொடர்பு கொள்ளுங்கள் அல்லது {link("Tamil Nadu Butterflies Facebook குழுமத்தில்", ab["facebookUrl"])} இணையுங்கள்.</p>
<div class="actions">{link("TNBS-க்கு மின்னஞ்சல் அனுப்பு", "mailto:" + CONTACT, "button light")}{link("முந்தைய Google Sites காப்பகம்", ORIGINAL, "button outline")}</div></div></section>"""
    else:
        body += f"""<section class="wrap section split">
<div><p class="kicker">Society story &amp; mission</p><h2>Built by field naturalists across 38 districts</h2>
<p>Geographically, Tamil Nadu spans a remarkable meeting ground where the Western Ghats and Eastern Ghats converge at the Nilgiri hills alongside fertile coastal plains and arid interior scrub. Yet before TNBS began compiling systematic records in 2012-2014, Tamil Nadu lacked an exclusive validated state checklist.</p>
<p>Registered formally in Coimbatore ({h(ab["registration"])}), TNBS coordinates field walks, Tamil Nadu Forest Department surveys, seasonal Danainae migration monitoring, school poster outreach, and the quarterly journal <em>Pattampoochi</em>.</p>
<dl class="facts">
<div><dt>Registration</dt><dd>{h(ab["registration"])}</dd></div>
<div><dt>Headquarters</dt><dd>{h(ab["address"])}</dd></div>
<div><dt>Community network</dt><dd>{link(ab["facebookGroup"], ab["facebookUrl"])}</dd></div>
<div><dt>iNaturalist Project</dt><dd>{link("Butterflies of Tamil Nadu (#47280)", INAT_PROJECT_URL)}</dd></div>
<div><dt>Video lecture</dt><dd>{link("TNBS President talk on Tamil Nadu Butterflies (YouTube)", ab["youtubeUrl"])}</dd></div>
<div><dt>Official contact</dt><dd>{link(CONTACT, "mailto:" + CONTACT)}</dd></div></dl></div>
<div class="emblem-panel"><img src="{asset_prefix}assets/tnbs-logo.png" alt="Official logo of The Nature and Butterfly Society featuring Papilio crino" width="173" height="173">
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
<p>TNBS prints and distributes free Tamil butterfly awareness posters and beginner booklets to government school teachers across Tamil Nadu.</p>
<div class="actions">{link("Request free Tamil school posters", ab["posterFormUrl"], "button")}{link("Browse activities", local(lang_prefix, "activities/"), "button outline")}</div></div></div></section>

<section id="research" class="journal"><div class="wrap section">
<p class="kicker">Scientific Contributions</p><h2>Peer-reviewed research &amp; publications</h2>
<p class="lede">Original life-cycle discoveries, state checklist datasets, and computer-vision research authored by TNBS members.</p>
<ul class="news-grid">{papers_html}</ul></div></section>

<section class="dark" id="get-involved"><div class="wrap section content"><p class="kicker">Join the effort</p><h2>Get involved with TNBS</h2>
<h3>Report a sighting</h3><p>Upload sightings from anywhere in Tamil Nadu to iNaturalist to join {link("Butterflies of Tamil Nadu (Project #47280)", INAT_PROJECT_URL)}, or email records for the four checklist entries awaiting validated Tamil Nadu confirmation.</p>
<h3>Identify &amp; learn with AI</h3><p>Try {link("Butterfly Vision AI", local(lang_prefix, "identify/"))} for quick species suggestions and cross-check field traits in our {link("329-species field guide", local(lang_prefix, "butterflies/"))}.</p>
<h3>Join a walk, survey, or write for Pattampoochi</h3><p>Write to TNBS or join our {link("Tamil Nadu Butterflies Facebook Group", ab["facebookUrl"])} to ask about regional butterfly walks, school awareness sessions, or submitting articles to <em>Pattampoochi</em>.</p>
<div class="actions">{link("Email TNBS", "mailto:" + CONTACT, "button light")}{link("Visit original Google Site archive", ORIGINAL, "button outline")}</div></div></section>"""

    render(
        "about/",
        "எங்களைப் பற்றி · TNBS" if is_ta else "About us · The Nature and Butterfly Society",
        about_desc,
        body,
        lang=lang,
    )


def sources(lang="en"):
    _, asset_prefix, lang_prefix, _, _, _ = paths_for("sources/", lang=lang)
    is_ta = lang == "ta"
    photos_list = "".join(
        f'<li><i>{h(s)}</i> · {credit_html(meta)}</li>'
        for s in sorted(PHOTOS)
        for meta in [photo_meta(s, asset_prefix)]
    )
    unvalidated_list = "".join(
        f'<li>{link((tamil_name(s) or BY_SCI[s]["name"]) if is_ta else BY_SCI[s]["name"], local(lang_prefix, route(BY_SCI[s])))} (<i>{h(s)}</i>)</li>'
        for s in ["Neptis palnica", "Arhopala bazaloides", "Hasora badra", "Arnetta mercara"]
    )
    table_rows = "".join(
        f'<tr><th scope="row">{h(fam_name(fam, lang))} ({h(fam_desc(fam, lang))})</th><td>{v1}</td><td><strong>{EXPECTED_FAMILY_COUNTS[fam]}</strong></td></tr>'
        for fam, v1 in [("Papilionidae", 19), ("Pieridae", 32), ("Nymphalidae", 96), ("Riodinidae", 2), ("Lycaenidae", 91), ("Hesperiidae", 83)]
    )
    member_counts = {}
    for s in sorted(PHOTOS):
        if is_member_photo(s):
            author = PHOTOS[s]["author"]
            member_counts[author] = member_counts.get(author, 0) + 1
    unit_sp = "இனங்கள்" if is_ta else "species"
    member_summary = ", ".join(f"{h(k)}: {v} {unit_sp}" for k, v in sorted(member_counts.items()))

    plants_dict = HOST_PLANTS.get("plants", {})
    host_species_count = len(HOST_PLANTS.get("bySpecies", {}))
    host_author_counts = {}
    host_photos_list_parts = []
    for pkey in sorted(plants_dict):
        plant = plants_dict[pkey]
        author = plant["author"]
        host_author_counts[author] = host_author_counts.get(author, 0) + 1
        lic_url, lic_name = resolve_license(plant.get("license") or "", plant.get("licenseName") or "TNBS Member Archive")
        c_html = credit_html({"author": author, "url": plant["url"], "license": lic_url, "licenseName": lic_name})
        common_txt = f' ({h(plant["commonName"])})' if plant.get("commonName") else ""
        sp_suffix = " sp." if plant.get("rank") == "genus" else ""
        host_photos_list_parts.append(f'<li><i>{h(plant["taxon"])}</i>{sp_suffix}{common_txt} · {c_html}</li>')
    unit_pl = "தாவரங்கள்" if is_ta else "plant taxa"
    host_author_summary = ", ".join(f"{h(k)}: {v} {unit_pl}" for k, v in sorted(host_author_counts.items()))
    host_photos_section = ""
    if plants_dict:
        if is_ta:
            host_photos_section = f"""<h3>உணவூட்டும் தாவரப் புகைப்படங்கள் ({host_species_count} பட்டாம்பூச்சி பக்கங்களில் {len(plants_dict)} தாவரப் பிரிவுகள்)</h3>
<p>TNBS உறுப்பினர்களின் சரிபார்க்கப்பட்ட iNaturalist பதிவுகளிலிருந்து ({host_author_summary}) உணவூட்டும் தாவரப் படங்கள் இணைக்கப்பட்டுள்ளன.</p>
<details class="taxonomy-disclosure"><summary>அனைத்து {len(plants_dict)} உணவூட்டும் தாவரப் பட ஆதாரங்களையும் காண்க</summary>
<div class="disclosure-body"><ul class="credit-list">{"".join(host_photos_list_parts)}</ul></div></details>"""
        else:
            host_photos_section = f"""<h3>Larval host plant photographs ({len(plants_dict)} plant taxa across {host_species_count} species pages)</h3>
<p>Larval host plant photographs are contributed from verified iNaturalist observations by TNBS members ({host_author_summary}) and appear inside the Caterpillar host plants card on matching butterfly species pages.</p>
<details class="taxonomy-disclosure"><summary>Show all {len(plants_dict)} host plant photo attributions</summary>
<div class="disclosure-body"><ul class="credit-list">{"".join(host_photos_list_parts)}</ul></div></details>"""

    gallery_species = len(GALLERIES)
    gallery_photos_total = sum(len(v) for v in GALLERIES.values())
    gallery_member_slides = sum(1 for v in GALLERIES.values() for s in v if s.get("member"))
    gallery_commons_slides = gallery_photos_total - gallery_member_slides
    proj = INAT.get("project") or {}

    t_papers = SITE_TA.get("researchPapers", []) if is_ta else []
    research_parts = []
    for p_idx, p in enumerate(SITE.get("researchPapers", [])):
        tp = t_papers[p_idx] if (is_ta and p_idx < len(t_papers)) else {}
        research_parts.append(f'<li>{link(tp.get("title") or p["title"], p["url"])} ({h(tp.get("authors") or p["authors"])}, {h(tp.get("venue") or p["venue"])})</li>')
    research_items = "".join(research_parts)

    sources_desc = (
        "தமிழ்நாடு பட்டாம்பூச்சிப் பட்டியல் ஆதாரங்கள், ஆய்வுக் கட்டுரைகள், தமிழ்ப் பெயர் ஆதாரங்கள், iNaturalist திட்டம் #47280 தரவு மற்றும் புகைப்பட நன்றிகள்."
        if is_ta
        else "Tamil Nadu Butterfly Checklist provenance, iNaturalist Project #47280 metrics, Tamil names, and complete photographer attributions."
    )
    body = heading(I18N_TA["nav"]["sources"] if is_ta else "Sources and photo credits", sources_desc)

    if is_ta:
        palmfly_lbl = tamil_name("Elymnias hypermnestra") or "Common Palmfly"
        silver_lbl = tamil_name("Cigaritis meghamalaiensis") or "Cloud Forest Silverline"
        table_cap = "தமிழ்நாடு பட்டாம்பூச்சிப் பட்டியல் குடும்ப எண்ணிக்கை: 2015 v1 மற்றும் 2025 (329 இனங்கள்)"
        body += f"""<section class="wrap section content">
<h2>தமிழ்நாடு பட்டாம்பூச்சிப் பட்டியல்</h2>
<p>இத்தளம் TNBS தொகுத்த <strong>{len(FAMILIES)} குடும்பங்களில் {len(SPECIES)} தமிழ்நாடு பட்டாம்பூச்சி இனங்களை</strong> (<strong>325 உறுதிப்படுத்தப்பட்டவை</strong> மற்றும் தமிழ்நாட்டில் புகைப்பட உறுதிப்படுத்தலுக்குக் காத்திருக்கும் 4 இனங்கள்) வழங்குகிறது.</p>
<p>அங்கீகரிக்கப்பட்ட தமிழ்ப் பெயர்கள் ({len(TAMIL_NAMES)} இனங்கள்) TNBS ஆவணங்கள் மற்றும் தமிழ் விக்கிப்பீடியா / Wikidata வகைப்பாடு தொகுப்புகளிலிருந்து திரட்டப்பட்டுள்ளன. அண்மை மாநிலச் சேர்க்கைகளில் {link(palmfly_lbl, local(lang_prefix, route(BY_SCI["Elymnias hypermnestra"])))} (<i>Elymnias hypermnestra</i>) மற்றும் {link(silver_lbl, local(lang_prefix, route(BY_SCI["Cigaritis meghamalaiensis"])))} (<i>Cigaritis meghamalaiensis</i>, Naicker et al. 2023) ஆகியவை அடங்கும்.</p>

<div class="table-scroll" role="region" tabindex="0" aria-label="{h(table_cap)}">
<table class="data-table"><caption>{h(table_cap)}</caption>
<thead><tr><th scope="col">குடும்பம்</th><th scope="col">2015 v1</th><th scope="col">2025</th></tr></thead>
<tbody>{table_rows}</tbody>
<tfoot><tr><th scope="row">மொத்த இனங்கள்</th><td>323</td><td><strong>329 (325 உறுதிப்படுத்தப்பட்டவை)</strong></td></tr></tfoot></table>
</div>

<h3>தமிழ்நாட்டில் உறுதிப்படுத்தலுக்குக் காத்திருக்கும் 4 இனங்கள்</h3>
<ul>{unvalidated_list}</ul>

<h3>ஆய்வுக் கட்டுரைகள், குடிமை அறிவியல் &amp; பட்டியல் ஆதாரங்கள்</h3>
<ul>{research_items}
<li>{link("iNaturalist-இல் தமிழ்நாட்டின் பட்டாம்பூச்சிகள் (திட்டம் #47280)", INAT_PROJECT_URL)}</li>
<li>{link("அண்மைப் பட்டாம்பூச்சி இதழ் (PDF)", issue_url(27))}</li>
<li>{link("முந்தைய TNBS பட்டியல் காப்பகம்", ORIGINAL + "/butterfly-checklist-of-tamil-nadu")}</li>
<li>{link("Butterfly Vision AI இனப் பதிவேடு", BUTTERFLY_VISION)}</li></ul>

<h2>புகைப்படங்கள் &amp; உரிமங்கள் ({len(PHOTOS)} / {len(SPECIES)} இனங்கள்)</h2>
<p>கள வழிகாட்டிப் படங்கள் TNBS உறுப்பினர்களின் ({member_summary}) பங்களிப்புகளையும், Wikimedia Commons மற்றும் iNaturalist CC திறந்த உரிமப் படங்களையும் இணைக்கின்றன. {gallery_species} இனங்களில் {gallery_photos_total} பல-கோணப் புகைப்படங்கள் ({gallery_member_slides} TNBS உறுப்பினர் படங்கள், {gallery_commons_slides} CC படங்கள்) உள்ளன. {link("iNaturalist திட்டம் #47280", INAT_PROJECT_URL)} ({proj.get('observations', 0):,} பதிவுகள், {proj.get('observersCount', 0):,} பங்களிப்பாளர்கள்) தரவுகளும் இணைக்கப்பட்டுள்ளன.</p>
<details class="taxonomy-disclosure"><summary>அனைத்து {len(PHOTOS)} முதன்மைப் புகைப்பட ஆதாரங்களையும் காண்க</summary>
<div class="disclosure-body"><ul class="credit-list">{photos_list}</ul></div></details>
{host_photos_section}
</section>"""
    else:
        gallery_note_line = (
            f" Multi-photo variation galleries cover <strong>{gallery_species}</strong> species pages with <strong>{gallery_photos_total}</strong> field photographs ({gallery_member_slides} by TNBS members and {gallery_commons_slides} open-licensed Wikimedia Commons &amp; iNaturalist CC variation photos)."
            if gallery_species
            else ""
        )
        inat_line = (
            f" Citizen-science counts, monthly flight curves, and distribution map tiles integrate live data from {link('Butterflies of Tamil Nadu (iNaturalist Project #47280)', INAT_PROJECT_URL)} ({proj.get('observations', 0):,} observations, {proj.get('observersCount', 0):,} observers)."
            if proj
            else ""
        )
        body += f"""<section class="wrap section content">
<h2>Tamil Nadu Butterfly Checklist</h2>
<p>This website presents TNBS's <strong>{len(SPECIES)}-species Tamil Nadu Butterfly Checklist across {len(FAMILIES)} families</strong> (compiled and updated through <em>Pattampoochi</em>, with <strong>325 validated species</strong> and 4 priority species awaiting validated photographic records in Tamil Nadu).</p>
<p>Verified Tamil vernacular butterfly names ({len(TAMIL_NAMES)} species) are compiled from TNBS/Government of Tamil Nadu records and Tamil Wikipedia / Wikidata taxonomic indices. Recent state additions include {link("Common Palmfly", local(lang_prefix, route(BY_SCI["Elymnias hypermnestra"])))} (<i>Elymnias hypermnestra</i>) and {link("Cloud Forest Silverline", local(lang_prefix, route(BY_SCI["Cigaritis meghamalaiensis"])))} (<i>Cigaritis meghamalaiensis</i>, Naicker et al. 2023).</p>

<div class="table-scroll" role="region" tabindex="0" aria-label="Tamil Nadu Butterfly Checklist family counts">
<table class="data-table"><caption>Tamil Nadu Butterfly Checklist family counts: 2015 v1 vs. 2025 (329 species)</caption>
<thead><tr><th scope="col">Family</th><th scope="col">2015 v1</th><th scope="col">2025</th></tr></thead>
<tbody>{table_rows}</tbody>
<tfoot><tr><th scope="row">Total species</th><td>323</td><td><strong>329 (325 validated)</strong></td></tr></tfoot></table>
</div>

<h3>Four checklist species awaiting validated Tamil Nadu confirmation</h3>
<ul>{unvalidated_list}</ul>

<h3>Peer-reviewed research, citizen science &amp; checklist references</h3>
<ul>{research_items}
<li>{link("Butterflies of Tamil Nadu on iNaturalist (Project #47280)", INAT_PROJECT_URL)}</li>
<li>{link("Latest Pattampoochi checklist issue PDF", issue_url(27))}</li>
<li>{link("Original TNBS checklist archive page", ORIGINAL + "/butterfly-checklist-of-tamil-nadu")}</li>
<li>{link("Butterfly Vision AI species registry", BUTTERFLY_VISION)}</li></ul>

<h2>Photographs &amp; open licenses ({len(PHOTOS)} / {len(SPECIES)} species illustrated)</h2>
<p>Field guide photographs combine Creative Commons and TNBS Member Archive field observations contributed by TNBS members ({member_summary}) with verified open-licensed Wikimedia Commons and iNaturalist CC images, paired with photographer credits and license or observation links.{gallery_note_line}{inat_line}</p>
<details class="taxonomy-disclosure"><summary>Show all {len(PHOTOS)} primary species photo attributions</summary>
<div class="disclosure-body"><ul class="credit-list">{photos_list}</ul></div></details>
{host_photos_section}
</section>"""

    render(
        "sources/",
        "ஆதாரங்கள் & நன்றி" if is_ta else "Checklist sources and photo credits",
        sources_desc,
        body,
        lang=lang,
    )


def quiz(lang="en"):
    _, asset_prefix, lang_prefix, _, _, _ = paths_for("quiz/", lang=lang)
    is_ta = lang == "ta"
    quiz_src = f"{asset_prefix}assets/{'quiz-data-ta.json' if is_ta else 'quiz-data.json'}"
    guide_base = local(lang_prefix, "butterflies/").removesuffix("index.html")
    q_ui = TA_UI.get("quizUi", {})

    body = heading(
        TA_UI["quizTitle"] if is_ta else "Interactive Butterfly Quiz",
        TA_UI["quizDesc"] if is_ta else f"Challenge yourself with four interactive modes: Photo ID across {len(PHOTOS)} species, Mixed Field Facts, Timed Rapid Fire, or Scientific Name Match, with streaks, lifelines, personal bests, and shareable score cards.",
    )
    noscript_q = (
        f'<noscript><p>வினாடி வினா விளையாட JavaScript அவசியம். {link(TA_UI["browseAll"], local(lang_prefix, "butterflies/"))}.</p></noscript>'
        if is_ta
        else f'<noscript><p>The interactive quiz requires JavaScript. {link("Browse all 329 species in the field guide", local(lang_prefix, "butterflies/"))}.</p></noscript>'
    )
    kbd_tip = (
        'விசைகள்: <kbd>1</kbd>-<kbd>4</kbd> விடை · <kbd>H</kbd> குறிப்பு · <kbd>Enter</kbd> அடுத்து'
        if is_ta
        else 'Keys: <kbd>1</kbd>-<kbd>4</kbd> answer · <kbd>H</kbd> hint · <kbd>Enter</kbd> next'
    )
    body += f"""<section class="wrap section"><div class="quiz" data-quiz data-quiz-src="{h(quiz_src)}" data-guide-base="{h(guide_base)}">
<div data-quiz-start>
<div class="quiz-lobby-head"><div><p class="kicker">{"சவாலைத் தேர்ந்தெடுக்கவும்" if is_ta else "Choose your challenge"}</p><h2>{"வினாடி வினா தொடங்குங்கள்" if is_ta else "Start a quiz session"}</h2></div>
<div class="quiz-best" data-quiz-best hidden></div></div>

<div class="quiz-mode-grid" role="group" aria-label="{"வினாடி வினா வகை" if is_ta else "Quiz mode"}">
<button type="button" class="mode-card" data-mode="photo" aria-pressed="true"><strong>{h(q_ui.get("photoModeTitle") if is_ta else "Photo ID Challenge")}</strong><span>{h(q_ui.get("photoModeDesc") if is_ta else "Identify real field photographs of butterflies from Tamil Nadu.")}</span></button>
<button type="button" class="mode-card" data-mode="mixed" aria-pressed="false"><strong>{h(q_ui.get("mixedModeTitle") if is_ta else "Mixed Field Quiz")}</strong><span>{h(q_ui.get("mixedModeDesc") if is_ta else "Blend butterfly photos with TNBS migration, host-plant, and ecology questions.")}</span></button>
<button type="button" class="mode-card" data-mode="rapid" aria-pressed="false"><strong>{h(q_ui.get("rapidModeTitle") if is_ta else "Timed Rapid Fire")}</strong><span>{h(q_ui.get("rapidModeDesc") if is_ta else "20 seconds per question: build streaks and earn speed bonus points!")}</span></button>
<button type="button" class="mode-card" data-mode="scientific" aria-pressed="false"><strong>{h(q_ui.get("sciModeTitle") if is_ta else "Scientific Name Match")}</strong><span>{h(q_ui.get("sciModeDesc") if is_ta else "Match Tamil Nadu common names to their binomial scientific names.")}</span></button>
</div>

<div class="quiz-settings">
<div class="field"><label for="quiz-family">{h(TA_UI["guideFamily"] if is_ta else "Focus family")}</label><select id="quiz-family">
<option value="">{"அனைத்து 6 குடும்பங்களும்" if is_ta else "All 6 families"}</option>
<option value="Papilionidae">{h(fam_name("Papilionidae", lang))} ({h(fam_desc("Papilionidae", lang))})</option>
<option value="Pieridae">{h(fam_name("Pieridae", lang))} ({h(fam_desc("Pieridae", lang))})</option>
<option value="Nymphalidae">{h(fam_name("Nymphalidae", lang))} ({h(fam_desc("Nymphalidae", lang))})</option>
<option value="Lycaenidae">{h(fam_name("Lycaenidae", lang))} ({h(fam_desc("Lycaenidae", lang))})</option>
<option value="Hesperiidae">{h(fam_name("Hesperiidae", lang))} ({h(fam_desc("Hesperiidae", lang))})</option>
</select></div>
<div class="field"><label for="quiz-difficulty">{"சிரம நிலை" if is_ta else "Difficulty"}</label><select id="quiz-difficulty">
<option value="standard">{"பொதுவானது" if is_ta else "Standard (Mixed distractors)"}</option>
<option value="expert">{"நிபுணர் நிலை" if is_ta else "Expert (Same-family lookalikes)"}</option>
</select></div>
<div class="field"><label for="quiz-count">{"கேள்விகள்" if is_ta else "Questions"}</label><select id="quiz-count">
<option value="8" selected>8</option>
<option value="12">12</option>
<option value="15">15</option>
</select></div></div>

<div class="actions" data-enhancement hidden><button type="button" class="button" data-start-btn>{h(TA_UI["quizStart"] if is_ta else "Start quiz →")}</button></div>
<p role="status" aria-live="polite" data-start-status class="caption"></p>
{noscript_q}
</div>

<div data-quiz-game hidden>
<div class="quiz-hud">
<span class="hud-chip" data-step>{"கேள்வி 1 / 8" if is_ta else "Question 1 of 8"}</span>
<span class="hud-chip hud-score" data-hud-score>{"மதிப்பெண்: 0" if is_ta else "Score: 0"}</span>
<span class="hud-chip hud-streak" data-hud-streak>{"தொடர்ச்சி: 0 🔥" if is_ta else "Streak: 0 🔥"}</span>
<span class="hud-chip hud-timer" data-hud-timer hidden>20s</span>
</div>
<progress class="quiz-progress" max="100" value="0" aria-label="{"வினாடி வினா முன்னேற்றம்" if is_ta else "Quiz progress"}" style="--quiz-hue: 145;"></progress>

<div class="quiz-lifelines">
<button type="button" class="choice" data-lifeline-5050>50:50</button>
<button type="button" class="choice" data-lifeline-hint>{"குறிப்பு (H)" if is_ta else "Hint (H)"}</button>
<span class="caption keyboard-tip">{kbd_tip}</span>
</div>

<h2 tabindex="-1" data-question></h2>
<p class="quiz-hint-box" data-hint-box hidden></p>
<div data-quiz-photo hidden></div>
<div class="quiz-options" data-options></div>
<div class="quiz-feedback" role="status" aria-live="polite" data-feedback></div>
<div class="actions"><button class="button" type="button" data-next hidden>{"அடுத்த கேள்வி" if is_ta else "Next question"}</button></div>
</div>

<div data-finish hidden>
<div class="rank-card">
<p class="kicker">{"வினாடி வினா முடிந்தது" if is_ta else "Session complete"}</p>
<h2 tabindex="-1" data-score></h2>
<p class="rank-badge" data-rank></p>
<p data-summary></p>
<dl class="mini-stats quiz-end-stats" data-end-stats></dl>
</div>
<div class="quiz-review-tools">
<div class="choices" role="group" aria-label="{"பதில்களை வடிகட்டு" if is_ta else "Filter review answers"}">
<button type="button" class="choice" data-review-filter="all" aria-pressed="true">{"அனைத்து விடைகளும்" if is_ta else "All answers"}</button>
<button type="button" class="choice" data-review-filter="missed" aria-pressed="false">{"தவறியவை மட்டும்" if is_ta else "Missed only"}</button>
</div>
<div class="actions-inline">
<button type="button" class="button outline" data-retry-missed hidden>{"தவறியதை மீண்டும் முயல்க" if is_ta else "Retry missed questions"}</button>
<button type="button" class="button outline" data-share-score>{"மதிப்பெண்ணை நகலெடு" if is_ta else "Copy score summary"}</button>
</div>
</div>
<p role="status" aria-live="polite" data-share-status class="caption"></p>
<ol class="review-list" data-review></ol>
<div class="actions">
<button type="button" class="button" data-restart>{"மீண்டும் விளையாடு" if is_ta else "Play another round"}</button>
<a class="button outline" href="{local(lang_prefix, "butterflies/")}">{h(TA_UI["exploreGuide"] if is_ta else "Browse the field guide")}</a>
<a class="button outline" href="{local(lang_prefix, "identify/")}">{h(TA_UI["identifyAi"] if is_ta else "Try Butterfly Vision AI")}</a>
</div></div></div></section>"""
    render(
        "quiz/",
        TA_UI["quizTitle"] if is_ta else "Interactive Tamil Nadu Butterfly Quiz",
        TA_UI["quizDesc"] if is_ta else "Test your butterfly identification skills across four interactive quiz modes.",
        body,
        image_key="Papilio crino",
        lang=lang,
    )


def build_quiz_data(lang="en"):
    asset_rel = "../../" if lang == "ta" else "../"
    is_ta = lang == "ta"
    photo_bank = []
    for entry in SPECIES:
        sci = entry["scientific"]
        if sci not in PHOTOS:
            continue
        card_meta = photo_meta(sci, asset_rel, thumb=True)
        full_meta = photo_meta(sci, asset_rel, thumb=False)
        prof = PROFILES.get(sci, {})
        t_prof = PROFILES_TA.get(sci, {}) if is_ta else {}
        ta_sp = tamil_name(sci)
        disp_name = f"{ta_sp} ({entry['name']})" if (is_ta and ta_sp) else entry["name"]
        if is_ta:
            clue = (
                t_prof.get("headline")
                or f"{fam_name(entry['family'], 'ta')} ({sub_desc(entry['subfamily'], 'ta')})."
            )
        else:
            clue = prof.get("headline") if (isinstance(prof, dict) and prof.get("headline")) else f"Family {entry['family']} ({entry['subfamily']})."
        photo_bank.append({
            "id": entry["id"],
            "name": disp_name,
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
        {
            "name": f"{tamil_name(s['scientific'])} ({s['name']})" if (is_ta and tamil_name(s["scientific"])) else s["name"],
            "scientific": s["scientific"],
            "family": s["family"],
            "subfamily": s["subfamily"],
            "slug": slug(s["scientific"]),
        }
        for s in SPECIES
    ]
    en_facts = [
        ["Which butterfly is Tamil Nadu's official State Butterfly (தமிழ் மறவன்)?", ["Tamil Yeoman", "Common Banded Peacock", "Southern Birdwing", "Red Pierrot"], "Tamil Nadu adopted the Tamil Yeoman (Cirrochroa thais) in 2019.", "cirrochroa-thais", "Nymphalidae", "Look for orange wings crossed by dark markings and a silvery-pale underside band."],
        ["Which butterfly species appears at the heart of The Nature and Butterfly Society (TNBS) emblem?", ["Common Banded Peacock", "Blue Mormon", "Tamil Yeoman", "Lime Butterfly"], "Papilio crino, the Common Banded Peacock, features emerald-green wings with a turquoise median band and serves as TNBS's emblem.", "papilio-crino", "Papilionidae", "An emerald-green swallowtail whose caterpillars feed on East Indian Satinwood."],
        ["How many butterfly species are documented in Tamil Nadu's state butterfly checklist?", ["329 species", "285 species", "312 species", "410 species"], "TNBS records 329 species across 6 families (325 validated in Tamil Nadu, with 4 awaiting confirmation).", "", "All", "The count increased from 323 in 2015 and 328 in 2022 to 329 in 2025."],
        ["Which two recent species additions expanded the Tamil Nadu checklist to 329 species?", ["Common Palmfly & Cloud Forest Silverline", "Blue Mormon & Painted Lady", "Crimson Rose & Yamfly", "Peacock Pansy & Rice Swift"], "Elymnias hypermnestra and Cigaritis meghamalaiensis (described from Meghamalai in 2023) brought the state list to 329.", "cigaritis-meghamalaiensis", "Lycaenidae", "One feeds on palms around Chennai and Sirumalai; the other is a newly described Theni hill silverline."],
        ["Which butterfly has a white underside with black markings and a bold orange hindwing border?", ["Red Pierrot", "Common Pierrot", "Banded Blue Pierrot", "Common Grass Yellow"], "The Red Pierrot (Talicada nyseus) breeds inside succulent Kalanchoe leaves.", "talicada-nyseus", "Lycaenidae", "Often seen fluttering gently near courtyard Kalanchoe plants."],
        ["Which large swallowtail is Tamil Nadu's largest butterfly, endemic to peninsular India?", ["Southern Birdwing", "Blue Mormon", "Clipper", "Malabar Banded Peacock"], "Troides minos reaches up to 190 mm wingspan with golden-yellow hindwings.", "troides-minos", "Papilionidae", "Also known as the Sahyadri Birdwing."],
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
    facts = TA_UI.get("quizFacts", en_facts) if is_ta else en_facts
    filename = "quiz-data-ta.json" if is_ta else "quiz-data.json"
    (OUT / "assets" / filename).write_text(json.dumps({"photos": photo_bank, "species": species_bank, "facts": facts}, ensure_ascii=False), encoding="utf-8")


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


def build_language(lang):
    home(lang=lang)
    guide(lang=lang)
    sightings(lang=lang)
    for entry in SPECIES:
        detail(entry, lang=lang)
    identify(lang=lang)
    magazine(lang=lang)
    news(lang=lang)
    activities(lang=lang)
    about(lang=lang)
    sources(lang=lang)
    quiz(lang=lang)
    render(
        "404.html",
        "பக்கம் கிடைக்கவில்லை" if lang == "ta" else "Page not found",
        "TNBS தமிழ்நாடு பட்டாம்பூச்சி முகப்பு அல்லது கள வழிகாட்டிக்குச் செல்லவும்." if lang == "ta" else "Find the TNBS home page, butterfly field guide, or Butterfly Vision AI tool.",
        heading(
            "பக்கம் கிடைக்கவில்லை" if lang == "ta" else "Page not found",
            "மேலே உள்ள பட்டியல் வழியாக முகப்பு அல்லது கள வழிகாட்டிக்குத் திரும்பவும்." if lang == "ta" else "Use the navigation menu to return to the TNBS home page or 329-species field guide.",
        ),
        lang=lang,
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
    build_language("en")
    build_language("ta")
    write_redirect("butterflies/cigaritis-meghamaleinsis", "../cigaritis-meghamalaiensis/index.html", "Cloud Forest Silverline (Cigaritis meghamalaiensis)")
    (OUT / ".nojekyll").touch()
    build_quiz_data("en")
    build_quiz_data("ta")
    (OUT / "assets" / "quiz-photos.json").write_text(json.dumps({s: photo_meta(s, "../") for s in PHOTOS}, ensure_ascii=False), encoding="utf-8")

    sitemap = OUT / "sitemap.xml"
    if BASE:
        urls = "".join(f"<url><loc>{h(BASE + path)}</loc></url>\n" for path in PAGES)
        sitemap.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n", encoding="utf-8")
    elif sitemap.exists():
        sitemap.unlink()
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\n" + (f"Sitemap: {BASE}sitemap.xml\n" if BASE else ""), encoding="utf-8")
    print(f"Built {len(PAGES)} public pages (EN + TA), 1 redirect, and EN/TA 404.html in {OUT}")


if __name__ == "__main__":
    main()
