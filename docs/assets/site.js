"use strict";

document.documentElement.classList.add("has-js");
const IS_TA = document.documentElement.lang === "ta";

/* Two-state Dark Mode Toggle (dark-mode & dark-mode-toggle compliant) */
(function initThemeToggle() {
    const KEY = "color-scheme";
    const meta = document.querySelector('meta[name="color-scheme"]');
    if (!meta) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");

    function getStored() {
        try {
            const v = localStorage.getItem(KEY);
            return v === "light" || v === "dark" ? v : "";
        } catch {
            return "";
        }
    }

    function syncMeta() {
        const stored = getStored();
        meta.content = stored || "light dark";
    }

    syncMeta();
    window.addEventListener("storage", (e) => {
        if (e.key === KEY || e.key === null) syncMeta();
    });

    for (const btn of document.querySelectorAll("[data-theme-toggle]")) {
        btn.addEventListener("click", () => {
            const current = getStored() || (mq.matches ? "dark" : "light");
            const target = current === "dark" ? "light" : "dark";
            const osScheme = mq.matches ? "dark" : "light";
            try {
                if (target !== osScheme) localStorage.setItem(KEY, target);
                else localStorage.removeItem(KEY);
            } catch {
                // Ignore storage block; still apply to current view
            }
            meta.content = target !== osScheme ? target : "light dark";
        });
    }
})();

/* Feature-detect native Popover API before loading polyfill only if missing */
if (!Object.hasOwn(HTMLElement.prototype, "popover")) {
    import("https://unpkg.com/@oddbird/popover-polyfill@latest/dist/popover.min.js").catch(() => {});
}

/* Container-adaptive Popover Navbar (modern-web-guidance navbar compliant) */
(function initAdaptiveNavbar() {
    const masthead = document.querySelector(".masthead");
    const headerInner = document.querySelector(".header-inner");
    const menuList = document.getElementById("primary-menu");
    if (!masthead || !headerInner || !menuList) return;

    let lastCollapsedWidth = 0;

    function isMenuOpen() {
        try {
            return menuList.matches(":popover-open, .\\:popover-open");
        } catch {
            return false;
        }
    }

    function updateNavLayout(forceMeasure = false) {
        const currentlyWide = masthead.classList.contains("is-wide");
        const curWidth = headerInner.clientWidth;
        if (!forceMeasure && !currentlyWide && curWidth <= lastCollapsedWidth) {
            return;
        }
        const wasOpen = !currentlyWide && isMenuOpen();
        masthead.classList.add("is-measuring");
        masthead.classList.add("is-wide");
        menuList.removeAttribute("popover");

        const fitsInline = headerInner.scrollWidth <= headerInner.clientWidth;
        if (fitsInline) {
            masthead.classList.add("is-wide");
            menuList.removeAttribute("popover");
            lastCollapsedWidth = 0;
        } else {
            masthead.classList.remove("is-wide");
            menuList.setAttribute("popover", "auto");
            lastCollapsedWidth = curWidth;
            if (wasOpen) {
                try {
                    menuList.showPopover();
                } catch {
                    // Popover polyfill still loading or already open
                }
            }
        }
        requestAnimationFrame(() => masthead.classList.remove("is-measuring"));
    }

    updateNavLayout(true);

    if ("ResizeObserver" in window) {
        const ro = new ResizeObserver((entries) => {
            const menuChanged = entries.some((entry) => entry.target === menuList);
            updateNavLayout(menuChanged);
        });
        ro.observe(headerInner);
        ro.observe(menuList);
    } else {
        window.addEventListener("resize", () => updateNavLayout(true), { passive: true });
    }

    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(() => updateNavLayout(true));
    }

    menuList.addEventListener("click", (e) => {
        const a = e.target.closest("a");
        if (a && menuList.hasAttribute("popover") && isMenuOpen()) {
            try {
                menuList.hidePopover();
            } catch {}
        }
    });
})();
const yearSpan = document.querySelector("footer [data-footer-year], footer [data-year]");
if (yearSpan) yearSpan.textContent = String(new Date().getFullYear());

/* Floating Back-to-Top button */
const backTopBtn = document.querySelector("[data-back-top]");
if (backTopBtn) {
    const syncTop = () => {
        backTopBtn.hidden = window.scrollY < 480;
    };
    window.addEventListener("scroll", syncTop, { passive: true });
    syncTop();
}

function watchImage(image, onError) {
    function recover() {
        image.hidden = true;
        if (onError) onError();
    }
    image.addEventListener("error", recover, { once: true });
    if (image.complete && !image.naturalWidth) recover();
}

for (const image of document.querySelectorAll(".hide-on-error")) {
    watchImage(image, () => {
        const panel = image.closest("figure, .card");
        if (!panel) return;
        if (panel.matches(".host-card")) {
            panel.hidden = true;
            return;
        }
        const credit = panel.querySelector(".credit") || panel.nextElementSibling;
        if (credit?.matches(".credit, .hero-credit")) credit.hidden = true;
    });
}

function normalize(value) {
    return String(value || "").normalize("NFC").toLowerCase()
        .replace(/[\u0300-\u036f]+/gu, "")
        .replace(/[^\p{L}\p{N}\p{M}]+/gu, " ").trim();
}

function appendCreditLink(target, text, href) {
    if (href) {
        const a = document.createElement("a");
        a.href = href;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = text;
        target.append(a);
    } else {
        target.append(text);
    }
}

function renderCreditLine(target, { author, url, license, licenseName, sourceLabel, caption }) {
    target.replaceChildren();
    if (caption) {
        target.textContent = caption;
        return;
    }
    if (!author) return;
    appendCreditLink(target, author, url);
    if (licenseName) {
        target.append(" · ");
        appendCreditLink(target, licenseName, license);
    }
    if (sourceLabel && url) {
        target.append(" · ");
        appendCreditLink(target, sourceLabel, url);
    }
}

const galleryControllers = new WeakMap();

/* Native <dialog> Photo Lightbox (compliant with dialog + light-dismiss-a-dialog) */
const lightbox = document.getElementById("lightbox");
if (lightbox) {
    const lbTitle = document.getElementById("lightbox-title");
    const lbSub = document.getElementById("lightbox-sub");
    const lbImg = document.getElementById("lightbox-img");
    const lbCredit = document.getElementById("lightbox-credit");
    const lbNav = lightbox.querySelector("[data-lightbox-nav]");
    const lbCounter = lightbox.querySelector("[data-lightbox-counter]");
    let activeController = null;
    let activeIdx = 0;

    function showLightboxSlide(idx) {
        if (!activeController || !activeController.items.length) return;
        const items = activeController.items;
        activeIdx = ((idx % items.length) + items.length) % items.length;
        const slide = items[activeIdx];
        lbTitle.textContent = slide.title || (IS_TA ? "TNBS புகைப்படம்" : "TNBS photograph");
        lbSub.textContent = slide.note ? `${slide.note} · ${slide.alt}` : (slide.alt || "");
        lbImg.src = slide.src;
        lbImg.alt = slide.alt || slide.title || (IS_TA ? "பட்டாம்பூச்சி புகைப்படம்" : "Butterfly photograph");
        renderCreditLine(lbCredit, slide);
        if (lbCounter) lbCounter.textContent = `${activeIdx + 1} / ${items.length}`;
        if (lbNav) lbNav.hidden = items.length < 2;
    }

    document.addEventListener("click", (event) => {
        const trigger = event.target.closest("[data-lightbox-src]");
        if (!trigger) return;
        const galleryRoot = trigger.closest("[data-species-gallery]");
        const controller = galleryRoot && trigger.hasAttribute("data-gallery-zoom")
            ? galleryControllers.get(galleryRoot)
            : null;
        if (controller && controller.items.length >= 2) {
            activeController = controller;
            showLightboxSlide(controller.getIdx());
        } else {
            activeController = null;
            if (lbNav) lbNav.hidden = true;
            lbTitle.textContent = trigger.dataset.lightboxTitle || (IS_TA ? "TNBS புகைப்படம்" : "TNBS photograph");
            lbSub.textContent = trigger.dataset.lightboxAlt || "";
            lbImg.src = trigger.dataset.lightboxSrc;
            lbImg.alt = trigger.dataset.lightboxAlt || trigger.dataset.lightboxTitle || (IS_TA ? "பட்டாம்பூச்சி புகைப்படம்" : "Butterfly photograph");
            renderCreditLine(lbCredit, {
                author: trigger.dataset.lightboxAuthor,
                url: trigger.dataset.lightboxUrl,
                license: trigger.dataset.lightboxLicense,
                licenseName: trigger.dataset.lightboxLicensename,
                caption: trigger.dataset.lightboxCaption,
            });
        }
        lightbox.showModal();
    });

    for (const stepBtn of lightbox.querySelectorAll("[data-lightbox-dir]")) {
        stepBtn.addEventListener("click", () => {
            if (!activeController) return;
            const next = activeIdx + Number(stepBtn.dataset.lightboxDir);
            showLightboxSlide(next);
            activeController.go(activeIdx, false);
        });
    }

    lightbox.addEventListener("keydown", (event) => {
        if (!lightbox.open || !activeController) return;
        if (event.altKey || event.ctrlKey || event.metaKey) return;
        if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
        if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
            event.preventDefault();
            const dir = event.key === "ArrowRight" ? 1 : -1;
            showLightboxSlide(activeIdx + dir);
            activeController.go(activeIdx, false);
        }
    });

    lightbox.addEventListener("close", () => {
        lightbox.returnValue = "";
        activeController = null;
        if (lbNav) lbNav.hidden = true;
    });

    if (!("closedBy" in HTMLDialogElement.prototype)) {
        const outside = (e, dialog) => {
            const r = dialog.getBoundingClientRect();
            return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
        };
        let pressedOutside = false;
        lightbox.addEventListener("pointerdown", (e) => {
            pressedOutside = outside(e, lightbox);
        });
        lightbox.addEventListener("pointerup", (e) => {
            if (pressedOutside && outside(e, lightbox)) lightbox.close();
        });
    }
}

