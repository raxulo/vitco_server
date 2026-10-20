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
        updateCollectionAmount();
        updateCollectionSaveState();
    }
    document.addEventListener("DOMContentLoaded", initForm);
    document.body.addEventListener("htmx:afterSwap", (evt) => {
        const target = evt.detail.target;
        if (target && (target.id === "form-collection" || target.id === "group-rate" || target.id === "cf-rate")) {
            if (target.id === "form-collection") applyAutoMilkType();
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
})();
