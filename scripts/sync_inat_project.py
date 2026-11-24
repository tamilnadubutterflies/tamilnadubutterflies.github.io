"""Sync iNaturalist Project #47280 (Butterflies of Tamil Nadu) stats, phenology, and CC photo gaps."""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
SPECIES_PATH = ROOT / "data" / "species.json"
PHOTOS_PATH = ROOT / "data" / "photos.json"
GALLERIES_PATH = ROOT / "data" / "galleries.json"
INAT_OUT_PATH = ROOT / "data" / "inat_project.json"

sys.path.insert(0, str(ROOT / "scripts"))
from sync_galleries import clean_place, inat_photo_id, normalize_primary_slide, parse_obs_metadata  # noqa: E402
from sync_member_photos import build_name_lookup, http_json, match_species, score_inat_photo  # noqa: E402
from sync_photos import COMMONS_ALIASES  # noqa: E402

PROJECT_ID = 47280
PROJECT_SLUG = "butterflies-of-tamil-nadu"
CC_LICENSES = "cc-by,cc-by-sa,cc0,cc-by-nc,cc-by-nc-sa"

# Verified iNaturalist taxonomy/spelling aliases mapped to checklist scientific names.
EXTRA_INAT_ALIASES = {
    "Kallima horsfieldi": ["Kallima horsfieldii"],
    "Caprona ransonnetti": ["Caprona ransonnettii"],
    "Potanthus pallidus": ["Potanthus pallida"],
    "Hyarotis coorga": ["Hyarotis microstictum"],
    "Chilades pandava": ["Luthrodes pandava"],
    "Pseudozizeeria maha": ["Zizeeria maha"],
    "Mycalesis igilia": ["Telinga igilia"],
    "Charaxes bharata": ["Polyura bharata", "Polyura athamas"],
    "Charaxes agrarius": ["Polyura agraria", "Charaxes agraria"],
    "Charaxes schreiber": ["Polyura schreiber"],
    "Pachliopta hector": ["Atrophaneura hector"],
    "Pachliopta aristolochiae": ["Atrophaneura aristolochiae"],
    "Pachliopta pandiyana": ["Atrophaneura pandiyana"],
}


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def extended_lookup(species_list):
    lookup = build_name_lookup(species_list)
    for sci, aliases in EXTRA_INAT_ALIASES.items():
        for alias in aliases:
            lookup.setdefault(alias.lower(), sci)
    return lookup


def taxon_query_candidates(entry):
    sci = entry["scientific"]
    cands = [sci]
    for alias in EXTRA_INAT_ALIASES.get(sci, []):
        cands.append(alias)
    for alias in COMMONS_ALIASES.get(sci, []):
        cands.append(alias)
    parts = sci.split()
    if len(parts) > 2:
        cands.append(" ".join(parts[:2]))
    seen = set()
    return [c for c in cands if not (c in seen or seen.add(c))]