/* Species Page Multi-Photo Variation Gallery Controller */
for (const galleryEl of document.querySelectorAll("[data-species-gallery]")) {
    const items = JSON.parse(galleryEl.dataset.speciesGallery || "[]");
    if (items.length < 2) continue;
    const mainImg = galleryEl.querySelector("[data-gallery-img]");
    const zoomBtn = galleryEl.querySelector("[data-gallery-zoom]");
    const counterEl = galleryEl.querySelector("[data-gallery-counter]");
    const noteEl = galleryEl.querySelector("[data-gallery-note]");
    const creditEl = galleryEl.querySelector("[data-gallery-credit]");
    const statusEl = galleryEl.querySelector("[data-gallery-status]");
    const thumbsWrap = galleryEl.querySelector(".gallery-thumbs");
    const thumbBtns = [...galleryEl.querySelectorAll("[data-gallery-idx]")];
    const dirBtns = [...galleryEl.querySelectorAll("[data-gallery-dir]")];
    let currentIdx = 0;

    function go(nextIdx, announce = true) {
        currentIdx = ((nextIdx % items.length) + items.length) % items.length;
        const slide = items[currentIdx];
        if (mainImg) {
            mainImg.hidden = false;
            mainImg.src = slide.src;
            mainImg.alt = slide.alt;
        }
        if (zoomBtn) {
            zoomBtn.dataset.galleryCurrent = String(currentIdx);
            zoomBtn.dataset.lightboxSrc = slide.src;
            zoomBtn.dataset.lightboxTitle = slide.title;
            zoomBtn.dataset.lightboxAlt = slide.alt;
            zoomBtn.dataset.lightboxAuthor = slide.author;
            zoomBtn.dataset.lightboxUrl = slide.url;
            zoomBtn.dataset.lightboxLicense = slide.license;
            zoomBtn.dataset.lightboxLicensename = slide.licenseName;
        }
        if (counterEl) counterEl.textContent = `${currentIdx + 1} / ${items.length}`;
        if (noteEl) {
            noteEl.textContent = slide.note || "";
            noteEl.hidden = !slide.note;
        }
        if (creditEl) {
            creditEl.hidden = false;
            renderCreditLine(creditEl, slide);
        }
        for (const btn of thumbBtns) {
            const active = Number(btn.dataset.galleryIdx) === currentIdx;
            btn.setAttribute("aria-current", String(active));
        }
        const activeThumb = thumbBtns[currentIdx];
        if (thumbsWrap && activeThumb) {
            const left = activeThumb.offsetLeft - thumbsWrap.clientWidth / 2 + activeThumb.offsetWidth / 2;
            const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
            thumbsWrap.scrollTo({ left: Math.max(0, left), behavior: reduced ? "auto" : "smooth" });
        }
        if (announce && statusEl) {
            statusEl.textContent = IS_TA
                ? `படம் ${currentIdx + 1} / ${items.length}: ${slide.note ? slide.note + ", " : ""}${slide.author}`
                : `Photo ${currentIdx + 1} of ${items.length}: ${slide.note ? slide.note + ", " : ""}photographed by ${slide.author}`;
        }
    }

    galleryControllers.set(galleryEl, { items, getIdx: () => currentIdx, go });

    for (const btn of thumbBtns) {
        btn.addEventListener("click", () => go(Number(btn.dataset.galleryIdx), true));
    }
    for (const btn of dirBtns) {
        btn.addEventListener("click", () => go(currentIdx + Number(btn.dataset.galleryDir), true));
    }
}

/* Home Interactive Flagship Butterfly Spotlight Switcher */
const spotlightBox = document.querySelector("[data-spotlight]");
if (spotlightBox) {
    const items = JSON.parse(spotlightBox.dataset.spotlight || "[]");
    const buttons = [...document.querySelectorAll("[data-spot-idx]")];
    const imgEl = spotlightBox.querySelector("[data-spot-img]");
    const zoomEl = spotlightBox.querySelector("[data-spot-zoom]");
    const creditEl = spotlightBox.querySelector("[data-spot-credit]");
    const famEl = spotlightBox.querySelector("[data-spot-family]");
    const nameEl = spotlightBox.querySelector("[data-spot-name]");
    const sciEl = spotlightBox.querySelector("[data-spot-sci]");
    const headEl = spotlightBox.querySelector("[data-spot-headline]");
    const wingEl = spotlightBox.querySelector("[data-spot-wingspan]");
    const hostEl = spotlightBox.querySelector("[data-spot-hosts]");
    const rangeEl = spotlightBox.querySelector("[data-spot-range]");
    const linkEl = spotlightBox.querySelector("[data-spot-link]");

    function selectSpotlight(idx) {
        const entry = items[idx];
        if (!entry) return;
        for (const b of buttons) b.setAttribute("aria-pressed", String(Number(b.dataset.spotIdx) === idx));
        imgEl.src = entry.src;
        imgEl.alt = entry.alt;
        zoomEl.dataset.lightboxSrc = entry.src;
        zoomEl.dataset.lightboxTitle = `${entry.name} (${entry.scientific})`;
        zoomEl.dataset.lightboxAlt = entry.alt;
        zoomEl.dataset.lightboxAuthor = entry.author;
        zoomEl.dataset.lightboxUrl = entry.authorUrl;
        zoomEl.dataset.lightboxLicense = entry.licenseUrl;
        zoomEl.dataset.lightboxLicensename = entry.licenseName;

        creditEl.replaceChildren();
        if (entry.authorUrl) {
            const a1 = document.createElement("a");
            a1.href = entry.authorUrl;
            a1.target = "_blank";
            a1.rel = "noopener noreferrer";
            a1.textContent = entry.author;
            creditEl.append(a1);
        } else {
            creditEl.append(entry.author);
        }
        if (entry.licenseName) {
            creditEl.append(" · ");
            if (entry.licenseUrl) {
                const a2 = document.createElement("a");
                a2.href = entry.licenseUrl;
                a2.target = "_blank";
                a2.rel = "noopener noreferrer";
                a2.textContent = entry.licenseName;
                creditEl.append(a2);
            } else {
                creditEl.append(entry.licenseName);
            }
        }

        famEl.textContent = entry.family;
        nameEl.textContent = entry.name;
        sciEl.textContent = entry.scientific;
        headEl.textContent = entry.headline;
        wingEl.textContent = entry.wingspan;
        if (Array.isArray(entry.hostsParts) && entry.hostsParts.length) {
            hostEl.replaceChildren();
            for (const [text, isItalic] of entry.hostsParts) {
                if (isItalic) {
                    const iEl = document.createElement("i");
                    iEl.textContent = text;
                    hostEl.append(iEl);
                } else {
                    hostEl.append(text);
                }
            }
        } else {
            hostEl.textContent = entry.hosts;
        }
        rangeEl.textContent = entry.range;
        linkEl.href = entry.url;
    }

    for (const btn of buttons) {
        btn.addEventListener("click", () => selectSpotlight(Number(btn.dataset.spotIdx)));
    }
}

/* Accessible Tabs Controller (tabs + search-hidden-content compliant) */
for (const tabRoot of document.querySelectorAll("[data-tabs]")) {
    const tablist = tabRoot.querySelector('[role="tablist"]');
    const tabs = [...tablist.querySelectorAll('[role="tab"]')];
    const panels = [...tabRoot.querySelectorAll('[role="tabpanel"]')];

    function activateTab(selectedTab, moveFocus = false) {
        const selectedId = selectedTab.id;
        tabs.forEach((t, i) => {
            const active = t === selectedTab;
            t.setAttribute("aria-selected", String(active));
            t.tabIndex = active ? 0 : -1;
            const p = panels[i];
            if (p) {
                if (active) {
                    p.hidden = false;
                    p.tabIndex = 0;
                } else {
                    p.hidden = "until-found";
                    p.removeAttribute("tabindex");
                }
            }
        });
        selectedTab.scrollIntoView({ block: "nearest", inline: "nearest" });
        if (moveFocus) selectedTab.focus();
    }

    tabs.forEach((tab, idx) => {
        tab.tabIndex = tab.getAttribute("aria-selected") === "true" ? 0 : -1;
        tab.addEventListener("click", () => activateTab(tab, false));
        tab.addEventListener("keydown", (e) => {
            let nextIdx = -1;
            if (e.key === "ArrowRight") nextIdx = (idx + 1) % tabs.length;
            else if (e.key === "ArrowLeft") nextIdx = (idx - 1 + tabs.length) % tabs.length;
            else if (e.key === "Home") nextIdx = 0;
            else if (e.key === "End") nextIdx = tabs.length - 1;
            if (nextIdx >= 0) {
                e.preventDefault();
                activateTab(tabs[nextIdx], true);
            }
        });
        const panel = panels[idx];
        if (panel) {
            panel.addEventListener("beforematch", () => activateTab(tab, false));
        }
    });
}

/* My Tamil Nadu Life List Tracker (localStorage) */
const LIFE_KEY = "tnbs-spotted-v1";
function readSpotted() {
    try {
        const raw = JSON.parse(localStorage.getItem(LIFE_KEY) || "[]");
        return new Set(Array.isArray(raw) ? raw : []);
    } catch {
        return new Set();
    }
}
function writeSpotted(set) {
    try {
        localStorage.setItem(LIFE_KEY, JSON.stringify([...set]));
    } catch {
        // Ignore storage restrictions
    }
}

let spottedSet = readSpotted();
function syncSpottedButtons() {
    for (const btn of document.querySelectorAll("[data-spot-btn]")) {
        const sci = btn.dataset.sci;
        const isSpotted = spottedSet.has(sci);
        const isDetail = btn.classList.contains("button");
        btn.setAttribute("aria-pressed", String(isSpotted));
        btn.textContent = isSpotted
            ? (isDetail
                ? (IS_TA ? "✓ தமிழ்நாட்டில் பார்த்தேன்" : "✓ Spotted in Tamil Nadu")
                : (IS_TA ? "✓ பார்த்தேன்" : "✓ Spotted"))
            : (isDetail
                ? (IS_TA ? "+ தமிழ்நாட்டில் பார்த்ததாகக் குறி" : "+ Mark as spotted in Tamil Nadu")
                : (IS_TA ? "+ பார்த்தேன்" : "+ Spotted"));
    }
    const bar = document.querySelector("[data-lifelist-bar]");
    if (bar) {
        const countEl = bar.querySelector("[data-lifelist-count]");
        const progEl = bar.querySelector("progress");
        const count = spottedSet.size;
        const pct = Math.round((count / 329) * 100);
        if (countEl) {
            countEl.textContent = IS_TA
                ? `${count} / 329 பார்த்தவை (${pct}%)`
                : `${count} / 329 spotted (${pct}%)`;
        }
        if (progEl) progEl.value = count;
    }
}
syncSpottedButtons();

document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-spot-btn]");
    if (!btn) return;
    const sci = btn.dataset.sci;
    if (!sci) return;
    if (spottedSet.has(sci)) spottedSet.delete(sci);
    else spottedSet.add(sci);
    writeSpotted(spottedSet);
    syncSpottedButtons();
    if (typeof window.__tnbsGuideRefresh === "function") window.__tnbsGuideRefresh(true);
});

