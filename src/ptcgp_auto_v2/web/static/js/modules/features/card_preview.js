// --- 通用拖拽状态 ---
const dragState = {
    isDragging: false,
    startX: 0,
    startY: 0,
    rotateX: 0,
    rotateY: 0,
    targetElement: null,
    shineElement: null,
    onDragEnd: null
};

// --- 全屏预览状态 ---
export const cardPreviewState = {
    isOpen: false,
    isDragging: false,
    startX: 0,
    startY: 0,
    currentX: 0,
    currentY: 0,
    rotateX: 0,
    rotateY: 0,
    targetElement: null
};

// --- 绑定拖拽事件（通用）---
function bindDragEvents(element, options = {}) {
    const {
        maxRotateX = 30,
        maxRotateY = 30,
        sensitivity = 0.4,
        shineElement = null,
        onDragEnd = null,
        autoReset = true
    } = options;

    dragState.rotateX = 0;
    dragState.rotateY = 0;
    dragState.targetElement = element;
    dragState.shineElement = shineElement;
    dragState.onDragEnd = onDragEnd;

    const handleDragStart = (e) => {
        e.preventDefault();
        dragState.isDragging = true;
        element.classList.add('dragging');

        if (e.type === 'touchstart') {
            dragState.startX = e.touches[0].clientX;
            dragState.startY = e.touches[0].clientY;
        } else {
            dragState.startX = e.clientX;
            dragState.startY = e.clientY;
        }
    };

    const handleDragMove = (e) => {
        if (!dragState.isDragging) return;
        e.preventDefault();

        let clientX, clientY;
        if (e.type === 'touchmove') {
            clientX = e.touches[0].clientX;
            clientY = e.touches[0].clientY;
        } else {
            clientX = e.clientX;
            clientY = e.clientY;
        }

        const deltaX = clientX - dragState.startX;
        const deltaY = clientY - dragState.startY;

        dragState.rotateY += deltaX * sensitivity;
        dragState.rotateX -= deltaY * sensitivity;

        dragState.rotateX = Math.max(-maxRotateX, Math.min(maxRotateX, dragState.rotateX));
        dragState.rotateY = Math.max(-maxRotateY, Math.min(maxRotateY, dragState.rotateY));

        updateDragRotation();

        dragState.startX = clientX;
        dragState.startY = clientY;
    };

    const handleDragEnd = () => {
        if (!dragState.isDragging) return;

        dragState.isDragging = false;
        element.classList.remove('dragging');

        if (autoReset) {
            animateReset(element);
        }

        if (dragState.onDragEnd) {
            dragState.onDragEnd();
        }
    };

    element.addEventListener('mousedown', handleDragStart);
    document.addEventListener('mousemove', handleDragMove);
    document.addEventListener('mouseup', handleDragEnd);

    element.addEventListener('touchstart', handleDragStart, { passive: false });
    document.addEventListener('touchmove', handleDragMove, { passive: false });
    document.addEventListener('touchend', handleDragEnd);
}

// --- 更新旋转角度 ---
function updateDragRotation() {
    const card = dragState.targetElement;
    if (!card) return;

    card.style.transform = `rotateY(${dragState.rotateY}deg) rotateX(${dragState.rotateX}deg)`;

    if (dragState.shineElement) {
        const shineX = -dragState.rotateY * 1.5;
        const shineY = dragState.rotateX * 1.5;
        dragState.shineElement.style.transform = `translateX(${shineX}px) translateY(${shineY}px)`;
    }
}

// --- 自动回正动画 ---
function animateReset(element) {
    const startX = dragState.rotateX;
    const startY = dragState.rotateY;
    if (Math.abs(startX) < 0.1 && Math.abs(startY) < 0.1) return;

    element.style.transition = 'transform 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)';
    dragState.rotateX = 0;
    dragState.rotateY = 0;
    updateDragRotation();

    setTimeout(() => {
        if (element) element.style.transition = 'transform 0.1s ease-out';
    }, 500);
}

// --- 初始化弹窗内卡牌拖拽 ---
export function initInlineCardDrag(elementId, shineSelector = null) {
    const element = document.getElementById(elementId);
    if (!element) return null;

    const shineElement = shineSelector ? element.querySelector(shineSelector) : null;

    bindDragEvents(element, {
        maxRotateX: 25,
        maxRotateY: 25,
        sensitivity: 0.35,
        shineElement: shineElement,
        autoReset: true
    });

    return element;
}

// --- 全屏卡牌预览 ---
export function openCardPreview(cardElement) {
    if (cardPreviewState.isOpen) return;

    const cardName = cardElement.dataset.cardName || 'Unknown';
    const cardRarity = cardElement.dataset.cardRarity || '';
    const cardSet = cardElement.dataset.cardSet || '';
    const cardNumber = cardElement.dataset.cardNumber || '';
    const cardImage = cardElement.dataset.cardImageHd
        || cardElement.dataset.cardImage
        || 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==';

    const previewHTML = `
        <div id="card-preview-overlay" class="card-preview-overlay">
            <div id="card-preview-container" class="card-preview-container">
                <div id="card-preview-card" class="card-preview-card">
                    <div class="card-preview-front">
                        <img src="${cardImage}" alt="${cardName}" class="card-preview-image" draggable="false" onerror="this.onerror=null;this.src='data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=='">
                        <div id="card-preview-shine" class="card-preview-shine"></div>
                    </div>
                </div>
                <div class="card-preview-info">
                    <div class="card-preview-name">${cardName}</div>
                    <div class="card-preview-meta">
                        ${cardRarity ? `<span class="card-preview-rarity">${cardRarity}</span>` : ''}
                        ${cardSet ? `<span class="card-preview-set">${cardSet}</span>` : ''}
                        ${cardNumber ? `<span class="card-preview-number">#${cardNumber}</span>` : ''}
                    </div>
                </div>
                <div class="card-preview-hint">拖动旋转查看 / Drag to rotate</div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', previewHTML);

    const overlay = document.getElementById('card-preview-overlay');
    if (overlay) {
        overlay.addEventListener('click', (event) => {
            if (event.target !== overlay) return;
            closeCardPreview();
        });
    }

    cardPreviewState.isOpen = true;
    cardPreviewState.rotateX = 0;
    cardPreviewState.rotateY = 0;
    cardPreviewState.targetElement = document.getElementById('card-preview-card');

    const cardEl = document.getElementById('card-preview-card');
    const shineEl = document.getElementById('card-preview-shine');

    bindDragEvents(cardEl, {
        maxRotateX: 45,
        maxRotateY: 45,
        sensitivity: 0.5,
        shineElement: shineEl,
        autoReset: true
    });

    document.body.style.overflow = 'hidden';

    requestAnimationFrame(() => {
        const overlay = document.getElementById('card-preview-overlay');
        if (overlay) overlay.classList.add('active');
    });
}

// --- 关闭全屏预览 ---
export function closeCardPreview(event) {
    if (event && event.target.id !== 'card-preview-overlay') return;

    const overlay = document.getElementById('card-preview-overlay');
    if (!overlay) return;

    overlay.classList.remove('active');

    setTimeout(() => {
        overlay.remove();
        cardPreviewState.isOpen = false;
        cardPreviewState.targetElement = null;
        document.body.style.overflow = '';
    }, 300);
}