def fetch_project_snapshot(species_list, by_sci, lookup):
    proj_data = http_json(f"https://api.inaturalist.org/v1/projects/{PROJECT_SLUG}")
    proj_raw = (proj_data.get("results") or [{}])[0]

    total_obs_data = http_json(
        "https://api.inaturalist.org/v1/observations?"
        + urlencode({"project_id": PROJECT_ID, "per_page": 1})
    )
    rg_obs_data = http_json(
        "https://api.inaturalist.org/v1/observations?"
        + urlencode({"project_id": PROJECT_ID, "quality_grade": "research", "per_page": 1})
    )
    recent_data = http_json(
        "https://api.inaturalist.org/v1/observations?"
        + urlencode({"project_id": PROJECT_ID, "photos": "true", "per_page": 12, "order_by": "observed_on"})
    )
    spp_data = http_json(
        "https://api.inaturalist.org/v1/observations/species_counts?"
        + urlencode({"project_id": PROJECT_ID, "per_page": 500})
    )
    obs_data = http_json(
        "https://api.inaturalist.org/v1/observations/observers?"
        + urlencode({"project_id": PROJECT_ID, "per_page": 12})
    )
    hist_data = http_json(
        "https://api.inaturalist.org/v1/observations/histogram?"
        + urlencode({"project_id": PROJECT_ID, "date_field": "observed", "interval": "month_of_year"})
    )

    month_map = (hist_data.get("results") or {}).get("month_of_year") or {}
    months_total = [int(month_map.get(str(m), 0)) for m in range(1, 13)]

    by_species = {}
    taxon_thumbs = {}
    for item in spp_data.get("results") or []:
        taxon = item.get("taxon") or {}
        sci = match_species({"taxon": taxon}, lookup)
        if not sci or sci not in by_sci:
            continue
        cnt = int(item.get("count") or 0)
        tid = int(taxon.get("id") or 0)
        dp = taxon.get("default_photo") or {}
        if sci not in taxon_thumbs and dp.get("medium_url"):
            taxon_thumbs[sci] = dp["medium_url"]
        rec = by_species.setdefault(sci, {"taxonId": tid, "count": 0, "months": [0] * 12})
        rec["count"] += cnt
        if not rec["taxonId"] and tid:
            rec["taxonId"] = tid

    # Query 12 monthly species_counts slices to build accurate Jan-Dec phenology per species.
    for m in range(1, 13):
        m_data = http_json(
            "https://api.inaturalist.org/v1/observations/species_counts?"
            + urlencode({"project_id": PROJECT_ID, "month": m, "per_page": 500})
        )
        for item in m_data.get("results") or []:
            taxon = item.get("taxon") or {}
            sci = match_species({"taxon": taxon}, lookup)
            if not sci or sci not in by_sci:
                continue
            tid = int(taxon.get("id") or 0)
            rec = by_species.setdefault(sci, {"taxonId": tid, "count": 0, "months": [0] * 12})
            rec["months"][m - 1] += int(item.get("count") or 0)
        time.sleep(0.25)

    top_species = []
    for sci, rec in sorted(by_species.items(), key=lambda kv: -kv[1]["count"])[:12]:
        sp = by_sci[sci]
        top_species.append(
            {
                "scientific": sci,
                "name": sp["name"],
                "slug": slugify(sci),
                "taxonId": rec["taxonId"],
                "count": rec["count"],
                "thumb": taxon_thumbs.get(sci, ""),
            }
        )

    top_observers = []
    for item in obs_data.get("results") or []:
        user = item.get("user") or {}
        top_observers.append(
            {
                "login": user.get("login") or "",
                "name": user.get("name") or user.get("login") or "",
                "observations": int(item.get("observation_count") or 0),
                "species": int(item.get("species_count") or 0),
            }
        )

    recent = []
    for obs in recent_data.get("results") or []:
        taxon = obs.get("taxon") or {}
        user = obs.get("user") or {}
        photos = obs.get("photos") or []
        thumb = ""
        if photos and photos[0].get("url"):
            thumb = photos[0]["url"].replace("/square.", "/medium.")
        sci = match_species(obs, lookup)
        sp = by_sci.get(sci) if sci else None
        place = clean_place(obs.get("place_guess")) or (obs.get("place_guess") or "Tamil Nadu")[:36]
        recent.append(
            {
                "id": int(obs.get("id") or 0),
                "observedOn": (obs.get("observed_on") or "")[:10],
                "taxonName": taxon.get("name") or "",
                "commonName": (sp["name"] if sp else "") or taxon.get("preferred_common_name") or taxon.get("name") or "",
                "scientific": sci or "",
                "slug": slugify(sci) if sci else "",
                "place": place,
                "user": user.get("name") or user.get("login") or "",
                "thumb": thumb,
                "url": f"https://www.inaturalist.org/observations/{obs.get('id')}",
                "quality": obs.get("quality_grade") or "",
            }
        )

    order = {s["scientific"]: s["id"] for s in species_list}
    ordered_species = {k: by_species[k] for k in sorted(by_species, key=lambda s: order.get(s, 9999))}

    return {
        "project": {
            "id": PROJECT_ID,
            "slug": PROJECT_SLUG,
            "title": proj_raw.get("title") or "Butterflies of Tamil Nadu",
            "url": f"https://www.inaturalist.org/projects/{PROJECT_SLUG}",
            "fetchedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "observations": int(total_obs_data.get("total_results") or 0),
            "researchGrade": int(rg_obs_data.get("total_results") or 0),
            "speciesCount": int(spp_data.get("total_results") or 0),
            "observersCount": int(obs_data.get("total_results") or 0),
        },
        "months": months_total,
        "topSpecies": top_species,
        "topObservers": top_observers,
        "recent": recent,
        "bySpecies": ordered_species,
    }


