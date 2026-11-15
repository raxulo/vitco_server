/**
 * Excel Column Order page (Plan 24.3, pages/sub_admin/column_layout.html;
 * sidebar: System Setup -> Excel Maps)
 *
 * - Reorders the rows by native drag and drop, the up / down buttons, or
 *   Alt + ArrowUp / ArrowDown on a focused row (focus follows the row).
 * - Keeps the row numbers, the live counters and the MCC / VLCC spreadsheet
 *   preview current.
 * - Tracks unsaved changes (status bar, Discard, leave-page warning) and
 *   marks the page saved after a successful HTMX save.
 * - Stops a save that would leave an export with no column (the server
 *   refuses it as well).
 *
 * The form posts the hidden `key` inputs in row order and the ticked `visible`
 * boxes.
 */
(function () {
    "use strict";

    const SHEET_FILES = { mcc: "MCC Collections.xlsx", vlcc: "VLCC Collections.xlsx" };

    /** Excel column letters: 0 -> A, 25 -> Z, 26 -> AA */
    function letter(index) {
        let name = "";
        for (let n = index + 1; n > 0; n = Math.floor((n - 1) / 26)) {
            name = String.fromCharCode(65 + ((n - 1) % 26)) + name;
        }
        return name;
    }

    function init(form) {
        if (!form || form.dataset.ready) return;
        form.dataset.ready = "1";

        const page = form.closest(".xm") || document;
        const list = form.querySelector('[data-role="list"]');
        const save = form.querySelector('[data-role="save"]');
        const reset = form.querySelector('[data-role="reset"]');
        const discard = form.querySelector('[data-role="discard"]');
        const warning = form.querySelector('[data-role="warning"]');
        const bar = form.querySelector('[data-role="bar"]');
        const statusText = form.querySelector('[data-role="status-text"]');
        const sheetName = form.querySelector('[data-role="sheet-name"]');
        const pill = page.querySelector('[data-role="state-pill"]');
        let dragged = null;

        const rows = () => Array.from(list.children);
        const isOn = (row) => row.querySelector('input[type="checkbox"]').checked;
        const snapshot = () => rows().map((row) => row.dataset.key + (isOn(row) ? "+" : "-")).join(",");
        let saved = snapshot();

        function stat(name, value) {
            const target = page.querySelector(`[data-stat="${name}"]`);
            if (target) target.textContent = value;
        }

        function renderPreview(sheet, headers) {
            const target = form.querySelector(`[data-preview="${sheet}"]`);
            target.replaceChildren();
            if (!headers.length) {
                const empty = document.createElement("li");
                empty.innerHTML = '<span class="xm-empty">No column switched on</span>';
                target.appendChild(empty);
                return;
            }
            headers.forEach((header, index) => {
                const cell = document.createElement("li");
                const col = document.createElement("span");
                col.className = "xm-col-letter";
                col.textContent = letter(index);
                const name = document.createElement("span");
                name.className = "xm-col-name";
                name.textContent = header;
                name.title = header;
                cell.append(col, name);
                target.appendChild(cell);
            });
        }

        function refresh() {
            const preview = { mcc: [], vlcc: [] };
            const all = rows();
            let shown = 0;
            all.forEach((row, index) => {
                row.querySelector('[data-role="no"]').textContent = index + 1;
                row.querySelector('[data-move="-1"]').disabled = index === 0;
                row.querySelector('[data-move="1"]').disabled = index === all.length - 1;
                const on = isOn(row);
                row.classList.toggle("is-off", !on);
                if (!on) return;
                shown += 1;
                const header = row.querySelector(".xm-header").textContent.trim();
                row.dataset.sheets.split(" ").forEach((sheet) => preview[sheet] && preview[sheet].push(header));
            });

            let empty = false;
            Object.keys(preview).forEach((sheet) => {
                renderPreview(sheet, preview[sheet]);
                stat(sheet, preview[sheet].length);
                empty = empty || preview[sheet].length === 0;
            });
            stat("shown", shown);

            const dirty = snapshot() !== saved;
            warning.hidden = !empty;
            save.disabled = empty || !dirty;
            discard.hidden = !dirty;
            bar.classList.toggle("is-dirty", dirty);
            statusText.textContent = empty
                ? "Each export needs at least one column"
                : dirty ? "Unsaved changes" : "All changes saved";
        }

        function moveRow(row, step) {
            if (step < 0 && row.previousElementSibling) {
                list.insertBefore(row, row.previousElementSibling);
            } else if (step > 0 && row.nextElementSibling) {
                list.insertBefore(row.nextElementSibling, row);
            } else {
                return false;
            }
            row.classList.remove("is-moved");
            void row.offsetWidth; // restart the highlight animation
            row.classList.add("is-moved");
            refresh();
            return true;
        }

        // ---- up / down buttons -----------------------------------------
        list.addEventListener("click", (event) => {
            const button = event.target.closest("[data-move]");
            if (!button || button.disabled) return;
            const row = button.closest(".xm-row");
            const step = Number(button.dataset.move);
            moveRow(row, step);
            // Keep keyboard focus on the same control (fall back to its pair at the ends)
            const again = row.querySelector(`[data-move="${step}"]`);
            (again.disabled ? row.querySelector(`[data-move="${-step}"]`) : again).focus();
        });

        // ---- Alt + ArrowUp / ArrowDown on any focused control in a row ---
        list.addEventListener("keydown", (event) => {
            if (!event.altKey || (event.key !== "ArrowUp" && event.key !== "ArrowDown")) return;
            const row = event.target.closest(".xm-row");
            if (!row) return;
            event.preventDefault();
            const focused = document.activeElement;
            if (moveRow(row, event.key === "ArrowUp" ? -1 : 1) && focused) focused.focus();
        });

        list.addEventListener("change", refresh);

        // ---- show all -------------------------------------------------------
        const showAll = page.querySelector('[data-role="show-all"]');
        if (showAll) {
            showAll.addEventListener("click", () => {
                rows().forEach((row) => { row.querySelector('input[type="checkbox"]').checked = true; });
                refresh();
            });
        }

        // ---- preview tabs ---------------------------------------------------
        page.querySelectorAll("[data-tab]").forEach((tab) => {
            tab.addEventListener("click", () => {
                page.querySelectorAll("[data-tab]").forEach((other) => {
                    const active = other === tab;
                    other.classList.toggle("is-active", active);
                    other.setAttribute("aria-selected", String(active));
                    form.querySelector(`[data-preview="${other.dataset.tab}"]`).hidden = !active;
                });
                sheetName.textContent = SHEET_FILES[tab.dataset.tab];
            });
        });

        // ---- drag and drop --------------------------------------------------
        function clearMarks() {
            rows().forEach((row) => row.classList.remove("is-over-top", "is-over-bottom"));
        }

        list.addEventListener("dragstart", (event) => {
            dragged = event.target.closest(".xm-row");
            if (!dragged) return;
            dragged.classList.add("is-dragging");
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("text/plain", dragged.dataset.key);
        });

        list.addEventListener("dragover", (event) => {
            if (!dragged) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
            const over = event.target.closest(".xm-row");
            clearMarks();
            if (!over || over === dragged) return;
            const box = over.getBoundingClientRect();
            over.classList.add(event.clientY > box.top + box.height / 2 ? "is-over-bottom" : "is-over-top");
        });

        list.addEventListener("drop", (event) => {
            if (!dragged) return;
            event.preventDefault();
            const over = event.target.closest(".xm-row");
            if (over && over !== dragged) {
                const box = over.getBoundingClientRect();
                const after = event.clientY > box.top + box.height / 2;
                list.insertBefore(dragged, after ? over.nextElementSibling : over);
            }
        });

        list.addEventListener("dragend", () => {
            clearMarks();
            if (dragged) dragged.classList.remove("is-dragging");
            dragged = null;
            refresh();
        });

        // ---- save / discard / leave ----------------------------------------
        form.addEventListener("submit", (event) => {
            if (save.disabled) event.preventDefault();
        });

        form.addEventListener("htmx:afterRequest", (event) => {
            if (event.detail.elt !== form || !event.detail.successful) return;
            saved = snapshot();
            if (pill) {
                pill.className = "xm-pill xm-pill-custom";
                pill.lastChild.textContent = "Custom order";
            }
            if (reset) reset.disabled = false;
            refresh();
        });

        discard.addEventListener("click", () => {
            saved = null; // let the reload through without the leave warning
            window.location.reload();
        });

        window.addEventListener("beforeunload", (event) => {
            if (saved !== null && snapshot() !== saved) {
                event.preventDefault();
                event.returnValue = "";
            }
        });

        refresh();
    }

    function boot() {
        init(document.getElementById("column-layout"));
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
    document.addEventListener("htmx:load", boot);
})();
