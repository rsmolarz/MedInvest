// Main JavaScript file for MedLearn Invest

// Initialize tooltips and popovers
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize Bootstrap popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    var alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        if (alert.classList.contains('alert-success') || alert.classList.contains('alert-info')) {
            setTimeout(function() {
                var bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }, 5000);
        }
    });

    // Form validation enhancement
    var forms = document.querySelectorAll('.needs-validation');
    Array.prototype.slice.call(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // Search functionality enhancement
    var searchInput = document.getElementById('search');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            var query = this.value.toLowerCase();
            var searchableElements = document.querySelectorAll('.searchable');
            
            searchableElements.forEach(function(element) {
                var text = element.textContent.toLowerCase();
                var parent = element.closest('.card');
                
                if (text.includes(query) || query === '') {
                    parent.style.display = '';
                } else {
                    parent.style.display = 'none';
                }
            });
        });
    }

    // Progress tracking
    trackModuleProgress();
    
    // Professional verification status
    updateVerificationStatus();
    
    // Portfolio calculations
    if (window.location.pathname.includes('portfolio')) {
        initializePortfolioCalculations();
    }
});

// Module progress tracking
function trackModuleProgress() {
    var modulePages = document.querySelectorAll('.module-page');
    
    modulePages.forEach(function(page) {
        var startTime = Date.now();
        
        // Track time spent on page
        window.addEventListener('beforeunload', function() {
            var timeSpent = Math.floor((Date.now() - startTime) / 1000 / 60); // minutes
            
            // Send time spent to server (would be implemented with actual API)
            console.log('Time spent on module:', timeSpent, 'minutes');
        });
    });
}

// Professional verification status updates
function updateVerificationStatus() {
    var verificationBadges = document.querySelectorAll('.verification-status');
    
    verificationBadges.forEach(function(badge) {
        if (badge.textContent.includes('Pending')) {
            badge.innerHTML = '<i class="fas fa-clock me-1"></i>Verification Pending';
            badge.className = 'badge bg-warning text-dark';
        } else if (badge.textContent.includes('Verified')) {
            badge.innerHTML = '<i class="fas fa-check-circle me-1"></i>Verified Professional';
            badge.className = 'badge bg-success';
        }
    });
}

// Portfolio calculation utilities
function initializePortfolioCalculations() {
    var transactionForm = document.querySelector('#transaction-form');
    
    if (transactionForm) {
        var quantityInput = transactionForm.querySelector('input[name="quantity"]');
        var priceInput = transactionForm.querySelector('input[name="price"]');
        var totalDisplay = document.getElementById('transaction-total');
        
        function updateTotal() {
            var quantity = parseFloat(quantityInput.value) || 0;
            var price = parseFloat(priceInput.value) || 0;
            var total = quantity * price;
            
            if (totalDisplay) {
                totalDisplay.textContent = '$' + total.toFixed(2);
            }
        }
        
        quantityInput.addEventListener('input', updateTotal);
        priceInput.addEventListener('input', updateTotal);
    }
}

// Utility functions for professional platform

// Format currency for display
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

// Format dates for medical professionals
function formatDate(date) {
    return new Intl.DateTimeFormat('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    }).format(new Date(date));
}

// Professional form validation
function validateMedicalLicense(license) {
    // Basic validation - in real app would check against medical board databases
    return license && license.length >= 6;
}

function validateEmail(email) {
    var re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

// Forum interaction utilities
function toggleReplyForm(postId) {
    var form = document.getElementById('reply-form-' + postId);
    if (form) {
        if (form.style.display === 'none' || form.style.display === '') {
            form.style.display = 'block';
            var textarea = form.querySelector('textarea');
            if (textarea) {
                textarea.focus();
            }
        } else {
            form.style.display = 'none';
        }
    }
}

// Learning module utilities
function markModuleComplete(moduleId) {
    // Would integrate with backend API
    console.log('Marking module complete:', moduleId);
    
    // Show completion animation
    var completionAlert = document.createElement('div');
    completionAlert.className = 'alert alert-success alert-dismissible fade show';
    completionAlert.innerHTML = `
        <i class="fas fa-check-circle me-2"></i>
        Module completed successfully! Well done, Doctor.
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    var container = document.querySelector('.container');
    if (container) {
        container.insertBefore(completionAlert, container.firstChild);
        
        // Auto-hide after 5 seconds
        setTimeout(function() {
            var bsAlert = new bootstrap.Alert(completionAlert);
            bsAlert.close();
        }, 5000);
    }
}

// Professional networking features
function connectWithPeer(userId) {
    console.log('Connecting with peer:', userId);
    // Would implement professional networking features
}

// Investment education utilities
function calculateCompoundInterest(principal, rate, time, compound) {
    return principal * Math.pow((1 + rate / compound), compound * time);
}

function calculateSimpleInterest(principal, rate, time) {
    return principal * (1 + rate * time);
}

// Medical specialty color coding
function getSpecialtyColor(specialty) {
    var colors = {
        'Cardiology': '#dc3545',
        'Neurology': '#6f42c1',
        'Orthopedic Surgery': '#fd7e14',
        'Pediatrics': '#20c997',
        'Surgery': '#dc3545',
        'Family Medicine': '#0dcaf0',
        'Internal Medicine': '#198754',
        'Emergency Medicine': '#ffc107',
        'Anesthesiology': '#6c757d'
    };
    
    return colors[specialty] || '#0066cc';
}

// Professional dashboard utilities
function updateDashboardStats() {
    // Would fetch real-time statistics
    console.log('Updating dashboard statistics...');
}

// Error handling for professional platform
function showProfessionalError(message) {
    var errorAlert = document.createElement('div');
    errorAlert.className = 'alert alert-danger alert-dismissible fade show';
    errorAlert.innerHTML = `
        <i class="fas fa-exclamation-triangle me-2"></i>
        <strong>Error:</strong> ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    var container = document.querySelector('.container');
    if (container) {
        container.insertBefore(errorAlert, container.firstChild);
    }
}

// Success message for professional actions
function showProfessionalSuccess(message) {
    var successAlert = document.createElement('div');
    successAlert.className = 'alert alert-success alert-dismissible fade show';
    successAlert.innerHTML = `
        <i class="fas fa-check-circle me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    var container = document.querySelector('.container');
    if (container) {
        container.insertBefore(successAlert, container.firstChild);
        
        // Auto-hide after 3 seconds
        setTimeout(function() {
            var bsAlert = new bootstrap.Alert(successAlert);
            bsAlert.close();
        }, 3000);
    }
}

// Export functions for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatCurrency,
        formatDate,
        validateMedicalLicense,
        validateEmail,
        calculateCompoundInterest,
        calculateSimpleInterest,
        getSpecialtyColor
    };
}