/* Enhanced Field Guide Search, Family Pills, Subfamily/Tag Filter, Life List, Sort & Pagination */
const guide = document.querySelector("[data-guide]");
if (guide) {
    const form = guide.querySelector("form");
    const search = form.elements.q;
    const family = form.elements.family;
    const subfamily = form.elements.subfamily;
    const tag = form.elements.tag;
    const sort = form.elements.sort;
    const familyPills = [...guide.querySelectorAll("[data-family-pill]")];
    const spottedFilterBtn = guide.querySelector("[data-spotted-filter]");
    const copyLifeBtn = guide.querySelector("[data-copy-lifelist]");
    const surpriseBtn = guide.querySelector("[data-surprise-btn]");
    const lifeStatus = guide.querySelector("[data-lifelist-status]");
    const container = guide.querySelector("[data-cards]");
    const cards = [...container.children].map((element) => ({
        element,
        id: Number(element.dataset.id),
        name: element.dataset.name || "",
        sci: element.dataset.sci || "",
        family: element.dataset.family || "",
        subfamily: element.dataset.subfamily || "",
        rawSci: element.querySelector("[data-spot-btn]")?.dataset.sci || "",
        hasPhoto: element.dataset.photo === "1",
        photoCount: Number(element.dataset.gallery || 0),
        hasTamilName: Boolean(element.querySelector(".tamil-name, .en-subname")),
        hasMemberPhoto: element.dataset.member === "1",
        hasProfile: element.dataset.profile === "1",
        validated: element.dataset.validated === "1",
        tags: new Set((element.dataset.tags || "").split(" ").filter(Boolean)),
        hasBv: Boolean((element.dataset.bv || "").trim()),
        terms: normalize(element.dataset.terms)
    }));
    const subfamilyToFamily = new Map();
    for (const card of cards) {
        if (card.subfamily && card.family) subfamilyToFamily.set(card.subfamily, card.family);
    }
    const viewButtons = [...guide.querySelectorAll("[data-view]")];
    const status = guide.querySelector("[data-results]");
    const empty = guide.querySelector("[data-empty]");
    const more = guide.querySelector("[data-more]");
    const pageSize = 24;
    let limit = pageSize;
    let view = "grid";

    function syncFamilyPills() {
        for (const p of familyPills) {
            p.setAttribute("aria-pressed", String(p.dataset.familyPill === family.value));
        }
    }

    function updateUrl() {
        const url = new URL(location.href);
        const params = {
            q: search.value.trim(),
            family: family.value,
            subfamily: subfamily.value,
            tag: tag.value,
            sort: sort.value !== "featured" ? sort.value : "",
            view: view === "list" ? "list" : ""
        };
        for (const [key, value] of Object.entries(params)) {
            if (value) url.searchParams.set(key, value);
            else url.searchParams.delete(key);
        }
        history.replaceState(null, "", url);
    }

    function matchesTag(card, chosen) {
        if (!chosen) return true;
        if (chosen === "spotted") return spottedSet.has(card.rawSci);
        if (chosen === "photo") return card.hasPhoto;
        if (chosen === "gallery") return card.photoCount >= 2;
        if (chosen === "tamil") return card.hasTamilName;
        if (chosen === "member") return card.hasMemberPhoto;
        if (chosen === "profile") return card.hasProfile;
        if (chosen === "unvalidated") return !card.validated;
        if (chosen === "bv") return card.hasBv;
        return card.tags.has(chosen);
    }

    function compareCards(a, b, mode) {
        if (mode === "id") return a.id - b.id;
        if (mode === "name") return a.name.localeCompare(b.name);
        if (mode === "sci") return a.sci.localeCompare(b.sci);
        return Number(b.hasPhoto) - Number(a.hasPhoto)
            || Number(b.hasMemberPhoto) - Number(a.hasMemberPhoto)
            || Number(b.hasProfile) - Number(a.hasProfile)
            || a.name.localeCompare(b.name);
    }

    let currentSort = "";
    let orderedCards = cards;

    function render() {
        const tokens = normalize(search.value).split(" ").filter(Boolean);
        const mode = sort.value || "featured";
        const needsReorder = mode !== currentSort;
        if (needsReorder) {
            orderedCards = [...cards].sort((a, b) => compareCards(a, b, mode));
            currentSort = mode;
        }
        let total = 0;
        const fragment = needsReorder ? document.createDocumentFragment() : null;
        for (const card of orderedCards) {
            const matches = (!family.value || card.family === family.value)
                && (!subfamily.value || card.subfamily === subfamily.value)
                && matchesTag(card, tag.value)
                && tokens.every((term) => card.terms.includes(term));
            if (matches) total += 1;
            card.element.hidden = !matches || total > limit;
            if (fragment) fragment.append(card.element);
        }
        if (fragment) container.replaceChildren(fragment);
        container.classList.toggle("list", view === "list");
        for (const button of viewButtons) {
            button.setAttribute("aria-pressed", String(button.dataset.view === view));
        }
        if (spottedFilterBtn) spottedFilterBtn.setAttribute("aria-pressed", String(tag.value === "spotted"));
        syncFamilyPills();
        status.textContent = IS_TA
            ? (total > limit ? `மொத்தம் ${total} இனங்களில் ${limit} காட்டப்படுகிறது` : `${total} பட்டாம்பூச்சி இனங்கள்`)
            : (total > limit ? `Showing ${limit} of ${total} matching species` : `${total} ${total === 1 ? "species match" : "species"}`);
        empty.hidden = total !== 0;
        more.hidden = limit >= total;
    }

    window.__tnbsGuideRefresh = (fromSpotToggle = false) => {
        if (fromSpotToggle && tag.value !== "spotted") return;
        render();
    };

    function filterChanged() {
        limit = pageSize;
        render();
        updateUrl();
    }

    const initial = new URLSearchParams(location.search);
    search.value = initial.get("q") || "";
    const setIfValid = (sel, val) => {
        if (val && [...sel.options].some((o) => o.value === val)) sel.value = val;
    };
    setIfValid(family, initial.get("family"));
    setIfValid(subfamily, initial.get("subfamily"));
    setIfValid(tag, initial.get("tag"));
    setIfValid(sort, initial.get("sort"));
    if (initial.get("view") === "list") view = "list";

    for (const pill of familyPills) {
        pill.addEventListener("click", () => {
            family.value = pill.dataset.familyPill;
            if (family.value && subfamily.value && subfamilyToFamily.get(subfamily.value) !== family.value) {
                subfamily.value = "";
            }
            filterChanged();
        });
    }

    if (spottedFilterBtn) {
        spottedFilterBtn.addEventListener("click", () => {
            tag.value = tag.value === "spotted" ? "" : "spotted";
            filterChanged();
        });
    }

    if (copyLifeBtn) {
        copyLifeBtn.addEventListener("click", async () => {
            const list = [...spottedSet].sort();
            const text = list.length
                ? (IS_TA
                    ? `எனது தமிழ்நாடு பட்டாம்பூச்சிப் பட்டியல் (${list.length}/329):\n` + list.join(", ")
                    : `My Tamil Nadu Butterfly Life List (${list.length}/329):\n` + list.join(", "))
                : (IS_TA
                    ? "இன்னும் எந்தப் பட்டாம்பூச்சியும் குறிக்கப்படவில்லை. அட்டைகளில் '+ பார்த்தேன்' என்பதைச் சொடுக்கவும்."
                    : "No butterflies marked as spotted yet. Click '+ Spotted' on any species card to build your list.");
            try {
                await navigator.clipboard.writeText(text);
                if (lifeStatus) {
                    lifeStatus.textContent = list.length
                        ? (IS_TA ? `${list.length} இனங்கள் நகலெடுக்கப்பட்டன.` : `Copied ${list.length} spotted species to clipboard.`)
                        : text;
                }
            } catch {
                if (lifeStatus) lifeStatus.textContent = text;
            }
        });
    }

    if (surpriseBtn) {
        surpriseBtn.addEventListener("click", () => {
            const pool = cards.filter((c) => !family.value || c.family === family.value);
            const pick = pool[Math.floor(Math.random() * pool.length)];
            const href = pick?.element.querySelector("h3 a")?.href;
            if (href) location.href = href;
        });
    }

    form.addEventListener("submit", (event) => event.preventDefault());
    form.addEventListener("input", filterChanged);
    form.addEventListener("change", (event) => {
        if (event.target === family && family.value && subfamily.value && subfamilyToFamily.get(subfamily.value) !== family.value) {
            subfamily.value = "";
        } else if (event.target === subfamily && subfamily.value) {
            const parentFamily = subfamilyToFamily.get(subfamily.value);
            if (family.value && parentFamily && family.value !== parentFamily) {
                family.value = parentFamily;
            }
        }
        filterChanged();
    });
    form.addEventListener("reset", () => queueMicrotask(filterChanged));
    more.addEventListener("click", () => {
        const before = limit;
        limit += pageSize;
        render();
        const visible = [...container.children].filter((el) => !el.hidden);
        visible[before]?.querySelector("h3 a")?.focus({ preventScroll: true });
    });
    for (const button of viewButtons) {
        button.addEventListener("click", () => {
            view = button.dataset.view;
            render();
            updateUrl();
        });
    }
    render();
}

/* Interactive Archive Filters (News, Press & Searchable Magazine Index) */
for (const archive of document.querySelectorAll("[data-records]")) {
    const form = archive.querySelector("form");
    const searchInput = archive.querySelector('input[type="search"]');
    const selects = [...archive.querySelectorAll("select")];
    const hiddenCat = archive.querySelector('input[name="category"]');
    const catPills = [...archive.querySelectorAll("[data-cat-pill]")];
    const records = [...archive.querySelectorAll("[data-record]")];
    const status = archive.querySelector("[data-status]");

    function filter() {
        const tokens = searchInput ? normalize(searchInput.value).split(" ").filter(Boolean) : [];
        let total = 0;
        for (const record of records) {
            const matchSelects = selects.every((input) => !input.value || input.value === record.dataset[input.name]);
            const matchCat = !hiddenCat || !hiddenCat.value || hiddenCat.value === record.dataset.category;
            const matchText = !tokens.length || tokens.every((t) => normalize(record.dataset.terms).includes(t));
            const show = matchSelects && matchCat && matchText;
            record.hidden = !show;
            if (show) total += 1;
            const det = record.querySelector("details.mag-articles");
            if (det && tokens.length && show) det.open = true;
            else if (det && !tokens.length) det.open = false;
        }
        status.textContent = IS_TA
            ? (total ? `${total} பதிவுகள் காட்டப்படுகின்றன` : "இந்த வடிகட்டிக்குப் பொருந்தும் பதிவுகள் இல்லை.")
            : (total ? `Showing ${total} ${total === 1 ? "entry" : "entries"}` : "No entries match these filters.");
    }

    for (const pill of catPills) {
        pill.addEventListener("click", () => {
            const val = pill.dataset.catPill;
            if (hiddenCat) hiddenCat.value = val;
            for (const p of catPills) p.setAttribute("aria-pressed", String(p === pill));
            filter();
        });
    }
    if (form) {
        form.addEventListener("submit", (e) => e.preventDefault());
        form.addEventListener("input", filter);
        form.addEventListener("change", filter);
        form.addEventListener("reset", () => {
            if (hiddenCat) hiddenCat.value = "";
            for (const p of catPills) p.setAttribute("aria-pressed", String(p.dataset.catPill === ""));
            queueMicrotask(filter);
        });
    } else {
        for (const input of selects) input.addEventListener("change", filter);
    }
    filter();
}

