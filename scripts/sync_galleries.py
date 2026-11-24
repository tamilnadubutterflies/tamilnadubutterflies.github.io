"""Build multi-photo variation galleries (TNBS members + Wikimedia Commons) into data/galleries.json."""
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
SPECIES_PATH = ROOT / "data" / "species.json"
PHOTOS_PATH = ROOT / "data" / "photos.json"
GALLERIES_PATH = ROOT / "data" / "galleries.json"

sys.path.insert(0, str(ROOT / "scripts"))
from sync_member_photos import (  # noqa: E402
    MEMBERS,
    build_name_lookup,
    http_json,
    match_species,
    score_inat_photo,
)
from sync_photos import (  # noqa: E402
    ALLOWED_MIMES,
    BAD_TITLE_RE,
    SPECIMEN_RE,
    api_get,
    candidate_names,
    extract_author,
    normalize_license,
)

MAX_MEMBER_TOTAL = 6
TARGET_WITH_COMMONS = 4

SKIP_PLACE_PARTS = {"tamil nadu", "tamilnadu", "india", "tn", "in"}


def inat_photo_id(url):
    m = re.search(r"/photos/(\d+)/", url or "")
    return m.group(1) if m else ""


def clean_place(place_guess):
    if not place_guess:
        return ""
    for raw_part in str(place_guess).split(","):
        part = re.sub(r"\b\d{5,6}\b", "", raw_part).strip(" -.")
        low = part.lower()
        if not part or low in SKIP_PLACE_PARTS or re.fullmatch(r"[A-Z]{2,3}", part):
            continue
        if len(part) <= 26:
            return part
        trimmed = part[:25].rsplit(" ", 1)[0].strip()
        return trimmed or part[:25]
    return ""


def parse_obs_metadata(obs):
    sex_or_stage = ""
    is_immature = False
    for ann in obs.get("annotations") or []:
        attr_id = ann.get("controlled_attribute_id")
        val_id = ann.get("controlled_value_id")
        if attr_id == 9:
            if val_id == 10:
                sex_or_stage = "Female"
            elif val_id == 11:
                sex_or_stage = "Male"
        elif attr_id == 1:
            if val_id == 6:
                sex_or_stage = "Caterpillar"
                is_immature = True
            elif val_id == 4:
                sex_or_stage = "Pupa"
                is_immature = True
            elif val_id == 7:
                sex_or_stage = "Egg"
                is_immature = True

    month_year = ""
    raw_date = obs.get("observed_on") or (obs.get("time_observed_at") or "")[:10]
    if raw_date and len(raw_date) >= 10:
        try:
            month_year = datetime.strptime(raw_date[:10], "%Y-%m-%d").strftime("%b %Y")
        except ValueError:
            month_year = ""

    place = clean_place(obs.get("place_guess"))
    tokens = [tok for tok in (sex_or_stage, place, month_year) if tok]
    return {
        "note": " · ".join(tokens),
        "tag": sex_or_stage or month_year,
        "month": month_year,
        "is_immature": is_immature,
    }


def normalize_primary_slide(rec):
    if isinstance(rec, dict):
        src = rec.get("source")
        if src == "local":
            return {
                "source": "local",
                "file": rec["file"],
                "author": rec["author"],
                "license": "",
                "licenseName": rec.get("licenseName", "TNBS Member Archive"),
                "url": rec.get("url", ""),
                "alt": rec["alt"],
                "note": "Primary field guide photo",
                "member": True,
            }
        if src == "inaturalist":
            lic = rec.get("license") or ""
            return {
                "source": "inaturalist",
                "thumb": rec["thumb"],
                "full": rec["full"],
                "author": rec["author"],
                "license": lic,
                "licenseName": "" if lic else rec.get("licenseName", "TNBS Member Archive"),
                "url": rec["url"],
                "alt": rec["alt"],
                "note": "Primary field guide photo",
                "member": bool(rec.get("member", True)),
            }
        return {
            "source": "commons",
            "file": rec["file"],
            "width": int(rec.get("width") or 0),
            "author": rec["author"],
            "license": rec.get("license", ""),
            "licenseName": "",
            "alt": rec["alt"],
            "note": "Primary field guide photo",
            "member": bool(rec.get("member")),
        }
    filename, author, lic, alt, width = rec
    return {
        "source": "commons",
        "file": filename,
        "width": int(width or 0),
        "author": author,
        "license": lic,
        "licenseName": "",
        "alt": alt,
        "note": "Primary field guide photo",
        "member": False,
    }


