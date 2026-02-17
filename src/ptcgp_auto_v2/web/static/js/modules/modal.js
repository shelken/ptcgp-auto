/**
 * Modal 管理模块
 * 提供统一的 Modal 打开/关闭控制
 */

export class ModalManager {
    constructor(containerId = 'modal-container', contentId = 'modal-content') {
        this.container = document.getElementById(containerId);
        this.content = document.getElementById(contentId);
        this.previousActiveElement = null;
        this.previousBodyOverflow = null;
        this.isOpen = false;

        if (this.container) {
            this.container.addEventListener('click', (event) => {
                if (event.target === this.container) {
                    this.close();
                }
            });
        }

        this.contentModeClasses = [
            'modal-content--owned-card-fixed',
        ];
    }

    applyContentMode() {
        if (!this.content) return;
        this.content.classList.remove(...this.contentModeClasses);

        const modeElement = this.content.querySelector('[data-modal-mode]');
        if (!modeElement) return;
        const mode = modeElement.getAttribute('data-modal-mode');
        if (mode === 'owned-card-fixed') {
            this.content.classList.add('modal-content--owned-card-fixed');
        }
    }

    open(htmlContent) {
        if (this.isOpen) return;
        
        this.previousActiveElement = document.activeElement;
        this.content.innerHTML = htmlContent;
        this.applyContentMode();
        
        // Process HTMX on new content
        if (typeof htmx !== 'undefined') {
            htmx.process(this.content);
        }
        
        this.container.classList.remove('hidden');
        this.container.setAttribute('aria-modal', 'true');
        this.container.setAttribute('role', 'dialog');
        this.isOpen = true;

        this.lockBodyScroll();
        
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
        this.content.classList.remove(...this.contentModeClasses);
        this.isOpen = false;

        this.unlockBodyScroll();
        
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
            this.lockBodyScroll();
        }

        this.applyContentMode();

        this.trapFocus();
        document.dispatchEvent(new CustomEvent('modal:opened', {
            detail: { modal: this }
        }));
    }

    lockBodyScroll() {
        if (this.previousBodyOverflow === null) {
            this.previousBodyOverflow = document.body.style.overflow;
        }
        document.body.style.overflow = 'hidden';
        document.documentElement.style.overflow = 'hidden';
    }

    unlockBodyScroll() {
        if (this.previousBodyOverflow !== null) {
            document.body.style.overflow = this.previousBodyOverflow;
            this.previousBodyOverflow = null;
        } else {
            document.body.style.overflow = '';
        }
        document.documentElement.style.overflow = '';
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
