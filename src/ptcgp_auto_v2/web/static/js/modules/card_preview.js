// --- 卡牌预览状态 ---
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

// --- 卡牌预览功能 ---
export function openCardPreview(cardElement) {
    // 防止重复打开
    if (cardPreviewState.isOpen) return;

    const cardName = cardElement.dataset.cardName || 'Unknown';
    const cardRarity = cardElement.dataset.cardRarity || '';
    const cardSet = cardElement.dataset.cardSet || '';
    const cardNumber = cardElement.dataset.cardNumber || '';
    const cardImage = cardElement.dataset.cardImageHd
        || cardElement.dataset.cardImage
        || '/static/card_back.png';

    const previewHTML = `
        <div id="card-preview-overlay" class="card-preview-overlay" onclick="closeCardPreview(event)">
            <div id="card-preview-container" class="card-preview-container">
                <div id="card-preview-card" class="card-preview-card">
                    <div class="card-preview-front">
                        <img src="${cardImage}" alt="${cardName}" class="card-preview-image" draggable="false" onerror="this.src='/static/card_back.png'">
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

    cardPreviewState.isOpen = true;
    cardPreviewState.rotateX = 0;
    cardPreviewState.rotateY = 0;
    cardPreviewState.targetElement = document.getElementById('card-preview-card');

    bindCardPreviewEvents();

    document.body.style.overflow = 'hidden';

    requestAnimationFrame(() => {
        const overlay = document.getElementById('card-preview-overlay');
        if (overlay) overlay.classList.add('active');
    });
}

// --- 关闭卡牌预览 ---
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

// --- 绑定拖拽事件 ---
function bindCardPreviewEvents() {
    const container = document.getElementById('card-preview-container');
    if (!container) return;

    container.addEventListener('mousedown', handleDragStart);
    document.addEventListener('mousemove', handleDragMove);
    document.addEventListener('mouseup', handleDragEnd);

    container.addEventListener('touchstart', handleDragStart, { passive: false });
    document.addEventListener('touchmove', handleDragMove, { passive: false });
    document.addEventListener('touchend', handleDragEnd);
}

// --- 拖拽开始 ---
function handleDragStart(e) {
    if (!cardPreviewState.isOpen) return;
    e.preventDefault();

    cardPreviewState.isDragging = true;

    if (e.type === 'touchstart') {
        cardPreviewState.startX = e.touches[0].clientX;
        cardPreviewState.startY = e.touches[0].clientY;
    } else {
        cardPreviewState.startX = e.clientX;
        cardPreviewState.startY = e.clientY;
    }

    const card = document.getElementById('card-preview-card');
    if (card) card.classList.add('dragging');
}

// --- 拖拽移动 ---
function handleDragMove(e) {
    if (!cardPreviewState.isDragging || !cardPreviewState.isOpen) return;

    e.preventDefault();

    let clientX;
    let clientY;
    if (e.type === 'touchmove') {
        clientX = e.touches[0].clientX;
        clientY = e.touches[0].clientY;
    } else {
        clientX = e.clientX;
        clientY = e.clientY;
    }

    const deltaX = clientX - cardPreviewState.startX;
    const deltaY = clientY - cardPreviewState.startY;

    cardPreviewState.rotateY += deltaX * 0.5;
    cardPreviewState.rotateX -= deltaY * 0.5;

    cardPreviewState.rotateX = Math.max(-45, Math.min(45, cardPreviewState.rotateX));
    cardPreviewState.rotateY = Math.max(-45, Math.min(45, cardPreviewState.rotateY));

    updateCardRotation();

    cardPreviewState.startX = clientX;
    cardPreviewState.startY = clientY;
}

// --- 拖拽结束 ---
function handleDragEnd() {
    if (!cardPreviewState.isDragging) return;

    cardPreviewState.isDragging = false;

    const card = document.getElementById('card-preview-card');
    if (card) card.classList.remove('dragging');

    animateResetToFront();
}

// --- 更新卡牌旋转 ---
function updateCardRotation() {
    const card = cardPreviewState.targetElement;
    if (!card) return;

    card.style.transform = `rotateY(${cardPreviewState.rotateY}deg) rotateX(${cardPreviewState.rotateX}deg)`;
    updateShineEffect();
}

// --- 更新卡牌光影 ---
function updateShineEffect() {
    const shine = document.getElementById('card-preview-shine');
    if (!shine) return;

    const shineX = -cardPreviewState.rotateY * 2;
    const shineY = cardPreviewState.rotateX * 2;

    const angle = 115 + (cardPreviewState.rotateY * 0.3);
    const opacity = 0.4 + (Math.abs(cardPreviewState.rotateY) / 90) * 0.3;

    shine.style.background = `linear-gradient(
        ${angle}deg,
        rgba(255, 255, 255, 0) 0%,
        rgba(255, 255, 255, 0) 35%,
        rgba(255, 255, 255, ${opacity}) 50%,
        rgba(255, 255, 255, 0) 65%,
        rgba(255, 255, 255, 0) 100%
    )`;
    shine.style.transform = `translateZ(2px) translateX(${shineX}px) translateY(${shineY}px)`;
}

// --- 自动回正动画 ---
function animateResetToFront() {
    if (!cardPreviewState.isOpen) return;

    const card = document.getElementById('card-preview-card');
    if (!card) return;

    const startX = cardPreviewState.rotateX;
    const startY = cardPreviewState.rotateY;
    if (Math.abs(startX) < 0.1 && Math.abs(startY) < 0.1) return;

    card.style.transition = 'transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)';
    cardPreviewState.rotateX = 0;
    cardPreviewState.rotateY = 0;
    updateCardRotation();

    setTimeout(() => {
        if (card) card.style.transition = 'transform 0.15s ease-out';
    }, 600);
}
