// ICT Ticketing System - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    initializeTooltips();
    
    // Initialize real-time updates
    initializeRealTimeUpdates();
    
    // Initialize form enhancements
    initializeFormEnhancements();
    
    // Initialize notification system
    initializeNotifications();
});

// Initialize Bootstrap tooltips
function initializeTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Real-time updates for ticket status
function initializeRealTimeUpdates() {
    // Check for updates every 30 seconds on ticket pages
    if (window.location.pathname.includes('/ticket/')) {
        setInterval(checkForUpdates, 30000);
    }
    
    // Update notification count
    setInterval(updateNotificationCount, 60000);
}

// Check for ticket updates
function checkForUpdates() {
    const ticketId = getTicketIdFromUrl();
    if (ticketId) {
        // This would be expanded to use WebSockets or Server-Sent Events
        console.log('Checking for updates on ticket:', ticketId);
    }
}

// Get ticket ID from current URL
function getTicketIdFromUrl() {
    const match = window.location.pathname.match(/\/ticket\/(\d+)/);
    return match ? match[1] : null;
}

// Update notification count
function updateNotificationCount() {
    // Skip API call to prevent errors
    console.log('Notification count update skipped');
}

// Form enhancements
function initializeFormEnhancements() {
    // Auto-resize textareas
    const textareas = document.querySelectorAll('textarea');
    textareas.forEach(textarea => {
        textarea.addEventListener('input', autoResize);
        autoResize.call(textarea);
    });
    
    // Priority color preview
    const prioritySelects = document.querySelectorAll('select[name="priority"]');
    prioritySelects.forEach(select => {
        select.addEventListener('change', updatePriorityPreview);
        updatePriorityPreview.call(select);
    });
    
    // Form validation feedback
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', handleFormSubmit);
    });
}

// Auto-resize textarea
function autoResize() {
    this.style.height = 'auto';
    this.style.height = this.scrollHeight + 'px';
}

// Update priority color preview
function updatePriorityPreview() {
    const priority = this.value;
    const colors = {
        'URGENT': 'danger',
        'HIGH': 'warning',
        'MEDIUM': 'info',
        'LOW': 'success'
    };
    
    // Remove existing classes
    this.className = this.className.replace(/bg-\w+/g, '');
    
    if (colors[priority]) {
        this.classList.add('bg-' + colors[priority]);
        if (priority === 'URGENT' || priority === 'HIGH') {
            this.style.color = 'white';
        } else {
            this.style.color = '';
        }
    }
}

// Handle form submission
function handleFormSubmit(event) {
    const form = event.target;
    const submitButton = form.querySelector('button[type="submit"]');
    
    if (submitButton) {
        // Add loading state
        const originalText = submitButton.innerHTML;
        submitButton.innerHTML = '<span class="loading"></span> Processing...';
        submitButton.disabled = true;
        
        // Reset button after a delay (in case form doesn't redirect)
        setTimeout(() => {
            submitButton.innerHTML = originalText;
            submitButton.disabled = false;
        }, 5000);
    }
}

// Notification system
function initializeNotifications() {
    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
    
    // Listen for new notifications (would be enhanced with WebSockets)
    // This is a placeholder for demonstration
    window.addEventListener('newNotification', handleNewNotification);
}

// Handle new notification
function handleNewNotification(event) {
    const notification = event.detail;
    
    // Show browser notification if permission granted
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(notification.title, {
            body: notification.message,
            icon: '/static/images/logo-small.png',
            tag: 'ict-ticket-' + notification.id
        });
    }
    
    // Show in-app toast notification
    showToast(notification.title, notification.message, 'info');
}

// Show toast notification
function showToast(title, message, type = 'info') {
    const toastContainer = getOrCreateToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <strong>${title}</strong><br>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: 5000
    });
    
    bsToast.show();
    
    // Remove toast element after it's hidden
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

