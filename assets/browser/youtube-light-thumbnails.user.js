// ==UserScript==
// @name         YouTube: light thumbnails, full quality on hover
// @namespace    setup-lab
// @version      0.2
// @description  Request YouTube preview images in the small size (mqdefault) instead of the large ones. A decoded 320x180 image costs about four times less memory than 480x360. Hovering a thumbnail loads the original.
// @match        *://*.youtube.com/*
// @grant        none
// @run-at       document-start
// ==/UserScript==
//
// The swap happens at the moment the address is assigned, so the large image is
// never requested at all — rewriting it afterwards would be too late.
(function () {
    'use strict';
    const BIG = /\/(maxresdefault|sddefault|hqdefault|hq720)(_[a-z0-9]+)?\.(jpg|webp)/;
    const original = new WeakMap();

    const shrink = (el, url) => {
        if (typeof url !== 'string' || !url.includes('ytimg.com') || !BIG.test(url)) return url;
        original.set(el, url);
        return url.replace(BIG, '/mqdefault.$3');
    };

    const proto = HTMLImageElement.prototype;
    const srcDesc = Object.getOwnPropertyDescriptor(proto, 'src');
    Object.defineProperty(proto, 'src', {
        configurable: true,
        enumerable: srcDesc.enumerable,
        get() { return srcDesc.get.call(this); },
        set(v) { srcDesc.set.call(this, shrink(this, v)); }
    });

    const srcsetDesc = Object.getOwnPropertyDescriptor(proto, 'srcset');
    const shrinkSet = (el, v) => typeof v === 'string'
        ? v.split(',').map(part => shrink(el, part.trim().split(/\s+/)[0]) + (part.trim().split(/\s+/)[1] ? ' ' + part.trim().split(/\s+/)[1] : '')).join(', ')
        : v;
    Object.defineProperty(proto, 'srcset', {
        configurable: true,
        enumerable: srcsetDesc.enumerable,
        get() { return srcsetDesc.get.call(this); },
        set(v) { srcsetDesc.set.call(this, shrinkSet(this, v)); }
    });

    const setAttr = Element.prototype.setAttribute;
    Element.prototype.setAttribute = function (name, value) {
        if (this instanceof HTMLImageElement) {
            if (name === 'src') value = shrink(this, value);
            else if (name === 'srcset') value = shrinkSet(this, value);
        }
        return setAttr.call(this, name, value);
    };

    // Hovering gives back the full-size image for that one thumbnail.
    document.addEventListener('mouseover', e => {
        const img = e.target?.closest?.('img');
        if (!img) return;
        const full = original.get(img);
        if (full) { original.delete(img); srcDesc.set.call(img, full); }
    }, true);
})();
