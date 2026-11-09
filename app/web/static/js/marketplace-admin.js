/* Marketplace Control Center: repeating rows, gallery, dependent fields and delete confirmation. */
(function () {
    'use strict';

    function renumberVariants() {
        document.querySelectorAll('[data-variant-row]').forEach(function (row, index) {
            row.querySelector('[name="variant_row"]').value = index;
            row.querySelector('[name="variant_default"]').value = index;
        });
    }

    function addRow(button) {
        var list = document.getElementById(button.dataset.addRow);
        var template = document.getElementById(button.dataset.template);
        var row = template.content.firstElementChild.cloneNode(true);
        list.appendChild(row);
        renumberVariants();
        var first = row.querySelector('input[type="text"]');
        if (first) first.focus();
    }

    function moveImage(item, direction) {
        var sibling = direction < 0 ? item.previousElementSibling : item.nextElementSibling;
        if (!sibling) return;
        if (direction < 0) item.parentNode.insertBefore(item, sibling);
        else item.parentNode.insertBefore(sibling, item);
    }

    function previewNewImages(input) {
        var list = document.getElementById(input.dataset.preview);
        list.textContent = '';
        Array.prototype.forEach.call(input.files, function (file) {
            var item = document.createElement('li');
            var image = document.createElement('img');
            image.alt = file.name;
            image.src = URL.createObjectURL(file);
            image.onload = function () { URL.revokeObjectURL(image.src); };
            item.appendChild(image);
            list.appendChild(item);
        });
        var count = document.querySelectorAll('[name="keep_image_id"]').length + input.files.length;
        var max = parseInt(input.dataset.max, 10);
        var message = document.getElementById(input.dataset.message);
        message.textContent = count > max ? 'A listing can have at most ' + max + ' images.' : '';
    }

    function applyVisibility() {
        document.querySelectorAll('[data-show-if]').forEach(function (element) {
            var parts = element.dataset.showIf.split('=');
            var control = document.querySelector('[name="' + parts[0] + '"]');
            element.hidden = !control || control.value !== parts[1];
        });
    }

    function filterBreeds() {
        var type = document.querySelector('[name="animal_type_id"]');
        var breed = document.querySelector('[name="breed_id"]');
        if (!type || !breed) return;
        Array.prototype.forEach.call(breed.options, function (option) {
            var matches = !option.value || option.dataset.type === type.value;
            option.hidden = !matches;
            option.disabled = !matches;
        });
        if (breed.selectedOptions[0] && breed.selectedOptions[0].disabled) breed.value = '';
    }

    document.addEventListener('click', function (event) {
        var button = event.target.closest('button');
        if (!button) return;

        if (button.dataset.addRow) {
            addRow(button);
        } else if ('removeRow' in button.dataset) {
            button.closest('[data-row]').remove();
            renumberVariants();
        } else if (button.dataset.move) {
            moveImage(button.closest('li'), parseInt(button.dataset.move, 10));
        } else if ('removeImage' in button.dataset) {
            button.closest('li').remove();
        }
    });

    document.addEventListener('change', function (event) {
        if (event.target.dataset.preview) previewNewImages(event.target);
        if (event.target.name === 'animal_type_id') filterBreeds();
        applyVisibility();
    });

    // Delete buttons: <form data-confirm="..."> is sent only after the dialog says yes
    document.addEventListener('submit', function (event) {
        var form = event.target;
        if (!form.dataset.confirm || form.dataset.confirmed) return;
        event.preventDefault();
        var dialog = document.getElementById('mk-confirm');
        dialog.querySelector('p').textContent = form.dataset.confirm;
        dialog.returnValue = '';
        dialog.onclose = function () {
            if (dialog.returnValue === 'yes') {
                form.dataset.confirmed = '1';
                form.submit();
            }
        };
        dialog.showModal();
    });

    // The sidebar highlights exact paths only; keep its item active on every Control Center page.
    // This runs before DOMContentLoaded, so the sidebar also opens the group that holds it.
    var menuItem = document.querySelector('.menu-item[data-match="/admin/marketplace"]');
    if (menuItem) menuItem.classList.add('active');

    renumberVariants();
    filterBreeds();
    applyVisibility();
})();
