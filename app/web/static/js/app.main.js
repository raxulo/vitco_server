(() => {
    const currentPath = window.location.pathname;

    document
        .querySelectorAll(".menu-item[data-match]")
        .forEach((item) => {

            const match = item.dataset.match;

            if (
                currentPath === match ||
                currentPath === `${match}/`
            ) {
                item.classList.add("active");
            }
        });
})();

// Collapsible Tree-view Sidebar Accordion
window.addEventListener('DOMContentLoaded', () => {
    const groups = document.querySelectorAll('.menu-group');
    groups.forEach(group => {
        const header = group.querySelector('.menu-group-header');
        const hasActiveChild = group.querySelector('.menu-item.active') !== null;
        
        if (hasActiveChild) {
            group.classList.add('expanded');
        }
        
        header.addEventListener('click', () => {
            group.classList.toggle('expanded');
        });
    });

    // Auto scroll active sidebar menu item into view
    const activeItem = document.querySelector('.menu-item.active');
    if (activeItem) {
        activeItem.scrollIntoView({ block: 'nearest', behavior: 'instant' });
    }
});