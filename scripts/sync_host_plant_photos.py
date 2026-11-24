"""Sync larval host plant photos from authorized TNBS members on iNaturalist into data/host_plants.json."""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
PROFILES_PATH = ROOT / "data" / "profiles.json"
SPECIES_PATH = ROOT / "data" / "species.json"
OUT_PATH = ROOT / "data" / "host_plants.json"

sys.path.insert(0, str(ROOT / "scripts"))
from sync_member_photos import http_json, score_inat_photo  # noqa: E402

MEMBERS = [
    ("nishanth2", "Nishanth CV (TNBS)", 60),
    ("theivaprakashamhari", "Theivaprakasham Hari (TNBS)", 45),
    ("ramanasaranhari", "Ramanasaran Hari (TNBS)", 30),
    ("sadheeskumar_k_tnbs", "Sadheeskumar K (TNBS)", 20),
    ("pavendhan", "Pavendhan Appavu (TNBS)", 10),
]

QUALITY_SCORES = {
    "research": 1000,
    "needs_id": 500,
    "casual": 200,
}

ALLOWED_RANKS = {"species", "variety", "subspecies", "hybrid", "genus"}

# Verified botanical synonyms mapping checklist hostPlant names to current iNaturalist accepted taxa.
BOTANICAL_SYNONYMS = {
    "murraya koenigii": "bergera koenigii",
    "cassia auriculata": "senna auriculata",
    "hybanthus enneaspermus": "pigea enneasperma",
    "passiflora foetida": "passiflora vesicaria",
    "prosopis juliflora": "neltuma juliflora",
    "millettia pinnata": "pongamia pinnata",
    "pongamia glabra": "pongamia pinnata",
    "zizyphus mauritiana": "ziziphus mauritiana",
    "zizyphus jujuba": "ziziphus mauritiana",
    "hibiscus rosa-sinensis": "hibiscus \u00d7 rosa-sinensis",
    "neolamarckia cadamba": "neolamarckia",
    "anthocephalus cadamba": "neolamarckia",
}

GENUS_SYNONYMS = {
    "murraya": "bergera",
    "acacia": "vachellia",
    "hybanthus": "pigea",
    "prosopis": "neltuma",
    "zizyphus": "ziziphus",
    "anthocephalus": "neolamarckia",
}

# Avoid matching distinct ornamental species to unrelated native congenerics where ecology differs sharply.
EXCLUDED_LOOSE_GENERA = {"oxalis"}

MAX_PHOTOS_PER_SPECIES = 4


def format_common_name(raw):
    name = (raw or "").strip()
    if not name:
        return ""
    return name[0].upper() + name[1:]


def extract_species_key(taxon_name, rank):
    parts = (taxon_name or "").strip().split()
    if not parts:
        return ""
    if rank == "hybrid" and "\u00d7" in taxon_name:
        return " ".join(parts).lower()
    if rank in {"species", "variety", "subspecies", "hybrid"} and len(parts) >= 2:
        return f"{parts[0]} {parts[1]}".lower()
    return parts[0].lower()


def fetch_member_plants(login, author_label, member_bonus):
    observations = []
    page = 1
    while page <= 8:
        params = {
            "user_login": login,
            "taxon_id": 47126,
            "per_page": 200,
            "page": page,
        }
        data = http_json("https://api.inaturalist.org/v1/observations?" + urlencode(params))
        results = data.get("results") or []
        if not results:
            break
        for obs in results:
            taxon = obs.get("taxon") or {}
            rank = (taxon.get("rank") or "").lower()
            tname = (taxon.get("name") or "").strip()
            quality = (obs.get("quality_grade") or "").lower()
            obs_id = obs.get("id")
            if rank not in ALLOWED_RANKS or not tname or quality not in QUALITY_SCORES or not obs_id:
                continue
            sp_key = extract_species_key(tname, rank)
            genus_key = tname.split()[0].lower()
            base_score = QUALITY_SCORES[quality] + member_bonus
            best_photo = None
            for p_idx, ph in enumerate(obs.get("photos") or []):
                p_score, lic = score_inat_photo(ph, allow_member_archive=True)
                if p_score < 0:
                    continue
                total_score = base_score + p_score + (5 if p_idx == 0 else 0)
                if not best_photo or total_score > best_photo[0]:
                    url = ph["url"]
                    best_photo = (
                        total_score,
                        {
                            "plantKey": sp_key if rank != "genus" else genus_key,
                            "taxon": " ".join(tname.split()[:2]) if rank in {"variety", "subspecies"} else tname,
                            "rank": "genus" if rank == "genus" else ("hybrid" if rank == "hybrid" else "species"),
                            "commonName": format_common_name(taxon.get("preferred_common_name")),
                            "thumb": url.replace("/square.", "/medium."),
                            "full": url.replace("/square.", "/large."),
                            "author": author_label,
                            "url": f"https://www.inaturalist.org/observations/{obs_id}",
                            "license": lic,
                            "licenseName": "TNBS Member Archive" if not lic else "",
                            "quality": quality,
                            "genusKey": genus_key,
                            "speciesKey": sp_key if rank != "genus" else "",
                        },
                    )
            if best_photo:
                observations.append(best_photo)
        if len(results) < 200:
            break
        page += 1
        time.sleep(0.4)
    return observations


