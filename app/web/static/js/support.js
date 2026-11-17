/*
 * Technical Support portal: small, dependency-free helpers (Phase 25.2).
 *
 *   SP.toast(message, type)     type: success | error | info
 *   data-confirm="Question?"    on a button or link: asks first (data-confirm-title, data-confirm-ok, data-danger)
 *   data-copy="text"            on a button: copies the text
 *   .sp-menu                    profile menu (click to open, Esc / outside click to close)
 *   [data-sp-nav-toggle]        opens and closes the sidebar drawer on small screens
 */
(function () {
    'use strict';

    var SP = window.SP = window.SP || {};

    /* ------------------------------------------------------------ toasts */

    var ICONS = { success: 'fa-circle-check', error: 'fa-circle-exclamation', info: 'fa-circle-info' };

    SP.toast = function (message, type) {
        var host = document.getElementById('sp-toasts');
        if (!host || !message) { return; }
        type = ICONS[type] ? type : 'info';
        var item = document.createElement('div');
        item.className = 'sp-toast is-' + type;
        item.setAttribute('role', type === 'error' ? 'alert' : 'status');
        var icon = document.createElement('i');
        icon.className = 'fa-solid ' + ICONS[type];
        var text = document.createElement('span');
        text.textContent = message;
        item.appendChild(icon);
        item.appendChild(text);
        host.appendChild(item);
        window.setTimeout(function () {
            item.style.opacity = '0';
            item.style.transition = 'opacity .2s';
            window.setTimeout(function () { item.remove(); }, 220);
        }, type === 'error' ? 6000 : 3500);
    };

    /* ------------------------------------------------------------ confirm dialog */

    function ensureDialog() {
        var dialog = document.getElementById('sp-confirm');
        if (dialog) { return dialog; }
        dialog = document.createElement('dialog');
        dialog.id = 'sp-confirm';
        dialog.className = 'sp-dialog';
        dialog.innerHTML =
            '<form method="dialog">' +
            '<div class="sp-dialog-body"><h3></h3><p></p></div>' +
            '<div class="sp-dialog-foot">' +
            '<button class="sp-btn" value="cancel">Cancel</button>' +
            '<button class="sp-btn is-primary" value="ok"></button>' +
            '</div></form>';
        document.body.appendChild(dialog);
        return dialog;
    }

    document.addEventListener('click', function (event) {
        var trigger = event.target.closest('[data-confirm]');
        if (!trigger) { return; }
        if (trigger.dataset.spConfirmed === '1') {
            delete trigger.dataset.spConfirmed;
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();

        var dialog = ensureDialog();
        dialog.querySelector('h3').textContent = trigger.dataset.confirmTitle || 'Are you sure?';
        dialog.querySelector('p').textContent = trigger.dataset.confirm;
        var ok = dialog.querySelector('button[value="ok"]');
        ok.textContent = trigger.dataset.confirmOk || 'Confirm';
        ok.classList.toggle('is-danger', trigger.hasAttribute('data-danger'));
        ok.classList.toggle('is-primary', !trigger.hasAttribute('data-danger'));
        dialog.returnValue = '';
        dialog.onclose = function () {
            if (dialog.returnValue === 'ok') {
                trigger.dataset.spConfirmed = '1';
                trigger.click();
            }
        };
        dialog.showModal();
    }, true);

    /* ------------------------------------------------------------ copy */

    document.addEventListener('click', function (event) {
        var button = event.target.closest('[data-copy]');
        if (!button) { return; }
        var value = button.dataset.copy;
        var done = function () { SP.toast('Copied', 'success'); };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(value).then(done, function () { SP.toast('Could not copy', 'error'); });
        }
    });

    /* ------------------------------------------------------------ profile menu and drawer */

    document.addEventListener('click', function (event) {
        document.querySelectorAll('.sp-menu.is-open').forEach(function (menu) {
            if (!menu.contains(event.target)) { menu.classList.remove('is-open'); }
        });
        var trigger = event.target.closest('.sp-menu-trigger');
        if (trigger) {
            var menu = trigger.closest('.sp-menu');
            var open = menu.classList.toggle('is-open');
            trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
        }
        if (event.target.closest('[data-sp-nav-toggle]')) {
            var app = document.querySelector('.sp-app');
            if (app) { app.classList.toggle('is-nav-open'); }
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape') { return; }
        document.querySelectorAll('.sp-menu.is-open').forEach(function (menu) { menu.classList.remove('is-open'); });
        var app = document.querySelector('.sp-app');
        if (app) { app.classList.remove('is-nav-open'); }
    });

    /* ------------------------------------------------------------ htmx feedback */

    document.body.addEventListener('htmx:responseError', function (event) {
        var message = 'Something went wrong. Please try again.';
        try {
            var body = JSON.parse(event.detail.xhr.responseText);
            message = (body.error && body.error.message) || body.message || message;
        } catch (ignore) { /* not JSON: keep the generic text */ }
        SP.toast(message, 'error');
    });

    document.body.addEventListener('htmx:sendError', function () {
        SP.toast('You appear to be offline.', 'error');
    });

    // A server response can ask for a toast: HX-Trigger: {"sp-toast": {"message": "...", "type": "success"}}
    document.body.addEventListener('sp-toast', function (event) {
        var detail = event.detail || {};
        SP.toast(detail.message || detail.value, detail.type);
    });
})();