// Get or create toast container
function getOrCreateToastContainer() {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }
    return container;
}

// Utility functions
const Utils = {
    // Format date for display
    formatDate: function(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    },
    
    // Capitalize first letter
    capitalize: function(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    },
    
    // Truncate text
    truncate: function(str, length = 50) {
        if (str.length <= length) return str;
        return str.substr(0, length) + '...';
    },
    
    // Generate random ID
    generateId: function() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    },
    
    // Debounce function
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
};

// Search functionality
function initializeSearch() {
    const searchInputs = document.querySelectorAll('.search-input');
    searchInputs.forEach(input => {
        input.addEventListener('input', Utils.debounce(handleSearch, 300));
    });
}

function handleSearch(event) {
    const query = event.target.value.toLowerCase();
    const searchableItems = document.querySelectorAll('.searchable-item');
    
    searchableItems.forEach(item => {
        const text = item.textContent.toLowerCase();
        if (text.includes(query)) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}

// Filter functionality
function initializeFilters() {
    const filterSelects = document.querySelectorAll('.filter-select');
    filterSelects.forEach(select => {
        select.addEventListener('change', handleFilter);
    });
}

function handleFilter(event) {
    const filterType = event.target.dataset.filter;
    const filterValue = event.target.value;
    const filterableItems = document.querySelectorAll(`[data-${filterType}]`);
    
    filterableItems.forEach(item => {
        const itemValue = item.dataset[filterType];
        if (!filterValue || itemValue === filterValue) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}

// Keyboard shortcuts
document.addEventListener('keydown', function(event) {
    // Ctrl/Cmd + K for search
    if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        const searchInput = document.querySelector('.search-input');
        if (searchInput) {
            searchInput.focus();
        }
    }
    
    // Escape to close modals
    if (event.key === 'Escape') {
        const openModal = document.querySelector('.modal.show');
        if (openModal) {
            const modalInstance = bootstrap.Modal.getInstance(openModal);
            if (modalInstance) {
                modalInstance.hide();
            }
        }
    }
});

// Auto-save functionality for forms
function initializeAutoSave() {
    const autoSaveForms = document.querySelectorAll('.auto-save-form');
    autoSaveForms.forEach(form => {
        const inputs = form.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            input.addEventListener('input', Utils.debounce(() => {
                autoSaveForm(form);
            }, 2000));
        });
    });
}

function autoSaveForm(form) {
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    
    // Save to localStorage
    const formId = form.id || 'auto-save-' + Utils.generateId();
    localStorage.setItem('auto-save-' + formId, JSON.stringify(data));
    
    // Show save indicator
    showSaveIndicator();
}

function showSaveIndicator() {
    const indicator = document.getElementById('save-indicator');
    if (indicator) {
        indicator.style.display = 'inline';
        setTimeout(() => {
            indicator.style.display = 'none';
        }, 2000);
    }
}

// Print functionality
function printPage() {
    window.print();
}

function printElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        const printWindow = window.open('', '_blank');
        printWindow.document.write(`
            <html>
                <head>
                    <title>ICT Tickets - Print</title>
                    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
                    <link href="/static/css/style.css" rel="stylesheet">
                </head>
                <body>
                    ${element.outerHTML}
                </body>
            </html>
        `);
        printWindow.document.close();
        printWindow.print();
    }
}

// Export error handler
window.addEventListener('error', function(event) {
    console.error('JavaScript Error:', event.error);
    
    // Show user-friendly error message for critical errors
    if (event.error.message.includes('Network')) {
        showToast('Connection Error', 'Please check your internet connection and try again.', 'danger');
    }
});

// Initialize all features when page loads
document.addEventListener('DOMContentLoaded', function() {
    initializeSearch();
    initializeFilters();
    initializeAutoSave();
});

// Global functions for template usage
window.TicketSystem = {
    Utils: Utils,
    showToast: showToast,
    printPage: printPage,
    printElement: printElement
};