/* Live Wikimedia Commons photo lookup for rare unpictured species */
const lookup = document.querySelector("[data-photo-lookup]");
if (lookup) {
    const button = lookup.querySelector("button");
    const status = lookup.querySelector("[data-lookup-status]");
    const display = lookup.querySelector("[data-lookup-result]");
    const names = JSON.parse(lookup.dataset.photoLookup);

    async function wikiRequest(host, params, signal) {
        const url = new URL(`https://${host}/w/api.php`);
        url.search = new URLSearchParams({ format: "json", formatversion: "2", origin: "*", ...params });
        const response = await fetch(url, { signal });
        if (!response.ok) throw new Error("Wikimedia request failed");
        return response.json();
    }

    function showPhoto(file, credit, license) {
        const figure = document.createElement("figure");
        const image = document.createElement("img");
        const caption = document.createElement("figcaption");
        const source = document.createElement("a");
        const terms = document.createElement("a");
        figure.className = "photo-large";
        caption.className = "credit";
        source.href = file.descriptionurl;
        source.target = "_blank";
        source.rel = "noopener noreferrer";
        source.textContent = credit;
        terms.href = license;
        terms.target = "_blank";
        terms.rel = "noopener noreferrer";
        terms.textContent = file.extmetadata.LicenseShortName.value;
        image.alt = `Reference image for ${names[0]}`;
        image.src = file.thumburl || file.url;
        caption.append(source, " · ", terms);
        figure.append(image, caption);
        display.replaceChildren(figure);
        watchImage(image, () => {
            display.replaceChildren();
            status.textContent = IS_TA
                ? "படத்தை ஏற்ற முடியவில்லை. Commons தேடல் இணைப்பைப் பயன்படுத்தலாம்."
                : "The image could not load. The Commons search link is available.";
            button.disabled = false;
        });
    }

    button.addEventListener("click", async () => {
        button.disabled = true;
        status.textContent = IS_TA ? "Wikimedia Commons சரிபார்க்கப்படுகிறது..." : "Checking Wikimedia Commons...";
        try {
            const signal = AbortSignal.timeout(10000);
            const article = await wikiRequest("en.wikipedia.org", {
                action: "query", titles: names.join("|"), redirects: 1,
                prop: "pageprops|pageimages", ppprop: "wikibase_item", piprop: "name", pilicense: "free"
            }, signal);
            const candidate = article.query?.pages.find((page) => page.pageimage && page.pageprops?.wikibase_item);
            if (!candidate) throw new Error("No suitable reference image");
            const entityId = candidate.pageprops.wikibase_item;
            const response = await wikiRequest("www.wikidata.org", {
                action: "wbgetclaims", entity: entityId, property: "P225"
            }, signal);
            const sameTaxon = response.claims?.P225?.some((claim) => names.includes(claim.mainsnak.datavalue?.value));
            if (!sameTaxon) throw new Error("Taxon could not be verified");
            const commons = await wikiRequest("commons.wikimedia.org", {
                action: "query", titles: "File:" + candidate.pageimage, prop: "imageinfo",
                iiprop: "url|extmetadata|mime", iiurlwidth: 640,
                iiextmetadatafilter: "Artist|LicenseShortName|LicenseUrl"
            }, signal);
            const file = commons.query?.pages[0]?.imageinfo?.[0];
            const metadata = file?.extmetadata;
            const creditMarkup = metadata?.Artist?.value;
            const license = metadata?.LicenseUrl?.value?.replace(/^http:/, "https:");
            const validImage = /^https:\/\/upload\.wikimedia\.org\//.test(file?.thumburl || file?.url)
                && /^https:\/\/commons\.wikimedia\.org\//.test(file?.descriptionurl);
            if (!validImage || !/^image\/(?:jpeg|png|webp)$/.test(file?.mime) || !creditMarkup ||
                !metadata?.LicenseShortName?.value || !/^https:\/\/creativecommons\.org\/(?:licenses\/(?:by|by-sa)\/[234]\.\d(?:\/[a-z-]+)?|publicdomain\/(?:zero|mark)\/1\.0)\/?$/.test(license)) {
                throw new Error("Open license and attribution could not be verified");
            }
            const credit = new DOMParser().parseFromString(creditMarkup, "text/html").body.textContent.trim();
            if (!credit) throw new Error("No attribution available");
            status.textContent = "";
            showPhoto(file, credit, license);
        } catch {
            status.textContent = IS_TA
                ? "தகுதியான உரிமத்துடன் கூடிய சரியான படம் கிடைக்கவில்லை. Commons தேடல் இணைப்பை முயற்சிக்கவும்."
                : "No exact-match photo with verified reuse details was returned. Try the Commons search link.";
            button.disabled = false;
        }
    });
}

