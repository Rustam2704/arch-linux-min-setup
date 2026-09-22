// ==UserScript==
// @name         Light images, full quality on hover
// @namespace    setup-lab
// @version      0.2
// @description  Show the smallest available version of responsive images; load the full one when the pointer is over it. Saves both traffic and the memory taken by decoded images.
// @match        *://*/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==
//
// Only touches images that the site itself offers in several sizes (srcset).
// Images with a single source are left alone — nothing is blocked or broken.
(function () {
    'use strict';
    const FULL = 'data-lih-full';

    function smallest(srcset) {
        const items = srcset.split(',').map(s => s.trim()).filter(Boolean).map(s => {
            const parts = s.split(/\s+/);
            const w = /(\d+)w/.exec(parts[1] || '');
            const x = /([\d.]+)x/.exec(parts[1] || '');
            return { url: parts[0], weight: w ? +w[1] : (x ? +x[1] * 1000 : 1000) };
        });
        if (items.length < 2) return null;
        items.sort((a, b) => a.weight - b.weight);
        return items[0].url;
    }

    function shrink(img) {
        if (img.dataset.lihDone || !img.srcset) return;
        const small = smallest(img.srcset);
        if (!small) return;
        img.dataset.lihDone = '1';
        img.setAttribute(FULL, img.currentSrc || img.src || '');
        img.dataset.lihSrcset = img.srcset;
        img.srcset = '';
        img.src = small;
    }

    function restore(img) {
        if (!img.dataset.lihSrcset) return;
        img.srcset = img.dataset.lihSrcset;
        const full = img.getAttribute(FULL);
        if (full) img.src = full;
        delete img.dataset.lihSrcset;
        delete img.dataset.lihDone;
    }

    // --- YouTube: thumbnails come as a single URL whose size is part of the path.
    // Swap the big variants for a smaller one; a decoded 320x180 image costs ~4x less
    // memory than 480x360. Hovering restores the original URL.
    const YT_BIG = /\/(maxresdefault|sddefault|hqdefault|hq720)(_[a-z0-9]+)?\.(jpg|webp)/;
    function ytShrink(img) {
        if (img.dataset.lihYt) return;
        const src = img.src || '';
        if (!/i\.ytimg\.com|ytimg\.com\/vi/.test(src) || !YT_BIG.test(src)) return;
        img.dataset.lihYt = '1';
        img.setAttribute(FULL, src);
        img.src = src.replace(YT_BIG, '/mqdefault.$3');
    }
    function ytRestore(img) {
        if (!img.dataset.lihYt) return;
        const full = img.getAttribute(FULL);
        if (full) { img.src = full; delete img.dataset.lihYt; }
    }

    const scan = root => {
        root.querySelectorAll?.('img[srcset]').forEach(shrink);
        root.querySelectorAll?.('img[src*="ytimg.com"]').forEach(ytShrink);
    };
    scan(document);
    new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => {
        if (n.nodeType === 1) { if (n.tagName === 'IMG') { shrink(n); ytShrink(n); } else scan(n); }
    }))).observe(document.documentElement, { childList: true, subtree: true });

    document.addEventListener('mouseover', e => {
        const img = e.target?.closest?.('img');
        if (img) { restore(img); ytRestore(img); }
    }, true);
})();
