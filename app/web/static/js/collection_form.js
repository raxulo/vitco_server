/*
 * Shared behaviour of the VLCC and MCC milk collection forms (#form-collection).
 *
 * - Milk type is never typed in: it follows the unit's cattle type
 *     Mixed       -> Mixed
 *     Cow/Buffalo -> FAT below the buffalo minimum FAT is Cow, otherwise Buffalo
 *   (form data-cattle-type: "0" Cow/Buffalo, "1" Mixed; data-buffalo-min-fat)
 * - The rate chart follows the farmer's / VLCC's assigned rank: rank N -> R<N>,
 *   and R1 when the rank is outside the chart list.
 * - Amount = quantity x rate, shown next to the rate and in the summary box,
 *   which always describes the entry being typed (it resets with the form).
 * - A save button marked data-require-unit-weight stays disabled until the
 *   supplying unit (#cf-shopid) is selected and a weight (#cf-qty) is entered.
 * - Typed values accept digits only:
 *     weight  (#cf-qty)            at most 6 digits, optional "." with up to 2 decimals
 *     FAT/SNF (#cf-fat, #cf-snf)   up to 2 digits "." up to 2 digits (max 99.99, e.g. 22.55)
 *     cans    (#cf-cans)           whole number
 * - Rate is 0 until both FAT and SNF are entered (and back to 0 when either is
 *   cleared); amount = weight x rate, so a 0 weight keeps the amount at 0.
 */