/* Butterfly Vision (butterflyvision.in) AI Identification Integration */
const bvWidget = document.querySelector("[data-bv-widget]");
if (bvWidget) {
    const speciesIndex = JSON.parse(bvWidget.dataset.speciesIndex || "{}");
    const modelButtons = [...bvWidget.querySelectorAll("[data-bv-model]")];
    const modelDesc = bvWidget.querySelector("[data-bv-model-desc]");
    const dropZone = bvWidget.querySelector("[data-bv-drop]");
    const fileInput = document.getElementById("bv-file");
    const previewBox = bvWidget.querySelector("[data-bv-preview]");
    const previewImg = document.getElementById("bv-preview-img");
    const fileMeta = document.getElementById("bv-file-meta");
    const status = bvWidget.querySelector("[data-bv-status]");
    const resultsBox = bvWidget.querySelector("[data-bv-results]");
    const runBtn = bvWidget.querySelector("[data-bv-run]");

    let activeModel = "wg";
    let selectedFile = null;
    let selectedDataUrl = "";

    for (const btn of modelButtons) {
        btn.addEventListener("click", () => {
            activeModel = btn.dataset.bvModel;
            for (const b of modelButtons) b.setAttribute("aria-pressed", String(b === btn));
            modelDesc.textContent = activeModel === "wg"
                ? (IS_TA
                    ? "தமிழ்நாடு மலைப்பகுதிகள், காடுகள் மற்றும் மேற்குத் தொடர்ச்சி மலை ஆய்வுகளுக்குப் பரிந்துரைக்கப்படுவது (300+ இனங்கள்)."
                    : "Recommended for Tamil Nadu hills, forests, and Western Ghats surveys (300+ species).")
                : (IS_TA
                    ? "இந்தியா முழுவதுமான பரந்த இனத் தொகுப்பு (800+ இனங்கள், 923+ உயிரினப் பிரிவுகள்)."
                    : "Broader national coverage across India (800+ species, 923+ taxa supported).");
        });
    }

    function resizeForUpload(dataUrl, fileType, fileName, maxSize) {
        return new Promise((resolve, reject) => {
            const outType = ["image/jpeg", "image/png", "image/webp"].includes(fileType) ? fileType : "image/jpeg";
            const img = new Image();
            img.onload = () => {
                let w = img.width;
                let h = img.height;
                if (w > h && w > maxSize) {
                    h = Math.round(h * (maxSize / w));
                    w = maxSize;
                } else if (h >= w && h > maxSize) {
                    w = Math.round(w * (maxSize / h));
                    h = maxSize;
                }
                const canvas = document.createElement("canvas");
                canvas.width = w;
                canvas.height = h;
                canvas.getContext("2d").drawImage(img, 0, 0, w, h);
                canvas.toBlob((blob) => {
                    if (!blob) reject(new Error("Canvas preparation failed"));
                    else resolve(new File([blob], fileName, { type: outType }));
                }, outType, 0.9);
            };
            img.onerror = () => reject(new Error("Could not read image"));
            img.src = dataUrl;
        });
    }

    function matchTnbsSpecies(className) {
        const parts = String(className || "").split(" - ").map((s) => s.trim().toLowerCase());
        for (const candidate of [parts[1], parts[0], String(className || "").toLowerCase()]) {
            if (candidate && speciesIndex[candidate]) return speciesIndex[candidate];
        }
        return null;
    }

    function handleSelectedFile(file) {
        if (!file || !file.type.startsWith("image/") || file.type === "image/svg+xml") {
            status.textContent = IS_TA
                ? "தயவுசெய்து JPG, PNG, அல்லது WebP பட்டாம்பூச்சிப் படத்தைத் தேர்ந்தெடுக்கவும்."
                : "Please choose a JPG, PNG, or WebP butterfly photograph.";
            return;
        }
        selectedFile = file;
        resultsBox.replaceChildren();
        const reader = new FileReader();
        reader.onload = () => {
            selectedDataUrl = String(reader.result || "");
            const probe = new Image();
            probe.onload = () => {
                previewImg.src = selectedDataUrl;
                const sizeNote = probe.width >= 600 && probe.height >= 600
                    ? (IS_TA ? "Butterfly Vision AI-க்கு உகந்த தெளிவுத்திறன்." : "Optimal resolution for Butterfly Vision.")
                    : (IS_TA ? "குறிப்பு: 600x600px மேல் உள்ள படங்கள் துல்லியமான முடிவைத் தரும்." : "Tip: Images wider than 600x600px yield higher recognition accuracy.");
                fileMeta.textContent = `${file.name} (${probe.width}x${probe.height}px) · ${sizeNote}`;
                previewBox.hidden = false;
                status.textContent = IS_TA
                    ? "படம் தயாராக உள்ளது. 'AI அடையாளம் இயக்கு' அல்லது butterflyvision.in திறக்கவும்."
                    : "Photo staged. Click 'Run AI identification' or open directly on butterflyvision.in.";
                runBtn.disabled = false;
            };
            probe.src = selectedDataUrl;
        };
        reader.readAsDataURL(file);
    }

    ["dragenter", "dragover"].forEach((evt) => {
        dropZone.addEventListener(evt, (e) => {
            e.preventDefault();
            dropZone.classList.add("dragover");
        });
    });
    ["dragleave", "drop"].forEach((evt) => {
        dropZone.addEventListener(evt, (e) => {
            e.preventDefault();
            dropZone.classList.remove("dragover");
        });
    });
    dropZone.addEventListener("drop", (e) => {
        const file = e.dataTransfer?.files?.[0];
        if (file) handleSelectedFile(file);
    });
    fileInput.addEventListener("click", () => {
        fileInput.value = "";
    });
    fileInput.addEventListener("change", (e) => {
        const file = e.target.files?.[0];
        if (file) handleSelectedFile(file);
    });

    runBtn.addEventListener("click", async () => {
        if (!selectedFile || !selectedDataUrl) return;
        runBtn.disabled = true;
        const modelLabel = IS_TA
            ? (activeModel === "wg" ? "மேற்குத் தொடர்ச்சி மலை" : "அகில இந்திய")
            : (activeModel === "wg" ? "Western Ghats" : "All India");
        status.textContent = IS_TA
            ? `படம் Butterfly Vision (${modelLabel} மாதிரி) தளத்திற்கு அனுப்பப்படுகிறது...`
            : `Sending resized photo to Butterfly Vision (${modelLabel} model)...`;
        resultsBox.replaceChildren();

        try {
            const resized = await resizeForUpload(selectedDataUrl, selectedFile.type, selectedFile.name, 1024);
            const formData = new FormData();
            formData.append("image", resized);
            formData.append("model_type", activeModel);

            const response = await fetch("https://butterflyvision.in/analyze", {
                method: "POST",
                body: formData,
                signal: AbortSignal.timeout(15000)
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            const preds = Array.isArray(data?.predictions) ? data.predictions : [];
            if (!preds.length) {
                status.textContent = IS_TA
                    ? "உறுதியான இனப் பொருத்தம் கிடைக்கவில்லை. butterflyvision.in தளத்தில் படத்தை அருகில் வெட்டி (crop) முயற்சிக்கவும்."
                    : "Butterfly Vision returned no confident species matches. Try cropping closer on butterflyvision.in.";
                runBtn.disabled = false;
                return;
            }
            status.textContent = IS_TA ? "முதன்மை Butterfly Vision AI கணிப்புகள்:" : "Top Butterfly Vision AI predictions:";
            const list = document.createElement("div");
            list.className = "bv-pred-list";
            for (const pred of preds.slice(0, 5)) {
                const rawConf = parseFloat(pred.probability);
                const conf = Number.isFinite(rawConf) ? Math.min(100, Math.max(0, rawConf)) : 0;
                const item = document.createElement("div");
                item.className = "bv-pred";
                const head = document.createElement("div");
                head.className = "bv-pred-head";
                const title = document.createElement("span");
                title.textContent = pred.class_name || (IS_TA ? "அறியப்படாத இனம்" : "Unknown species");
                const pct = document.createElement("span");
                pct.textContent = `${conf.toFixed(1)}%`;
                head.append(title, pct);

                const bar = document.createElement("div");
                bar.className = "bv-bar";
                const fill = document.createElement("div");
                fill.className = "bv-bar-fill";
                fill.style.width = `${conf}%`;
                bar.append(fill);
                item.append(head, bar);

                const matched = matchTnbsSpecies(pred.class_name);
                if (matched) {
                    const linkP = document.createElement("p");
                    linkP.className = "caption";
                    linkP.style.marginTop = ".4rem";
                    const bvWidgetEl = document.querySelector("[data-bv-widget]");
                    const bvPrefix = bvWidgetEl?.dataset.langPrefix || "../";
                    const a = document.createElement("a");
                    a.href = bvPrefix + matched[2] + "index.html";
                    a.textContent = IS_TA
                        ? `TNBS கள வழிகாட்டி: ${matched[0]} (${matched[1]}) →`
                        : `Open TNBS Field Guide: ${matched[0]} (${matched[1]}) →`;
                    linkP.append(a);
                    item.append(linkP);
                }
                list.append(item);
            }
            resultsBox.replaceChildren(list);
            runBtn.disabled = false;
        } catch {
            status.textContent = IS_TA
                ? "வெளிப்புறத் தளக் கொள்கை (CORS) காரணமாக நேரடி அனுப்புதல் தடுக்கப்பட்டுள்ளது. 'butterflyvision.in ↗' பொத்தானைச் சொடுக்கிப் படத்தைப் பதிவேற்றவும்."
                : "Direct browser submission to butterflyvision.in is restricted by the remote server's CORS policy from external domains. Use 'Open on butterflyvision.in ↗' to upload and crop your staged photo directly on the Butterfly Vision app.";
            const fallback = document.createElement("div");
            fallback.className = "notice";
            const p = document.createElement("p");
            p.textContent = IS_TA
                ? `உங்கள் படம் தயார்! புதிய தாவலில் butterflyvision.in தளத்தைத் திறந்து, ${modelLabel} மாதிரியைத் தேர்ந்தெடுத்துப் படத்தைச் செதுக்கி (crop) அடையாளம் காணவும்.`
                : "Your photo is ready! Open butterflyvision.in in a new tab, choose the "
                + modelLabel
                + " model, and use Butterfly Vision's built-in crop tool for best accuracy.";
            fallback.append(p);
            resultsBox.replaceChildren(fallback);
            runBtn.disabled = false;
        }
    });
}

/* Interactive Multi-Mode Butterfly Quiz */
const quiz = document.querySelector("[data-quiz]");
if (quiz) {
    const find = (name) => quiz.querySelector(`[data-${name}]`);
    const startScreen = find("quiz-start");
    const gameScreen = find("quiz-game");
    const finishScreen = find("finish");
    const modeButtons = [...startScreen.querySelectorAll("[data-mode]")];
    const familySelect = document.getElementById("quiz-family");
    const diffSelect = document.getElementById("quiz-difficulty");
    const countSelect = document.getElementById("quiz-count");
    const startBtn = find("start-btn");
    const startStatus = find("start-status");
    const bestBox = find("quiz-best");

    const stepBadge = find("step");
    const scoreBadge = find("hud-score");
    const streakBadge = find("hud-streak");
    const timerBadge = find("hud-timer");
    const progressEl = quiz.querySelector("progress");
    const btn5050 = find("lifeline-5050");
    const btnHint = find("lifeline-hint");
    const hintBox = find("hint-box");
    const promptEl = find("question");
    const photoPreview = find("quiz-photo");
    const optionsEl = find("options");
    const feedbackEl = find("feedback");
    const nextBtn = find("next");
    const retryMissedBtn = find("retry-missed");
    const shareBtn = find("share-score");
    const shareStatus = find("share-status");
    const reviewList = find("review");
    const reviewFilterBtns = [...finishScreen.querySelectorAll("[data-review-filter]")];

    const quizSrc = quiz.dataset.quizSrc || "../assets/quiz-data.json";
    const guideBase = quiz.dataset.guideBase || "../butterflies/";
    const TA_FAM_NAMES = {
        Papilionidae: "பாப்பிலியோனிடே",
        Pieridae: "பியரிடே",
        Nymphalidae: "நிம்பாலிடே",
        Lycaenidae: "லைசீனிடே",
        Hesperiidae: "ஹெஸ்பெரிடே",
        Riodinidae: "ரியோடினிடே"
    };
    const STORAGE_KEY = "tnbs-quiz-stats-v1";
    let quizData = null;
    let selectedMode = "photo";
    let questions = [];
    let results = [];
    let points = 0;
    let streak = 0;
    let bestStreak = 0;
    let timerId = null;
    let secondsLeft = 20;
    let hintUsedThisQ = false;
    let lifeline5050Left = 2;
    let hintsLeft = 2;
    let answeredCurrent = false;

    function shuffle(items) {
        const arr = [...items];
        for (let i = arr.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [arr[i], arr[j]] = [arr[j], arr[i]];
        }
        return arr;
    }

    function loadStats() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
        } catch {
            return null;
        }
    }

    function saveStats(accuracyPct, sessionPoints, sessionStreak) {
        try {
            const prev = loadStats() || { played: 0, bestScore: 0, bestPct: 0, bestStreak: 0 };
            const updated = {
                played: prev.played + 1,
                bestScore: Math.max(prev.bestScore, sessionPoints),
                bestPct: Math.max(prev.bestPct, accuracyPct),
                bestStreak: Math.max(prev.bestStreak, sessionStreak)
            };
            localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
            renderBestStats(updated);
        } catch {
            // Storage unavailable
        }
    }

    function renderBestStats(stats = loadStats()) {
        if (!stats || !stats.played) {
            bestBox.hidden = true;
            return;
        }
        bestBox.hidden = false;
        bestBox.textContent = IS_TA
            ? `சிறந்த சாதனை: ${stats.bestPct}% · அதிக மதிப்பெண்: ${stats.bestScore} புள்ளிகள் · உயர் தொடர்: ${stats.bestStreak} (${stats.played} சுற்றுகள்)`
            : `Personal best: ${stats.bestPct}% · Top score: ${stats.bestScore} pts · Best streak: ${stats.bestStreak} (${stats.played} ${stats.played === 1 ? "round" : "rounds"})`;
    }
    renderBestStats();

    for (const btn of modeButtons) {
        btn.addEventListener("click", () => {
            selectedMode = btn.dataset.mode;
            for (const b of modeButtons) b.setAttribute("aria-pressed", String(b === btn));
        });
    }

    async function ensureQuizData() {
        if (quizData) return quizData;
        startStatus.textContent = IS_TA
            ? "தமிழ்நாடு பட்டாம்பூச்சி வினாடி வினாத் தொகுப்பு ஏற்றப்படுகிறது..."
            : "Loading verified Tamil Nadu butterfly quiz bank...";
        const resp = await fetch(quizSrc, { signal: AbortSignal.timeout(6000) });
        if (!resp.ok) throw new Error("Failed to load quiz data");
        quizData = await resp.json();
        startStatus.textContent = "";
        return quizData;
    }

    function pickDistractors(target, pool, field, difficulty) {
        const sameFamily = pool.filter((s) => s[field] !== target[field] && s.family === target.family);
        const otherFamily = pool.filter((s) => s[field] !== target[field] && s.family !== target.family);
        let source = difficulty === "expert" && sameFamily.length >= 3 ? sameFamily : [...sameFamily, ...otherFamily];
        if (difficulty === "expert" && sameFamily.length < 3) {
            source = [...sameFamily, ...shuffle(otherFamily)];
        }
        const unique = [];
        const seen = new Set([target[field]]);
        for (const item of shuffle(source)) {
            if (!seen.has(item[field])) {
                seen.add(item[field]);
                unique.push(item[field]);
                if (unique.length === 3) break;
            }
        }
        return unique;
    }

    function makePhotoQuestion(entry, pool, difficulty) {
        const distractors = pickDistractors(entry, pool, "name", difficulty);
        const famLabel = IS_TA ? (TA_FAM_NAMES[entry.family] || entry.family) : entry.family;
        return {
            type: "photo",
            text: IS_TA
                ? `இந்தத் தமிழ்நாடு பட்டாம்பூச்சியை அடையாளம் காண்க (${famLabel}):`
                : `Identify this Tamil Nadu butterfly (${entry.family}):`,
            choices: [entry.name, ...distractors],
            correct: entry.name,
            note: `${entry.name} (${entry.scientific}): ${entry.clue}`,
            hint: `${famLabel} (${entry.subfamily}). ${entry.clue}`,
            slug: entry.slug,
            media: entry
        };
    }

    function makeScientificQuestion(entry, pool, difficulty) {
        const distractors = pickDistractors(entry, pool, "scientific", difficulty);
        const famLabel = IS_TA ? (TA_FAM_NAMES[entry.family] || entry.family) : entry.family;
        return {
            type: "scientific",
            text: IS_TA
                ? `${entry.name} பட்டாம்பூச்சியின் அறிவியல் பெயர் என்ன?`
                : `What is the scientific name of the ${entry.name}?`,
            choices: [entry.scientific, ...distractors],
            correct: entry.scientific,
            note: IS_TA
                ? `${entry.name}, ${famLabel} (${entry.subfamily}) குடும்பத்தைச் சேர்ந்தது; இதன் அறிவியல் பெயர் ${entry.scientific}.`
                : `${entry.name} belongs to family ${entry.family} (${entry.subfamily}) and carries the scientific name ${entry.scientific}.`,
            hint: IS_TA
                ? `குடும்பம்: ${famLabel} (${entry.subfamily}). "${entry.scientific.split(" ")[0]}" எனத் தொடங்கும்.`
                : `Family: ${entry.family} (${entry.subfamily}). Starts with "${entry.scientific.split(" ")[0]}".`,
            slug: entry.slug,
            media: quizData.photos.find((p) => p.slug === entry.slug) || null
        };
    }

    function makeFactQuestion(factRow) {
        const [qText, choices, explanation, slug, family, hint] = factRow;
        const famLabel = IS_TA ? (TA_FAM_NAMES[family] || family) : family;
        return {
            type: "fact",
            text: qText,
            choices,
            correct: choices[0],
            note: explanation,
            hint: hint || (IS_TA ? `தொடர்புடைய குடும்பம்: ${famLabel}.` : `Related family: ${family}.`),
            slug,
            media: null
        };
    }

    function buildQuestionSet(mode, fam, difficulty, count) {
        const photoPoolAll = quizData.photos;
        const speciesPoolAll = quizData.species;
        const photoPool = fam ? photoPoolAll.filter((p) => p.family === fam) : photoPoolAll;
        const speciesPool = fam ? speciesPoolAll.filter((s) => s.family === fam) : speciesPoolAll;
        const factPool = fam
            ? quizData.facts.filter((f) => f[4] === fam || f[4] === "All")
            : quizData.facts;

        const out = [];
        function topUpPhotos(usedSlugs) {
            for (const extra of shuffle(photoPool)) {
                if (out.length >= count) break;
                if (usedSlugs.has(extra.slug)) continue;
                usedSlugs.add(extra.slug);
                out.push(makePhotoQuestion(extra, photoPoolAll, difficulty));
            }
        }
        if (mode === "photo") {
            for (const item of shuffle(photoPool).slice(0, count)) {
                out.push(makePhotoQuestion(item, photoPoolAll, difficulty));
            }
        } else if (mode === "scientific") {
            for (const item of shuffle(speciesPool).slice(0, count)) {
                out.push(makeScientificQuestion(item, speciesPoolAll, difficulty));
            }
        } else if (mode === "rapid") {
            const pCount = Math.ceil(count * 0.65);
            const chosenPhotos = shuffle(photoPool).slice(0, pCount);
            const usedSlugs = new Set(chosenPhotos.map((p) => p.slug));
            const chosenFacts = shuffle(factPool.filter((f) => !usedSlugs.has(f[3]))).slice(0, count - chosenPhotos.length);
            for (const p of chosenPhotos) out.push(makePhotoQuestion(p, photoPoolAll, difficulty));
            for (const f of chosenFacts) out.push(makeFactQuestion(f));
            topUpPhotos(usedSlugs);
        } else {
            const pCount = Math.min(Math.ceil(count / 2), photoPool.length);
            const chosenPhotos = shuffle(photoPool).slice(0, pCount);
            const usedSlugs = new Set(chosenPhotos.map((p) => p.slug));
            const chosenFacts = shuffle(factPool.filter((f) => !usedSlugs.has(f[3]))).slice(0, count - pCount);
            for (const p of chosenPhotos) out.push(makePhotoQuestion(p, photoPoolAll, difficulty));
            for (const f of chosenFacts) out.push(makeFactQuestion(f));
            topUpPhotos(usedSlugs);
        }
        return shuffle(out).slice(0, count);
    }

    function stopTimer() {
        if (timerId) {
            clearInterval(timerId);
            timerId = null;
        }
    }

    function updateHud() {
        const idx = results.length;
        stepBadge.textContent = IS_TA
            ? `கேள்வி ${Math.min(idx + 1, questions.length)} / ${questions.length}`
            : `Question ${Math.min(idx + 1, questions.length)} of ${questions.length}`;
        scoreBadge.textContent = IS_TA ? `மதிப்பெண்: ${points}` : `Score: ${points}`;
        streakBadge.textContent = IS_TA
            ? `தொடர்ச்சி: ${streak}${streak >= 3 ? " 🔥" : ""}`
            : `Streak: ${streak}${streak >= 3 ? " 🔥" : ""}`;
        const pct = Math.round((idx / questions.length) * 100);
        progressEl.value = pct;
        progressEl.style.setProperty("--quiz-hue", String(120 + Math.round((pct / 100) * 35)));
        btn5050.textContent = IS_TA
            ? `50:50 இரண்டை நீக்கு (${lifeline5050Left})`
            : `50:50 Eliminate two (${lifeline5050Left})`;
        btn5050.disabled = answeredCurrent || lifeline5050Left <= 0;
        btnHint.textContent = IS_TA ? `களக் குறிப்பு (${hintsLeft})` : `Field hint (${hintsLeft})`;
        btnHint.disabled = answeredCurrent || hintUsedThisQ || hintsLeft <= 0;
    }

    function recordAnswer(q, chosenText, timedOut = false) {
        if (answeredCurrent) return;
        answeredCurrent = true;
        stopTimer();

        const isCorrect = !timedOut && chosenText === q.correct;
        if (isCorrect) {
            streak += 1;
            bestStreak = Math.max(bestStreak, streak);
            const streakBonus = (streak - 1) * 25;
            const speedBonus = selectedMode === "rapid" ? secondsLeft * 5 : 0;
            points += 100 + streakBonus + speedBonus;
        } else {
            streak = 0;
        }
        results.push({ question: q, correct: isCorrect, chosen: chosenText });

        for (const btn of optionsEl.children) {
            btn.disabled = true;
            const label = btn.dataset.choice;
            if (label === q.correct) btn.dataset.state = "correct";
            else if (!isCorrect && label === chosenText) btn.dataset.state = "incorrect";
        }
        btn5050.disabled = true;
        btnHint.disabled = true;

        feedbackEl.replaceChildren();
        const badge = document.createElement("strong");
        badge.textContent = isCorrect
            ? (IS_TA ? "✓ சரி! " : "✓ Correct! ")
            : timedOut
                ? (IS_TA ? `⏱ நேரம் முடிந்தது! விடை: ${q.correct}. ` : `⏱ Time's up! Answer: ${q.correct}. `)
                : (IS_TA ? `✗ சரியான விடை: ${q.correct}. ` : `✗ Answer: ${q.correct}. `);
        feedbackEl.append(badge, q.note);
        if (q.slug) {
            feedbackEl.append(" ");
            const spLink = document.createElement("a");
            spLink.href = `${guideBase}${q.slug}/index.html`;
            spLink.textContent = IS_TA ? "இனப் பக்கத்தைப் பார் →" : "Inspect species page →";
            feedbackEl.append(spLink);
        }

        if (q.media && !photoPreview.hidden && q.media.url) {
            const cap = photoPreview.querySelector("figcaption");
            if (cap && !cap.dataset.linked) {
                cap.dataset.linked = "1";
                const orig = document.createElement("a");
                orig.href = q.media.url;
                orig.target = "_blank";
                orig.rel = "noopener noreferrer";
                orig.textContent = IS_TA ? "மூலப் புகைப்பட ஆதாரம்" : "Original photo source";
                cap.append(" · ", orig);
            }
        }
        scoreBadge.textContent = IS_TA ? `மதிப்பெண்: ${points}` : `Score: ${points}`;
        streakBadge.textContent = IS_TA
            ? `தொடர்ச்சி: ${streak}${streak >= 3 ? " 🔥" : ""}`
            : `Streak: ${streak}${streak >= 3 ? " 🔥" : ""}`;
        nextBtn.hidden = false;
        nextBtn.textContent = results.length === questions.length
            ? (IS_TA ? "இறுதித் தகுதி & மீளாய்வைப் பார் →" : "See final rank & review →")
            : (IS_TA ? "அடுத்த கேள்வி →" : "Next question →");
        nextBtn.focus();
    }

    function renderQuestion() {
        stopTimer();
        answeredCurrent = false;
        hintUsedThisQ = false;
        hintBox.hidden = true;
        hintBox.textContent = "";
        const q = questions[results.length];

        updateHud();
        promptEl.textContent = q.text;
        photoPreview.replaceChildren();
        photoPreview.hidden = !q.media;

        if (q.media) {
            const figure = document.createElement("figure");
            figure.className = "photo-large";
            const zoomBtn = document.createElement("button");
            zoomBtn.type = "button";
            zoomBtn.className = "photo-zoom";
            zoomBtn.dataset.lightboxSrc = q.media.fullSrc || q.media.src;
            zoomBtn.dataset.lightboxTitle = IS_TA ? "வினாடி வினா புகைப்படம்" : "Quiz specimen preview";
            zoomBtn.dataset.lightboxAlt = IS_TA ? "அடையாளத்திற்கான பெரிதாக்கப்பட்ட பார்வை" : "Enlarged view for identification";
            zoomBtn.dataset.lightboxAuthor = q.media.author;
            zoomBtn.dataset.lightboxUrl = q.media.url;
            zoomBtn.dataset.lightboxLicense = q.media.license;
            zoomBtn.dataset.lightboxLicensename = q.media.licenseName;
            zoomBtn.setAttribute("aria-label", IS_TA ? "புகைப்படத்தை பெரிதாக்கவும்" : "Enlarge butterfly photograph for closer inspection");

            const img = document.createElement("img");
            img.src = q.media.src;
            img.alt = IS_TA ? "அடையாளம் காண வேண்டிய பட்டாம்பூச்சிப் படம்." : "Butterfly photograph for identification.";
            const hint = document.createElement("span");
            hint.className = "zoom-hint";
            hint.setAttribute("aria-hidden", "true");
            hint.textContent = IS_TA ? "பெரிதாக்கு" : "Zoom";
            zoomBtn.append(img, hint);

            const cap = document.createElement("figcaption");
            cap.className = "credit";
            cap.append(q.media.author);
            if (q.media.licenseName) {
                cap.append(" · ");
                if (q.media.license) {
                    const lic = document.createElement("a");
                    lic.href = q.media.license;
                    lic.target = "_blank";
                    lic.rel = "noopener noreferrer";
                    lic.textContent = q.media.licenseName;
                    cap.append(lic);
                } else {
                    cap.append(q.media.licenseName);
                }
            }

            figure.append(zoomBtn, cap);
            photoPreview.append(figure);
            watchImage(img, () => { photoPreview.hidden = true; });
        }

        feedbackEl.textContent = "";
        nextBtn.hidden = true;
        optionsEl.replaceChildren();
        const shuffledChoices = shuffle(q.choices);
        shuffledChoices.forEach((choiceText, idx) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.dataset.choice = choiceText;
            const num = document.createElement("span");
            num.className = "option-num";
            num.textContent = String(idx + 1);
            const txt = document.createElement("span");
            txt.textContent = choiceText;
            btn.append(num, txt);
            btn.addEventListener("click", () => recordAnswer(q, choiceText, false), { once: true });
            optionsEl.append(btn);
        });

        if (selectedMode === "rapid") {
            secondsLeft = 20;
            timerBadge.hidden = false;
            timerBadge.classList.remove("urgent");
            timerBadge.textContent = `${secondsLeft}s`;
            timerId = setInterval(() => {
                secondsLeft -= 1;
                timerBadge.textContent = `${secondsLeft}s`;
                if (secondsLeft <= 5) timerBadge.classList.add("urgent");
                if (secondsLeft <= 0) recordAnswer(q, "", true);
            }, 1000);
        } else {
            timerBadge.hidden = true;
        }
        promptEl.focus();
    }

    function startRound(customQuestions = null) {
        const count = Number(countSelect.value) || 8;
        questions = customQuestions || buildQuestionSet(selectedMode, familySelect.value, diffSelect.value, count);
        if (!questions.length) {
            startStatus.textContent = IS_TA
                ? "அந்தக் குடும்ப வடிகட்டியில் போதுமான கேள்விகள் இல்லை. அனைத்து குடும்பங்களையும் தேர்வு செய்க."
                : "Not enough questions matched that family filter. Try All families.";
            return;
        }
        results = [];
        points = 0;
        streak = 0;
        bestStreak = 0;
        lifeline5050Left = 2;
        hintsLeft = 2;
        startScreen.hidden = true;
        finishScreen.hidden = true;
        gameScreen.hidden = false;
        renderQuestion();
    }

    startBtn.addEventListener("click", async () => {
        startBtn.disabled = true;
        try {
            await ensureQuizData();
            startRound();
        } catch {
            startStatus.textContent = IS_TA
                ? "வினாடி வினா தரவை ஏற்ற முடியவில்லை. HTTP வழியே தளத்தைத் திறக்கவும்."
                : "Could not load quiz data. Serve the site over HTTP (e.g., GitHub Pages or python -m http.server) to play.";
        } finally {
            startBtn.disabled = false;
        }
    });

    btn5050.addEventListener("click", () => {
        if (answeredCurrent || lifeline5050Left <= 0) return;
        const q = questions[results.length];
        const wrongButtons = shuffle([...optionsEl.children].filter((b) => !b.disabled && b.dataset.choice !== q.correct));
        for (const b of wrongButtons.slice(0, 2)) {
            b.disabled = true;
            b.dataset.eliminated = "true";
        }
        lifeline5050Left -= 1;
        updateHud();
    });

    btnHint.addEventListener("click", () => {
        if (answeredCurrent || hintUsedThisQ || hintsLeft <= 0) return;
        const q = questions[results.length];
        hintBox.textContent = IS_TA ? `களக் குறிப்பு: ${q.hint}` : `Field hint: ${q.hint}`;
        hintBox.hidden = false;
        hintUsedThisQ = true;
        hintsLeft -= 1;
        updateHud();
    });

    function finishRound() {
        stopTimer();
        progressEl.value = 100;
        gameScreen.hidden = true;
        finishScreen.hidden = false;
        const correctCount = results.filter((r) => r.correct).length;
        const pct = Math.round((correctCount / questions.length) * 100);
        const rank = IS_TA
            ? (pct >= 90 ? "மூத்த பட்டாம்பூச்சி ஆய்வாளர்"
                : pct >= 75 ? "சிறப்பு இயற்கை ஆர்வலர்"
                : pct >= 50 ? "பட்டாம்பூச்சி ஆய்வாளர்"
                : "வளரும் இயற்கை ஆர்வலர்")
            : (pct >= 90 ? "Master Lepidopterist"
                : pct >= 75 ? "Senior Field Naturalist"
                : pct >= 50 ? "Butterfly Explorer"
                : "Budding Naturalist");

        saveStats(pct, points, bestStreak);
        find("score").textContent = IS_TA
            ? `${questions.length} இல் ${correctCount} சரி (${pct}%)`
            : `${correctCount} out of ${questions.length} correct (${pct}%)`;
        find("rank").textContent = IS_TA ? `பெற்ற தகுதி: ${rank}` : `Rank earned: ${rank}`;
        find("summary").textContent = IS_TA
            ? "கீழே உள்ள விடைகளை மீளாய்வு செய்யவும், தவறிய கேள்விகளை மீண்டும் முயலவும், அல்லது TNBS கள வழிகாட்டியில் இனங்களைப் பார்க்கவும்."
            : "Review every sighting below, retry missed questions, or explore species profiles in the TNBS field guide.";

        find("end-stats").innerHTML = IS_TA
            ? `
            <div><dt>மதிப்பெண்</dt><dd>${points} புள்ளிகள்</dd></div>
            <div><dt>துல்லியம்</dt><dd>${pct}%</dd></div>
            <div><dt>உயர் தொடர்</dt><dd>${bestStreak}</dd></div>
            <div><dt>வகை</dt><dd>${selectedMode.toUpperCase()}</dd></div>`
            : `
            <div><dt>Score</dt><dd>${points} pts</dd></div>
            <div><dt>Accuracy</dt><dd>${pct}%</dd></div>
            <div><dt>Best streak</dt><dd>${bestStreak}</dd></div>
            <div><dt>Mode</dt><dd>${selectedMode.toUpperCase()}</dd></div>`;

        const missedCount = results.filter((r) => !r.correct).length;
        retryMissedBtn.hidden = missedCount === 0;
        shareStatus.textContent = "";

        function renderReview(filterMode) {
            for (const b of reviewFilterBtns) b.setAttribute("aria-pressed", String(b.dataset.reviewFilter === filterMode));
            reviewList.replaceChildren();
            for (const r of results) {
                if (filterMode === "missed" && r.correct) continue;
                const li = document.createElement("li");
                li.className = "review-item" + (r.correct ? "" : " missed");
                const prefix = r.correct ? "✓ " : "✗ ";
                li.append(prefix + r.question.note + " ");
                if (r.question.slug) {
                    const a = document.createElement("a");
                    a.href = `${guideBase}${r.question.slug}/index.html`;
                    a.textContent = IS_TA ? "கள வழிகாட்டிப் பக்கம் →" : "Field guide page →";
                    li.append(a);
                }
                reviewList.append(li);
            }
            if (filterMode === "missed" && !reviewList.children.length) {
                const li = document.createElement("li");
                li.className = "review-item";
                li.textContent = IS_TA
                    ? "தவறிய கேள்விகள் எதுவும் இல்லை. முழுமையான வெற்றி!"
                    : "No missed questions. Perfect round!";
                reviewList.append(li);
            }
        }
        renderReview("all");
        for (const b of reviewFilterBtns) {
            b.onclick = () => renderReview(b.dataset.reviewFilter);
        }
        find("score").focus();
    }

    nextBtn.addEventListener("click", () => {
        if (results.length < questions.length) renderQuestion();
        else finishRound();
    });

    retryMissedBtn.addEventListener("click", () => {
        const missedQuestions = results.filter((r) => !r.correct).map((r) => r.question);
        if (missedQuestions.length) startRound(shuffle(missedQuestions));
    });

    shareBtn.addEventListener("click", async () => {
        const correctCount = results.filter((r) => r.correct).length;
        const pct = Math.round((correctCount / questions.length) * 100);
        const summaryText = IS_TA
            ? `TNBS தமிழ்நாடு பட்டாம்பூச்சி வினாடி வினா (${selectedMode}): ${correctCount}/${questions.length} (${pct}%) · ${points} புள்ளிகள் · உயர் தொடர் ${bestStreak}!`
            : `TNBS Tamil Nadu Butterfly Quiz (${selectedMode}): ${correctCount}/${questions.length} (${pct}%) · ${points} pts · Best streak ${bestStreak}!`;
        try {
            await navigator.clipboard.writeText(summaryText);
            shareStatus.textContent = IS_TA
                ? `நகலெடுக்கப்பட்டது: "${summaryText}"`
                : `Copied to clipboard: "${summaryText}"`;
        } catch {
            shareStatus.textContent = summaryText;
        }
    });

    find("restart").addEventListener("click", () => {
        stopTimer();
        finishScreen.hidden = true;
        gameScreen.hidden = true;
        startScreen.hidden = false;
        startScreen.querySelector("button").focus();
    });

    document.addEventListener("keydown", (e) => {
        if (gameScreen.hidden || lightbox?.open) return;
        if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
        if (["1", "2", "3", "4"].includes(e.key) && !answeredCurrent) {
            const idx = Number(e.key) - 1;
            const targetBtn = optionsEl.children[idx];
            if (targetBtn && !targetBtn.disabled) targetBtn.click();
        } else if (e.key.toLowerCase() === "h" && !answeredCurrent && !btnHint.disabled) {
            btnHint.click();
        } else if (e.key === "Enter" && answeredCurrent && !nextBtn.hidden && document.activeElement?.tagName !== "A") {
            e.preventDefault();
            nextBtn.click();
        }
    });
}

