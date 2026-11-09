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
        header.setAttribute('aria-expanded', String(group.classList.contains('expanded')));

        const toggleGroup = () => {
            const expanded = group.classList.toggle('expanded');
            header.setAttribute('aria-expanded', String(expanded));
        };
        header.addEventListener('click', toggleGroup);
        header.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                toggleGroup();
            }
        });
    });

    // Auto scroll active sidebar menu item into view
    const activeItem = document.querySelector('.menu-item.active');
    if (activeItem) {
        activeItem.scrollIntoView({ block: 'nearest', behavior: 'instant' });
    }

    syncSidebarCollapseButton();
});

// ── Sidebar: collapse / expand on desktop (remembered), off-canvas on phones ──
function isSidebarCollapsed() {
    return document.documentElement.classList.contains('sidebar-collapsed');
}

function syncSidebarCollapseButton() {
    const btn = document.getElementById('sidebar-collapse-btn');
    if (!btn) return;
    const collapsed = isSidebarCollapsed();
    btn.setAttribute('aria-expanded', String(!collapsed));
    btn.title = collapsed ? 'Expand sidebar (Ctrl + B)' : 'Collapse sidebar (Ctrl + B)';
}

function toggleSidebarCollapse() {
    const collapsed = document.documentElement.classList.toggle('sidebar-collapsed');
    try {
        localStorage.setItem('sidebarCollapsed', collapsed ? '1' : '0');
    } catch (e) { /* storage blocked: state lasts for this page only */ }
    document.querySelector('.sidebar-tooltip')?.classList.remove('show');
    syncSidebarCollapseButton();
}

// Hamburger in the topbar (phones & tablets): slide the sidebar in / out
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (!sidebar) return;
    const open = sidebar.classList.toggle('open');
    if (overlay) overlay.classList.toggle('show', open);
    document.body.classList.toggle('sidebar-open', open);
}

function closeSidebar() {
    document.getElementById('sidebar')?.classList.remove('open');
    document.getElementById('sidebar-overlay')?.classList.remove('show');
    document.body.classList.remove('sidebar-open');
}

// Collapsed icon rail: instant label tooltip next to the hovered item
(() => {
    let tip = null;

    function hideTip() {
        tip?.classList.remove('show');
    }

    document.addEventListener('mouseover', (e) => {
        const item = e.target.closest?.('.sidebar .menu-item[data-tooltip]');
        if (!item || !isSidebarCollapsed() || window.matchMedia('(max-width: 992px)').matches) {
            if (!item) hideTip();
            return;
        }
        if (!tip) {
            tip = document.createElement('div');
            tip.className = 'sidebar-tooltip';
            tip.setAttribute('role', 'tooltip');
            document.body.appendChild(tip);
        }
        const rect = item.getBoundingClientRect();
        tip.textContent = item.dataset.tooltip;
        tip.style.left = `${rect.right + 12}px`;
        tip.style.top = `${rect.top + rect.height / 2}px`;
        tip.classList.add('show');
    });

    document.addEventListener('scroll', hideTip, true);
    window.addEventListener('blur', hideTip);

    // Auto-close drawer on mobile / tablet when navigation item is clicked
    document.addEventListener('click', (e) => {
        const item = e.target.closest?.('.sidebar .menu-item');
        if (item && window.matchMedia('(max-width: 992px)').matches) {
            closeSidebar();
        }
    });

    // Auto-reset mobile open state if resized to desktop
    window.addEventListener('resize', () => {
        if (window.innerWidth > 992) {
            closeSidebar();
        }
    });
})();

window.toggleSidebarCollapse = toggleSidebarCollapse;
window.toggleSidebar = toggleSidebar;
window.closeSidebar = closeSidebar;

document.addEventListener('keydown', (e) => {
    // Ctrl / Cmd + B toggles the sidebar (not while typing in a field)
    const typing = e.target.closest?.('input, textarea, select, [contenteditable="true"]');
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === 'b' && !typing) {
        e.preventDefault();
        if (window.matchMedia('(max-width: 992px)').matches) {
            toggleSidebar();
        } else {
            toggleSidebarCollapse();
        }
    }
    if (e.key === 'Escape') closeSidebar();
});