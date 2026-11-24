<<<<<<< HEAD
# The Nature and Butterfly Society

A static website for The Nature and Butterfly Society (TNBS), built for GitHub Pages and custom domains. It features the 329-species Tamil Nadu butterfly field guide (with complete structured profiles and 328 verified photographs including CC-licensed observations by TNBS members), a personal **Tamil Nadu Life List** tracker, **Butterfly Vision** AI identification (`https://butterflyvision.in/`), an interactive multi-mode quiz, peer-reviewed research publications (including *Journal of Threatened Taxa* #6656), 49 verified press & *Pattampoochi* reports, an About Us gallery, and all 27 issues of *Pattampoochi* with a searchable 147-article index.

## Preview

From the project directory, run `python -m http.server 8765 --directory docs` and open [http://localhost:8765](http://localhost:8765). Serving over HTTP allows the interactive quiz and AI helper modules to load their JSON metadata.

## Publish on GitHub Pages

1. Before publishing, set the public GitHub Pages address and rebuild. Use the complete address including the repository name for a project site, for example `https://YOUR-ACCOUNT.github.io/YOUR-REPO/`.

   ```powershell
   $env:SITE_URL = 'https://YOUR-ACCOUNT.github.io/YOUR-REPO/'
   python scripts/build.py
   ```

   Alternatively, put the public URL on a single line in `data/site-url.txt`. The build sets canonical URLs, social share URLs, Organization JSON-LD, and `sitemap.xml`.
2. Push this project to your GitHub repository. In **Settings → Pages**, choose **Deploy from a branch**, select the publishing branch, and choose **/docs**.
3. When you switch to your custom domain, configure it under **Settings → Pages**, apply the DNS records GitHub specifies, enable **Enforce HTTPS**, rebuild with the new `SITE_URL`, and submit `sitemap.xml` in Google Search Console.

## Update content & media

| File | Contents |
| --- | --- |
| `data/species.json` | 329 Tamil Nadu checklist entries (325 validated in TN, 4 awaiting validation), subfamilies, conservation tags, and Butterfly Vision model coverage |
| `data/taxonomy.json` | Structured field-guide notes and photography tips for all 6 families and 21 subfamilies |
| `data/profiles.json` | Detailed identification marks, Tamil Nadu distribution, host plants, seasonality, behaviour, and field references for all 329 species |
| `data/photos.json` | Verified Wikimedia Commons and CC-licensed TNBS member iNaturalist photos, photographer credits, Creative Commons / Public Domain licenses, and alt text (synced via `scripts/sync_photos.py` and `scripts/sync_member_photos.py`) |
| `data/site.json` | *Pattampoochi* issue IDs, verified press & magazine reports, peer-reviewed research papers, regional hotspots, community directory, fieldwork activities, About Us milestones & gallery, and Butterfly Vision metadata |
| `data/magazine_index.json` | Searchable index of 147 articles spanning all 27 issues of *Pattampoochi* |
| `assets/tnbs-logo.png`, `assets/photos/`, `assets/about/` | Official TNBS society logo, locally cached *Papilio crino* hero photograph, and authentic TNBS fieldwork/outreach photos |
| `assets/site.css`, `assets/site.js` | Responsive editorial styling, sticky header, native `<dialog>` photo lightbox, accessible hotspot tabs, Life List tracker, field guide filters/sorting, Butterfly Vision integration, and multi-mode interactive quiz |
| `scripts/build.py`, `scripts/sync_photos.py`, `scripts/sync_member_photos.py` | Static site generator (`docs/`), Wikimedia Commons sync script, and TNBS member iNaturalist/Commons sync script |

Run `python scripts/build.py` after any data or asset edits. To enable inline direct browser predictions inside `identify/index.html` from your custom domain in addition to the built-in `butterflyvision.in` handoff, allowlist your GitHub Pages / custom domain origin in `butterflyvision.in`'s FastAPI `CORSMiddleware`.
=======
# tamilnadubutterflies.github.io
>>>>>>> 4ad6e83ea29563474746a8a6af7b9bc8ba4a6107