/* Live iNaturalist Project #47280 Feed Refresh (Sightings Hub) */
const inatLive = document.querySelector("[data-inat-live]");
if (inatLive) {
    let speciesIndex = {};
    try {
        speciesIndex = JSON.parse(inatLive.dataset.speciesIndex || "{}");
    } catch {
        speciesIndex = {};
    }
    const obsEl = inatLive.querySelector("[data-inat-obs]");
    const rgEl = inatLive.querySelector("[data-inat-rg]");
    const sppEl = inatLive.querySelector("[data-inat-spp]");
    const observersEl = inatLive.querySelector("[data-inat-observers]");
    const statusEl = document.querySelector("[data-inat-status]");
    const recentEl = document.querySelector("[data-inat-recent]");

    const fetchInatJson = async (url) => {
        const resp = await fetch(url, { signal: AbortSignal.timeout(7000) });
        if (!resp.ok) throw new Error("iNaturalist API HTTP " + resp.status);
        return resp.json();
    };

    (async () => {
        const base = "https://api.inaturalist.org/v1";
        const [obsRes, rgRes, sppRes, obsvRes, recRes] = await Promise.allSettled([
            fetchInatJson(`${base}/observations?project_id=47280&per_page=0`),
            fetchInatJson(`${base}/observations?project_id=47280&quality_grade=research&per_page=0`),
            fetchInatJson(`${base}/observations/species_counts?project_id=47280&per_page=0`),
            fetchInatJson(`${base}/observations/observers?project_id=47280&per_page=0`),
            fetchInatJson(`${base}/observations?project_id=47280&photos=true&order_by=observed_on&order=desc&per_page=12`)
        ]);

        let updatedAny = false;
        if (obsRes.status === "fulfilled" && typeof obsRes.value.total_results === "number" && obsEl) {
            obsEl.textContent = obsRes.value.total_results.toLocaleString("en-US");
            updatedAny = true;
        }
        if (rgRes.status === "fulfilled" && typeof rgRes.value.total_results === "number" && rgEl) {
            rgEl.textContent = rgRes.value.total_results.toLocaleString("en-US");
            updatedAny = true;
        }
        if (sppRes.status === "fulfilled" && typeof sppRes.value.total_results === "number" && sppEl) {
            sppEl.textContent = sppRes.value.total_results.toLocaleString("en-US");
            updatedAny = true;
        }
        if (obsvRes.status === "fulfilled" && typeof obsvRes.value.total_results === "number" && observersEl) {
            observersEl.textContent = obsvRes.value.total_results.toLocaleString("en-US");
            updatedAny = true;
        }

        if (recRes.status === "fulfilled" && Array.isArray(recRes.value.results) && recentEl) {
            const frag = document.createDocumentFragment();
            for (const obs of recRes.value.results) {
                const sci = obs.taxon?.name || "";
                const matched = sci ? speciesIndex[sci.toLowerCase()] : null;
                const disp = matched?.name || obs.taxon?.preferred_common_name || sci || (IS_TA ? "பட்டாம்பூச்சி பதிவு" : "Butterfly sighting");
                const obsUrl = `https://www.inaturalist.org/observations/${encodeURIComponent(obs.id)}`;
                const photoUrl = obs.photos?.[0]?.url ? obs.photos[0].url.replace("/square.", "/medium.") : "";

                const card = document.createElement("article");
                card.className = "card sighting-card";
                if (photoUrl) {
                    const media = document.createElement("div");
                    media.className = "media";
                    const img = document.createElement("img");
                    img.src = photoUrl;
                    img.alt = disp;
                    img.loading = "lazy";
                    img.decoding = "async";
                    media.append(img);
                    if (obs.observed_on) {
                        const badge = document.createElement("span");
                        badge.className = "photo-count-badge";
                        badge.textContent = obs.observed_on;
                        media.append(badge);
                    }
                    card.append(media);
                }

                const body = document.createElement("div");
                body.className = "card-body";
                const meta = document.createElement("p");
                meta.className = "card-meta";
                meta.textContent = obs.place_guess || (IS_TA ? "தமிழ்நாடு" : "Tamil Nadu");

                const h3 = document.createElement("h3");
                const spLink = document.createElement("a");
                spLink.textContent = disp;
                if (matched?.href) {
                    spLink.href = matched.href;
                } else {
                    spLink.href = obsUrl;
                    spLink.target = "_blank";
                    spLink.rel = "noopener noreferrer";
                }
                h3.append(spLink);

                const sciP = document.createElement("p");
                sciP.className = "scientific";
                sciP.textContent = sci;

                const capP = document.createElement("p");
                capP.className = "caption";
                const userLink = document.createElement("a");
                userLink.href = obsUrl;
                userLink.target = "_blank";
                userLink.rel = "noopener noreferrer";
                userLink.textContent = `${obs.user?.name || obs.user?.login || "iNaturalist observer"} · iNaturalist ↗`;
                capP.append(userLink);

                body.append(meta, h3, sciP, capP);
                card.append(body);
                frag.append(card);
            }
            if (frag.childNodes.length) {
                recentEl.replaceChildren(frag);
                updatedAny = true;
            }
        }

        if (statusEl) {
            statusEl.textContent = updatedAny
                ? (IS_TA
                    ? "நேரடி iNaturalist திட்டம் #47280 தரவு இப்போது ஒத்திசைக்கப்பட்டது."
                    : "Live iNaturalist Project #47280 feed synced just now.")
                : (IS_TA
                    ? "கட்டமைப்பு நேரப் பதிவுக் காட்சி (நேரடி iNaturalist இணைப்பு இப்போது கிடைக்கவில்லை)."
                    : "Showing build-time snapshot (live iNaturalist refresh unavailable offline).");
        }
    })();
}

