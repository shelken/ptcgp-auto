export async function fetchText(url) {
    const response = await fetch(url, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    });
    if (!response.ok) {
        throw new Error(`请求失败: ${response.status}`);
    }
    return response.text();
}
export async function fetchJson(url) {
    const response = await fetch(url, {
        headers: {
            Accept: 'application/json'
        }
    });
    if (!response.ok) {
        throw new Error(`请求失败: ${response.status}`);
    }
    return (await response.json());
}