def index_plant_observations(all_candidates):
    by_species = {}
    by_genus = {}
    for score, rec in all_candidates:
        sp_key = rec["speciesKey"]
        gen_key = rec["genusKey"]
        if sp_key:
            prev = by_species.get(sp_key)
            if not prev or score > prev[0]:
                by_species[sp_key] = (score, rec)
        # Prefer species-level identifications over genus-only ones at the same quality grade.
        gen_score = score + (15 if rec["rank"] != "genus" else 0)
        prev_g = by_genus.get(gen_key)
        if not prev_g or gen_score > prev_g[0]:
            by_genus[gen_key] = (gen_score, rec)
    return (
        {k: v[1] for k, v in by_species.items()},
        {k: v[1] for k, v in by_genus.items()},
    )


def match_host_string(host_label, by_species, by_genus):
    base = re.split(r"\s*\(", host_label)[0].strip()
    low = base.lower()
    if low in BOTANICAL_SYNONYMS:
        target = BOTANICAL_SYNONYMS[low]
        if target in by_species:
            return by_species[target], "synonym"
        if " " not in target and target in by_genus:
            return by_genus[target], "genus"

    m = re.match(r"^([A-Z][a-z]+)\s+([a-z-]+|\u00d7\s*[a-z-]+)", base)
    if not m:
        return None, ""
    g = m.group(1).lower()
    e = m.group(2).lower()
    binom = f"{g} {e}"

    if e in {"species", "spp", "sp"}:
        target_g = GENUS_SYNONYMS.get(g, g)
        if g not in EXCLUDED_LOOSE_GENERA and target_g in by_genus:
            return by_genus[target_g], "genus"
        return None, ""

    if binom in by_species:
        return by_species[binom], "exact"

    syn = BOTANICAL_SYNONYMS.get(binom)
    if syn:
        if syn in by_species:
            return by_species[syn], "synonym"
        if " " not in syn and syn in by_genus:
            return by_genus[syn], "genus"

    target_g = GENUS_SYNONYMS.get(g, g)
    if g not in EXCLUDED_LOOSE_GENERA and target_g in by_genus:
        return by_genus[target_g], "genus"
    return None, ""


def main():
    species_list = json.loads(SPECIES_PATH.read_text(encoding="utf-8-sig"))
    profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8-sig"))

    all_candidates = []
    for login, label, bonus in MEMBERS:
        cands = fetch_member_plants(login, label, bonus)
        all_candidates.extend(cands)
        print(f"Fetched {len(cands)} plant photo observations from {login} ({label})")

    by_species, by_genus = index_plant_observations(all_candidates)
    print(f"Indexed {len(by_species)} species-level plant taxa and {len(by_genus)} genera")

    plants = {}
    by_butterfly = {}
    tier_priority = {"exact": 0, "synonym": 1, "genus": 2}

    for entry in species_list:
        sci = entry["scientific"]
        prof = profiles.get(sci) or {}
        raw_hosts = prof.get("hostPlants") or []
        raw_matches = []
        for hp in raw_hosts:
            rec, kind = match_host_string(hp, by_species, by_genus)
            if rec:
                raw_matches.append((tier_priority[kind], kind, hp, rec))

        if not raw_matches:
            continue

        raw_matches.sort(key=lambda item: (item[0], -QUALITY_SCORES[item[3]["quality"]]))
        seen_urls = set()
        seen_keys = set()
        chosen = []
        for _, kind, hp, rec in raw_matches:
            pkey = rec["plantKey"]
            if pkey in seen_keys or rec["url"] in seen_urls:
                continue
            seen_keys.add(pkey)
            seen_urls.add(rec["url"])
            plants[pkey] = {
                "taxon": rec["taxon"],
                "rank": rec["rank"],
                "commonName": rec["commonName"],
                "thumb": rec["thumb"],
                "full": rec["full"],
                "author": rec["author"],
                "url": rec["url"],
                "license": rec["license"],
                "licenseName": rec["licenseName"],
                "quality": rec["quality"],
            }
            chosen.append(
                {
                    "plantKey": pkey,
                    "hostLabel": hp,
                    "matchKind": kind,
                }
            )
            if len(chosen) >= MAX_PHOTOS_PER_SPECIES:
                break
        if chosen:
            by_butterfly[sci] = chosen

    ordered_plants = {k: plants[k] for k in sorted(plants)}
    payload = {"plants": ordered_plants, "bySpecies": by_butterfly}
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    by_author = {}
    for rec in ordered_plants.values():
        by_author[rec["author"]] = by_author.get(rec["author"], 0) + 1
    print(f"Wrote {len(ordered_plants)} unique host plants covering {len(by_butterfly)} / {len(species_list)} butterfly species to {OUT_PATH}")
    print("Host plant photographers:", by_author)


if __name__ == "__main__":
    main()
