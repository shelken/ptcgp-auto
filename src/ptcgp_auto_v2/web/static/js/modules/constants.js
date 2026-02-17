// --- 管理页 hash 白名单 ---
export const MANAGEMENT_HASH_WHITELIST = [
    'accounts',
    'plans',
    'tasks',
    'metadata',
    'friendships',
    'daily-gift',
    'exchange-cards'
];

// --- 判断是否为管理页 hash ---
export function isManagementHash(hash) {
    return MANAGEMENT_HASH_WHITELIST.includes(hash);
}