def fetch_cc_gap_candidates(entry, seen_ids, seen_urls):
    sci = entry["scientific"]
    common_name = entry["name"]
    candidates = []
    seen_obs = set()
    queries = taxon_query_candidates(entry)

    # First check TN Project #47280, then fall back globally for scarce taxa, keeping strict CC RG filter.
    scopes = [
        {"project_id": PROJECT_ID, "per_page": 20},
        {"per_page": 20},
    ]
    for scope in scopes:
        if len(candidates) >= 6:
            break
        for q_name in queries:
            params = {
                "taxon_name": q_name,
                "quality_grade": "research",
                "photo_license": CC_LICENSES,
                **scope,
            }
            data = http_json("https://api.inaturalist.org/v1/observations?" + urlencode(params))
            results = data.get("results") or []
            for obs in results:
                obs_id = obs.get("id")
                if not obs_id or obs_id in seen_obs:
                    continue
                seen_obs.add(obs_id)
                user = obs.get("user") or {}
                author = (user.get("name") or user.get("login") or "").strip()
                if not author:
                    continue
                meta = parse_obs_metadata(obs)
                obs_url = f"https://www.inaturalist.org/observations/{obs_id}"
                for p_idx, ph in enumerate(obs.get("photos") or []):
                    sc, lic = score_inat_photo(ph, allow_member_archive=False)
                    if sc < 0 or not lic:
                        continue
                    base_url = ph["url"]
                    pid = inat_photo_id(base_url)
                    thumb = base_url.replace("/square.", "/medium.")
                    full = base_url.replace("/square.", "/large.")
                    if (pid and pid in seen_ids) or thumb in seen_urls:
                        continue
                    note = meta["note"]
                    if p_idx > 0:
                        note = f"Angle {p_idx + 1}" + (f" · {note}" if note else "")
                    in_tn = "project_id" in scope
                    bonus = 20 if in_tn else 0
                    candidates.append(
                        (
                            sc + bonus + (5 if p_idx == 0 else 0),
                            p_idx,
                            pid,
                            {
                                "source": "inaturalist",
                                "thumb": thumb,
                                "full": full,
                                "author": f"{author} (iNaturalist)",
                                "license": lic,
                                "licenseName": "",
                                "url": obs_url,
                                "alt": f"{common_name} ({sci}) photographed by {author}" + (f" ({note})" if note else ""),
                                "note": note or ("Tamil Nadu observation" if in_tn else "Field observation photo"),
                                "member": False,
                            },
                        )
                    )
            time.sleep(0.25)
            if len(candidates) >= 6:
                break

    candidates.sort(key=lambda item: (-item[0], item[1]))
    picked = []
    used_authors = set()
    deferred = []
    for _, _, pid, slide in candidates:
        if (pid and pid in seen_ids) or slide["thumb"] in seen_urls:
            continue
        if slide["author"] in used_authors:
            deferred.append((pid, slide))
            continue
        picked.append(slide)
        if pid:
            seen_ids.add(pid)
        seen_urls.add(slide["thumb"])
        used_authors.add(slide["author"])
        if len(picked) >= 4:
            break
    for pid, slide in deferred:
        if len(picked) >= 4:
            break
        if (pid and pid in seen_ids) or slide["thumb"] in seen_urls:
            continue
        picked.append(slide)
        if pid:
            seen_ids.add(pid)
        seen_urls.add(slide["thumb"])
    return picked


def gap_fill_photos(species_list, by_sci):
    photos = json.loads(PHOTOS_PATH.read_text(encoding="utf-8-sig"))
    galleries = json.loads(GALLERIES_PATH.read_text(encoding="utf-8-sig")) if GALLERIES_PATH.exists() else {}

    gap_species = [s for s in species_list if s["scientific"] not in photos or s["scientific"] not in galleries]
    if not gap_species:
        print("No photo or gallery gaps remain.")
        return

    print(f"Checking CC RG iNaturalist records for {len(gap_species)} remaining photo/gallery gaps...")
    primary_added = 0
    galleries_added = 0

    for entry in gap_species:
        sci = entry["scientific"]
        slides = []
        if sci in photos:
            slides.append(normalize_primary_slide(photos[sci]))
        seen_ids = {
            inat_photo_id(s.get("thumb") or s.get("full"))
            for s in slides
            if s.get("source") == "inaturalist"
        } - {""}
        seen_urls = {s.get("thumb") or s.get("full") or s.get("file") for s in slides} - {""}

        needed = max(0, 4 - len(slides))
        if needed > 0:
            extra = fetch_cc_gap_candidates(entry, seen_ids, seen_urls)[:needed]
            slides.extend(extra)

        if sci not in photos and slides:
            first = slides[0]
            photos[sci] = {
                "source": "inaturalist",
                "thumb": first["thumb"],
                "full": first["full"],
                "author": first["author"],
                "license": first["license"],
                "url": first["url"],
                "alt": first["alt"],
                "member": False,
            }
            primary_added += 1

        if sci not in galleries and len(slides) >= 2:
            galleries[sci] = slides[:4]
            galleries_added += 1

    order = {s["scientific"]: s["id"] for s in species_list}
    if primary_added:
        ordered_photos = {k: photos[k] for k in sorted(photos, key=lambda s: order.get(s, 9999)) if k in order}
        PHOTOS_PATH.write_text(json.dumps(ordered_photos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if galleries_added:
        ordered_galleries = {k: galleries[k] for k in sorted(galleries, key=lambda s: order.get(s, 9999)) if k in order}
        GALLERIES_PATH.write_text(json.dumps(ordered_galleries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Gap fill complete: added {primary_added} primary photos (total {len(photos)}/{len(species_list)}), {galleries_added} galleries (total {len(galleries)}/{len(species_list)})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats-only", action="store_true", help="Refresh Project #47280 stats and phenology without running photo gap fills.")
    parser.add_argument("--skip-gaps", action="store_true", help="Alias for --stats-only.")
    args = parser.parse_args()

    species_list = json.loads(SPECIES_PATH.read_text(encoding="utf-8-sig"))
    by_sci = {s["scientific"]: s for s in species_list}
    lookup = extended_lookup(species_list)

    snapshot = fetch_project_snapshot(species_list, by_sci, lookup)
    INAT_OUT_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    proj = snapshot["project"]
    print(
        f"Synced iNaturalist Project #{proj['id']}: {proj['observations']} obs ({proj['researchGrade']} RG), "
        f"{proj['speciesCount']} taxa ({len(snapshot['bySpecies'])} TN checklist matches), {proj['observersCount']} observers"
    )

    if not (args.stats_only or args.skip_gaps):
        gap_fill_photos(species_list, by_sci)


if __name__ == "__main__":
    main()
