"""Populate data/photos.json with verified open-licensed Wikimedia Commons photos."""
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SPECIES_PATH = ROOT / "data" / "species.json"
PHOTOS_PATH = ROOT / "data" / "photos.json"
USER_AGENT = "TNBSWebsite/1.0 (https://sites.google.com/view/tamilnadubutterflies; tamilnadubutterflies@gmail.com)"

# Taxonomic synonyms often used on Wikimedia Commons / Wikipedia titles
COMMONS_ALIASES = {
    "Telinga adolphei": ["Mycalesis adolphei"],
    "Telinga oculus": ["Mycalesis oculus"],
    "Telinga davisoni": ["Heteropsis davisoni", "Mycalesis davisoni"],
    "Cigaritis lohita": ["Spindasis lohita"],
    "Cigaritis vulcanus": ["Spindasis vulcanus"],
    "Cigaritis schistacea": ["Spindasis schistacea"],
    "Cigaritis ictis": ["Spindasis ictis"],
    "Cigaritis abnormis": ["Spindasis abnormis"],
    "Cigaritis elima": ["Spindasis elima"],
    "Cigaritis meghamalaiensis": ["Spindasis meghamalaiensis"],
    "Charaxes bharata": ["Polyura bharata", "Polyura athamas"],
    "Charaxes agrarius": ["Polyura agraria", "Charaxes agraria"],
    "Charaxes schreiber": ["Polyura schreiber"],
    "Papilio daksha": ["Papilio helenus"],
    "Graphium teredon": ["Graphium sarpedon"],
    "Halpemorpha hyrtacus": ["Halpe hyrtacus"],
    "Pseudozizeeria maha": ["Zizeeria maha"],
    "Everes lacturnus": ["Cupido lacturnus"],
    "Chilades pandava": ["Luthrodes pandava"],
    "Chilades parrhassius": ["Chilades parrhasius"],
    "Freyeria putli": ["Chilades putli", "Freyeria trochylus"],
    "Freyeria trochylus": ["Chilades trochylus"],
    "Kaniska canace": ["Nymphalis canace"],
    "Tanaecia lepidea": ["Cynitia lepidea"],
    "Symphaedra nais": ["Euthalia nais"],
    "Orsotrioena medus": ["Orsotriaena medus"],
    "Libythea laius": ["Libythea lepita"],
    "Neptis nata hampsoni": ["Neptis nata"],
    "Neptis palnica": ["Neptis soma"],
    "Argynnis hybrida": ["Argynnis hyperbius"],
    "Argynnis castetsi": ["Argynnis hyperbius"],
    "Celaenorrhinus fusca": ["Celaenorrhinus ruficornis"],
    "Hyarotis coorga": ["Hyarotis microstictum"],
    "Arhopala alea": ["Arhopala canaraica"],
    "Appias wardii": ["Appias wardi"],
    "Baracus subditus": ["Baracus vittatus"],
    "Cethosia mahratta": ["Cethosia nietneri mahratta"],
    "Borbo bevani": ["Pseudoborbo bevani"],
}

BAD_TITLE_RE = re.compile(
    r"(?:^|[^a-z])(map|range|distribution|diagram|logo|icon|coat|stamp|drawing|illustration|seitz|moore|bingham|lepidoptera_indica|plate|taxonomy|cladogram|icones)(?:[^a-z]|$)",
    re.I,
)
SPECIMEN_RE = re.compile(
    r"(?:mhnt|museum|specimen|drawer|mounted|set_specimen|pinned|holotype|paratype|lectotype|collector|zsm|rmnh|nbm|nhm)",
    re.I,
)
ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}


class _TextStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def strip_html(raw):
    if not raw:
        return ""
    parser = _TextStripper()
    parser.feed(str(raw))
    text = " ".join(parser.parts)
    return re.sub(r"\s+", " ", text).strip()


def normalize_license(short_name, license_url):
    url = (license_url or "").strip().replace("http://", "https://")
    low_short = (short_name or "").strip().lower()
    if not url:
        if low_short == "cc0" or "cc0" in low_short:
            return "cc0/1.0"
        if "public domain" in low_short or low_short == "pd":
            return "pdm/1.0"
        return ""
    m = re.match(r"^https://creativecommons\.org/licenses/((?:by|by-sa)/[0-9]+\.[0-9]+)(?:/[a-z-]+)?/?$", url)
    if m:
        return m.group(1)
    if re.match(r"^https://creativecommons\.org/publicdomain/zero/1\.0(?:/[a-z-]+)?/?$", url):
        return "cc0/1.0"
    if re.match(r"^https://creativecommons\.org/publicdomain/mark/1\.0(?:/[a-z-]+)?/?$", url):
        return "pdm/1.0"
    if "cc0" in low_short:
        return "cc0/1.0"
    return ""