def fetch_all_member_candidates(lookup, by_sci):
    by_species = {}
    obs_notes = {}
    for member_idx, (login, author_label) in enumerate(MEMBERS):
        author_short = author_label.replace(" (TNBS)", "")
        count = 0
        page = 1
        while page <= 8:
            params = {
                "user_login": login,
                "taxon_id": 47224,
                "per_page": 200,
                "page": page,
            }
            data = http_json("https://api.inaturalist.org/v1/observations?" + urlencode(params))
            results = data.get("results") or []
            if not results:
                break
            for obs in results:
                quality = (obs.get("quality_grade") or "").lower()
                if quality not in {"research", "needs_id"}:
                    continue
                sci = match_species(obs, lookup)
                if not sci or sci not in by_sci:
                    continue
                obs_id = obs.get("id")
                if not obs_id:
                    continue
                obs_url = f"https://www.inaturalist.org/observations/{obs_id}"
                meta = parse_obs_metadata(obs)
                if meta["note"]:
                    obs_notes[obs_url] = meta["note"]
                sp = by_sci[sci]
                for p_idx, ph in enumerate(obs.get("photos") or []):
                    sc, lic = score_inat_photo(ph, allow_member_archive=True)
                    if sc < 0:
                        continue
                    base_url = ph["url"]
                    thumb = base_url.replace("/square.", "/medium.")
                    full = base_url.replace("/square.", "/large.")
                    note = meta["note"]
                    if p_idx > 0:
                        note = f"Angle {p_idx + 1}" + (f" · {note}" if note else "")
                    slide = {
                        "source": "inaturalist",
                        "thumb": thumb,
                        "full": full,
                        "author": author_label,
                        "license": lic,
                        "licenseName": "" if lic else "TNBS Member Archive",
                        "url": obs_url,
                        "alt": f"{sp['name']} ({sci}) field photograph by {author_short}"
                        + (f" ({note})" if note else ""),
                        "note": note or "Field observation photo",
                        "member": True,
                    }
                    by_species.setdefault(sci, []).append(
                        {
                            "obs_id": obs_id,
                            "p_idx": p_idx,
                            "quality": quality,
                            "score": sc + (5 if p_idx == 0 else 0),
                            "author": author_label,
                            "member_idx": member_idx,
                            "tag": meta["tag"],
                            "month": meta["month"],
                            "is_immature": meta["is_immature"],
                            "photo_id": inat_photo_id(base_url),
                            "slide": slide,
                        }
                    )
                    count += 1
            if len(results) < 200:
                break
            page += 1
            time.sleep(0.35)
        print(f"Fetched {count} member photo candidates from {login} ({author_label})")
    return by_species, obs_notes