/* Interactive Leaflet + iNaturalist Heatmap/Points Map */
let leafletLoaderPromise = null;
function loadLeaflet() {
    if (window.L) return Promise.resolve(window.L);
    if (leafletLoaderPromise) return leafletLoaderPromise;
    leafletLoaderPromise = new Promise((resolve, reject) => {
        if (!document.querySelector('link[data-leaflet-css]')) {
            const css = document.createElement("link");
            css.rel = "stylesheet";
            css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
            css.crossOrigin = "";
            css.dataset.leafletCss = "1";
            document.head.append(css);
        }
        const script = document.createElement("script");
        script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
        script.crossOrigin = "";
        script.onload = () => {
            if (window.L) resolve(window.L);
            else {
                leafletLoaderPromise = null;
                reject(new Error("Leaflet loaded without window.L"));
            }
        };
        script.onerror = () => {
            leafletLoaderPromise = null;
            reject(new Error("Failed to load Leaflet"));
        };
        document.head.append(script);
    });
    return leafletLoaderPromise;
}

for (const mapBox of document.querySelectorAll("[data-inat-map]")) {
    const projectId = mapBox.dataset.project || "47280";
    const taxonId = mapBox.dataset.taxonId || "";
    const isLazy = mapBox.dataset.lazyMap === "true";
    const canvas = mapBox.querySelector("[data-map-canvas]");
    const statusEl = mapBox.querySelector("[data-map-status]");
    const loadBtn = mapBox.querySelector("[data-load-map]");
    const layerBtns = [...mapBox.querySelectorAll("[data-map-layer]")];

    let activeMode = mapBox.dataset.mapMode || "heatmap";
    let map = null;
    let heatmapLayer = null;
    let pointsLayer = null;
    let currentOverlay = null;
    let initPromise = null;

    const syncButtons = (mode) => {
        mapBox.dataset.mapMode = mode;
        for (const btn of layerBtns) {
            btn.setAttribute("aria-pressed", String(btn.dataset.mapLayer === mode));
        }
    };

    const applyLayer = (mode) => {
        if (!map || !heatmapLayer || !pointsLayer) return;
        const target = mode === "points" ? pointsLayer : heatmapLayer;
        if (currentOverlay && currentOverlay !== target) {
            map.removeLayer(currentOverlay);
        }
        if (currentOverlay !== target) {
            target.addTo(map);
            currentOverlay = target;
        }
        if (statusEl) {
            statusEl.textContent = mode === "points"
                ? (IS_TA
                    ? "புள்ளிப் பதிவுகள்: தனிப்பட்ட தமிழ்நாடு அவதானிப்பு இடங்கள் (iNaturalist + OpenStreetMap)."
                    : "Observation points from iNaturalist Project #47280 over OpenStreetMap.")
                : (IS_TA
                    ? "வெப்ப வரைபடம்: தமிழ்நாடு திட்டம் #47280 அவதானிப்பு அடர்த்தி (iNaturalist + OpenStreetMap)."
                    : "Density heatmap from iNaturalist Project #47280 over OpenStreetMap.");
        }
    };

    const initMap = () => {
        if (initPromise) return initPromise;
        initPromise = (async () => {
            if (loadBtn) {
                loadBtn.closest(".inat-map-placeholder")?.remove();
            }
            if (canvas) canvas.hidden = false;
            if (statusEl) {
                statusEl.textContent = IS_TA ? "வரைபடம் ஏற்றப்படுகிறது..." : "Loading interactive map...";
            }
            try {
                const L = await loadLeaflet();
                map = L.map(canvas, { scrollWheelZoom: false }).setView([11.12, 78.66], 7);
                L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
                    attribution: "&copy; OpenStreetMap contributors · &copy; iNaturalist",
                    maxZoom: 19
                }).addTo(map);

                const params = `project_id=${encodeURIComponent(projectId)}${taxonId ? `&taxon_id=${encodeURIComponent(taxonId)}` : ""}`;
                heatmapLayer = L.tileLayer(`https://api.inaturalist.org/v1/colored_heatmap/{z}/{x}/{y}.png?${params}`, {
                    maxZoom: 19,
                    opacity: 0.85
                });
                pointsLayer = L.tileLayer(`https://api.inaturalist.org/v1/points/{z}/{x}/{y}.png?${params}`, {
                    maxZoom: 19,
                    opacity: 0.92
                });
                applyLayer(activeMode);
                setTimeout(() => map.invalidateSize(), 60);
            } catch {
                initPromise = null;
                if (statusEl) {
                    statusEl.textContent = IS_TA
                        ? "வரைபடத்தை ஏற்ற முடியவில்லை; மேலே உள்ள iNaturalist இணைப்பைப் பயன்படுத்தவும்."
                        : "Interactive map could not be loaded offline; use the iNaturalist link above.";
                }
            }
        })();
        return initPromise;
    };

    if (loadBtn) {
        loadBtn.addEventListener("click", () => {
            initMap();
        });
    }
    for (const btn of layerBtns) {
        btn.addEventListener("click", async () => {
            activeMode = btn.dataset.mapLayer || "heatmap";
            syncButtons(activeMode);
            await initMap();
            if (map) applyLayer(activeMode);
        });
    }

    if (!isLazy) {
        if ("IntersectionObserver" in window) {
            const observer = new IntersectionObserver((entries) => {
                if (entries.some((entry) => entry.isIntersecting)) {
                    observer.disconnect();
                    initMap();
                }
            }, { rootMargin: "300px" });
            observer.observe(mapBox);
        } else {
            initMap();
        }
    }
}

for (const enhancement of document.querySelectorAll("[data-enhancement]")) enhancement.hidden = false;