(function () {
    const MILK_COW = "0";
    const MILK_BUFFALO = "1";
    const MILK_MIXED = "2";

    const byId = (id) => document.getElementById(id);
    const num = (id) => parseFloat(byId(id)?.value);

    /** Set #cf-type from the cattle type / FAT. Returns true when the value changed. */
    function applyAutoMilkType() {
        const form = byId("form-collection");
        const type = byId("cf-type");
        if (!form || !type) return false;

        let next;
        if (form.dataset.cattleType === "1") {
            next = MILK_MIXED;
        } else {
            const fat = num("cf-fat");
            if (isNaN(fat)) return false;
            const buffaloMinFat = parseFloat(form.dataset.buffaloMinFat);
            next = !isNaN(buffaloMinFat) && buffaloMinFat > 0 && fat >= buffaloMinFat ? MILK_BUFFALO : MILK_COW;
        }
        if (type.value === next) return false;
        type.value = next;
        return true;
    }

    /** Pick R<rank> in #cf-ratechart (R1 when the rank is not in the list) and recalculate. */
    function selectRateChartByRank(rank) {
        const select = byId("cf-ratechart");
        if (!select || select.options.length === 0) return;
        const index = parseInt(rank, 10) - 1;
        select.selectedIndex = index >= 0 && index < select.options.length ? index : 0;
        select.dispatchEvent(new Event("change", { bubbles: true }));
    }

    /** Amount next to the rate + the summary box, both for the current entry only. */
    function updateCollectionAmount() {
        const qty = num("cf-qty") || 0;
        const rate = num("cf-rate") || 0;
        const amount = qty * rate;

        const set = (id, value, prop = "innerText") => {
            const el = byId(id);
            if (el) el[prop] = value;
        };
        set("cf-amount", amount ? amount.toFixed(2) : "", "value");
        set("cf-total-hidden", amount.toFixed(2), "value");
        set("cf-total-display", amount.toFixed(2));
        set("lbl-rate", rate.toFixed(2));
        set("lbl-qty", qty.toFixed(2));
    }

    // ---------------------------------------------------------
    // Typed values: digits only, with the allowed length / decimals
    // ---------------------------------------------------------
    const WEIGHT_MAX_DIGITS = 6;

    /** Keep digits and the first "."; cut the integer / decimal parts to the given lengths. */
    function cleanDecimal(value, maxInt, maxDec) {
        let text = String(value || "").replace(/[^\d.]/g, "");
        const dot = text.indexOf(".");
        let intPart = dot === -1 ? text : text.slice(0, dot);
        let decPart = dot === -1 ? null : text.slice(dot + 1).replace(/\./g, "");
        intPart = intPart.slice(0, maxInt);
        if (decPart !== null) decPart = decPart.slice(0, maxDec);
        return decPart === null ? intPart : `${intPart}.${decPart}`;
    }

    /** Weight: at most 6 digits in all, up to 2 of them after the "." (e.g. 123456, 1234.56). */
    function cleanWeight(value) {
        let text = cleanDecimal(value, WEIGHT_MAX_DIGITS, 2);
        const digits = text.replace(".", "");
        const [intPart, decPart] = text.split(".");
        if (decPart === undefined) return text;
        // 6 whole digits leave no room for decimals (or the ".")
        const room = WEIGHT_MAX_DIGITS - intPart.length;
        if (room <= 0) return intPart;
        return digits.length > WEIGHT_MAX_DIGITS ? `${intPart}.${decPart.slice(0, room)}` : text;
    }

    const CLEANERS = {
        "cf-qty": cleanWeight,
        "cf-fat": (v) => cleanDecimal(v, 2, 2),
        "cf-snf": (v) => cleanDecimal(v, 2, 2),
        "cf-cans": (v) => String(v || "").replace(/\D/g, ""),
    };

    // Capture phase: cleaned before the forms' own input handlers (rate, amount) read the value
    document.addEventListener("input", (evt) => {
        const el = evt.target;
        const clean = el && CLEANERS[el.id];
        if (!clean || el.readOnly) return;
        const cleaned = clean(el.value);
        if (cleaned !== el.value) el.value = cleaned;
    }, true);

    // ---------------------------------------------------------
    // Rate: 0 until FAT and SNF are both entered
    // ---------------------------------------------------------
    /** True when FAT and SNF both hold a value above 0. */
    function hasFatAndSnf() {
        return num("cf-fat") > 0 && num("cf-snf") > 0;
    }

    /** Rate back to 0 (and the amount with it). */
    function resetCollectionRate() {
        const rate = byId("cf-rate");
        if (rate) rate.value = "0.00";
        updateCollectionAmount();
    }

    // A rate response that arrives after FAT / SNF was cleared must not bring the rate back
    document.body.addEventListener("htmx:afterSwap", (evt) => {
        const target = evt.detail.target;
        if (target && (target.id === "group-rate" || target.id === "cf-rate") && !hasFatAndSnf()) {
            resetCollectionRate();
        }
    });

    window.hasFatAndSnf = hasFatAndSnf;
    window.resetCollectionRate = resetCollectionRate;

    /** Enable the save button only once the unit is selected and the weight entered. */
    function updateCollectionSaveState() {
        const button = document.querySelector("#form-collection [data-require-unit-weight]");
        if (!button) return;
        const unitSelected = (byId("cf-shopid")?.value || "").trim() !== "";
        const ready = unitSelected && num("cf-qty") > 0;
        button.disabled = !ready;
        button.style.opacity = ready ? "" : "0.55";
        button.style.cursor = ready ? "pointer" : "not-allowed";
        button.title = ready ? "Preview receipt and save collection" : "Select the VLCC and enter the weight first";
    }

    window.applyAutoMilkType = applyAutoMilkType;
    window.selectRateChartByRank = selectRateChartByRank;
    window.updateCollectionAmount = updateCollectionAmount;
    window.updateCollectionSaveState = updateCollectionSaveState;

    // A freshly rendered form (page load, unit change, after save): derive milk type, reset totals
    function initForm() {
        applyAutoMilkType();
        if (!hasFatAndSnf()) resetCollectionRate();
        updateCollectionAmount();
        updateCollectionSaveState();
    }
    document.addEventListener("DOMContentLoaded", initForm);
    document.body.addEventListener("htmx:afterSwap", (evt) => {
        const target = evt.detail.target;
        if (target && (target.id === "form-collection" || target.id === "group-rate" || target.id === "cf-rate")) {
            if (target.id === "form-collection") {
                applyAutoMilkType();
                if (!hasFatAndSnf()) resetCollectionRate();
            }
            updateCollectionAmount();
            updateCollectionSaveState();
        }
    });

    // Capture phase: also catches the non-bubbling events fired when the weight / VLCC
    // are filled in by code (device reading, sample lookup)
    ["input", "change"].forEach((type) => {
        document.addEventListener(type, (evt) => {
            if (evt.target && evt.target.matches && evt.target.matches("#cf-shopid, #cf-qty")) {
                updateCollectionSaveState();
            }
        }, true);
    });

    /*
     * Live entry date and shift of a new entry (DECISION-029). Both fields are read-only.
     * #cf-date[data-live-clock] holds the server's entry time when the form was rendered
     * (IST, already minus the MCC's shift delay); it then moves on with the browser's
     * elapsed time, so a wrong PC clock or time zone does not matter. #cf-shift follows it:
     * Morning before data-morning-end (12:00 when not set), otherwise Evening.
     * The server stamps the saved entry itself; these fields only show what it will use.
     */
    const clockAnchors = new WeakMap();
    const pad = (value) => String(value).padStart(2, "0");

    function serverMillis(text) {
        const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/.exec(text || "");
        if (!m) return null;
        return Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0));
    }

    function tickEntryClock() {
        const input = document.querySelector("#form-collection #cf-date[data-live-clock]");
        if (!input) return;
        let anchor = clockAnchors.get(input);
        if (!anchor) {
            const server = serverMillis(input.dataset.liveClock);
            if (server === null) return;
            anchor = { server, client: Date.now() };
            clockAnchors.set(input, anchor);
        }
        const at = new Date(anchor.server + (Date.now() - anchor.client));
        const hours = at.getUTCHours();
        const minutes = at.getUTCMinutes();
        input.value = `${at.getUTCFullYear()}-${pad(at.getUTCMonth() + 1)}-${pad(at.getUTCDate())}` +
            `T${pad(hours)}:${pad(minutes)}:${pad(at.getUTCSeconds())}`;

        const shift = byId("cf-shift");
        if (shift && shift.dataset.morningEnd !== undefined) {
            const end = /^(\d{1,2}):(\d{2})/.exec(shift.dataset.morningEnd) || [null, "12", "00"];
            const morning = hours * 60 + minutes < (+end[1]) * 60 + (+end[2]);
            const next = morning ? "0" : "1";
            if (shift.value !== next) shift.value = next;
        }
    }

    document.addEventListener("DOMContentLoaded", tickEntryClock);
    document.body.addEventListener("htmx:afterSwap", tickEntryClock);
    setInterval(tickEntryClock, 1000);
})();
