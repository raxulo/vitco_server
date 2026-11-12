/**
 * Quickyee Excel Data Exchange Client Library
 * Handles: Template download, asynchronous Export, Chunked/Single Upload,
 * Asynchronous Import, Dynamic Polling with poll_after_ms, and Result Summaries.
 */

(function () {
    "use strict";

    let currentJob = null;
    let pollTimer = null;
    let currentKind = null;

    const KIND_CONFIG = {
        farmers: {
            title: "Farmer Excel Exchange",
            subtitle: "Import and export milk supplying farmers",
            targetLabel: "Target VLCC Center",
            targetHelp: "Select the VLCC center to export from or import farmers into",
            targetRequired: true,
            hasMode: true,
            defaultMode: "UPSERT"
        },
        vlccs: {
            title: "VLCC Masters Excel Exchange",
            subtitle: "Import and export Village Level Collection Centers",
            targetLabel: "Owner (Admin / Sub-Admin / MCC)",
            targetHelp: "Select the owner whose VLCCs you wish to export or import",
            targetRequired: false,
            hasMode: true,
            defaultMode: "UPSERT"
        },
        prodata: {
            title: "Prodata Rate-Chart Excel Exchange",
            subtitle: "Export and atomically replace rate chart slab rows",
            targetLabel: "Target Rate Chart",
            targetHelp: "Select the rate chart to export or replace rows for",
            targetRequired: true,
            hasMode: false,
            defaultMode: "UPSERT"
        },
        formula: {
            title: "Formula Rate-Chart Excel Exchange",
            subtitle: "Export formula parameters & preview grid, or import formula configuration",
            targetLabel: "Target Rate Chart",
            targetHelp: "Select the formula rate chart to export or update",
            targetRequired: true,
            hasMode: false,
            defaultMode: "UPSERT"
        }
    };

    /**
     * Open the Excel Exchange Modal for a specific kind ('farmers', 'vlccs', 'prodata')
     * @param {string} kind
     * @param {string} initialTab - 'export' | 'import' | 'template'
     */
    window.openExcelExchangeModal = function (kind, initialTab) {
        currentKind = kind;
        const config = KIND_CONFIG[kind];
        if (!config) {
            console.error("Unknown excel exchange kind:", kind);
            return;
        }

        const modal = document.getElementById("excel-exchange-modal");
        if (!modal) return;

        // Reset views
        document.getElementById("excel-modal-title").innerText = config.title;
        document.getElementById("excel-modal-subtitle").innerText = config.subtitle;
        document.getElementById("excel-target-label").innerText = config.targetLabel;
        document.getElementById("excel-target-help").innerText = config.targetHelp;

        // Mode container visibility (only farmers and vlccs have mode)
        const modeGroup = document.getElementById("excel-mode-group");
        if (modeGroup) {
            modeGroup.style.display = config.hasMode ? "block" : "none";
        }

        // Show main panels, hide progress/summary
        showView("form");
        resetForm();

        // Switch to initial tab
        switchTab(initialTab || "import");

        // Fetch options
        loadOptions(kind);

        modal.classList.add("active");
        document.body.style.overflow = "hidden";
    };

    window.closeExcelExchangeModal = function () {
        const modal = document.getElementById("excel-exchange-modal");
        if (modal) modal.classList.remove("active");
        document.body.style.overflow = "";
        if (pollTimer) {
            clearTimeout(pollTimer);
            pollTimer = null;
        }
    };

    function showView(viewName) {
        document.getElementById("excel-view-form").style.display = viewName === "form" ? "block" : "none";
        document.getElementById("excel-view-progress").style.display = viewName === "progress" ? "block" : "none";
        document.getElementById("excel-view-summary").style.display = viewName === "summary" ? "block" : "none";
    }

    const isRateChartKind = (k) => (k === "prodata" || k === "formula");

    function handleTargetChange(kind) {
        const select = document.getElementById("excel-target-select");
        const newFields = document.getElementById("excel-new-chart-fields");
        if (!newFields) return;
        const isImportTab = document.querySelector(".excel-modal-tab.active")?.dataset.tab === "import";
        if (isRateChartKind(kind) && select && select.value === "__NEW__" && isImportTab) {
            newFields.style.display = "block";
        } else {
            newFields.style.display = "none";
        }
    }

    function switchTab(tabName) {
        const tabs = document.querySelectorAll(".excel-modal-tab");
        tabs.forEach(t => t.classList.toggle("active", t.dataset.tab === tabName));

        document.getElementById("excel-tab-content-import").style.display = tabName === "import" ? "block" : "none";
        document.getElementById("excel-tab-content-export").style.display = tabName === "export" ? "block" : "none";

        const select = document.getElementById("excel-target-select");
        if (select) {
            const newOpt = select.querySelector('option[value="__NEW__"]');
            if (tabName === "export") {
                if (newOpt) newOpt.disabled = true;
                if (select.value === "__NEW__") {
                    const firstValid = Array.from(select.options).find(o => o.value && o.value !== "__NEW__");
                    select.value = firstValid ? firstValid.value : "";
                }
            } else {
                if (newOpt) newOpt.disabled = false;
            }
        }

        handleTargetChange(currentKind);
    }

    window.switchExcelTab = switchTab;

    function resetForm() {
        const fileInput = document.getElementById("excel-file-input");
        if (fileInput) fileInput.value = "";
        document.getElementById("excel-file-display").style.display = "none";
        document.getElementById("excel-drop-zone").style.display = "flex";
        document.getElementById("excel-import-btn").disabled = true;
        document.getElementById("excel-dry-run-checkbox").checked = false;
        document.getElementById("excel-error-alert").style.display = "none";

        const newChartName = document.getElementById("excel-new-chart-name");
        if (newChartName) newChartName.value = "";
        const newMilkType = document.getElementById("excel-new-chart-milk-type");
        if (newMilkType) newMilkType.value = "2";
        const newEffFrom = document.getElementById("excel-new-chart-effective-from");
        if (newEffFrom) {
            newEffFrom.value = new Date().toISOString().split("T")[0];
        }
        const newFields = document.getElementById("excel-new-chart-fields");
        if (newFields) newFields.style.display = "none";
    }

    function showError(msg) {
        const alertBox = document.getElementById("excel-error-alert");
        if (alertBox) {
            alertBox.innerText = msg;
            alertBox.style.display = "block";
        }
    }

    /**
     * Fetch options from /api/v1/excel/{kind}/options
     */
    async function loadOptions(kind) {
        const select = document.getElementById("excel-target-select");
        const lockBadge = document.getElementById("excel-target-lock-badge");
        select.innerHTML = '<option value="">Loading choices...</option>';
        select.disabled = true;
        if (lockBadge) lockBadge.style.display = "none";

        try {
            const res = await fetch(`/api/v1/excel/${kind}/options`, {
                headers: { "HX-Request": "true" }
            });
            if (!res.ok) throw new Error("Failed to load options");
            const data = await res.json();
            const items = data.items || [];

            select.innerHTML = "";
            const config = KIND_CONFIG[kind];
            if (!config.targetRequired) {
                const opt = document.createElement("option");
                opt.value = "";
                opt.text = "-- Global / All Accessible --";
                select.appendChild(opt);
            }

            if (isRateChartKind(kind)) {
                const newOpt = document.createElement("option");
                newOpt.value = "__NEW__";
                newOpt.text = "+ Create New Rate Chart from Excel";
                newOpt.style.fontWeight = "bold";
                newOpt.style.color = "#059669";
                select.appendChild(newOpt);
            }

            items.forEach(item => {
                const opt = document.createElement("option");
                opt.value = item.id;
                opt.text = item.name + (item.code ? ` (${item.code})` : "");
                if (item.can_modify === false && isRateChartKind(kind)) {
                    opt.dataset.readonly = "true";
                    opt.text += " [View Only]";
                }
                select.appendChild(opt);
            });

            select.onchange = function () {
                handleTargetChange(kind);
            };

            if (isRateChartKind(kind)) {
                select.disabled = false;
                const isImportTab = document.querySelector(".excel-modal-tab.active")?.dataset.tab === "import";
                if (isImportTab) {
                    select.value = "__NEW__";
                } else if (items.length > 0) {
                    select.value = items[0].id;
                }
                handleTargetChange(kind);
            } else if (items.length === 1 && config.targetRequired) {
                select.value = items[0].id;
                select.disabled = true;
                if (lockBadge) {
                    lockBadge.style.display = "inline-flex";
                    lockBadge.innerText = "Locked: Only 1 available";
                }
            } else if (items.length === 0 && config.targetRequired) {
                select.innerHTML = '<option value="">No targets available</option>';
                select.disabled = true;
            } else {
                select.disabled = false;
            }
        } catch (e) {
            console.error("Options error:", e);
            select.innerHTML = '<option value="">Error loading choices</option>';
        }
    }

    /**
     * Direct template download
     */
    window.downloadExcelTemplate = function () {
        if (!currentKind) return;
        window.location.href = `/api/v1/excel/${currentKind}/template`;
    };

    /**
     * Export Handler
     */
    window.submitExcelExport = async function () {
        if (!currentKind) return;
        const select = document.getElementById("excel-target-select");
        const targetId = select.value || null;
        const config = KIND_CONFIG[currentKind];

        if (config.targetRequired && !targetId) {
            showError("Please select a target before exporting.");
            return;
        }
        if (isRateChartKind(currentKind) && targetId === "__NEW__") {
            showError("Cannot export a new rate chart. Please select an existing rate chart to export.");
            return;
        }

        let payload = {};
        if (currentKind === "farmers") payload.vlcc_id = targetId;
        else if (currentKind === "vlccs") payload.owner_id = targetId;
        else if (isRateChartKind(currentKind)) payload.chart_id = targetId;

        try {
            showView("progress");
            document.getElementById("excel-progress-title").innerText = "Exporting Data...";
            document.getElementById("excel-progress-subtitle").innerText = "Generating your Excel spreadsheet in the background";

            const res = await fetch(`/api/v1/excel/${currentKind}/export`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "HX-Request": "true"
                },
                body: JSON.stringify(payload)
            });

            if (res.status === 429) {
                const err = await res.json();
                throw new Error(err.message || "Export capacity busy. Please try again shortly.");
            }

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error?.message || err.message || "Failed to start export");
            }

            const data = await res.json();
            const job = data.data;
            pollJob(job.id, true);
        } catch (e) {
            showView("form");
            showError(e.message);
        }
    };

    /**
     * Collection list export (DECISION-028): 'mcc-collections' | 'vlcc-collections'.
     * Sends the page's current filters from its URL, so the file holds what the list shows,
     * then reuses the modal's progress, polling and download views.
     */
    const COLLECTION_EXPORTS = {
        "mcc-collections": { title: "MCC Collections Export", subtitle: "All entries matching the current filters" },
        "vlcc-collections": { title: "VLCC Collections Export", subtitle: "All entries matching the current filters" }
    };
    const COLLECTION_FILTERS = ["search", "mcc_id", "vlcc_id", "milk_type", "date_from", "date_to", "start_shift", "end_shift"];

    window.exportCollectionsToExcel = async function (kind) {
        const config = COLLECTION_EXPORTS[kind];
        const modal = document.getElementById("excel-exchange-modal");
        if (!config || !modal) return;

        currentKind = kind;
        document.getElementById("excel-modal-title").innerText = config.title;
        document.getElementById("excel-modal-subtitle").innerText = config.subtitle;
        document.getElementById("excel-error-alert").style.display = "none";
        document.getElementById("excel-progress-title").innerText = "Exporting Data...";
        document.getElementById("excel-progress-subtitle").innerText = "Generating your Excel spreadsheet in the background";
        updateProgressBar(10, "Starting export...");
        showView("progress");
        modal.classList.add("active");
        document.body.style.overflow = "hidden";

        const query = new URLSearchParams(window.location.search);
        const payload = {};
        COLLECTION_FILTERS.forEach(key => {
            const value = (query.get(key) || "").trim();
            if (value) payload[key] = value;
        });

        try {
            const res = await fetch(`/api/v1/excel/${kind}/export`, {
                method: "POST",
                headers: { "Content-Type": "application/json", "HX-Request": "true" },
                body: JSON.stringify(payload)
            });
            const body = await res.json().catch(() => ({}));

            // An export of this kind is already running for this user: follow it instead
            const runningId = body.error?.details?.job_id;
            if (res.status === 409 && runningId) {
                pollJob(runningId, true);
                return;
            }
            if (!res.ok) {
                throw new Error(body.error?.message || body.message || body.detail || "Failed to start export");
            }
            pollJob(body.data.id, true);
        } catch (e) {
            renderSummary({ status: "FAILED", error_message: e.message }, true);
        }
    };

    /**
     * File Selection Handling
     */
    window.handleExcelFileSelect = function (input) {
        if (!input.files || input.files.length === 0) return;
        const file = input.files[0];
        setChosenFile(file);
    };

    function setChosenFile(file) {
        if (!file.name.toLowerCase().endsWith(".xlsx")) {
            showError("Only Microsoft Excel (.xlsx) files are supported.");
            return;
        }
        document.getElementById("excel-error-alert").style.display = "none";
        document.getElementById("excel-file-name").innerText = file.name;
        document.getElementById("excel-file-size").innerText = (file.size / 1024).toFixed(1) + " KB";
        document.getElementById("excel-drop-zone").style.display = "none";
        document.getElementById("excel-file-display").style.display = "flex";
        document.getElementById("excel-import-btn").disabled = false;
        window._selectedExcelFile = file;
    }

    window.removeChosenExcelFile = function () {
        resetForm();
        window._selectedExcelFile = null;
    };

    /**
     * Import Handler: Handles file upload (single or chunked) then submits import job
     */
    window.submitExcelImport = async function () {
        const file = window._selectedExcelFile;
        if (!file || !currentKind) return;

        const select = document.getElementById("excel-target-select");
        const targetId = select.value || null;
        const config = KIND_CONFIG[currentKind];

        if (config.targetRequired && !targetId) {
            showError("Please select a target before importing.");
            return;
        }

        if (isRateChartKind(currentKind) && targetId === "__NEW__") {
            const chartName = (document.getElementById("excel-new-chart-name")?.value || "").trim();
            if (!chartName) {
                showError("Please enter a name for the new rate chart.");
                return;
            }
        }

        const modeSelect = document.getElementById("excel-mode-select");
        const mode = modeSelect ? modeSelect.value : "UPSERT";
        const dryRun = document.getElementById("excel-dry-run-checkbox").checked;

        showView("progress");
        document.getElementById("excel-progress-title").innerText = "Uploading Spreadsheet...";
        document.getElementById("excel-progress-subtitle").innerText = "Transferring data safely to the server";
        updateProgressBar(10, "Uploading file...");

        try {
            let uploadId;
            if (file.size <= 5 * 1024 * 1024) {
                // Single request upload for <= 5MB
                const formData = new FormData();
                formData.append("file", file, file.name);
                const upRes = await fetch("/api/v1/excel/uploads/single", {
                    method: "POST",
                    headers: { "HX-Request": "true" },
                    body: formData
                });
                if (!upRes.ok) throw new Error("Upload failed. Please check file format and size.");
                const upData = await upRes.json();
                uploadId = upData.data.id;
            } else {
                // Chunked upload
                uploadId = await uploadInChunks(file);
            }

            updateProgressBar(30, "Submitting import job...");
            document.getElementById("excel-progress-title").innerText = "Processing Spreadsheet...";
            document.getElementById("excel-progress-subtitle").innerText = "Worker engine is validating and saving records";

            let payload = {
                upload_id: uploadId,
                dry_run: dryRun
            };
            if (config.hasMode) payload.mode = mode;

            if (currentKind === "farmers") payload.vlcc_id = targetId;
            else if (currentKind === "vlccs") payload.owner_id = targetId;
            else if (isRateChartKind(currentKind)) {
                if (targetId === "__NEW__") {
                    payload.chart_id = null;
                    payload.chart_name = (document.getElementById("excel-new-chart-name")?.value || "").trim();
                    payload.milk_type = parseInt(document.getElementById("excel-new-chart-milk-type")?.value || "2", 10);
                    const effDate = document.getElementById("excel-new-chart-effective-from")?.value;
                    if (effDate) payload.effective_from = effDate;
                } else {
                    payload.chart_id = targetId;
                }
            }

            const res = await fetch(`/api/v1/excel/${currentKind}/import`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "HX-Request": "true"
                },
                body: JSON.stringify(payload)
            });

            if (res.status === 429) {
                const err = await res.json();
                throw new Error(err.message || "Import queue full. Please wait a moment.");
            }

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.error?.message || err.message || "Failed to submit import");
            }

            const data = await res.json();
            pollJob(data.data.id, false);
        } catch (e) {
            showView("form");
            showError(e.message);
        }
    };

    /**
     * Chunked upload implementation
     */
    async function uploadInChunks(file) {
        const chunkSize = 5 * 1024 * 1024;
        const totalChunks = Math.ceil(file.size / chunkSize);

        // 1. Create upload session
        const initRes = await fetch("/api/v1/excel/uploads", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "HX-Request": "true"
            },
            body: JSON.stringify({
                file_name: file.name,
                size: file.size
            })
        });
        if (!initRes.ok) throw new Error("Could not initialize chunked upload");
        const initData = await initRes.json();
        const uploadId = initData.data.id;

        // 2. Upload chunks sequentially
        for (let i = 0; i < totalChunks; i++) {
            const start = i * chunkSize;
            const end = Math.min(file.size, start + chunkSize);
            const chunk = file.slice(start, end);

            const chunkRes = await fetch(`/api/v1/excel/uploads/${uploadId}/chunks/${i}`, {
                method: "PUT",
                headers: { "HX-Request": "true" },
                body: chunk
            });
            if (!chunkRes.ok) throw new Error(`Failed to upload chunk ${i + 1} of ${totalChunks}`);
            const pct = 10 + Math.floor((i + 1) / totalChunks * 20);
            updateProgressBar(pct, `Uploaded chunk ${i + 1}/${totalChunks}...`);
        }

        // 3. Complete upload
        const compRes = await fetch(`/api/v1/excel/uploads/${uploadId}/complete`, {
            method: "POST",
            headers: { "HX-Request": "true" }
        });
        if (!compRes.ok) throw new Error("Could not finalize upload assembly");
        return uploadId;
    }

    /**
     * Poll job status until completion or failure
     */
    function pollJob(jobId, isExport) {
        if (pollTimer) clearTimeout(pollTimer);

        async function step() {
            try {
                const res = await fetch(`/api/v1/excel/jobs/${jobId}`, {
                    headers: { "HX-Request": "true" }
                });
                if (!res.ok) throw new Error("Could not retrieve job status");
                const body = await res.json();
                const job = body.data;
                currentJob = job;

                const statusName = job.status?.name || job.status;
                const total = job.total_rows || 0;
                const processed = job.processed_rows || 0;

                if (statusName === "PENDING") {
                    updateProgressBar(20, "Queued in background worker...");
                } else if (statusName === "RUNNING") {
                    const pct = total > 0 ? Math.min(95, Math.floor((processed / total) * 75) + 20) : 50;
                    updateProgressBar(pct, `Processed ${processed.toLocaleString()}${total > 0 ? ' of ' + total.toLocaleString() : ''} rows...`);
                } else if (statusName === "COMPLETED") {
                    updateProgressBar(100, "Completed successfully!");
                    setTimeout(() => renderSummary(job, isExport), 500);
                    return;
                } else if (statusName === "FAILED") {
                    updateProgressBar(100, "Job failed");
                    setTimeout(() => renderSummary(job, isExport), 500);
                    return;
                }

                const delay = Math.max(300, job.poll_after_ms || 1000);
                pollTimer = setTimeout(step, delay);
            } catch (e) {
                console.error("Polling error:", e);
                pollTimer = setTimeout(step, 2000);
            }
        }

        step();
    }

    function updateProgressBar(percent, text) {
        const bar = document.getElementById("excel-progress-fill");
        const label = document.getElementById("excel-progress-text");
        if (bar) bar.style.width = percent + "%";
        if (label) label.innerText = text;
    }

    function renderSummary(job, isExport) {
        showView("summary");
        const isSuccess = (job.status?.name || job.status) === "COMPLETED";

        const iconBox = document.getElementById("excel-summary-icon");
        const title = document.getElementById("excel-summary-title");
        const msg = document.getElementById("excel-summary-msg");

        if (isSuccess) {
            iconBox.innerHTML = '<i class="fa-solid fa-circle-check" style="color: #10b981; font-size: 48px;"></i>';
            title.innerText = isExport ? "Export Completed!" : "Import Completed!";
            msg.innerText = isExport
                ? `Successfully generated ${job.total_rows || 0} rows spreadsheet.`
                : `Successfully processed file with ${job.inserted || 0} inserted, ${job.updated || 0} updated, and ${job.discarded || 0} discarded.`;
        } else {
            iconBox.innerHTML = '<i class="fa-solid fa-circle-xmark" style="color: #ef4444; font-size: 48px;"></i>';
            title.innerText = "Job Failed";
            msg.innerText = job.error_message || "The operation encountered an unexpected error.";
        }

        document.getElementById("excel-stat-total").innerText = (job.total_rows || 0).toLocaleString();
        document.getElementById("excel-stat-inserted").innerText = (job.inserted || 0).toLocaleString();
        document.getElementById("excel-stat-updated").innerText = (job.updated || 0).toLocaleString();
        document.getElementById("excel-stat-discarded").innerText = (job.discarded || 0).toLocaleString();

        const downloadReportBtn = document.getElementById("excel-download-report-btn");
        const downloadExportBtn = document.getElementById("excel-download-export-btn");

        if (isExport && isSuccess) {
            downloadExportBtn.style.display = "inline-flex";
            downloadExportBtn.onclick = () => window.location.href = `/api/v1/excel/jobs/${job.id}/file`;
            // Auto trigger export download
            window.location.href = `/api/v1/excel/jobs/${job.id}/file`;
        } else {
            downloadExportBtn.style.display = "none";
        }

        if (!isExport && job.discarded > 0) {
            downloadReportBtn.style.display = "inline-flex";
            downloadReportBtn.onclick = () => window.location.href = `/api/v1/excel/jobs/${job.id}/file`;
        } else {
            downloadReportBtn.style.display = "none";
        }
    }

    // Setup drag and drop on load
    document.addEventListener("DOMContentLoaded", function () {
        const dropZone = document.getElementById("excel-drop-zone");
        if (!dropZone) return;

        ["dragenter", "dragover"].forEach(name => {
            dropZone.addEventListener(name, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add("dragover");
            }, false);
        });

        ["dragleave", "drop"].forEach(name => {
            dropZone.addEventListener(name, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove("dragover");
            }, false);
        });

        dropZone.addEventListener("drop", (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files && files.length > 0) {
                setChosenFile(files[0]);
            }
        });
    });

})();
