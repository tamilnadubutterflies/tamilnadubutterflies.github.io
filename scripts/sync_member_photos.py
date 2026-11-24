"""Sync authorized TNBS members' butterfly photos (Commons + iNaturalist) into data/photos.json."""
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SPECIES_PATH = ROOT / "data" / "species.json"
PHOTOS_PATH = ROOT / "data" / "photos.json"
CRINO_LOCAL = ROOT / "assets" / "photos" / "papilio-crino.jpg"

sys.path.insert(0, str(ROOT / "scripts"))
from sync_photos import COMMONS_ALIASES  # noqa: E402

UA = {"User-Agent": "TNBSWebsite/1.0 (https://tamilnadubutterflies.github.io/; tamilnadubutterflies@gmail.com)"}

LICENSE_MAP = {
    "cc-by": "by/4.0",
    "cc-by-sa": "by-sa/4.0",
    "cc-by-nc": "by-nc/4.0",
    "cc-by-nc-sa": "by-nc-sa/4.0",
    "cc0": "cc0/1.0",
}

MEMBERS = [
    ("nishanth2", "Nishanth CV (TNBS)"),
    ("pavendhan", "Pavendhan Appavu (TNBS)"),
    ("ramanasaranhari", "Ramanasaran Hari (TNBS)"),
    ("sadheeskumar_k_tnbs", "Sadheeskumar K (TNBS)"),
    ("theivaprakashamhari", "Theivaprakasham Hari (TNBS)"),
]


def http_json(url):
    req = Request(url, headers=UA)
    for attempt in range(4):
        try:
            with urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            if attempt == 3:
                raise RuntimeError(f"Failed fetching {url}: {exc}") from exc
            time.sleep(1.5 * (attempt + 1))
    return {}


def build_name_lookup(species_list):
    lookup = {}
    for entry in species_list:
        sci = entry["scientific"]
        names = [sci]
        parts = sci.split()
        if len(parts) > 2:
            names.append(" ".join(parts[:2]))
        for syn in COMMONS_ALIASES.get(sci, []):
            names.append(syn)
        for alias in entry.get("aliases", []):
            if " " in alias and alias[0].isupper() and alias.split()[1].islower():
                names.append(alias)
        for cand in names:
            lookup.setdefault(cand.lower(), sci)
    return lookup


def match_species(obs, lookup):
    taxon = obs.get("taxon") or {}
    tname = (taxon.get("name") or "").strip()
    if not tname:
        return None
    low = tname.lower()
    if low in lookup:
        return lookup[low]
    parts = tname.split()
    if len(parts) > 2:
        binom = " ".join(parts[:2]).lower()
        if binom in lookup:
            return lookup[binom]
    return None


def score_inat_photo(photo, allow_member_archive=True):
    raw_lic = (photo.get("license_code") or "").lower()
    if raw_lic:
        lic = LICENSE_MAP.get(raw_lic)
        if not lic:
            return -1, None
    elif allow_member_archive:
        lic = ""
    else:
        return -1, None
    url = photo.get("url") or ""
    if "/square." not in url:
        return -1, None
    dims = photo.get("original_dimensions") or {}
    w = int(dims.get("width") or 0)
    h = int(dims.get("height") or 0)
    if w and w < 500:
        return -1, None
    score = 100
    if w >= 1200:
        score += 20
    elif w >= 800:
        score += 10
    if w and h:
        ratio = w / h
        if 0.8 <= ratio <= 1.75:
            score += 15
        if w > h:
            score += 5
    if lic in {"by/4.0", "by-sa/4.0", "cc0/1.0"}:
        score += 3
    elif lic:
        score += 1
    return score, lic


def fetch_member_inat(login, author_label, lookup):
    matched = {}
    page = 1
    while page <= 8:
        params = {
            "user_login": login,
            "taxon_id": 47224,
            "quality_grade": "research",
            "per_page": 200,
            "page": page,
        }
        data = http_json("https://api.inaturalist.org/v1/observations?" + urlencode(params))
        results = data.get("results") or []
        if not results:
            break
        for obs in results:
            sci = match_species(obs, lookup)
            if not sci:
                continue
            obs_id = obs.get("id")
            if not obs_id:
                continue
            for p_idx, ph in enumerate(obs.get("photos") or []):
                sc, lic = score_inat_photo(ph, allow_member_archive=True)
                if sc < 0:
                    continue
                if p_idx == 0:
                    sc += 5
                prev = matched.get(sci)
                if not prev or sc > prev[0]:
                    base_url = ph["url"]
                    thumb = base_url.replace("/square.", "/medium.")
                    full = base_url.replace("/square.", "/large.")
                    dims = ph.get("original_dimensions") or {}
                    matched[sci] = (
                        sc,
                        {
                            "source": "inaturalist",
                            "thumb": thumb,
                            "full": full,
                            "author": author_label,
                            "license": lic,
                            "url": f"https://www.inaturalist.org/observations/{obs_id}",
                            "w": int(dims.get("width") or 0),
                            "h": int(dims.get("height") or 0),
                        },
                    )
        if len(results) < 200:
            break
        page += 1
        time.sleep(0.4)
    return {k: v[1] for k, v in matched.items()}


