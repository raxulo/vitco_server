/*
 * Print the report preview (#mcc-report-preview-content) as a clean document.
 *
 * The preview is copied into a hidden iframe and printed there, so it runs as
 * normal page flow instead of an absolutely positioned box inside the modal.
 * Browsers ignore page breaks inside absolutely positioned content; here they
 * work, so every member of a ledger report (marked .rp-member-start in
 * report_preview.html) starts on its own page. The preview's own <style> tags
 * travel with it (e.g. landscape pages for wide reports).
 */
(function () {
    const FRAME_ID = "report-print-iframe";

    // Undo the in-page print trick (hidden page + absolute receipt): inside the iframe it is the whole page
    const RESET = `
        html, body { margin: 0; padding: 0; background: #fff; }
        body * { visibility: visible !important; }
        .thermal-receipt { position: static !important; padding: 0 !important; max-width: none !important; }
        .no-print { display: none !important; }
    `;

    function frame() {
        let iframe = document.getElementById(FRAME_ID);
        if (!iframe) {
            iframe = document.createElement("iframe");
            iframe.id = FRAME_ID;
            iframe.title = "Report print";
            iframe.setAttribute("aria-hidden", "true");
            Object.assign(iframe.style, { position: "fixed", right: "0", bottom: "0", width: "0", height: "0", border: "0" });
            document.body.appendChild(iframe);
        }
        return iframe;
    }

    window.printReportPreview = function () {
        const preview = document.getElementById("mcc-report-preview-content");
        if (!preview || !preview.innerHTML.trim()) {
            window.print();
            return;
        }
        const iframe = frame();
        const doc = iframe.contentWindow.document;
        doc.open();
        doc.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${document.title}</title></head>`
            + `<body>${preview.innerHTML}<style>${RESET}</style></body></html>`);
        doc.close();
        // Let the copied content lay out before printing
        setTimeout(() => {
            try {
                iframe.contentWindow.focus();
                iframe.contentWindow.print();
            } catch (err) {
                console.error("Report print in a frame failed; printing the page instead", err);
                window.print();
            }
        }, 250);
    };
})();