def pick_diverse_member_slides(sci, existing_slides, candidates):
    seen_photo_ids = {
        inat_photo_id(s.get("thumb") or s.get("full"))
        for s in existing_slides
        if s.get("source") == "inaturalist"
    } - {""}
    seen_urls = {
        s.get("thumb") or s.get("full") or s.get("file")
        for s in existing_slides
    } - {""}
    seen_authors = {s["author"] for s in existing_slides}
    seen_tags = set()

    # Best photo per observation (Pass A: distinct sightings/photographers/dates)
    best_per_obs = {}
    secondary_pool = []
    for cand in candidates:
        pid = cand["photo_id"]
        t_url = cand["slide"]["thumb"]
        if (pid and pid in seen_photo_ids) or t_url in seen_urls:
            continue
        oid = cand["obs_id"]
        prev = best_per_obs.get(oid)
        if not prev or (
            cand["quality"] == "research" and prev["quality"] != "research",
            cand["score"],
        ) > (
            prev["quality"] == "research" and cand["quality"] != "research",
            prev["score"],
        ):
            if prev:
                secondary_pool.append(prev)
            best_per_obs[oid] = cand
        else:
            secondary_pool.append(cand)

    added = []
    # Greedily select Pass A candidates maximizing photographer, stage, and seasonal diversity
    remaining_obs = list(best_per_obs.values())
    while remaining_obs and len(existing_slides) + len(added) < MAX_MEMBER_TOTAL:
        remaining_obs.sort(
            key=lambda c: (
                c["is_immature"],
                0 if c["quality"] == "research" else 1,
                0 if c["author"] not in seen_authors else 1,
                0 if (c["tag"] and c["tag"] not in seen_tags) else 1,
                -c["score"],
                c["member_idx"],
            )
        )
        pick = remaining_obs.pop(0)
        pid = pick["photo_id"]
        t_url = pick["slide"]["thumb"]
        if (pid and pid in seen_photo_ids) or t_url in seen_urls:
            continue
        added.append(pick["slide"])
        if pid:
            seen_photo_ids.add(pid)
        seen_urls.add(t_url)
        seen_authors.add(pick["author"])
        if pick["tag"]:
            seen_tags.add(pick["tag"])

    # Pass B: Fill remaining slots up to MAX_MEMBER_TOTAL with additional angles from multi-photo obs
    secondary_pool.sort(
        key=lambda c: (
            c["is_immature"],
            0 if c["quality"] == "research" else 1,
            -c["score"],
            c["p_idx"],
        )
    )
    for pick in secondary_pool:
        if len(existing_slides) + len(added) >= MAX_MEMBER_TOTAL:
            break
        pid = pick["photo_id"]
        t_url = pick["slide"]["thumb"]
        if (pid and pid in seen_photo_ids) or t_url in seen_urls:
            continue
        added.append(pick["slide"])
        if pid:
            seen_photo_ids.add(pid)
        seen_urls.add(t_url)
    return added


def classify_commons_note(filename):
    low = filename.lower()
    if any(k in low for k in ("wsf", "wet_season", "wet-season", "wet season")):
        return "Wet-season form"
    if any(k in low for k in ("dsf", "dry_season", "dry-season", "dry season")):
        return "Dry-season form"
    if "female" in low:
        return "Female variation"
    if re.search(r"(?:^|[^a-z])male(?:[^a-z]|$)", low):
        return "Male variation"
    if any(k in low for k in ("mating", "copula")):
        return "Mating pair"
    if any(k in low for k in ("open", "upper", "dorsal", "upperside")):
        return "Open-wing view"
    if any(k in low for k in ("close", "under", "ventral", "underside")):
        return "Closed-wing view"
    return "Field variation photo"


def fetch_commons_supplements(entry, existing_slides, needed):
    sci = entry["scientific"]
    common_name = entry["name"]
    existing_files = {
        s["file"].replace(" ", "_").lower()
        for s in existing_slides
        if s.get("source") == "commons" and s.get("file")
    }
    existing_notes = {s.get("note", "") for s in existing_slides}
    candidates = {}

    for cat_name in candidate_names(entry):
        data = api_get(
            "commons.wikimedia.org",
            {
                "action": "query",
                "generator": "categorymembers",
                "gcmtitle": "Category:" + cat_name,
                "gcmtype": "file",
                "gcmlimit": 25,
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl",
            },
        )
        pages = (data.get("query") or {}).get("pages") or []
        for page in pages:
            title = page.get("title") or ""
            if not title.startswith("File:"):
                continue
            filename = title.removeprefix("File:")
            norm_key = filename.replace(" ", "_").lower()
            if norm_key in existing_files or norm_key in candidates:
                continue
            ii = (page.get("imageinfo") or [None])[0]
            if not ii:
                continue
            mime = ii.get("mime", "")
            w = int(ii.get("width") or 0)
            h = int(ii.get("height") or 0)
            if mime not in ALLOWED_MIMES or w < 500 or h < 350:
                continue
            if BAD_TITLE_RE.search(filename) or SPECIMEN_RE.search(filename):
                continue
            md = ii.get("extmetadata") or {}
            lic = normalize_license(
                (md.get("LicenseShortName") or {}).get("value", ""),
                (md.get("LicenseUrl") or {}).get("value", ""),
            )
            if not lic:
                continue
            author = extract_author(md, filename)
            if not author:
                continue
            note = classify_commons_note(filename)
            score = 100
            if w >= 960 and h >= 640:
                score += 20
            elif w >= 700:
                score += 10
            if w >= h:
                score += 5
            if any(k in filename.lower() for k in ("india", "kerala", "tamil", "karnataka", "bengal", "wlb", "open", "close")):
                score += 10
            if lic in {"by/4.0", "by-sa/4.0", "cc0/1.0"}:
                score += 3
            chosen_width = 960 if w >= 960 else (500 if w >= 500 else 0)
            candidates[norm_key] = (
                score,
                {
                    "source": "commons",
                    "file": filename,
                    "width": chosen_width,
                    "author": author,
                    "license": lic,
                    "licenseName": "",
                    "alt": f"{common_name} ({sci}) {note.lower()}",
                    "note": note,
                    "member": False,
                },
            )
        time.sleep(0.06)
        if len(candidates) >= needed * 3:
            break

    picked = []
    pool = list(candidates.values())
    used_authors = set()
    while pool and len(picked) < needed:
        pool.sort(
            key=lambda pair: (
                0 if pair[1]["note"] not in existing_notes else 1,
                0 if pair[1]["author"] not in used_authors else 1,
                -pair[0],
            )
        )
        _, slide = pool.pop(0)
        picked.append(slide)
        existing_notes.add(slide["note"])
        used_authors.add(slide["author"])
    return picked


