import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const BASE_URL = process.env.PTCGP_WEB_E2E_BASE_URL ?? 'http://127.0.0.1:8000'
const LANG = 'en'
const EXPECTED_PACK_POINTS = new Map([
  ['A1', 111],
  ['A2', 222]
])

type BootstrapResponse = {
  options: {
    card_sets: Array<{ code: string; display_name: string }>
    rarities: string[]
  }
}

type RecordsItem = {
  account_name: string
  current_points: number | null
  series: string
  record: {
    account_id: number
  }
}

type RecordsResponse = {
  items: RecordsItem[]
}

type OwnedCardItem = {
  card: {
    id: number
    name: string
  }
  total_count: number
}

type OwnedCardsResponse = {
  items: OwnedCardItem[]
}

type OwnedCardDetailResponse = {
  card: {
    id: number
    name: string
  }
  total_accounts: number
  total_count: number
}

type ExchangeAccountsResponse = {
  accounts: Array<{
    account_id: number
    count: number
    exchange_points: number
  }>
  total_items: number
  total_count: number
}

async function getJson<T>(request: APIRequestContext, path: string): Promise<T> {
  const response = await request.get(`${BASE_URL}${path}`)
  expect(response.ok(), `${path} status=${response.status()}`).toBe(true)
  return await response.json() as T
}

async function waitForAppReady(page: Page): Promise<void> {
  await expect(page.locator('.tab-nav')).toBeVisible()
}

async function collectConsoleErrors(page: Page): Promise<string[]> {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') {
      errors.push(message.text())
    }
  })
  page.on('pageerror', (error) => {
    errors.push(error.message)
  })
  return errors
}

