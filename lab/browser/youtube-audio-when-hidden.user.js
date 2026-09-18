// ==UserScript==
// @name         YouTube: drop video quality when the tab is hidden
// @namespace    setup-lab
// @version      0.1
// @description  When you switch away from a YouTube tab the video drops to the smallest quality, so it stops eating memory and CPU while the sound keeps playing. Coming back restores the quality.
// @match        *://*.youtube.com/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==
//
// No add-on does this automatically (the ones on the store are manual switches),
// hence these few lines. Decoding 144p instead of 1080p is what actually frees
// the memory — the audio track is untouched.
(function () {
    'use strict';
    const LOW = 'tiny';
    let saved = null;

    const player = () => document.getElementById('movie_player');

    function toLow() {
        const p = player();
        if (!p || !p.setPlaybackQualityRange || document.pictureInPictureElement) return;
        try {
            if (!saved) saved = p.getPlaybackQuality?.() || 'auto';
            p.setPlaybackQualityRange(LOW, LOW);
            p.setPlaybackQuality?.(LOW);
        } catch (e) { /* YouTube changed its player again — do nothing */ }
    }

    function restore() {
        const p = player();
        if (!p || !p.setPlaybackQualityRange || !saved) return;
        try {
            const want = saved === LOW ? 'auto' : saved;
            p.setPlaybackQualityRange(want === 'auto' ? 'tiny' : want, 'highres');
            p.setPlaybackQuality?.(want);
        } catch (e) { /* ignore */ }
        saved = null;
    }

    document.addEventListener('visibilitychange', () => {
        // fullscreen video keeps playing in the foreground even when the page reports hidden
        if (document.hidden && !document.fullscreenElement) toLow();
        else restore();
    });
})();