def main():
    species_list = json.loads(SPECIES_PATH.read_text(encoding="utf-8-sig"))
    by_sci = {s["scientific"]: s for s in species_list}
    lookup = build_name_lookup(species_list)
    photos = json.loads(PHOTOS_PATH.read_text(encoding="utf-8-sig"))

    member_cands, obs_notes = fetch_all_member_candidates(lookup, by_sci)

    galleries = {}
    member_total_slides = 0
    commons_total_slides = 0

    for idx, entry in enumerate(species_list, 1):
        sci = entry["scientific"]
        slides = []
        if sci in photos:
            primary = normalize_primary_slide(photos[sci])
            if primary.get("source") == "inaturalist" and primary.get("url") in obs_notes:
                primary["note"] = "Primary photo · " + obs_notes[primary["url"]]
            slides.append(primary)

        if sci == "Papilio crino":
            slides.append(
                {
                    "source": "local",
                    "file": "assets/photos/home-hero-crino.jpg",
                    "author": "Pavendhan A (TNBS)",
                    "license": "",
                    "licenseName": "TNBS Member Archive",
                    "url": "",
                    "alt": "Common Banded Peacock (Papilio crino) basking with open emerald-green and turquoise-banded wings on green foliage, photographed by Pavendhan A",
                    "note": "Open-wing dorsal view · Member archive",
                    "member": True,
                }
            )

        # Tier 1: TNBS members (all licenses)
        cands = member_cands.get(sci, [])
        if cands:
            slides.extend(pick_diverse_member_slides(sci, slides, cands))

        # Tier 2: Supplement with verified Wikimedia Commons category photos up to 4 slides
        if len(slides) < TARGET_WITH_COMMONS:
            needed = TARGET_WITH_COMMONS - len(slides)
            supplements = fetch_commons_supplements(entry, slides, needed)
            slides.extend(supplements)

        if idx % 50 == 0:
            print(f"Processed {idx}/{len(species_list)} species ({len(galleries)} galleries so far)...")

        if len(slides) >= 2:
            galleries[sci] = slides
            for s in slides:
                if s.get("member"):
                    member_total_slides += 1
                else:
                    commons_total_slides += 1

    GALLERIES_PATH.write_text(json.dumps(galleries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    hist = {}
    for slides in galleries.values():
        hist[len(slides)] = hist.get(len(slides), 0) + 1
    total_slides = sum(len(v) for v in galleries.values())
    print(f"Saved {len(galleries)} species multi-photo galleries ({total_slides} total slides) to {GALLERIES_PATH}")
    print(f"Slides breakdown -> TNBS members: {member_total_slides}, Commons: {commons_total_slides}")
    print(f"Photo count distribution per species: {dict(sorted(hist.items()))}")
    print(f"Papilio crino gallery count: {len(galleries.get('Papilio crino', []))}")


if __name__ == "__main__":
    main()
