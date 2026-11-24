"""Extract verified Tamil butterfly names from TNBS records, Tamil Wikipedia, and Wikidata."""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
SPECIES_PATH = ROOT / "data" / "species.json"
PROFILES_PATH = ROOT / "data" / "profiles.json"
OUT_PATH = ROOT / "data" / "tamil_names.json"

sys.path.insert(0, str(ROOT / "scripts"))
from sync_inat_project import extended_lookup  # noqa: E402
from sync_member_photos import http_json  # noqa: E402

# Official TNBS / Government of Tamil Nadu curated butterfly names (highest priority).
CURATED_TAMIL = {
    "Cirrochroa thais": "தமிழ் மறவன்",
    "Papilio crino": "மயில் அழகி",
    "Troides minos": "தென் அழகி",
    "Papilio polymnestor": "நீல அழகி",
    "Papilio polytes": "கறிவேப்பிலை அழகி",
    "Papilio demoleus": "எலுமிச்சை அழகி",
    "Pachliopta hector": "சிவப்புடல் அழகி",
    "Pachliopta aristolochiae": "உரோசா அழகி",
    "Danaus chrysippus": "வெந்தய வரியன்",
    "Danaus genutia": "ஆரஞ்சு வரியன்",
    "Tirumala limniace": "நீல வரியன்",
    "Euploea core": "வெண்புள்ளிக் கருப்பன்",
    "Junonia lemonias": "எலுமிச்சை வண்ணன்",
    "Junonia almana": "மயில் வண்ணன்",
    "Junonia orithya": "நீல வண்ணன்",
    "Junonia hierta": "மஞ்சள் வண்ணன்",
    "Ariadne merione": "ஆமணக்கு வரியன்",
    "Hypolimnas misippus": "மாய வரியன்",
    "Hypolimnas bolina": "முட்டை வரியன்",
    "Euthalia aconthea": "கனிச்சிறகன்",
    "Acraea terpsicore": "செம்பழுப்பு வரியன்",
    "Ypthima ceylonica": "வெள்ளை நால்வளையன்",
    "Elymnias hypermnestra": "பனைச் சிறகன்",
    "Catopsilia pomona": "கொன்னை வெள்ளையன்",
    "Eurema hecabe": "புல் மஞ்சள்",
    "Delias eucharis": "மஞ்சள் எழிலி",
    "Talicada nyseus": "செம்முனை நீலன்",
    "Castalius rosimon": "விகடன்",
    "Lampides boeticus": "பட்டாணி நீலன்",
    "Graphium doson": "நாட்டு நீல அழகி",
    "Graphium agamemnon": "மரகத அழகி",
    "Graphium nomius": "கத்திவால் அழகி",
    "Spialia galba": "நரைச்சிறகுத் தாவி",
}

TAWIKI_SYNONYMS = {
    "pathysa nomius": "Graphium nomius",
    "pathysa antiphates": "Graphium antiphates",
    "graphium sarpedon": "Graphium teredon",
    "papilio helenus": "Papilio daksha",
    "chilasa clytia": "Papilio clytia",
    "zizeeria lysimon": "Zizeeria karsandra",
    "zizeeria otis": "Zizina otis",
    "spindasis vulcanus": "Cigaritis vulcanus",
    "spindasis lohita": "Cigaritis lohita",
    "spindasis ictis": "Cigaritis ictis",
    "spindasis schistacea": "Cigaritis schistacea",
    "polyura athamas": "Charaxes bharata",
    "polyura agraria": "Charaxes agrarius",
    "hyarotis adrastus": "Hyarotis adrastus",
    "euthalia garuda": "Euthalia aconthea",
    "phalantha phalantha": "Phalanta phalantha",
    "precis almana": "Junonia almana",
    "precis atlites": "Junonia atlites",
    "precis hierta": "Junonia hierta",
    "precis iphita": "Junonia iphita",
    "precis lemonias": "Junonia lemonias",
    "precis orithya": "Junonia orithya",
    "cyaniris puspa": "Acytolepis puspa",
    "euchrysops pandava": "Chilades pandava",
    "jamides bochus": "Jamides bochus",
    "badamia exclamationis": "Badamia exclamationis",
    "hasora chromus": "Hasora chromus",
}

SKIP_TRANSLIT_PREFIXES = (
    "பச்லியோப்டா",
    "சிரோகோரா",
    "தாருகசு",
    "அத்திமா",
    "சலாமிசு",
    "சிந்துசா",
    "குமோதலேசு",
    "ஆக்டிசெரா",
    "உனா ",
    "அக்மெதியா",
    "கார்தியா",
    "கங்காரா",
    "கேடபசில்மா",
    "கசோரா",
)


def has_tamil(text):
    return any("\u0b80" <= ch <= "\u0bff" for ch in (text or ""))


def clean_tamil_title(raw):
    text = re.sub(r"\s*\(பட்டாம்பூச்சி\)", "", raw or "")
    text = re.sub(r"\s*\([^)]*list[^)]*\)", "", text, flags=re.I)
    text = text.replace("?", "").strip(" ,.-")
    return re.sub(r"\s+", " ", text).strip()


def is_clean_vernacular(ta_name):
    if not has_tamil(ta_name):
        return False
    if any(bad in ta_name for bad in ("பட்டியல்", "லின்னேயஸ்", "கிராமர்", "மூரே", "ஃபேப்ரிசியஸ்")):
        return False
    if ta_name.startswith(SKIP_TRANSLIT_PREFIXES):
        return False
    if len(ta_name) < 3 or len(ta_name) > 55:
        return False
    return True