def api_get(host, params):
    url = f"https://{host}/w/api.php?" + urlencode({"format": "json", "formatversion": "2", **params})
    req = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            if attempt == 2:
                return {}
            time.sleep(1.0 + attempt)
    return {}


def candidate_names(entry):
    sci = entry["scientific"]
    names = [sci]
    parts = sci.split()
    if len(parts) > 2:
        names.append(" ".join(parts[:2]))
    for alias in entry.get("aliases", []):
        if re.fullmatch(r"[A-Z][a-z]+ [a-z]+(?: [a-z]+)?", alias):
            names.append(alias)
    for syn in COMMONS_ALIASES.get(sci, []):
        names.append(syn)
    seen = set()
    return [n for n in names if not (n in seen or seen.add(n))]


def extract_author(metadata, filename):
    artist = strip_html((metadata.get("Artist") or {}).get("value", ""))
    if not artist or artist.lower() in {"unknown", "anonymous"}:
        return ""
    if len(artist) > 90:
        artist = artist[:87].rsplit(" ", 1)[0] + "…"
    return artist


def score_file(title, ii, common_name):
    filename = title.removeprefix("File:")
    mime = ii.get("mime", "")
    w = int(ii.get("width") or 0)
    h = int(ii.get("height") or 0)
    if mime not in ALLOWED_MIMES or w < 320 or h < 240:
        return -1, None
    if BAD_TITLE_RE.search(filename):
        return -1, None
    md = ii.get("extmetadata") or {}
    lic = normalize_license(
        (md.get("LicenseShortName") or {}).get("value", ""),
        (md.get("LicenseUrl") or {}).get("value", ""),
    )
    if not lic:
        return -1, None
    author = extract_author(md, filename)
    if not author:
        return -1, None
    is_specimen = bool(SPECIMEN_RE.search(filename))
    score = 100
    if is_specimen:
        score -= 70
    if w >= 960 and h >= 640:
        score += 20
    elif w >= 500:
        score += 10
    if w >= h:
        score += 5
    if any(k in filename.lower() for k in ("india", "kerala", "tamil", "karnataka", "bengal", "wlb", "open", "close")):
        score += 10
    if lic.startswith("by"):
        score += 3
    chosen_width = 960 if w >= 960 else (500 if w >= 500 else 0)
    alt = (
        f"Museum specimen of {common_name} ({filename.rsplit('.', 1)[0]})"
        if is_specimen
        else f"{common_name} photographed in the field"
    )
    return score, [filename, author, lic, alt, chosen_width]


def batch_wikipedia_pass(species_list, photos):
    title_to_species = {}
    all_titles = []
    for entry in species_list:
        if entry["scientific"] in photos:
            continue
        for cand in candidate_names(entry):
            if cand not in title_to_species:
                title_to_species[cand] = entry
                all_titles.append(cand)

    wiki_candidates = {}  # scientific -> filename
    for i in range(0, len(all_titles), 45):
        chunk = all_titles[i : i + 45]
        data = api_get(
            "en.wikipedia.org",
            {
                "action": "query",
                "titles": "|".join(chunk),
                "redirects": 1,
                "prop": "pageprops|pageimages",
                "ppprop": "wikibase_item",
                "piprop": "name",
                "pilicense": "free",
            },
        )
        q = data.get("query") or {}
        norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
        redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
        pages_by_title = {p.get("title"): p for p in q.get("pages", []) if not p.get("missing")}
        qid_map = {}
        for orig_title in chunk:
            t = norm.get(orig_title, orig_title)
            t = redir.get(t, t)
            page = pages_by_title.get(t)
            if page and page.get("pageimage") and (page.get("pageprops") or {}).get("wikibase_item"):
                qid_map.setdefault(page["pageprops"]["wikibase_item"], []).append((orig_title, page["pageimage"]))

        if qid_map:
            wd = api_get(
                "www.wikidata.org",
                {
                    "action": "wbgetentities",
                    "ids": "|".join(list(qid_map.keys())[:45]),
                    "props": "claims",
                },
            )
            entities = wd.get("entities") or {}
            for qid, pairs in qid_map.items():
                claims = (entities.get(qid) or {}).get("claims") or {}
                p225_vals = {
                    c.get("mainsnak", {}).get("datavalue", {}).get("value")
                    for c in claims.get("P225", [])
                }
                for orig_title, fname in pairs:
                    entry = title_to_species[orig_title]
                    sci = entry["scientific"]
                    if sci in wiki_candidates:
                        continue
                    allowed = set(candidate_names(entry))
                    if p225_vals & allowed:
                        wiki_candidates[sci] = fname
        time.sleep(0.25)

    if not wiki_candidates:
        return

    entry_by_sci = {s["scientific"]: s for s in species_list}
    items = list(wiki_candidates.items())
    for i in range(0, len(items), 45):
        batch = items[i : i + 45]
        file_titles = ["File:" + fn for _, fn in batch]
        cm = api_get(
            "commons.wikimedia.org",
            {
                "action": "query",
                "titles": "|".join(file_titles),
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl",
            },
        )
        q = cm.get("query") or {}
        norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
        pages = {p.get("title"): p for p in q.get("pages", [])}
        for sci, fname in batch:
            ft = norm.get("File:" + fname, "File:" + fname)
            page = pages.get(ft)
            ii = ((page or {}).get("imageinfo") or [None])[0]
            if not ii:
                continue
            sc, record = score_file(ft, ii, entry_by_sci[sci]["name"])
            if sc >= 30 and record:  # only keep Wikipedia photo immediately if non-specimen; otherwise Commons category pass may find live photo!
                photos[sci] = record
        time.sleep(0.25)


