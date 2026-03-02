// Plan 编辑器模块 - 处理 edit_plan.html 的表单逻辑

/**
 * 计算并更新所有 interval 字段到请求参数中
 * 在 HTMX 序列化参数之前执行（htmx:configRequest 事件）
 */
function updateIntervalParameters(event) {
    const elt = event.detail?.elt;
    if (!(elt instanceof Element)) return;

    // 只处理 plan 编辑表单
    const form = elt.closest('form[data-action="sync-plan-intervals-submit"]');
    if (!form) return;

    form.querySelectorAll('[data-interval-group]').forEach((group) => {
        const daysInput = group.querySelector("[data-interval-unit='days']");
        const hoursInput = group.querySelector("[data-interval-unit='hours']");
        const minutesInput = group.querySelector("[data-interval-unit='minutes']");
        const secondsInput = group.querySelector("[data-interval-unit='seconds']");
        const totalInput = group.querySelector('[data-interval-total]');

        if (!daysInput || !hoursInput || !minutesInput || !secondsInput || !totalInput) {
            return;
        }

        const days = parseInt(daysInput.value || '0', 10) || 0;
        const hours = parseInt(hoursInput.value || '0', 10) || 0;
        const minutes = parseInt(minutesInput.value || '0', 10) || 0;
        const seconds = parseInt(secondsInput.value || '0', 10) || 0;
        const total = (days * 86400) + (hours * 3600) + (minutes * 60) + seconds;

        // 从 input name 提取 task_type (格式: task_interval_{task_type})
        const nameMatch = totalInput.name?.match(/^task_interval_(.+)$/);
        if (nameMatch) {
            const taskType = nameMatch[1];
            event.detail.parameters[`task_interval_${taskType}`] = String(Math.max(0, total));
        }
    });
}

// 注册 HTMX 配置请求事件监听器
document.body.addEventListener('htmx:configRequest', updateIntervalParameters);
