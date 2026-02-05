def build_owned_cards_next_page_url(
    page: int,
    lang: str,
    sort_by: str,
    account_id: int | None,
    rarity: list[str],
    card_type: list[str],
    set_code: list[str],
    pack_name: list[str],
    element: list[str],
) -> str:
    """构建已拥有卡牌分页 URL。"""
    next_page_url = f"/api/owned-cards?page={page + 1}&lang={lang}&sort_by={sort_by}"
    if account_id is not None:
        next_page_url += f"&account_id={account_id}"
    for item in rarity:
        next_page_url += f"&rarity={item}"
    for item in card_type:
        next_page_url += f"&card_type={item}"
    for item in set_code:
        next_page_url += f"&set_code={item}"
    for item in pack_name:
        next_page_url += f"&pack_name={item}"
    for item in element:
        next_page_url += f"&element={item}"
    return next_page_url