def fetch_commons_file(filename, author_label):
    cm = http_json(
        "https://commons.wikimedia.org/w/api.php?"
        + urlencode(
            {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "titles": "File:" + filename,
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiextmetadatafilter": "LicenseShortName|LicenseUrl",
            }
        )
    )
    pages = (cm.get("query") or {}).get("pages") or []
    ii = ((pages[0] if pages else {}).get("imageinfo") or [None])[0]
    if not ii:
        raise RuntimeError(f"Could not verify Commons file: {filename}")
    w = int(ii.get("width") or 0)
    lic_url = ((ii.get("extmetadata") or {}).get("LicenseUrl") or {}).get("value", "")
    lic = "by-sa/4.0" if "by-sa/4.0" in lic_url else ("by/4.0" if "by/4.0" in lic_url else "by-sa/4.0")
    return {
        "source": "commons",
        "file": filename,
        "width": 960 if w >= 960 else (500 if w >= 500 else 0),
        "author": author_label,
        "license": lic,
        "member": True,
    }


def main():
    species_list = json.loads(SPECIES_PATH.read_text(encoding="utf-8-sig"))
    by_sci = {s["scientific"]: s for s in species_list}
    lookup = build_name_lookup(species_list)
    photos = json.loads(PHOTOS_PATH.read_text(encoding="utf-8-sig"))

    # Preserve Papilio crino and any local photo files unless explicitly updated
    reserved = {"Papilio crino"} | {
        k for k, v in photos.items() if isinstance(v, dict) and v.get("source") == "local"
    }

    member_assigned = {}

    # 1. Nishanth CV (Wikimedia Commons verified upload)
    if "Mycalesis anaxias" in by_sci:
        nish = fetch_commons_file("White-bar bushbrown.jpg", "Nishanth CV (TNBS)")
        nish["alt"] = f"{by_sci['Mycalesis anaxias']['name']} ({'Mycalesis anaxias'}) photographed in the field by Nishanth CV"
        member_assigned["Mycalesis anaxias"] = nish

    # Priority order: Nishanth CV -> Pavendhan Appavu -> Ramanasaran Hari -> Sadheeskumar K -> Theivaprakasham Hari
    member_results = {}
    for login, label in MEMBERS:
        res = fetch_member_inat(login, label, lookup)
        member_results[login] = res
        print(f"Fetched {len(res)} species from iNaturalist user {login} ({label})")

    crino_cand = member_results.get("theivaprakashamhari", {}).get("Papilio crino")
    if crino_cand:
        print(f"Note: Theivaprakasham Hari has Papilio crino candidate: w={crino_cand.get('w')} h={crino_cand.get('h')} url={crino_cand['url']}")

    for login, label in MEMBERS:
        added = 0
        for sci, rec in member_results[login].items():
            if sci in reserved or sci in member_assigned:
                continue
            sp = by_sci[sci]
            clean = {
                "source": "inaturalist",
                "thumb": rec["thumb"],
                "full": rec["full"],
                "author": label,
                "license": rec["license"],
                "url": rec["url"],
                "alt": f"{sp['name']} ({sci}) photographed in the field by {label.replace(' (TNBS)', '')}",
                "member": True,
            }
            if not rec["license"]:
                clean["licenseName"] = "TNBS Member Archive"
            member_assigned[sci] = clean
            added += 1
        print(f"Assigned {added} species to {label}")

    # Also check Theivaprakasham Hari Commons uploads for Potanthus pallidus or extra species not covered above
    for sci, rec in member_assigned.items():
        photos[sci] = rec

    order = {s["scientific"]: s["id"] for s in species_list}
    ordered = {k: photos[k] for k in sorted(photos, key=lambda s: order.get(s, 9999)) if k in order}
    PHOTOS_PATH.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Summary by member
    counts = {}
    for sci, val in ordered.items():
        if isinstance(val, dict) and val.get("member"):
            counts[val["author"]] = counts.get(val["author"], 0) + 1
    print(f"Total photos in data/photos.json: {len(ordered)} / {len(species_list)}")
    print("Member photo summary:", counts)


if __name__ == "__main__":
    main()