test.describe('最近 Web 提交浏览器 E2E', () => {
  test('Records 根路由、query/lang、筛选 URL 同步与 History 不被旧 state 覆盖', async ({ page, request }) => {
    const bootstrap = await getJson<BootstrapResponse>(request, `/api/react/bootstrap?lang=${LANG}`)
    const firstSet = bootstrap.options.card_sets.find((set) => set.code === 'A1')
    expect(firstSet, 'Web E2E fixture 必须包含 A1 card_set').toBeDefined()

    await page.goto(`${BASE_URL}/#/?lang=${LANG}`)
    await waitForAppReady(page)
    await expect(page).toHaveURL(/#\/records\?lang=en/)

    if (!firstSet) {
      throw new Error('Web E2E fixture 缺少 A1 card_set')
    }

    await page.goto('about:blank')
    await page.goto(`${BASE_URL}/#/records?lang=${LANG}&records_q=Pikachu&records_view=list&records_set=${encodeURIComponent(firstSet.code)}`)
    await expect(page.locator('#records-card-name-query')).toHaveValue('Pikachu')
    await expect(page.locator('.records-list')).toHaveClass(/records-list--list/)
    await expect(page.getByRole('button', { name: firstSet.display_name })).toHaveClass(/bg-\[color:var\(--brand\)\]/)

    await page.locator('#records-card-name-query').fill('Mewtwo')
    await expect(page).toHaveURL(/records_q=Mewtwo/)
    await expect(page).toHaveURL(new RegExp(`records_set=${firstSet.code}`))
    await expect(page).toHaveURL(/records_view=list/)
    await expect(page).toHaveURL(/lang=en/)

    await page.goto(`${BASE_URL}/#/records?lang=${LANG}&records_q=Charizard&records_view=grid`)
    await expect(page.locator('#records-card-name-query')).toHaveValue('Charizard')
    await expect(page.locator('.records-list')).toHaveClass(/records-list--grid/)

    await page.goBack()
    await expect(page.locator('#records-card-name-query')).toHaveValue('Mewtwo')
    await expect(page.locator('.records-list')).toHaveClass(/records-list--list/)
    await expect(page).toHaveURL(/records_q=Mewtwo/)

    await page.goForward()
    await expect(page.locator('#records-card-name-query')).toHaveValue('Charizard')
    await expect(page.locator('.records-list')).toHaveClass(/records-list--grid/)
    await expect(page).toHaveURL(/records_q=Charizard/)
  })

  test('Owned Cards URL query 初始化筛选、sort、view、scope，并跟随 Back/Forward 同步', async ({ page }) => {
    await page.goto(`${BASE_URL}/#/owned-cards?lang=${LANG}&owned_q=Pikachu&owned_scope=missing&owned_sort=count&owned_view=list&owned_counts=hide&owned_page=0`)
    await waitForAppReady(page)

    await expect(page.locator('#owned-card-name-query')).toHaveValue('Pikachu')
    await expect(page.locator('.owned-scope-btn.is-active')).toHaveText(/missing/i)
    await expect(page.getByRole('button', { name: /^COUNT/i })).toHaveClass(/bg-\[color:var\(--brand\)\]/)
    await expect(page.getByRole('button', { name: /^LIST$/i })).toHaveClass(/bg-\[color:var\(--brand\)\]/)
    await expect(page.getByRole('button', { name: /SHOW COUNTS/i })).toBeVisible()

    await page.locator('#owned-card-name-query').fill('Mewtwo')
    await expect(page).toHaveURL(/owned_q=Mewtwo/)
    await expect(page).toHaveURL(/owned_scope=missing/)
    await expect(page).toHaveURL(/owned_sort=count/)
    await expect(page).toHaveURL(/owned_view=list/)

    await page.goto(`${BASE_URL}/#/owned-cards?lang=${LANG}&owned_q=Charizard&owned_scope=all&owned_sort=rarity&owned_view=grid&owned_counts=show`)
    await expect(page.locator('#owned-card-name-query')).toHaveValue('Charizard')
    await expect(page.locator('.owned-scope-btn.is-active')).toHaveText(/all/i)
    await expect(page.getByRole('button', { name: /^RARITY \(DESC\)$/i })).toHaveClass(/bg-\[color:var\(--brand\)\]/)
    await expect(page.getByRole('button', { name: /^GRID$/i })).toHaveClass(/bg-\[color:var\(--brand\)\]/)

    await page.goBack()
    await expect(page.locator('#owned-card-name-query')).toHaveValue('Mewtwo')
    await expect(page.locator('.owned-scope-btn.is-active')).toHaveText(/missing/i)
    await expect(page.getByRole('button', { name: /^COUNT/i })).toHaveClass(/bg-\[color:var\(--brand\)\]/)
    await expect(page.getByRole('button', { name: /^LIST$/i })).toHaveClass(/bg-\[color:var\(--brand\)\]/)

    await page.goForward()
    await expect(page.locator('#owned-card-name-query')).toHaveValue('Charizard')
    await expect(page.locator('.owned-scope-btn.is-active')).toHaveText(/all/i)
    await expect(page.getByRole('button', { name: /^RARITY \(DESC\)$/i })).toHaveClass(/bg-\[color:var\(--brand\)\]/)
    await expect(page.getByRole('button', { name: /^GRID$/i })).toHaveClass(/bg-\[color:var\(--brand\)\]/)
  })

  test('localStorage 抛 DOMException 时 Records/Owned 仍渲染且无 console error', async ({ browser }) => {
    const context = await browser.newContext()
    await context.addInitScript(() => {
      const storage = {
        getItem: () => { throw new DOMException('blocked', 'SecurityError') },
        setItem: () => { throw new DOMException('blocked', 'SecurityError') },
        removeItem: () => { throw new DOMException('blocked', 'SecurityError') },
        clear: () => { throw new DOMException('blocked', 'SecurityError') },
        key: () => null,
        length: 0
      }
      Object.defineProperty(window, 'localStorage', {
        configurable: true,
        value: storage
      })
    })

    const page = await context.newPage()
    const errors = await collectConsoleErrors(page)

    await page.goto(`${BASE_URL}/#/records?lang=${LANG}&records_view=list`)
    await waitForAppReady(page)
    await expect(page.locator('.records-page')).toBeVisible()
    await expect(page.locator('#records-card-name-query')).toBeVisible()

    await page.goto(`${BASE_URL}/#/owned-cards?lang=${LANG}&owned_view=list`)
    await expect(page.locator('.owned-page')).toBeVisible()
    await expect(page.locator('#owned-card-name-query')).toBeVisible()

    expect(errors).toEqual([])
    await context.close()
  })

  test('Owned Cards detail/exchange accounts query smoke', async ({ page, request }) => {
    const owned = await getJson<OwnedCardsResponse>(request, `/api/react/owned-cards?lang=${LANG}&ownership_scope=all&page=0&page_size=10`)
    const firstCard = owned.items.find((item) => item.card.name === 'Pikachu')
    expect(firstCard, 'Web E2E fixture 必须包含 Pikachu owned card').toBeDefined()
    if (!firstCard) {
      throw new Error('Web E2E fixture 缺少 Pikachu owned card')
    }
    expect(firstCard.total_count).toBe(2)

    const detail = await getJson<OwnedCardDetailResponse>(request, `/api/react/owned-cards/${firstCard.card.id}/detail?lang=${LANG}&ownership_scope=all&page_size=6`)
    expect(detail.card.name).toBe('Pikachu')
    expect(detail.total_accounts).toBe(1)
    expect(detail.total_count).toBe(2)

    const exchangeAccounts = await getJson<ExchangeAccountsResponse>(request, `/api/react/owned-cards/${firstCard.card.id}/exchange-accounts?lang=${LANG}&q=&sort_by=account_id&sort_order=asc&page=0&page_size=6`)
    expect(exchangeAccounts.total_items).toBe(1)
    expect(exchangeAccounts.total_count).toBe(2)
    expect(exchangeAccounts.accounts[0]).toMatchObject({ count: 2, exchange_points: 5000 })

    await page.goto(`${BASE_URL}/#/owned-cards?lang=${LANG}&owned_scope=all&owned_view=grid`)
    await waitForAppReady(page)
    const firstCardButton = page.locator('.owned-card').first()
    await expect(firstCardButton).toBeVisible()
    await firstCardButton.click()
    await expect(page.locator('.owned-detail-modal')).toBeVisible()
    await expect(page.locator('#owned-modal-account-query')).toBeVisible()
    await expect(page.locator('#owned-exchange-target-friend-id')).toBeVisible()
  })

  test('Records pack points API 只按当前 series 暴露 points', async ({ request }) => {
    const records = await getJson<RecordsResponse>(request, `/api/react/records?lang=${LANG}&page=0&page_size=20`)
    expect(records.items.length, 'Web E2E fixture 必须包含 A1/A2 records').toBeGreaterThanOrEqual(2)

    const actualPointsBySeries = new Map<string, number | null>()
    for (const item of records.items) {
      if (EXPECTED_PACK_POINTS.has(item.series)) {
        actualPointsBySeries.set(item.series, item.current_points)
      }
    }

    for (const [series, points] of EXPECTED_PACK_POINTS) {
      expect(actualPointsBySeries.get(series), `${series} current_points`).toBe(points)
    }
    expect(actualPointsBySeries.size).toBe(EXPECTED_PACK_POINTS.size)
  })
})