def fetch_tawiki_list(species_list, lookup):
    en_lookup = {s["name"].lower(): s["scientific"] for s in species_list}
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "titles": "தமிழ்நாட்டில் காணப்படும் பட்டாம்பூச்சிகளின் பட்டியல்",
    }
    data = http_json("https://ta.wikipedia.org/w/api.php?" + urlencode(params))
    pages = (data.get("query") or {}).get("pages") or []
    content = ((pages[0].get("revisions") or [{}])[0].get("slots") or {}).get("main", {}).get("content", "")

    matched = {}
    for line in content.splitlines():
        s = line.strip()
        if not s.startswith("*"):
            continue
        m = re.match(r"^\*+\s*(?:''')?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", s)
        if not m:
            continue
        ta_cand = clean_tamil_title(m.group(2) or m.group(1))
        if not is_clean_vernacular(ta_cand):
            continue

        sci = None
        for italic in re.findall(r"''([^']+)''", s):
            cleaned = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", italic)
            cleaned = cleaned.replace("[[", "").replace("]]", "")
            cleaned = re.sub(r"\([A-Z][a-z]+\)", " ", cleaned)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            parts = cleaned.split()
            for cand in [cleaned, " ".join(parts[:2]) if len(parts) >= 2 else ""]:
                low = cand.lower()
                if not low:
                    continue
                if low in TAWIKI_SYNONYMS and TAWIKI_SYNONYMS[low] in {x["scientific"] for x in species_list}:
                    sci = TAWIKI_SYNONYMS[low]
                    break
                if low in lookup:
                    sci = lookup[low]
                    break
            if sci:
                break

        if not sci:
            for en_cand in re.findall(r"\(([^)]+)\)", s):
                first_part = en_cand.split(",")[0].strip().lower()
                if first_part in en_lookup:
                    sci = en_lookup[first_part]
                    break

        if sci and sci not in matched:
            matched[sci] = ta_cand
    return matched


def fetch_wikidata_tamil(species_list, already):
    # Query English Wikipedia -> Wikidata QIDs -> Tamil labels & tawiki titles
    remaining = [s for s in species_list if s["scientific"] not in already]
    titles = [s["scientific"] for s in remaining]
    title_to_qid = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i : i + 50]
        data = http_json(
            "https://en.wikipedia.org/w/api.php?"
            + urlencode(
                {
                    "action": "query",
                    "format": "json",
                    "formatversion": "2",
                    "redirects": 1,
                    "prop": "pageprops",
                    "ppprop": "wikibase_item",
                    "titles": "|".join(chunk),
                }
            )
        )
        q = data.get("query") or {}
        norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
        redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
        qids_by_page = {
            p.get("title"): (p.get("pageprops") or {}).get("wikibase_item")
            for p in q.get("pages", [])
            if (p.get("pageprops") or {}).get("wikibase_item")
        }
        for orig in chunk:
            t = redir.get(norm.get(orig, orig), norm.get(orig, orig))
            if t in qids_by_page:
                title_to_qid[orig] = qids_by_page[t]
        time.sleep(0.15)

    qids = sorted(set(title_to_qid.values()))
    qid_to_ta = {}
    for i in range(0, len(qids), 50):
        chunk = qids[i : i + 50]
        wd = http_json(
            "https://www.wikidata.org/w/api.php?"
            + urlencode(
                {
                    "action": "wbgetentities",
                    "format": "json",
                    "ids": "|".join(chunk),
                    "props": "labels|sitelinks",
                    "languages": "ta",
                    "sitefilter": "tawiki",
                }
            )
        )
        for qid, ent in (wd.get("entities") or {}).items():
            raw = (
                ((ent.get("labels") or {}).get("ta") or {}).get("value")
                or ((ent.get("sitelinks") or {}).get("tawiki") or {}).get("title")
                or ""
            )
            cleaned = clean_tamil_title(raw)
            if is_clean_vernacular(cleaned):
                qid_to_ta[qid] = cleaned
        time.sleep(0.15)

    matched = {}
    for sci, qid in title_to_qid.items():
        if qid in qid_to_ta:
            matched[sci] = qid_to_ta[qid]
    return matched


def main():
    species_list = json.loads(SPECIES_PATH.read_text(encoding="utf-8-sig"))
    by_sci = {s["scientific"]: s for s in species_list}
    lookup = extended_lookup(species_list)
    profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8-sig"))

    result = {}
    for sci, ta in CURATED_TAMIL.items():
        if sci in by_sci:
            result[sci] = {"ta": ta, "source": "TNBS Curated Checklist"}

    wiki_ta = fetch_tawiki_list(species_list, lookup)
    wiki_added = 0
    for sci, ta in wiki_ta.items():
        if sci not in result:
            result[sci] = {"ta": ta, "source": "Tamil Wikipedia Checklist"}
            wiki_added += 1

    wd_ta = fetch_wikidata_tamil(species_list, result)
    wd_added = 0
    for sci, ta in wd_ta.items():
        if sci not in result:
            result[sci] = {"ta": ta, "source": "Wikidata / Tamil Wikipedia"}
            wd_added += 1

    order = {s["scientific"]: s["id"] for s in species_list}
    ordered = {k: result[k] for k in sorted(result, key=lambda s: order.get(s, 9999))}
    OUT_PATH.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Sync tamilName into profiles.json cleanly
    for sci, info in ordered.items():
        prof = profiles.get(sci)
        if isinstance(prof, dict):
            if sci == "Cirrochroa thais":
                prof["tamilName"] = "தமிழ் மறவன் (Tamil Maravan)"
            elif not prof.get("tamilName"):
                prof["tamilName"] = info["ta"]

    PROFILES_PATH.write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"Saved {len(ordered)} Tamil butterfly names to {OUT_PATH} "
        f"(curated: {len(result) - wiki_added - wd_added}, ta.wiki: {wiki_added}, wikidata: {wd_added})"
    )


if __name__ == "__main__":
    main()
