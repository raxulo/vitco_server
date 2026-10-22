/*
 * FAT / SNF limit boxes of the MCC and VLCC create / edit forms
 * (cow, buffalo and fixed-rate limits), plus the weight MCC sample codes.
 *
 * - A limit accepts digits only: up to 2 digits "." up to 2 digits (max 99.99).
 * - When a minimum equals its maximum, the maximum moves up by 0.1 automatically.
 * - Sample codes (#sample-start, #sample-end) accept digits only, at most 6.
 */
(function () {
    // [minimum id, maximum id]
    const LIMIT_PAIRS = [
        ["cow-min-fat", "cow-max-fat"],
        ["cow-min-snf", "cow-max-snf"],
        ["buffalo-min-fat", "buffalo-max-fat"],
        ["buffalo-min-snf", "buffalo-max-snf"],
        ["fixed-min-fat", "fixed-max-fat"],
        ["fixed-min-snf", "fixed-max-snf"],
    ];
    const LIMIT_IDS = new Set(LIMIT_PAIRS.flat());
    const SAMPLE_IDS = new Set(["sample-start", "sample-end"]);
    const SAMPLE_MAX_DIGITS = 6;
    const LIMIT_MAX = 99.99;

    /** Keep digits and the first "."; at most 2 digits on each side of it. */
    function cleanLimit(value) {
        const text = String(value || "").replace(/[^\d.]/g, "");
        const dot = text.indexOf(".");
        if (dot === -1) return text.slice(0, 2);
        const intPart = text.slice(0, dot).slice(0, 2);
        const decPart = text.slice(dot + 1).replace(/\./g, "").slice(0, 2);
        return `${intPart}.${decPart}`;
    }

    // Capture phase: cleaned before any other handler (e.g. buffalo min FAT sync) reads it
    document.addEventListener("input", (evt) => {
        const el = evt.target;
        if (!el || el.readOnly) return;
        let cleaned = null;
        if (LIMIT_IDS.has(el.id)) cleaned = cleanLimit(el.value);
        else if (SAMPLE_IDS.has(el.id)) cleaned = String(el.value || "").replace(/\D/g, "").slice(0, SAMPLE_MAX_DIGITS);
        if (cleaned !== null && cleaned !== el.value) el.value = cleaned;
    }, true);

    /** Minimum == maximum -> maximum + 0.1 (never above 99.99). */
    function bumpMaxIfEqual(minId, maxId) {
        const min = document.getElementById(minId);
        const max = document.getElementById(maxId);
        if (!min || !max) return;
        const low = parseFloat(min.value);
        const high = parseFloat(max.value);
        if (Number.isNaN(low) || Number.isNaN(high) || Math.abs(low - high) > 1e-9) return;
        const next = Math.min(LIMIT_MAX, Math.round((high + 0.1) * 100) / 100);
        if (next === high) return;
        max.value = next.toFixed(2).replace(/0$/, "");
        // Let dependent fields follow (cow max FAT -> buffalo min FAT)
        max.dispatchEvent(new Event("input", { bubbles: true }));
        max.dispatchEvent(new Event("change", { bubbles: true }));
    }

    // On leaving / changing a limit box (not on every key, so "6" -> "6.5" can be typed)
    document.addEventListener("change", (evt) => {
        const id = evt.target && evt.target.id;
        if (!LIMIT_IDS.has(id)) return;
        for (const [minId, maxId] of LIMIT_PAIRS) {
            if (id === minId || id === maxId) bumpMaxIfEqual(minId, maxId);
        }
        // Buffalo min FAT follows cow max FAT, so re-check the buffalo pair too
        if (id === "cow-max-fat" || id === "cow-min-fat") bumpMaxIfEqual("buffalo-min-fat", "buffalo-max-fat");
    });
})();
