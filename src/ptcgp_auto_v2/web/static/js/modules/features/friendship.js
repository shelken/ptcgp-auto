// 好友关系模块 - 处理 friendship_list.html 的表单逻辑

/**
 * 同步 friendship 状态表单字段
 * 在 HTMX 配置请求时同步 biz_date_local 到状态表单
 */
function syncFriendshipState(event) {
    const elt = event.detail?.elt;
    if (!(elt instanceof Element)) return;

    // 处理 friendship 状态表单同步
    const select = elt.closest('[data-action="sync-friendship-state"]');
    if (select instanceof HTMLSelectElement) {
        const stateName = select.dataset.stateName;
        if (!stateName) return;

        const stateInput = document.querySelector(`#friendship-state-form input[name="${stateName}"]`);
        if (stateInput) {
            stateInput.value = select.value;
        }

        // 触发筛选缓存保存
        const stateForm = document.getElementById('friendship-state-form');
        if (stateForm instanceof HTMLFormElement && stateForm.dataset.filterCacheKey) {
            // 触发 filter:saved 事件
            document.dispatchEvent(new CustomEvent('filter:saved', {
                detail: { formId: stateForm.id, form: stateForm }
            }));
        }
    }
}

// 注册 change 事件监听器处理 select 变更
document.body.addEventListener('change', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;

    const actionElement = target.closest('[data-action="sync-friendship-state"]');
    if (!actionElement) return;

    const stateName = actionElement.dataset.stateName;
    if (!stateName) return;

    const stateInput = document.querySelector(`#friendship-state-form input[name="${stateName}"]`);
    if (stateInput) {
        stateInput.value = actionElement.value;
    }

    const stateForm = document.getElementById('friendship-state-form');
    if (stateForm instanceof HTMLFormElement && stateForm.dataset.filterCacheKey) {
        document.dispatchEvent(new CustomEvent('filter:saved', {
            detail: { formId: stateForm.id, form: stateForm }
        }));
    }
});
