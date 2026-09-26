/**
 * Enhanced Dropdown functionality for NeuroBeat
 * Makes all dropdown options visible without requiring clicks
 */

document.addEventListener('DOMContentLoaded', function() {
    // Convert all form-select elements to always-visible dropdowns
    const selectElements = document.querySelectorAll('.form-select');

    selectElements.forEach(select => {
        convertToVisibleDropdown(select);
    });
});

function convertToVisibleDropdown(selectElement) {
    // Skip if already converted
    if (selectElement.style.display === 'none' || selectElement.dataset.converted === 'true') return;
    selectElement.dataset.converted = 'true';

    // Create container for the custom dropdown
    const container = document.createElement('div');
    container.className = 'dropdown-container';

    // Create the visible dropdown container
    const dropdown = document.createElement('div');
    dropdown.className = 'custom-dropdown';

    // Get the original select's attributes
    const selectName = selectElement.name;
    const selectId = selectElement.id;
    const selectRequired = selectElement.required;
    const selectOnChange = selectElement.getAttribute('onchange');

    // Create hidden input to store the selected value
    const hiddenInput = document.createElement('input');
    hiddenInput.type = 'hidden';
    hiddenInput.name = selectName;
    hiddenInput.id = selectId ? selectId + '_hidden' : '';

    // IMPORTANT: Remove name and required from original select so HTML5
    // constraint validation never encounters an unfocusable hidden element!
    selectElement.removeAttribute('name');
    selectElement.removeAttribute('required');
    selectElement.required = false;

    // Create options in the visible dropdown
    let hasSelectedOption = false;
    Array.from(selectElement.options).forEach((option, index) => {
        if (option.value === '') return; // Skip empty options

        const optionDiv = document.createElement('div');
        optionDiv.className = 'dropdown-option';
        optionDiv.textContent = option.textContent;
        optionDiv.dataset.value = option.value;

        // Set selected option if pre-selected
        if (option.selected && option.value) {
            optionDiv.classList.add('selected');
            hiddenInput.value = option.value;
            selectElement.value = option.value;
            hasSelectedOption = true;
        }

        // Add click event listener with improved animation
        optionDiv.addEventListener('click', function() {
            // Remove selected class from all options
            dropdown.querySelectorAll('.dropdown-option').forEach(opt => {
                opt.classList.remove('selected');
            });

            // Add selected class to clicked option with animation
            this.classList.add('selected');

            // Update hidden input value AND original select value
            hiddenInput.value = this.dataset.value;
            selectElement.value = this.dataset.value;

            // Remove error state if present
            dropdown.style.borderColor = '';
            const err = container.querySelector('.dropdown-error-msg');
            if (err) err.remove();

            // Trigger change event
            const changeEvent = new Event('change', { bubbles: true });
            hiddenInput.dispatchEvent(changeEvent);

            // Call original onchange if it exists
            if (selectOnChange) {
                try {
                    eval(selectOnChange);
                } catch (e) {
                    console.warn('Error executing onchange:', e);
                }
            }

            // Add visual feedback
            this.style.transform = 'scale(0.98)';
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
        });

        dropdown.appendChild(optionDiv);
    });

    // Build the new structure
    container.appendChild(hiddenInput);
    container.appendChild(dropdown);

    // If select was required, intercept form submit to validate selection
    if (selectRequired) {
        const form = selectElement.closest('form');
        if (form) {
            form.addEventListener('submit', function(e) {
                if (!hiddenInput.value) {
                    e.preventDefault();
                    e.stopPropagation();
                    dropdown.style.borderColor = '#dc3545';
                    if (!container.querySelector('.dropdown-error-msg')) {
                        const err = document.createElement('div');
                        err.className = 'dropdown-error-msg text-danger small mt-1';
                        err.textContent = 'Please select an option.';
                        container.appendChild(err);
                    }
                    dropdown.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            });
        }
    }

    // Replace the original select element
    selectElement.parentNode.insertBefore(container, selectElement);
    selectElement.style.display = 'none';

    // Copy any data attributes or classes that might be needed
    if (selectElement.className.includes('form-select')) {
        container.classList.add('form-select-container');
    }

    // Store reference for easier access
    container.dataset.originalSelect = selectId || selectName;
}

// Function to get value from custom dropdown
function getDropdownValue(selectId) {
    const select = document.getElementById(selectId);
    if (!select) return null;

    // Check if it's been converted to custom dropdown
    const hiddenInput = document.querySelector(`input[name="${select.name}"]`);
    if (hiddenInput) {
        return hiddenInput.value;
    }

    // Fallback to regular select value
    return select.value;
}

// Function to set selected value in custom dropdown
function setDropdownValue(elementId, value) {
    const hiddenInput = document.getElementById(elementId);
    const container = hiddenInput?.parentElement;

    if (container) {
        // Update hidden input
        hiddenInput.value = value;

        // Update visual selection
        const dropdown = container.querySelector('.custom-dropdown');
        dropdown.querySelectorAll('.dropdown-option').forEach(option => {
            option.classList.remove('selected');
            if (option.dataset.value === value) {
                option.classList.add('selected');
            }
        });
    }
}