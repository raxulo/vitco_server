/* Store behaviour. Pages work without it; this adds slideshow controls, gallery, size picker and quick filters. */
(function () {
    'use strict';

    var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var scrollMode = reducedMotion ? 'auto' : 'smooth';

    function setupCarousel(carousel) {
        var INTERVAL_MS = 6000;
        var track = carousel.querySelector('[data-slides]');
        var dots = Array.prototype.slice.call(carousel.querySelectorAll('[data-carousel-dot]'));
        var pauseButton = carousel.querySelector('[data-carousel-pause]');
        if (!dots.length) return;

        var userPaused = reducedMotion;
        var hovering = false;
        var index = 0;

        function show(target) {
            track.scrollTo({ left: target * track.clientWidth, behavior: scrollMode });
        }

        function markDot() {
            index = Math.round(track.scrollLeft / track.clientWidth);
            dots.forEach(function (dot, position) {
                if (position === index) dot.setAttribute('aria-current', 'true');
                else dot.removeAttribute('aria-current');
            });
        }

        function drawPauseButton() {
            pauseButton.setAttribute('aria-label', userPaused ? 'Play slideshow' : 'Pause slideshow');
            pauseButton.querySelector('i').className = 'fa-solid ' + (userPaused ? 'fa-play' : 'fa-pause');
        }

        dots.forEach(function (dot) {
            dot.addEventListener('click', function () {
                userPaused = true;
                drawPauseButton();
                show(parseInt(dot.dataset.carouselDot, 10));
            });
        });
        pauseButton.addEventListener('click', function () {
            userPaused = !userPaused;
            drawPauseButton();
        });
        track.addEventListener('scroll', function () { window.requestAnimationFrame(markDot); }, { passive: true });
        carousel.addEventListener('mouseenter', function () { hovering = true; });
        carousel.addEventListener('mouseleave', function () { hovering = false; });
        carousel.addEventListener('focusin', function () { hovering = true; });
        carousel.addEventListener('focusout', function () { hovering = false; });

        window.setInterval(function () {
            if (userPaused || hovering || document.hidden) return;
            show((index + 1) % dots.length);
        }, INTERVAL_MS);

        drawPauseButton();
        markDot();
    }

    function setupGallery(gallery) {
        var track = gallery.querySelector('[data-gallery-track]');
        var thumbs = Array.prototype.slice.call(gallery.querySelectorAll('[data-gallery-thumb]'));
        if (!thumbs.length) return;

        thumbs.forEach(function (thumb) {
            thumb.addEventListener('click', function () {
                track.scrollTo({ left: parseInt(thumb.dataset.galleryThumb, 10) * track.clientWidth, behavior: scrollMode });
            });
        });
        track.addEventListener('scroll', function () {
            window.requestAnimationFrame(function () {
                var index = Math.round(track.scrollLeft / track.clientWidth);
                thumbs.forEach(function (thumb, position) {
                    if (position === index) thumb.setAttribute('aria-current', 'true');
                    else thumb.removeAttribute('aria-current');
                });
            });
        }, { passive: true });
    }

    function setText(selector, text) {
        var element = document.querySelector(selector);
        if (element) element.textContent = text;
    }

    function chooseSize(input) {
        var hasOffer = parseInt(input.dataset.off, 10) > 0;
        document.querySelectorAll('[data-buy]').forEach(function (button) {
            button.disabled = input.dataset.inStock !== '1';
        });
        setText('[data-size-price]', input.dataset.price);
        setText('[data-size-mrp]', input.dataset.mrp);
        setText('[data-size-off]', input.dataset.off + '% off');
        setText('[data-size-stock]', input.dataset.stock);
        document.querySelector('[data-size-mrp]').hidden = !hasOffer;
        document.querySelector('[data-size-off]').hidden = !hasOffer;
    }

    document.querySelectorAll('[data-carousel]').forEach(setupCarousel);
    document.querySelectorAll('[data-gallery]').forEach(setupGallery);

    document.addEventListener('change', function (event) {
        var target = event.target;
        if (target.name === 'variant_id' && target.dataset.price) chooseSize(target);
        if ('autosubmit' in target.dataset) target.form.requestSubmit();
    });

    document.documentElement.classList.add('js');

    // Against double clicks; the server would still make only one order
    document.addEventListener('submit', function (event) {
        if (!('checkout' in event.target.dataset)) return;
        var button = event.target.querySelector('[data-place-order]');
        button.disabled = true;
        button.textContent = 'Placing your order…';
    });

    // Filters start closed on phones and tablets, so results come first
    var filters = document.querySelector('[data-filters]');
    if (filters && window.matchMedia('(max-width: 900px)').matches) filters.removeAttribute('open');
})();