def commons_category_search_pass(species_list, photos):
    for entry in species_list:
        sci = entry["scientific"]
        if sci in photos:
            continue
        best_score = -1
        best_record = None
        for cand in candidate_names(entry):
            cat_title = "Category:" + cand.replace(" ", "_")
            res = api_get(
                "commons.wikimedia.org",
                {
                    "action": "query",
                    "generator": "categorymembers",
                    "gcmtitle": cat_title,
                    "gcmtype": "file",
                    "gcmlimit": 18,
                    "prop": "imageinfo",
                    "iiprop": "url|size|mime|extmetadata",
                    "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl",
                },
            )
            pages = (res.get("query") or {}).get("pages") or []
            for p in pages:
                ii = (p.get("imageinfo") or [None])[0]
                if not ii:
                    continue
                sc, rec = score_file(p.get("title", ""), ii, entry["name"])
                if sc > best_score:
                    best_score, best_record = sc, rec
            time.sleep(0.2)
            if best_score >= 95:
                break

        if best_score < 40:
            # Fallback to intitle exact binomial search on Commons
            binomial = " ".join(sci.split()[:2])
            res = api_get(
                "commons.wikimedia.org",
                {
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": f'intitle:"{binomial}"',
                    "gsrnamespace": 6,
                    "gsrlimit": 12,
                    "prop": "imageinfo",
                    "iiprop": "url|size|mime|extmetadata",
                    "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl",
                },
            )
            pages = (res.get("query") or {}).get("pages") or []
            tokens = [t.lower() for t in binomial.split()]
            for p in pages:
                title = p.get("title", "")
                low_title = title.lower()
                if not all(t in low_title for t in tokens):
                    continue
                ii = (p.get("imageinfo") or [None])[0]
                if not ii:
                    continue
                sc, rec = score_file(title, ii, entry["name"])
                if sc > best_score:
                    best_score, best_record = sc, rec
            time.sleep(0.2)

        if best_record:
            photos[sci] = best_record


def main():
    species_list = json.loads(SPECIES_PATH.read_text(encoding="utf-8-sig"))
    existing = json.loads(PHOTOS_PATH.read_text(encoding="utf-8-sig"))
    # Preserve curated entries and ensure Papilio crino hero entry is exact
    photos = dict(existing)
    photos["Papilio crino"] = [
        "Open wing basking position of Papilio crino (Fabricius, 1793) - Common Banded Peacock (2) WLB.jpg",
        "Anitava Roy",
        "by-sa/4.0",
        "Common Banded Peacock basking with open emerald-green and turquoise-banded wings on a leaf",
        1280,
    ]

    before = len(photos)
    print(f"Starting with {before} curated photo entries...")
    batch_wikipedia_pass(species_list, photos)
    print(f"After Pass 1 (Wikipedia + Wikidata P225): {len(photos)} entries")
    commons_category_search_pass(species_list, photos)
    print(f"After Pass 2 (Commons Category + Intitle Search): {len(photos)}/{len(species_list)} entries")

    # Sort deterministically by checklist order
    order = {s["scientific"]: s["id"] for s in species_list}
    ordered = {k: photos[k] for k in sorted(photos, key=lambda s: order.get(s, 9999)) if k in order}
    PHOTOS_PATH.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    missing = [s["scientific"] for s in species_list if s["scientific"] not in ordered]
    print(f"Saved {len(ordered)} verified photos. Missing ({len(missing)}): {missing}")


if __name__ == "__main__":
    main()
