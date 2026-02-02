/**
 * Modal 管理模块
 * 提供统一的 Modal 打开/关闭控制
 */

export class ModalManager {
    constructor(containerId = 'modal-container', contentId = 'modal-content') {
        this.container = document.getElementById(containerId);
        this.content = document.getElementById(contentId);
        this.previousActiveElement = null;
        this.isOpen = false;
    }

    open(htmlContent) {
        if (this.isOpen) return;
        
        this.previousActiveElement = document.activeElement;
        this.content.innerHTML = htmlContent;
        
        // Process HTMX on new content
        if (typeof htmx !== 'undefined') {
            htmx.process(this.content);
        }
        
        this.container.classList.remove('hidden');
        this.container.setAttribute('aria-modal', 'true');
        this.container.setAttribute('role', 'dialog');
        this.isOpen = true;
        
        // Trap focus
        this.trapFocus();
        
        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('modal:opened', { 
            detail: { modal: this } 
        }));
    }

    close() {
        if (!this.isOpen) return;
        
        this.container.classList.add('hidden');
        this.container.removeAttribute('aria-modal');
        this.container.removeAttribute('role');
        this.content.innerHTML = '';
        this.isOpen = false;
        
        // Restore focus
        if (this.previousActiveElement && this.previousActiveElement.focus) {
            this.previousActiveElement.focus();
        }
        
        document.dispatchEvent(new CustomEvent('modal:closed'));
    }

    trapFocus() {
        const focusableElements = this.content.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        
        if (focusableElements.length > 0) {
            focusableElements[0].focus();
        }
    }

    openFromSwap() {
        if (!this.container || !this.content) return;

        if (!this.isOpen) {
            this.previousActiveElement = document.activeElement;
            this.container.classList.remove('hidden');
            this.container.setAttribute('aria-modal', 'true');
            this.container.setAttribute('role', 'dialog');
            this.isOpen = true;
        }

        this.trapFocus();
        document.dispatchEvent(new CustomEvent('modal:opened', {
            detail: { modal: this }
        }));
    }
}

// Singleton instance
let modalInstance = null;

export function getModal() {
    if (!modalInstance) {
        modalInstance = new ModalManager();
    }
    return modalInstance;
}

// Global functions for inline onclick handlers
window.openModal = (html) => getModal().open(html);
window.closeModal = () => getModal().close();
