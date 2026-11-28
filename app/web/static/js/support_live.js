/*
 * Technical Support portal: live updates (Phase 27, REQ-73 to REQ-75). Dependency-free.
 *
 * One WebSocket (/ws/support, signed in by the session cookie). The server decides what this
 * member may hear; this file only shows it:
 *   - sidebar badges and the tab title count
 *   - the ticket list refreshes (new rows are highlighted)
 *   - the open ticket's conversation appends new messages, marks deleted ones, shows typing, the side panel refreshes
 *   - a toast, and optionally a soft sound and a desktop notification (off until the member turns it on)
 * Markup always comes from the server's own pages (fetched and picked apart), never built here.
 * The socket reconnects with backoff and asks for what it missed; if the server says that is too much
 * it reloads the parts of the page instead. While it is down the page polls every 20 seconds.
 */
(function () {
    'use strict';

    var body = document.body;
    if (!body || !body.getAttribute('data-sp-live') || !window.WebSocket) { return; }

    var SP = window.SP = window.SP || {};
    var ME = body.getAttribute('data-sp-user') || '';
    var badge = document.getElementById('sp-live');
    var baseTitle = document.title;
    var lastId = 0, socket = null, attempts = 0, reconnectTimer = null, pollTimer = null, pollLatest = null;
    var heartbeat = null, debounce = {}, typingSentAt = 0, typingHide = null, audio = null;
    // "Reconnecting" only after the line has been down this long: moving between pages closes and reopens the
    // socket in well under a second, which is not worth a warning
    var GRACE_MS = 3000, graceTimer = null, leaving = false;

    /* ------------------------------------------------------------ small helpers */

    function store(key, value) {
        try {
            if (value === undefined) { return window.localStorage.getItem(key); }
            window.localStorage.setItem(key, value);
        } catch (ignore) { /* private mode: the setting just does not persist */ }
        return null;
    }

    function later(name, delay, fn) {
        window.clearTimeout(debounce[name]);
        debounce[name] = window.setTimeout(fn, delay);
    }

    function status(state) {
        window.clearTimeout(graceTimer);
        graceTimer = null;
        if (!badge) { return; }
        var map = { live: ['Live', 'is-live'], retry: ['Reconnecting', 'is-retry'], off: ['Offline', ''] };
        var entry = map[state] || map.off;
        badge.hidden = false;
        badge.textContent = entry[0];
        badge.className = 'sp-live ' + entry[1];
    }

    // The line is down: say so only if it is still down after the grace time (a `hello` cancels it)
    function dropped() {
        if (graceTimer) { return; }                     // counting from the first drop: failed retries do not restart it
        graceTimer = window.setTimeout(function () { graceTimer = null; status('retry'); }, GRACE_MS);
    }

    // The previous page was live a moment ago: start as Live instead of flashing a warning
    function wasLive() {
        try {
            var saved = (window.sessionStorage.getItem('sp-live') || '').split(':');
            return saved[0] === 'live' && Date.now() - Number(saved[1]) < 15000;
        } catch (ignore) { return false; }
    }

    function rememberLive() {
        try { window.sessionStorage.setItem('sp-live', 'live:' + Date.now()); } catch (ignore) { /* private mode */ }
    }

    function fetchPage(url) {
        return fetch(url, { credentials: 'same-origin', headers: { 'X-SP-Live': '1' } }).then(function (response) {
            if (!response.ok || response.redirected && /\/login/.test(response.url)) { return null; }
            return response.text();
        }).then(function (html) {
            return html ? new DOMParser().parseFromString(html, 'text/html') : null;
        }).catch(function () { return null; });
    }

    /* ------------------------------------------------------------ badges and title */

    function showCounts(counts) {
        var waiting = 0;
        Object.keys(counts || {}).forEach(function (key) {
            document.querySelectorAll('[data-sp-count="' + key + '"]').forEach(function (el) {
                el.textContent = counts[key];
                el.hidden = !counts[key];
            });
            if (key !== 'all') { waiting += counts[key] || 0; }
        });
        document.title = (waiting ? '(' + waiting + ') ' : '') + baseTitle;
    }

    function refreshCounts() {
        return fetch('/support/_live/counts', { credentials: 'same-origin' }).then(function (r) {
            return r.ok ? r.json() : null;
        }).then(function (data) {
            if (data) { showCounts(data.counts); }
            return data;
        }).catch(function () { return null; });
    }

    /* ------------------------------------------------------------ list */

    function refreshList() {
        var list = document.getElementById('sp-list');
        if (!list) { return; }
        var known = {};
        list.querySelectorAll('[data-ticket-id]').forEach(function (row) { known[row.getAttribute('data-ticket-id')] = 1; });
        fetchPage(window.location.href).then(function (doc) {
            var fresh = doc && doc.getElementById('sp-list');
            if (!fresh) { return; }
            fresh.querySelectorAll('[data-ticket-id]').forEach(function (row) {
                if (!known[row.getAttribute('data-ticket-id')]) { row.classList.add('is-new'); }
            });
            list.innerHTML = fresh.innerHTML;
            var sub = document.querySelector('.sp-page-sub'), freshSub = doc.querySelector('.sp-page-sub');
            if (sub && freshSub) { sub.textContent = freshSub.textContent; }
        });
    }

    /* ------------------------------------------------------------ open ticket */

    function openTicketId() {
        var thread = document.getElementById('sp-thread');
        return thread ? thread.getAttribute('data-ticket-id') : null;
    }

    function refreshThread() {
        var thread = document.getElementById('sp-thread');
        if (!thread) { return; }
        fetchPage(window.location.href).then(function (doc) {
            var fresh = doc && doc.getElementById('sp-thread');
            var box = thread.querySelector('.sp-thread');
            var freshBox = fresh && fresh.querySelector('.sp-thread');
            if (!freshBox || !box) { return; }
            // A reply box that appeared or went away (ticket closed or reopened) needs the whole section
            if (!!fresh.querySelector('.sp-composer') !== !!thread.querySelector('.sp-composer')) {
                thread.outerHTML = fresh.outerHTML;
                return;
            }
            var have = box.children.length, added = 0;
            var atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
            Array.prototype.slice.call(freshBox.children, have).forEach(function (node) {
                box.appendChild(document.importNode(node, true));
                added += 1;
            });
            var count = thread.querySelector('.sp-card-head .sp-muted'), freshCount = fresh.querySelector('.sp-card-head .sp-muted');
            if (count && freshCount) { count.textContent = freshCount.textContent; }
            if (!added) { return; }
            if (atBottom) {
                box.scrollTop = box.scrollHeight;
            } else {
                var pill = thread.querySelector('[data-new-messages]');
                if (pill) { pill.hidden = false; }
            }
            if (!document.hidden && socket && socket.readyState === 1) {
                socket.send(JSON.stringify({ type: 'read', ticket_id: openTicketId() }));
            }
        });
    }

    // A message was deleted: swap just that bubble for the server's "deleted" version (others keep playing audio)
    function replaceMessage(messageId) {
        var thread = document.getElementById('sp-thread');
        if (!thread || !messageId) { return; }
        fetchPage(window.location.href).then(function (doc) {
            var selector = '[data-message-id="' + String(messageId).replace(/[^0-9]/g, '') + '"]';
            var mine = thread.querySelector(selector), fresh = doc && doc.querySelector('#sp-thread ' + selector);
            if (mine && fresh) { mine.replaceWith(document.importNode(fresh, true)); }
        });
    }

    function refreshSide() {
        var side = document.getElementById('sp-side');
        if (!side) { return; }
        fetchPage(window.location.href).then(function (doc) {
            var fresh = doc && doc.getElementById('sp-side');
            if (!fresh || side.contains(document.activeElement)) { return; }   // never pull a control out from under a hand
            side.innerHTML = fresh.innerHTML;
            var head = document.querySelector('.sp-page-head'), freshHead = doc.querySelector('.sp-page-head');
            if (head && freshHead) { head.innerHTML = freshHead.innerHTML; }
        });
    }

    function showTyping(event) {
        var thread = document.getElementById('sp-thread');
        if (!thread || event.ticket_id !== openTicketId()) { return; }
        var line = thread.querySelector('[data-typing]');
        if (!line) { return; }
        line.textContent = (event.data && event.data.staff) ? 'A colleague is typing…' : 'The requester is typing…';
        line.hidden = false;
        window.clearTimeout(typingHide);
        typingHide = window.setTimeout(function () { line.hidden = true; }, 5000);
    }

    document.addEventListener('click', function (event) {
        var pill = event.target.closest('[data-new-messages]');
        if (pill) {
            var box = document.querySelector('#sp-thread .sp-thread');
            if (box) { box.scrollTop = box.scrollHeight; }
            pill.hidden = true;
        }
    });

    document.addEventListener('scroll', function (event) {
        var box = event.target;
        if (box && box.classList && box.classList.contains('sp-thread') && box.scrollHeight - box.scrollTop - box.clientHeight < 80) {
            var pill = document.querySelector('#sp-thread [data-new-messages]');
            if (pill) { pill.hidden = true; }
        }
    }, true);

    // "is typing": at most once every three seconds while the member types
    document.addEventListener('input', function (event) {
        if (!event.target || event.target.id !== 'sp-body' || !socket || socket.readyState !== 1) { return; }
        var now = Date.now();
        if (now - typingSentAt < 3000) { return; }
        typingSentAt = now;
        var mode = document.querySelector('#sp-thread input[name="mode"]:checked');
        socket.send(JSON.stringify({ type: 'typing', ticket_id: openTicketId(), note: !!mode && mode.value === 'note' }));
    });

    /* ------------------------------------------------------------ alerts */

    function alertsOn() { return store('sp-alerts') === '1'; }

    function syncAlertsMenu() {
        var button = document.querySelector('[data-sp-alerts]');
        if (!button) { return; }
        button.setAttribute('aria-checked', alertsOn() ? 'true' : 'false');
        var state = button.querySelector('[data-sp-alerts-state]');
        if (state) { state.textContent = alertsOn() ? 'On' : 'Off'; }
    }

    // Every page load starts without sound: the browser lets a page play only after the member has used it
    // (or, in Chrome, used the previous page of the site). So with alerts on, the sound is set up when the page
    // opens and woken by the member's first click or key press here; until then a beep is simply skipped.
    function ensureAudio() {
        if (!audio) {
            try { audio = new (window.AudioContext || window.webkitAudioContext)(); } catch (ignore) { audio = null; }
        }
        if (audio && audio.state === 'suspended') { audio.resume().catch(function () { /* still waiting for a click */ }); }
        return audio;
    }

    function wakeAudio() {
        if (!alertsOn()) { return; }
        var context = ensureAudio();
        if (context && context.state === 'running') {
            document.removeEventListener('pointerdown', wakeAudio, true);
            document.removeEventListener('keydown', wakeAudio, true);
        }
    }

    function tone(context) {
        var osc = context.createOscillator(), gain = context.createGain();
        osc.type = 'sine';
        osc.frequency.value = 880;
        gain.gain.value = 0.04;
        osc.connect(gain);
        gain.connect(context.destination);
        osc.start();
        osc.stop(context.currentTime + 0.12);
    }

    function beep() {
        try {
            var context = ensureAudio();
            if (!context) { return; }
            if (context.state === 'running') { tone(context); return; }
            context.resume().then(function () { tone(context); }, function () { /* not allowed yet */ });
        } catch (ignore) { /* no sound is fine */ }
    }

    document.addEventListener('click', function (event) {
        var button = event.target.closest('[data-sp-alerts]');
        if (!button) { return; }
        var turnOn = !alertsOn();
        store('sp-alerts', turnOn ? '1' : '0');
        if (turnOn) {
            // Both need a click from the member first, which is this one
            if (window.Notification && Notification.permission === 'default') { Notification.requestPermission(); }
            beep();
        }
        syncAlertsMenu();
    });

    function announce(text, href) {
        if (SP.toast) { SP.toast(text, 'info'); }
        if (!alertsOn()) { return; }
        beep();
        if (document.hidden && window.Notification && Notification.permission === 'granted') {
            var note = new Notification('Technical Support', { body: text, tag: 'sp-live' });
            note.onclick = function () { window.focus(); if (href) { window.location.href = href; } note.close(); };
        }
    }

    /* ------------------------------------------------------------ events */

    function onEvent(event) {
        var here = openTicketId();
        var mine = here && event.ticket_id === here;
        later('counts', 250, refreshCounts);
        if (document.getElementById('sp-list')) { later('list', 300, refreshList); }
        if (mine) {
            if (event.type === 'message.created' || event.type === 'note.created') { later('thread', 250, refreshThread); }
            if (event.type === 'message.deleted') { replaceMessage(event.data && event.data.message_id); }
            if (event.type === 'ticket.updated') { later('side', 300, function () { refreshSide(); refreshThread(); }); }
            return;
        }
        var link = '/support/tickets/' + event.ticket_id;
        if (event.type === 'ticket.created') {
            announce('New ticket ' + event.ticket_no, link);
        } else if (event.type === 'message.created') {
            announce('New message on ' + event.ticket_no, link);
        } else if (event.type === 'ticket.updated' && event.data && event.data.change === 'assigned' && event.assigned_to === ME) {
            announce('Ticket ' + event.ticket_no + ' was assigned to you', link);
        }
    }

    function refreshAll() {
        refreshCounts();
        refreshList();
        refreshSide();
        refreshThread();
    }

    function onMessage(raw) {
        var message;
        try { message = JSON.parse(raw); } catch (ignore) { return; }
        if (message.type === 'hello') {
            status('live');
            rememberLive();
            stopPolling();
            if (message.resync || !lastId) {
                lastId = message.latest_id;
                if (message.resync) { refreshAll(); }
            }
        } else if (message.type === 'event') {
            lastId = Math.max(lastId, message.id || 0);
            onEvent(message.event);
        } else if (message.type === 'typing') {
            showTyping(message.event);
        }
    }

    /* ------------------------------------------------------------ connection */

    function stopPolling() {
        window.clearInterval(pollTimer);
        pollTimer = null;
    }

    // While the socket is down: look at the server every 20 seconds and reload what changed
    function startPolling() {
        if (pollTimer) { return; }
        pollTimer = window.setInterval(function () {
            refreshCounts().then(function (data) {
                if (!data) { return; }
                if (pollLatest !== null && data.latest_id !== pollLatest) { refreshAll(); }
                pollLatest = data.latest_id;
            });
        }, 20000);
    }

    function scheduleReconnect() {
        window.clearTimeout(reconnectTimer);
        var delay = Math.min(30000, 1000 * Math.pow(2, attempts)) + Math.random() * 500;
        attempts += 1;
        reconnectTimer = window.setTimeout(connect, delay);
    }

    function connect() {
        var scheme = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        var url = scheme + window.location.host + body.getAttribute('data-sp-live') + (lastId ? '?last_event_id=' + lastId : '');
        try { socket = new WebSocket(url); } catch (ignore) { dropped(); scheduleReconnect(); startPolling(); return; }

        socket.onopen = function () { attempts = 0; };
        socket.onmessage = function (message) { onMessage(message.data); };
        socket.onclose = function (event) {
            window.clearInterval(heartbeat);
            socket = null;
            if (leaving) { return; }                       // the browser is opening another page: not a drop
            if (event.code === 4401 || event.code === 4403) { status('off'); return; }   // signed out or no access: do not hammer
            dropped();
            startPolling();
            scheduleReconnect();
        };
        socket.onerror = function () { /* onclose follows */ };

        window.clearInterval(heartbeat);
        heartbeat = window.setInterval(function () {
            if (socket && socket.readyState === 1) { socket.send(JSON.stringify({ type: 'ping' })); }
        }, 25000);
    }

    window.addEventListener('online', function () { window.clearTimeout(reconnectTimer); if (!socket) { connect(); } });
    document.addEventListener('visibilitychange', function () {
        if (!document.hidden && !socket) { window.clearTimeout(reconnectTimer); connect(); }
    });

    // Leaving for another page closes the socket; keep the Live state for the next page to start from
    window.addEventListener('pagehide', function () {
        leaving = true;
        if (socket && socket.readyState === 1) { rememberLive(); }
    });
    // Coming back through the browser's back button (page restored from memory): carry on
    window.addEventListener('pageshow', function (event) {
        if (!event.persisted) { return; }
        leaving = false;
        if (!socket) { window.clearTimeout(reconnectTimer); connect(); }
    });

    syncAlertsMenu();
    if (alertsOn()) {
        ensureAudio();
        document.addEventListener('pointerdown', wakeAudio, true);
        document.addEventListener('keydown', wakeAudio, true);
    }
    if (wasLive()) { status('live'); }                     // else the badge stays hidden until the first hello
    dropped();
    connect();
})();
