import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { buildQuery, fetchJson, requestFormJson, requestJson } from '@/lib/api'
import { tr } from '@/lib/i18n'

interface ManagementPageProps {
  lang: string
  t: Record<string, string>
}

interface ColumnDef {
  key: string
  label: string
  render?: (row: Record<string, unknown>) => string
}

interface AccountPlanItemState {
  plan_id: number
  plan_name: string
  is_active: boolean
}

interface PlanTaskConfigState {
  enabled: boolean
  resetType: string
  intervalSeconds: number
}

const sections = [
  { key: 'accounts', labelKey: 'menu_accounts', fallback: 'Accounts' },
  { key: 'plans', labelKey: 'menu_plans', fallback: 'Plans' },
  { key: 'resources', labelKey: 'menu_resources', fallback: 'Resources' },
  { key: 'tasks', labelKey: 'menu_tasks', fallback: 'Tasks' },
  { key: 'metadata', labelKey: 'menu_metadata', fallback: 'Metadata' },
  { key: 'daily-gift', labelKey: 'menu_daily_gift', fallback: 'Daily Gift' },
  { key: 'friendships', labelKey: 'menu_friendships', fallback: 'Friendships' },
  { key: 'exchange-cards', labelKey: 'menu_exchange_cards', fallback: 'Exchange Cards' },
  { key: 'notifications', labelKey: 'menu_notifications', fallback: 'Notifications' }
] as const

function toText(value: unknown, t?: Record<string, string>): string {
  if (value === null || value === undefined) {
    return '-'
  }
  if (typeof value === 'boolean') {
    const locale = t ?? {}
    return value ? tr(locale, 'label_read', 'Yes') : tr(locale, 'label_unread', 'No')
  }
  if (typeof value === 'number') {
    return String(value)
  }
  if (typeof value === 'string') {
    return value
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return '-'
    }
    if (typeof value[0] === 'string' || typeof value[0] === 'number') {
      return value.join(', ')
    }
    return `${value.length} ${tr(t ?? {}, 'label_total_records', 'items')}`
  }
  return JSON.stringify(value)
}

function formatTime(value: unknown): string {
  if (typeof value !== 'string' || value.length === 0) {
    return '-'
  }
  return value.replace('T', ' ').slice(0, 19)
}

function statusLabel(t: Record<string, string>, value: unknown): string {
  const key = typeof value === 'string' ? value : ''
  if (!key) {
    return '-'
  }
  return tr(t, `status_${key}`, key)
}

function taskTypeLabel(t: Record<string, string>, value: unknown): string {
  const key = typeof value === 'string' ? value : ''
  if (!key) {
    return '-'
  }
  return tr(t, `task_${key}`, key)
}

function requestTypeLabel(t: Record<string, string>, value: unknown): string {
  const key = typeof value === 'string' ? value : ''
  if (!key) {
    return '-'
  }
  return tr(t, `friend_request_type_${key}`, key)
}

function requestStatusLabel(t: Record<string, string>, value: unknown): string {
  const key = typeof value === 'string' ? value : ''
  if (!key) {
    return '-'
  }
  return tr(t, `friend_request_status_${key}`, key)
}

function exchangeStatusLabel(t: Record<string, string>, value: unknown): string {
  const key = typeof value === 'string' ? value : ''
  if (!key) {
    return '-'
  }
  return tr(t, `exchange_request_status_${key}`, key)
}

function Pager({
  page,
  hasPrev,
  hasNext,
  onPrev,
  onNext,
  t
}: {
  page: number
  hasPrev: boolean
  hasNext: boolean
  onPrev: () => void
  onNext: () => void
  t: Record<string, string>
}) {
  return (
    <div className="pagination-row">
      <span className="text-xs mono">{tr(t, 'page_label', 'Page')} {page + 1}</span>
      <div className="filter-row">
        <Button size="sm" variant="outline" type="button" disabled={!hasPrev} onClick={onPrev}>
          {tr(t, 'btn_prev_page', 'Previous')}
        </Button>
        <Button size="sm" variant="outline" type="button" disabled={!hasNext} onClick={onNext}>
          {tr(t, 'btn_next_page', 'Next')}
        </Button>
      </div>
    </div>
  )
}

function DataGrid({
  rows,
  columns,
  t
}: {
  rows: Record<string, unknown>[]
  columns: ColumnDef[]
  t: Record<string, string>
}) {
  return (
    <div className="table-wrap">
      <table className="grid-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key}>{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="text-center text-muted">{tr(t, 'label_no_data', 'No data')}</td>
            </tr>
          )}
          {rows.map((row, rowIndex) => (
            <tr key={`${rowIndex}-${toText(row.id, t)}`}>
              {columns.map((col) => (
                <td key={`${rowIndex}-${col.key}`}>
                  {col.render ? col.render(row) : toText(row[col.key], t)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AccountsSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const queryClient = useQueryClient()
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)
  const [editingAccount, setEditingAccount] = useState<Record<string, unknown> | null>(null)
  const [editingPlans, setEditingPlans] = useState<{ accountId: number; items: AccountPlanItemState[] } | null>(null)
  const [currentPlans, setCurrentPlans] = useState<Record<string, unknown>[]>([])
  const [editingPackConfig, setEditingPackConfig] = useState<{ accountId: number; setCode: string; boosterName: string } | null>(null)
  const [cardSets, setCardSets] = useState<Array<{ code: string; display_name: string }>>([])
  const [boosterOptions, setBoosterOptions] = useState<Array<{ name: string; display_name: string }>>([])

  const queryString = useMemo(
    () =>
      buildQuery({
        lang,
        q,
        page,
        page_size: 10
      }),
    [lang, page, q]
  )

  const query = useQuery({
    queryKey: ['management-accounts', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/accounts?${queryString}`)
  })

  const saveAccountMutation = useMutation({
    mutationFn: (payload: { accountId: number; nickname: string; remark: string }) =>
      requestJson<{ ok: boolean; message: string }>(`/api/react/management/accounts/${payload.accountId}`, {
        method: 'PUT',
        body: { nickname: payload.nickname, remark: payload.remark }
      }),
    onSuccess: (result) => {
      alert(result.message)
      setEditingAccount(null)
      queryClient.invalidateQueries({ queryKey: ['management-accounts'] })
    }
  })

  const savePlansMutation = useMutation({
    mutationFn: (payload: { accountId: number; items: AccountPlanItemState[] }) =>
      requestJson<{ ok: boolean }>(`/api/react/management/accounts/${payload.accountId}/plans`, {
        method: 'PUT',
        body: payload.items.map((item) => ({ plan_id: item.plan_id, is_active: item.is_active }))
      }),
    onSuccess: () => {
      setEditingPlans(null)
      queryClient.invalidateQueries({ queryKey: ['management-accounts'] })
    }
  })

  const savePackConfigMutation = useMutation({
    mutationFn: (payload: { accountId: number; setCode: string; boosterName: string }) =>
      requestJson<{ ok: boolean; message: string }>(`/api/react/management/accounts/${payload.accountId}/pack-config`, {
        method: 'PUT',
        body: { set_code: payload.setCode, booster_name: payload.boosterName }
      }),
    onSuccess: (result) => {
      alert(result.message)
      setEditingPackConfig(null)
      queryClient.invalidateQueries({ queryKey: ['management-accounts'] })
    }
  })

  const items = ((query.data?.items as unknown[]) ?? []) as Record<string, unknown>[]
  const packConfigs = (query.data?.pack_configs as Record<string, Record<string, unknown>>) ?? {}
  const autoPackMap = (query.data?.auto_pack_map as Record<string, Record<string, unknown>>) ?? {}

  async function openPlansEditor(accountId: number) {
    const data = await fetchJson<Record<string, unknown>>(`/api/react/management/accounts/${accountId}/plans?${buildQuery({ lang })}`)
    const current = ((data.current_assocs as unknown[]) ?? []) as Record<string, unknown>[]
    const available = ((data.available_plans as unknown[]) ?? []) as Record<string, unknown>[]

    const currentItems = current
      .map((item) => ({
        plan_id: Number(item.plan_id),
        plan_name: toText((item.task_plan as Record<string, unknown>)?.name, t),
        is_active: Boolean(item.is_active),
        priority: Number(item.priority ?? 0)
      }))
      .filter((item) => Number.isFinite(item.plan_id))
      .sort((a, b) => b.priority - a.priority)
      .map(({ plan_id, plan_name, is_active }) => ({ plan_id, plan_name, is_active }))

    const existingIds = new Set(currentItems.map((item) => item.plan_id))
    const candidateItems = available
      .map((item) => ({
        plan_id: Number(item.id),
        plan_name: toText(item.name, t),
        is_active: false
      }))
      .filter((item) => Number.isFinite(item.plan_id) && !existingIds.has(item.plan_id))

    setCurrentPlans(current)
    setEditingPlans({ accountId, items: [...currentItems, ...candidateItems] })
  }

  async function openPackConfigEditor(accountId: number) {
    const [config, sets] = await Promise.all([
      fetchJson<Record<string, unknown>>(`/api/react/management/accounts/${accountId}/pack-config?${buildQuery({ lang })}`),
      fetchJson<Array<{ code: string; display_name: string }>>('/api/react/management/card-sets')
    ])
    const setCode = String(config.selected_set_code ?? '')
    const boosterName = String(config.selected_booster_name ?? '')
    setCardSets(sets)
    if (setCode) {
      const boosters = await fetchJson<Array<{ name: string; display_name: string }>>(`/api/react/management/card-sets/${encodeURIComponent(setCode)}/boosters`)
      setBoosterOptions(boosters)
    } else {
      setBoosterOptions([])
    }
    setEditingPackConfig({ accountId, setCode, boosterName })
  }

  return (
    <section className="section-stack">
      <div className="surface-card section-stack">
        <div className="pagination-row">
          <div className="section-title">{tr(t, 'menu_accounts', 'Accounts')}</div>
          <div className="filter-row">
            <input className="field-input" value={q} onChange={(event) => setQ(event.target.value)} placeholder={tr(t, 'filter_account_id_placeholder', 'Search account')} />
            <Button type="button" size="sm" variant="outline" onClick={() => setPage(0)}>{tr(t, 'label_search', 'Search')}</Button>
          </div>
        </div>

        {query.isLoading && <div className="text-sm text-muted">{tr(t, 'label_loading', 'Loading...')}</div>}
        {query.isError && <div className="text-sm text-danger">{(query.error as Error).message}</div>}

        {query.data && (
          <>
            <div className="table-wrap">
              <table className="grid-table">
                <thead>
                  <tr>
                    <th>{tr(t, 'col_id', 'ID')}</th>
                    <th>{tr(t, 'col_nickname', 'Nickname')}</th>
                    <th>{tr(t, 'col_friend_id', 'Friend ID')}</th>
                    <th>{tr(t, 'col_plans', 'Plans')}</th>
                    <th>{tr(t, 'col_target_pack', 'Target Pack')}</th>
                    <th>{tr(t, 'col_actions', 'Actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 && (
                    <tr>
                      <td colSpan={6} className="text-center text-muted">{tr(t, 'label_no_data', 'No data')}</td>
                    </tr>
                  )}
                  {items.map((item) => {
                    const accountId = Number(item.id)
                    const associations = ((item.task_plan_associations as unknown[]) ?? []) as Record<string, unknown>[]
                    const activePlanNames = associations
                      .filter((assoc) => Boolean(assoc.is_active) && typeof assoc.task_plan === 'object' && assoc.task_plan !== null)
                      .map((assoc) => toText((assoc.task_plan as Record<string, unknown>).name))
                    const config = packConfigs[String(accountId)]
                    const autoPack = autoPackMap[String(accountId)]
                    const targetPack =
                      config
                        ? `${toText(config.set_code, t)}/${toText(config.booster_name, t)}`
                        : autoPack
                          ? `${toText(autoPack.set_code, t)}/${toText(autoPack.booster_name, t)} (${tr(t, 'label_auto', 'Auto')})`
                          : '-'

                    return (
                      <tr key={accountId}>
                        <td className="mono">{toText(item.id)}</td>
                        <td>{toText(item.nickname || item.display_name, t)}</td>
                        <td className="mono">{toText(item.friend_id, t)}</td>
                        <td>{activePlanNames.length > 0 ? activePlanNames.join(', ') : '-'}</td>
                        <td>{targetPack}</td>
                        <td>
                          <div className="filter-row">
                            <Button type="button" size="sm" variant="outline" onClick={() => setEditingAccount(item)}>{tr(t, 'btn_edit', 'Edit')}</Button>
                            <Button type="button" size="sm" variant="outline" onClick={() => openPlansEditor(accountId)}>{tr(t, 'btn_edit_plans', 'Plans')}</Button>
                            <Button type="button" size="sm" variant="outline" onClick={() => openPackConfigEditor(accountId)}>{tr(t, 'btn_pack_config_title', 'Pack Config')}</Button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <Pager
              page={Number(query.data.page ?? 0)}
              hasPrev={Boolean(query.data.has_prev)}
              hasNext={Boolean(query.data.has_next)}
              onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
              onNext={() => setPage((prev) => prev + 1)}
              t={t}
            />
          </>
        )}
      </div>

      {editingAccount && (
        <div className="dialog-overlay" onClick={() => setEditingAccount(null)}>
          <div className="dialog-card section-stack" onClick={(event) => event.stopPropagation()}>
            <div className="section-title">{tr(t, 'modal_title_edit_account', 'Edit Account')} #{toText(editingAccount.id, t)}</div>
            <label className="section-subtitle">{tr(t, 'label_nickname', 'Nickname')}</label>
            <input
              className="field-input"
              value={toText(editingAccount.nickname)}
              onChange={(event) => setEditingAccount((prev) => (prev ? { ...prev, nickname: event.target.value } : null))}
            />
            <label className="section-subtitle">{tr(t, 'label_remark', 'Remark')}</label>
            <textarea
              className="field-textarea"
              value={toText(editingAccount.remark)}
              onChange={(event) => setEditingAccount((prev) => (prev ? { ...prev, remark: event.target.value } : null))}
            />
            <div className="filter-row">
              <Button type="button" size="sm" onClick={() => saveAccountMutation.mutate({ accountId: Number(editingAccount.id), nickname: toText(editingAccount.nickname), remark: toText(editingAccount.remark) })}>
                {tr(t, 'btn_save', 'Save')}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={() => setEditingAccount(null)}>{tr(t, 'label_cancel', 'Cancel')}</Button>
            </div>
          </div>
        </div>
      )}

      {editingPlans && (
        <div className="dialog-overlay" onClick={() => setEditingPlans(null)}>
          <div className="dialog-card section-stack" onClick={(event) => event.stopPropagation()}>
            <div className="section-title">{tr(t, 'btn_edit_plans', 'Plans')} #{editingPlans.accountId}</div>
            <div className="section-subtitle">{tr(t, 'label_active_plans', 'Active Plans')}</div>
            <div className="filter-row">
              {currentPlans.map((item) => (
                <span key={toText(item.plan_id, t)} className="tag">{toText((item.task_plan as Record<string, unknown>)?.name, t)}</span>
              ))}
            </div>
            <div className="section-subtitle">{tr(t, 'option_select_plan', 'Select plan')}</div>
            <div className="section-stack">
              {editingPlans.items.map((planItem, index) => {
                const checked = planItem.is_active
                return (
                  <div key={planItem.plan_id} className="filter-row">
                    <label className="filter-row">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(event) => {
                          setEditingPlans((prev) => {
                            if (!prev) {
                              return prev
                            }
                            const nextItems = [...prev.items]
                            nextItems[index] = { ...nextItems[index], is_active: event.target.checked }
                            return { ...prev, items: nextItems }
                          })
                        }}
                      />
                      <span>{planItem.plan_name}</span>
                    </label>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={index === 0}
                      onClick={() => {
                        setEditingPlans((prev) => {
                          if (!prev || index === 0) {
                            return prev
                          }
                          const nextItems = [...prev.items]
                          const tmp = nextItems[index - 1]
                          nextItems[index - 1] = nextItems[index]
                          nextItems[index] = tmp
                          return { ...prev, items: nextItems }
                        })
                      }}
                    >
                      ↑
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={index === editingPlans.items.length - 1}
                      onClick={() => {
                        setEditingPlans((prev) => {
                          if (!prev || index === prev.items.length - 1) {
                            return prev
                          }
                          const nextItems = [...prev.items]
                          const tmp = nextItems[index + 1]
                          nextItems[index + 1] = nextItems[index]
                          nextItems[index] = tmp
                          return { ...prev, items: nextItems }
                        })
                      }}
                    >
                      ↓
                    </Button>
                  </div>
                )
              })}
            </div>
            <div className="filter-row">
              <Button type="button" size="sm" onClick={() => savePlansMutation.mutate(editingPlans)}>{tr(t, 'btn_save', 'Save')}</Button>
              <Button type="button" size="sm" variant="outline" onClick={() => setEditingPlans(null)}>{tr(t, 'label_cancel', 'Cancel')}</Button>
            </div>
          </div>
        </div>
      )}

      {editingPackConfig && (
        <div className="dialog-overlay" onClick={() => setEditingPackConfig(null)}>
          <div className="dialog-card section-stack" onClick={(event) => event.stopPropagation()}>
            <div className="section-title">{tr(t, 'btn_pack_config_title', 'Pack Config')} #{editingPackConfig.accountId}</div>
            <label className="section-subtitle">{tr(t, 'label_target_series', 'Target Series')}</label>
            <select
              className="field-select"
              value={editingPackConfig.setCode}
              onChange={async (event) => {
                const setCode = event.target.value
                if (!setCode) {
                  setBoosterOptions([])
                  setEditingPackConfig((prev) => (prev ? { ...prev, setCode: '', boosterName: '' } : null))
                  return
                }
                const boosters = await fetchJson<Array<{ name: string; display_name: string }>>(`/api/react/management/card-sets/${encodeURIComponent(setCode)}/boosters`)
                setBoosterOptions(boosters)
                setEditingPackConfig((prev) => (prev ? { ...prev, setCode, boosterName: boosters[0]?.name ?? '' } : null))
              }}
            >
              <option value="">{tr(t, 'label_no_pack_auto', 'No target pack (auto select)')}</option>
              {cardSets.map((setItem) => (
                <option key={setItem.code} value={setItem.code}>{setItem.display_name}</option>
              ))}
            </select>

            <label className="section-subtitle">{tr(t, 'label_target_booster', 'Target Booster')}</label>
            <select className="field-select" value={editingPackConfig.boosterName} onChange={(event) => setEditingPackConfig((prev) => (prev ? { ...prev, boosterName: event.target.value } : null))}>
              <option value="">{tr(t, 'label_none', '-- None --')}</option>
              {boosterOptions.map((booster) => (
                <option key={booster.name} value={booster.name}>{booster.display_name}</option>
              ))}
            </select>

            <div className="filter-row">
              <Button type="button" size="sm" onClick={() => savePackConfigMutation.mutate({ accountId: editingPackConfig.accountId, setCode: editingPackConfig.setCode, boosterName: editingPackConfig.boosterName })}>{tr(t, 'btn_save', 'Save')}</Button>
              <Button type="button" size="sm" variant="outline" onClick={() => setEditingPackConfig(null)}>{tr(t, 'label_cancel', 'Cancel')}</Button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

function PlansSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const queryClient = useQueryClient()
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)
  const [editingPlanId, setEditingPlanId] = useState<number | null>(null)
  const [isPlanEditorOpen, setIsPlanEditorOpen] = useState(false)
  const [planName, setPlanName] = useState('')
  const [planDesc, setPlanDesc] = useState('')
  const [taskOptions, setTaskOptions] = useState<string[]>([])
  const [resetTypeOptions, setResetTypeOptions] = useState<string[]>([])
  const [taskOrder, setTaskOrder] = useState<string[]>([])
  const [taskConfigMap, setTaskConfigMap] = useState<Record<string, PlanTaskConfigState>>({})

  const queryString = useMemo(() => buildQuery({ lang, q, page, page_size: 10 }), [lang, page, q])

  const query = useQuery({
    queryKey: ['management-plans', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/plans?${queryString}`)
  })

  const saveMutation = useMutation({
    mutationFn: (payload: { planId: number | null; name: string; description: string; tasks: string[]; taskConfigMap: Record<string, PlanTaskConfigState> }) => {
      const form = new FormData()
      if (payload.planId !== null) {
        form.set('plan_id', String(payload.planId))
      }
      form.set('name', payload.name)
      form.set('description', payload.description)
      form.set('task_order', JSON.stringify(payload.tasks))
      payload.tasks.forEach((taskType) => {
        form.set(`task_enabled_${taskType}`, 'on')
        const config = payload.taskConfigMap[taskType]
        if (!config) {
          return
        }
        form.set(`task_reset_${taskType}`, config.resetType || 'default')
        if (config.resetType === 'interval' && config.intervalSeconds > 0) {
          form.set(`task_interval_${taskType}`, String(config.intervalSeconds))
        }
      })
      return requestFormJson<{ ok: boolean; message: string; error?: string }>('/api/react/management/plans', {
        method: 'POST',
        body: form
      })
    },
    onSuccess: (result) => {
      if (!result.ok) {
        alert(result.message)
        return
      }
      setEditingPlanId(null)
      setIsPlanEditorOpen(false)
      queryClient.invalidateQueries({ queryKey: ['management-plans'] })
    }
  })

  const deleteMutation = useMutation({
    mutationFn: (planId: number) => requestJson<{ ok: boolean; message: string }>(`/api/react/management/plans/${planId}`, { method: 'DELETE' }),
    onSuccess: (result) => {
      alert(result.message)
      queryClient.invalidateQueries({ queryKey: ['management-plans'] })
    }
  })

  async function openEditor(planId: number | null) {
    const data = await fetchJson<Record<string, unknown>>(`/api/react/management/plans/edit?${buildQuery({ lang, plan_id: planId ?? undefined })}`)
    const plan = (data.plan as Record<string, unknown> | null) ?? null
    const availableTasks = ((data.available_tasks as unknown[]) ?? []) as string[]
    const selectedTasks = ((plan?.task_types_list as unknown[]) ?? []) as string[]
    const configDict = (plan?.config_dict as Record<string, Record<string, unknown>> | undefined) ?? {}
    const normalizedTaskOrder = [...selectedTasks, ...availableTasks.filter((task) => !selectedTasks.includes(task))]
    const nextTaskConfigMap: Record<string, PlanTaskConfigState> = {}
    for (const taskType of normalizedTaskOrder) {
      const config = configDict[taskType] ?? {}
      const resetTypeRaw = String(config.reset_type ?? 'default')
      const resetType = resetTypeRaw.length > 0 ? resetTypeRaw : 'default'
      const intervalRaw = Number(config.interval_seconds ?? 3600)
      nextTaskConfigMap[taskType] = {
        enabled: selectedTasks.includes(taskType),
        resetType,
        intervalSeconds: Number.isFinite(intervalRaw) && intervalRaw > 0 ? intervalRaw : 3600
      }
    }

    setTaskOptions(availableTasks)
    setTaskOrder(normalizedTaskOrder)
    setResetTypeOptions(((data.reset_types as unknown[]) ?? []) as string[])
    setTaskConfigMap(nextTaskConfigMap)
    setPlanName(toText(plan?.name ?? ''))
    setPlanDesc(toText(plan?.description ?? ''))
    setEditingPlanId(planId)
    setIsPlanEditorOpen(true)
  }

  const items = ((query.data?.items as unknown[]) ?? []) as Record<string, unknown>[]

  return (
    <section className="section-stack">
      <div className="surface-card section-stack">
        <div className="pagination-row">
          <div className="section-title">{tr(t, 'menu_plans', 'Plans')}</div>
          <div className="filter-row">
            <input className="field-input" value={q} onChange={(event) => setQ(event.target.value)} placeholder={tr(t, 'label_search', 'Search')} />
            <Button type="button" size="sm" variant="outline" onClick={() => setPage(0)}>{tr(t, 'label_search', 'Search')}</Button>
            <Button type="button" size="sm" onClick={() => openEditor(null)}>{tr(t, 'btn_new_plan', 'New')}</Button>
          </div>
        </div>

        <DataGrid
          rows={items}
          columns={[
            { key: 'id', label: tr(t, 'col_id', 'ID') },
            { key: 'name', label: tr(t, 'col_name', 'Name') },
            { key: 'description', label: tr(t, 'col_description', 'Description') },
            { key: 'task_types_list', label: tr(t, 'col_task', 'Task'), render: (row) => toText(row.task_types_list, t) },
            {
              key: 'actions',
              label: tr(t, 'col_actions', 'Actions'),
              render: (row) => {
                const planId = Number(row.id)
                return `${tr(t, 'btn_edit', 'Edit')}#${planId}`
              }
            }
          ]}
          t={t}
        />

        <div className="filter-row">
          {items.map((item) => (
            <div key={toText(item.id, t)} className="filter-row">
              <Button type="button" size="sm" variant="outline" onClick={() => openEditor(Number(item.id))}>{tr(t, 'btn_edit', 'Edit')} {toText(item.name, t)}</Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  const template = tr(t, 'confirm_delete_plan', "Delete plan '{name}'?")
                  const name = toText(item.name, t)
                  if (confirm(template.replace('{name}', name))) {
                    deleteMutation.mutate(Number(item.id))
                  }
                }}
              >
                {tr(t, 'btn_delete', 'Delete')}
              </Button>
            </div>
          ))}
        </div>

        <Pager
          page={Number(query.data?.page ?? 0)}
          hasPrev={Boolean(query.data?.has_prev)}
          hasNext={Boolean(query.data?.has_next)}
          onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
          onNext={() => setPage((prev) => prev + 1)}
          t={t}
        />
      </div>

      {isPlanEditorOpen && (
        <div className="dialog-overlay" onClick={() => { setEditingPlanId(null); setIsPlanEditorOpen(false) }}>
          <div className="dialog-card section-stack" onClick={(event) => event.stopPropagation()}>
            <div className="section-title">
              {editingPlanId ? `${tr(t, 'btn_edit', 'Edit')} #${editingPlanId}` : tr(t, 'modal_title_new_plan', 'New Plan')}
            </div>
            <label className="section-subtitle">{tr(t, 'label_name', 'Name')}</label>
            <input className="field-input" value={planName} onChange={(event) => setPlanName(event.target.value)} />
            <label className="section-subtitle">{tr(t, 'label_description', 'Description')}</label>
            <textarea className="field-textarea" value={planDesc} onChange={(event) => setPlanDesc(event.target.value)} />
            <label className="section-subtitle">{tr(t, 'label_task_config', 'Task Config')}</label>
            <div className="section-stack">
              {(taskOrder.length > 0 ? taskOrder : taskOptions).map((task, index) => {
                const config = taskConfigMap[task] ?? {
                  enabled: false,
                  resetType: 'default',
                  intervalSeconds: 3600
                }
                return (
                  <div key={task} className="surface-card section-stack">
                    <div className="filter-row">
                      <label className="filter-row">
                        <input
                          type="checkbox"
                          checked={config.enabled}
                          onChange={(event) => {
                            const enabled = event.target.checked
                            setTaskConfigMap((prev) => ({
                              ...prev,
                              [task]: { ...config, enabled }
                            }))
                          }}
                        />
                        <span>{taskTypeLabel(t, task)}</span>
                      </label>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={index === 0}
                        onClick={() => {
                          setTaskOrder((prev) => {
                            if (index === 0) {
                              return prev
                            }
                            const next = [...prev]
                            const tmp = next[index - 1]
                            next[index - 1] = next[index]
                            next[index] = tmp
                            return next
                          })
                        }}
                      >
                        ↑
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={index === taskOrder.length - 1}
                        onClick={() => {
                          setTaskOrder((prev) => {
                            if (index === prev.length - 1) {
                              return prev
                            }
                            const next = [...prev]
                            const tmp = next[index + 1]
                            next[index + 1] = next[index]
                            next[index] = tmp
                            return next
                          })
                        }}
                      >
                        ↓
                      </Button>
                    </div>
                    <div className="filter-row">
                      <select
                        className="field-select"
                        value={config.resetType}
                        onChange={(event) => {
                          const resetType = event.target.value
                          setTaskConfigMap((prev) => ({
                            ...prev,
                            [task]: { ...config, resetType }
                          }))
                        }}
                      >
                        {resetTypeOptions.map((resetType) => (
                          <option key={resetType} value={resetType}>
                            {resetType}
                          </option>
                        ))}
                        {!resetTypeOptions.includes('default') && <option value="default">default</option>}
                      </select>
                      {config.resetType === 'interval' && (
                        <input
                          className="field-input"
                          type="number"
                          min={1}
                          value={config.intervalSeconds}
                          onChange={(event) => {
                            const intervalSeconds = Number(event.target.value)
                            setTaskConfigMap((prev) => ({
                              ...prev,
                              [task]: {
                                ...config,
                                intervalSeconds: Number.isFinite(intervalSeconds) && intervalSeconds > 0 ? intervalSeconds : 1
                              }
                            }))
                          }}
                          placeholder={tr(t, 'label_interval_seconds', 'seconds')}
                        />
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="filter-row">
              <Button
                type="button"
                size="sm"
                onClick={() => {
                  const enabledOrderedTasks = taskOrder.filter((task) => taskConfigMap[task]?.enabled)
                  saveMutation.mutate({
                    planId: editingPlanId,
                    name: planName.trim(),
                    description: planDesc.trim(),
                    tasks: enabledOrderedTasks,
                    taskConfigMap
                  })
                }}
              >
                {tr(t, 'btn_save', 'Save')}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={() => { setEditingPlanId(null); setIsPlanEditorOpen(false) }}>{tr(t, 'label_cancel', 'Cancel')}</Button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

function ResourcesSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)
  const [view, setView] = useState('stats')

  const queryString = useMemo(() => buildQuery({ lang, q, page, page_size: 20, view }), [lang, page, q, view])
  const query = useQuery({
    queryKey: ['management-resources', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/resources?${queryString}`)
  })

  const items = ((query.data?.items as unknown[]) ?? []) as Record<string, unknown>[]
  const columns = useMemo<ColumnDef[]>(() => {
    if (items.length === 0) {
      return []
    }
    const keys = Object.keys(items[0])
    return keys.map((key) => ({ key, label: key }))
  }, [items])

  return (
    <section className="surface-card section-stack">
      <div className="pagination-row">
        <div className="section-title">{tr(t, 'menu_resources', 'Resources')}</div>
        <div className="filter-row">
          <Button type="button" size="sm" variant={view === 'stats' ? 'default' : 'outline'} onClick={() => { setView('stats'); setPage(0) }}>{tr(t, 'menu_resources', 'Resources')}</Button>
          <Button type="button" size="sm" variant={view === 'pack-points' ? 'default' : 'outline'} onClick={() => { setView('pack-points'); setPage(0) }}>{tr(t, 'section_packs', 'Pack Points')}</Button>
          <input className="field-input" value={q} onChange={(event) => setQ(event.target.value)} placeholder={tr(t, 'filter_account_search_placeholder', 'Search account')} />
          <Button type="button" size="sm" variant="outline" onClick={() => setPage(0)}>{tr(t, 'label_search', 'Search')}</Button>
        </div>
      </div>
      {columns.length > 0 && <DataGrid rows={items} columns={columns} t={t} />}
      <Pager
        page={Number(query.data?.page ?? 0)}
        hasPrev={Boolean(query.data?.has_prev)}
        hasNext={Boolean(query.data?.has_next)}
        onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPage((prev) => prev + 1)}
        t={t}
      />
    </section>
  )
}

function TasksSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(0)
  const [status, setStatus] = useState<string[]>([])
  const [taskTypes, setTaskTypes] = useState<string[]>([])
  const [accountKeyword, setAccountKeyword] = useState('')
  const [sortBy, setSortBy] = useState('dispatch_priority')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')

  const normalizedAccountKeyword = accountKeyword.trim()
  const selectedAccountMatch = normalizedAccountKeyword.match(/^(\d+)/)
  const selectedAccountId = selectedAccountMatch?.[1] ?? ''
  const selectedAccountQuery = selectedAccountId ? '' : normalizedAccountKeyword

  const accountOptionsQuery = useQuery({
    queryKey: ['management-task-account-options', normalizedAccountKeyword],
    queryFn: () =>
      fetchJson<{ accounts: Array<Record<string, unknown>> }>(
        `/api/react/management/tasks/account-options?${buildQuery({ q: normalizedAccountKeyword })}`
      ),
    enabled: normalizedAccountKeyword.length > 0
  })

  const queryString = useMemo(
    () =>
      buildQuery({
        lang,
        page,
        page_size: 20,
        status,
        task_type: taskTypes,
        account_id: selectedAccountId || undefined,
        account_q: selectedAccountQuery || undefined,
        sort_by: sortBy,
        sort_order: sortOrder
      }),
    [lang, page, selectedAccountId, selectedAccountQuery, sortBy, sortOrder, status, taskTypes]
  )
  const query = useQuery({
    queryKey: ['management-tasks', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/tasks?${queryString}`)
  })

  const resetMutation = useMutation({
    mutationFn: () =>
      requestJson<{ ok: boolean; message: string }>('/api/react/management/tasks/reset-completed', {
        method: 'POST',
        body: {
          status,
          task_type: taskTypes,
          account_id: selectedAccountId || null
        }
      }),
    onSuccess: (result) => {
      alert(result.message)
      queryClient.invalidateQueries({ queryKey: ['management-tasks'] })
    }
  })

  const rows = ((query.data?.items as unknown[]) ?? []) as Record<string, unknown>[]
  const statusOptions = ((query.data?.status_options as unknown[]) ?? []) as string[]
  const taskTypeOptions = ((query.data?.task_types as unknown[]) ?? []) as string[]
  const accountOptions = ((accountOptionsQuery.data?.accounts as unknown[]) ?? []) as Record<string, unknown>[]

  return (
    <section className="surface-card section-stack">
      <div className="pagination-row">
        <div className="section-title">{tr(t, 'menu_tasks', 'Tasks')}</div>
        <div className="filter-row">
          <input
            className="field-input"
            list="task-account-options"
            value={accountKeyword}
            onChange={(event) => {
              setPage(0)
              setAccountKeyword(event.target.value)
            }}
            placeholder={tr(t, 'filter_account_id_placeholder', 'Account ID / nickname / friend id')}
          />
          <datalist id="task-account-options">
            {accountOptions.map((item) => {
              const id = toText(item.id, t)
              const displayName = toText(item.display_name || item.nickname, t)
              const friendId = toText(item.friend_id, t)
              const optionLabel = `${id} ${displayName} (${friendId})`
              return <option key={id} value={optionLabel} />
            })}
          </datalist>
          <Button size="sm" type="button" variant="outline" onClick={() => setPage(0)}>{tr(t, 'label_search', 'Search')}</Button>
          <Button
            size="sm"
            type="button"
            onClick={() => {
              const warning = tr(
                t,
                'desc_reset_completed_warning',
                'This action will reset completed tasks to pending based on current filters.'
              )
              const ignoreHint = tr(
                t,
                'desc_reset_completed_ignore_init',
                'Init account tasks are always ignored.'
              )
              if (confirm(`${warning}\n${ignoreHint}`)) {
                resetMutation.mutate()
              }
            }}
          >
            {tr(t, 'btn_reset_completed', 'Reset Completed')}
          </Button>
        </div>
      </div>

      <div className="form-grid">
        <div className="section-stack">
          <div className="section-subtitle">{tr(t, 'filter_status', 'Status')}</div>
          {statusOptions.map((item) => (
            <label key={item} className="filter-row">
              <input
                type="checkbox"
                checked={status.includes(item)}
                onChange={(event) => {
                  setPage(0)
                  setStatus((prev) => {
                    if (event.target.checked) {
                      return [...prev, item]
                    }
                    return prev.filter((value) => value !== item)
                  })
                }}
              />
              <span>{statusLabel(t, item)}</span>
            </label>
          ))}
        </div>
        <div className="section-stack">
          <div className="section-subtitle">{tr(t, 'filter_task', 'Task')}</div>
          {taskTypeOptions.map((item) => (
            <label key={item} className="filter-row">
              <input
                type="checkbox"
                checked={taskTypes.includes(item)}
                onChange={(event) => {
                  setPage(0)
                  setTaskTypes((prev) => {
                    if (event.target.checked) {
                      return [...prev, item]
                    }
                    return prev.filter((value) => value !== item)
                  })
                }}
              />
              <span>{taskTypeLabel(t, item)}</span>
            </label>
          ))}
        </div>
        <div className="section-stack">
          <div className="section-subtitle">{tr(t, 'filter_sort', 'Sort')}</div>
          <div className="filter-row">
            <Button type="button" size="sm" variant={sortBy === 'dispatch_priority' ? 'default' : 'outline'} onClick={() => { setSortBy('dispatch_priority'); setSortOrder('asc'); setPage(0) }}>
              {tr(t, 'col_dispatch_priority', 'Dispatch Priority')}
            </Button>
            <Button type="button" size="sm" variant={sortBy === 'last_completed_at' ? 'default' : 'outline'} onClick={() => { setSortBy('last_completed_at'); setSortOrder('desc'); setPage(0) }}>
              {tr(t, 'col_last_completed', 'Last Completed')}
            </Button>
            <Button type="button" size="sm" variant={sortBy === 'last_duration_seconds' ? 'default' : 'outline'} onClick={() => { setSortBy('last_duration_seconds'); setSortOrder('desc'); setPage(0) }}>
              {tr(t, 'col_last_duration', 'Last Duration')}
            </Button>
            <Button type="button" size="sm" variant={sortBy === 'next_run_at' ? 'default' : 'outline'} onClick={() => { setSortBy('next_run_at'); setSortOrder('asc'); setPage(0) }}>
              {tr(t, 'col_next_run', 'Next Run')}
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={() => { setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc')); setPage(0) }}>
              {sortOrder.toUpperCase()}
            </Button>
          </div>
        </div>
      </div>

      <DataGrid
        rows={rows}
        columns={[
          { key: 'id', label: tr(t, 'col_id', 'ID') },
          { key: 'account_id', label: tr(t, 'col_account', 'Account') },
          { key: 'task_type', label: tr(t, 'col_task', 'Task'), render: (row) => taskTypeLabel(t, row.task_type) },
          { key: 'status', label: tr(t, 'col_status', 'Status'), render: (row) => statusLabel(t, row.status) },
          {
            key: 'dispatch_rank',
            label: tr(t, 'col_dispatch_priority', 'Dispatch Priority'),
            render: (row) => {
              const rank = Number(row.dispatch_rank ?? 0)
              const total = Number(row.dispatch_rank_total ?? 0)
              if (rank <= 0 || total <= 0) {
                return '-'
              }
              return `${rank}/${total}`
            }
          },
          { key: 'last_completed_at_iso', label: tr(t, 'col_last_completed', 'Last Completed'), render: (row) => formatTime(row.last_completed_at_iso) },
          {
            key: 'last_duration_seconds',
            label: tr(t, 'col_last_duration', 'Last Duration'),
            render: (row) => {
              const duration = Number(row.last_duration_seconds ?? 0)
              if (!Number.isFinite(duration) || duration <= 0) {
                return '-'
              }
              return `${duration.toFixed(1)}s`
            }
          },
          { key: 'reset_type', label: tr(t, 'col_reset_type', 'Reset Type') },
          { key: 'next_run_at_iso', label: tr(t, 'col_next_run', 'Next Run'), render: (row) => formatTime(row.next_run_at_iso) },
          { key: 'plan_name', label: tr(t, 'col_plan', 'Plan') },
          { key: 'plan_priority', label: tr(t, 'label_priority', 'Priority') },
          {
            key: 'target_pack_label',
            label: tr(t, 'col_target_pack', 'Target Pack'),
            render: (row) => {
              const value = toText(row.target_pack_label, t)
              if (value === '-') {
                return value
              }
              return Boolean(row.target_pack_auto) ? `${value} (${tr(t, 'label_auto', 'Auto')})` : value
            }
          },
          { key: 'error_message', label: tr(t, 'col_error', 'Error') }
        ]}
        t={t}
      />

      <Pager
        page={Number(query.data?.page ?? 0)}
        hasPrev={Boolean(query.data?.has_prev)}
        hasNext={Boolean(query.data?.has_next)}
        onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPage((prev) => prev + 1)}
        t={t}
      />
    </section>
  )
}

function MetadataSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const [selectedNodeType, setSelectedNodeType] = useState('root')
  const [selectedNodeId, setSelectedNodeId] = useState('all')
  const [currentAction, setCurrentAction] = useState('update_new_series')
  const [previewResult, setPreviewResult] = useState<Record<string, unknown> | null>(null)
  const [checkResult, setCheckResult] = useState<Record<string, unknown> | null>(null)

  const queryString = useMemo(
    () =>
      buildQuery({
        lang,
        selected_node_type: selectedNodeType,
        selected_node_id: selectedNodeId,
        current_action: currentAction,
        ui_step: 1
      }),
    [currentAction, lang, selectedNodeId, selectedNodeType]
  )

  const query = useQuery({
    queryKey: ['management-metadata', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/metadata?${queryString}`)
  })

  const previewMutation = useMutation({
    mutationFn: () =>
      requestJson<Record<string, unknown>>('/api/react/management/metadata/preview', {
        method: 'POST',
        body: {
          action: currentAction,
          node_type: selectedNodeType,
          node_id: selectedNodeId,
          force_refresh: false
        }
      }),
    onSuccess: (result) => setPreviewResult(result)
  })

  const executeMutation = useMutation({
    mutationFn: () =>
      requestJson<Record<string, unknown>>('/api/react/management/metadata/execute', {
        method: 'POST',
        body: {
          snapshot_id: previewResult?.snapshot_id
        }
      }),
    onSuccess: (result) => {
      alert(`${tr(t, 'label_success_records', 'Done')}: ${toText(result.status ?? 'ok', t)}`)
      setPreviewResult(null)
    }
  })

  const checkMutation = useMutation({
    mutationFn: () => requestJson<Record<string, unknown>>('/api/react/management/metadata/check', { method: 'POST', body: {} }),
    onSuccess: (result) => setCheckResult(result)
  })

  const availableActions = ((query.data?.available_actions as unknown[]) ?? []) as string[]

  return (
    <section className="surface-card section-stack">
      <div className="section-title">{tr(t, 'menu_metadata', 'Metadata')}</div>
      <div className="form-grid">
        <div className="section-stack">
          <label className="section-subtitle">{tr(t, 'metadata_label_mode', 'Node Type')}</label>
          <select className="field-select" value={selectedNodeType} onChange={(event) => setSelectedNodeType(event.target.value)}>
            <option value="root">root</option>
            <option value="set">set</option>
            <option value="pack">pack</option>
            <option value="card">card</option>
          </select>
        </div>
        <div className="section-stack">
          <label className="section-subtitle">{tr(t, 'metadata_label_source', 'Node ID')}</label>
          <input className="field-input" value={selectedNodeId} onChange={(event) => setSelectedNodeId(event.target.value)} />
        </div>
        <div className="section-stack">
          <label className="section-subtitle">{tr(t, 'metadata_label_action', 'Action')}</label>
          <select className="field-select" value={currentAction} onChange={(event) => setCurrentAction(event.target.value)}>
            {(availableActions.length > 0 ? availableActions : ['update_new_series']).map((action) => (
              <option key={action} value={action}>{action}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="filter-row">
        <Button type="button" size="sm" onClick={() => previewMutation.mutate()}>{tr(t, 'btn_refresh', 'Preview')}</Button>
        <Button type="button" size="sm" variant="outline" onClick={() => checkMutation.mutate()}>{tr(t, 'btn_recheck_sources', 'Check Sources')}</Button>
        <Button type="button" size="sm" variant="outline" disabled={!previewResult?.snapshot_id} onClick={() => executeMutation.mutate()}>
          {tr(t, 'metadata_label_result', 'Execute')}
        </Button>
      </div>

      {previewResult && (
        <pre className="surface-card text-xs mono">{JSON.stringify(previewResult, null, 2)}</pre>
      )}
      {checkResult && (
        <pre className="surface-card text-xs mono">{JSON.stringify(checkResult, null, 2)}</pre>
      )}
    </section>
  )
}

function DailyGiftSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const [page, setPage] = useState(0)
  const [pairPage, setPairPage] = useState(0)
  const [date, setDate] = useState('')
  const [accountId, setAccountId] = useState('')

  const queryString = useMemo(
    () => buildQuery({ lang, page, pair_page: pairPage, biz_date_local: date || undefined, account_id: accountId || undefined }),
    [accountId, date, lang, page, pairPage]
  )
  const query = useQuery({
    queryKey: ['management-daily-gift', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/daily-gift?${queryString}`)
  })

  const records = ((query.data?.records as unknown[]) ?? []) as Record<string, unknown>[]
  const pairs = ((query.data?.pair_send_status_rows as unknown[]) ?? []) as Record<string, unknown>[]

  return (
    <section className="surface-card section-stack">
      <div className="pagination-row">
        <div className="section-title">{tr(t, 'menu_daily_gift', 'Daily Gift')}</div>
        <div className="filter-row">
          <input className="field-input" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
          <input className="field-input" value={accountId} onChange={(event) => setAccountId(event.target.value)} placeholder={tr(t, 'account_id', 'Account ID')} />
          <Button type="button" size="sm" variant="outline" onClick={() => { setPage(0); setPairPage(0) }}>{tr(t, 'label_search', 'Search')}</Button>
        </div>
      </div>

      <div className="section-subtitle">{tr(t, 'section_daily_gift_records', 'Gift Records')}</div>
      <DataGrid
        rows={records}
        columns={[
          { key: 'id', label: tr(t, 'col_id', 'ID') },
          { key: 'account_name', label: tr(t, 'col_account', 'Account') },
          { key: 'target_name', label: tr(t, 'col_to_account_id', 'Target Account') },
          { key: 'card_label', label: tr(t, 'col_card', 'Card') },
          { key: 'status', label: tr(t, 'col_status', 'Status'), render: (row) => statusLabel(t, row.status) },
          { key: 'updated_at', label: tr(t, 'col_updated_at', 'Updated At'), render: (row) => formatTime(row.updated_at) }
        ]}
        t={t}
      />
      <Pager
        page={Number(query.data?.page ?? 0)}
        hasPrev={Boolean(query.data?.has_prev)}
        hasNext={Boolean(query.data?.has_next)}
        onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPage((prev) => prev + 1)}
        t={t}
      />

      <div className="section-subtitle">{tr(t, 'label_pair_link', 'Pair Status')}</div>
      <DataGrid
        rows={pairs}
        columns={[
          { key: 'left_name', label: tr(t, 'col_account', 'Account A') },
          { key: 'right_name', label: tr(t, 'col_to_account_id', 'Account B') },
          { key: 'left_to_right_status', label: tr(t, 'col_direction_left_to_right', 'A→B'), render: (row) => statusLabel(t, row.left_to_right_status) },
          { key: 'right_to_left_status', label: tr(t, 'col_direction_right_to_left', 'B→A'), render: (row) => statusLabel(t, row.right_to_left_status) },
          { key: 'pair_progress', label: tr(t, 'col_progress', 'Progress') }
        ]}
        t={t}
      />
      <Pager
        page={Number(query.data?.pair_page ?? 0)}
        hasPrev={Boolean(query.data?.pair_has_prev)}
        hasNext={Boolean(query.data?.pair_has_next)}
        onPrev={() => setPairPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPairPage((prev) => prev + 1)}
        t={t}
      />
    </section>
  )
}

function FriendshipsSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(0)
  const [q, setQ] = useState('')
  const [accountId, setAccountId] = useState('')
  const [fromAccountId, setFromAccountId] = useState('')
  const [targetAccountId, setTargetAccountId] = useState('')
  const [friendIdInput, setFriendIdInput] = useState('')

  const queryString = useMemo(() => buildQuery({ lang, page, q, account_id: accountId || undefined, from_account_id: fromAccountId || undefined }), [accountId, fromAccountId, lang, page, q])
  const query = useQuery({
    queryKey: ['management-friendships', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/friendships?${queryString}`)
  })

  const addMutation = useMutation({
    mutationFn: () =>
      requestJson<{ ok: boolean; message: string }>('/api/react/management/friendships/add', {
        method: 'POST',
        body: {
          from_account_id: Number(fromAccountId || 0),
          to_account_id: Number(targetAccountId || 0),
          to_friend_id: friendIdInput
        }
      }),
    onSuccess: (result) => {
      alert(result.message)
      queryClient.invalidateQueries({ queryKey: ['management-friendships'] })
    }
  })

  const deleteMutation = useMutation({
    mutationFn: () =>
      requestJson<{ ok: boolean; message: string }>('/api/react/management/friendships/delete', {
        method: 'POST',
        body: {
          from_account_id: Number(fromAccountId || 0),
          to_account_id: Number(targetAccountId || 0),
          friend_id: friendIdInput
        }
      }),
    onSuccess: (result) => {
      alert(result.message)
      queryClient.invalidateQueries({ queryKey: ['management-friendships'] })
    }
  })

  const cancelMutation = useMutation({
    mutationFn: (requestId: number) => requestJson<{ ok: boolean; message: string }>(`/api/react/management/friendships/${requestId}/cancel`, { method: 'POST', body: {} }),
    onSuccess: (result) => {
      alert(result.message)
      queryClient.invalidateQueries({ queryKey: ['management-friendships'] })
    }
  })

  const requests = ((query.data?.requests as unknown[]) ?? []) as Record<string, unknown>[]
  const friendships = ((query.data?.friendships as unknown[]) ?? []) as Record<string, unknown>[]
  const accounts = (((query.data?.accounts as unknown[]) ?? []) as Record<string, unknown>[])

  return (
    <section className="surface-card section-stack">
      <div className="section-title">{tr(t, 'menu_friendships', 'Friendships')}</div>
      <div className="form-grid">
        <input className="field-input" value={q} onChange={(event) => setQ(event.target.value)} placeholder={tr(t, 'label_search', 'Search')} />
        <select className="field-select" value={accountId} onChange={(event) => setAccountId(event.target.value)}>
          <option value="">{tr(t, 'label_all_accounts', 'All Accounts')}</option>
          {accounts.map((item) => (
            <option key={toText(item.id, t)} value={toText(item.id, t)}>{toText(item.display_name, t)}</option>
          ))}
        </select>
        <select className="field-select" value={fromAccountId} onChange={(event) => setFromAccountId(event.target.value)}>
          <option value="">{tr(t, 'label_from_account', 'From Account')}</option>
          {accounts.map((item) => (
            <option key={toText(item.id, t)} value={toText(item.id, t)}>{toText(item.display_name, t)}</option>
          ))}
        </select>
        <select className="field-select" value={targetAccountId} onChange={(event) => setTargetAccountId(event.target.value)}>
          <option value="">{tr(t, 'label_target_account_optional', 'Target Account (optional)')}</option>
          {accounts.map((item) => (
            <option key={toText(item.id, t)} value={toText(item.id, t)}>{toText(item.display_name, t)}</option>
          ))}
        </select>
        <input className="field-input" value={friendIdInput} onChange={(event) => setFriendIdInput(event.target.value)} placeholder={tr(t, 'placeholder_friend_id', 'Friend ID (optional)')} />
      </div>
      <div className="filter-row">
        <Button type="button" size="sm" variant="outline" onClick={() => setPage(0)}>{tr(t, 'label_search', 'Search')}</Button>
        <Button type="button" size="sm" onClick={() => addMutation.mutate()}>{tr(t, 'btn_create_add_request', 'Create Add Request')}</Button>
        <Button type="button" size="sm" variant="outline" onClick={() => deleteMutation.mutate()}>{tr(t, 'btn_create_delete_request', 'Create Delete Request')}</Button>
      </div>

      <div className="section-subtitle">{tr(t, 'section_friend_requests', 'Requests')}</div>
      <div className="table-wrap">
        <table className="grid-table">
          <thead>
            <tr>
              <th>{tr(t, 'col_id', 'ID')}</th>
              <th>{tr(t, 'col_type', 'Type')}</th>
              <th>{tr(t, 'col_account', 'Account')}</th>
              <th>{tr(t, 'col_friend_id', 'Friend ID')}</th>
              <th>{tr(t, 'col_status', 'Status')}</th>
              <th>{tr(t, 'label_created_time', 'Created')}</th>
              <th>{tr(t, 'col_actions', 'Actions')}</th>
            </tr>
          </thead>
          <tbody>
            {requests.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center text-muted">{tr(t, 'label_no_data', 'No data')}</td>
              </tr>
            )}
            {requests.map((row) => (
              <tr key={toText(row.id, t)}>
                <td className="mono">{toText(row.id, t)}</td>
                <td>{requestTypeLabel(t, row.request_type)}</td>
                <td>{toText(row.account_id, t)}</td>
                <td className="mono">{toText(row.to_friend_id, t)}</td>
                <td>{requestStatusLabel(t, row.status)}</td>
                <td className="mono">{formatTime(row.created_at)}</td>
                <td>
                  <Button type="button" size="sm" variant="outline" onClick={() => cancelMutation.mutate(Number(row.id))}>
                    {tr(t, 'label_cancel', 'Cancel')}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="section-subtitle">{tr(t, 'section_friendships', 'Friendships')}</div>
      <DataGrid
        rows={friendships}
        columns={[
          { key: 'id', label: tr(t, 'col_id', 'ID') },
          { key: 'account_id', label: tr(t, 'col_account_id', 'Account ID') },
          { key: 'friend_id', label: tr(t, 'col_friend_id', 'Friend ID') },
          { key: 'friendship_status', label: tr(t, 'col_status', 'Status') },
          { key: 'created_at', label: tr(t, 'label_created_time', 'Created'), render: (row) => formatTime(row.created_at) }
        ]}
        t={t}
      />

      <Pager
        page={Number(query.data?.page ?? 0)}
        hasPrev={Boolean(query.data?.has_prev)}
        hasNext={Boolean(query.data?.has_next)}
        onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPage((prev) => prev + 1)}
        t={t}
      />
    </section>
  )
}

function ExchangeCardsSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(0)
  const [q, setQ] = useState('')
  const [accountId, setAccountId] = useState('')
  const [status, setStatus] = useState('')

  const queryString = useMemo(() => buildQuery({ lang, page, q, account_id: accountId || undefined, status: status || undefined }), [accountId, lang, page, q, status])
  const query = useQuery({
    queryKey: ['management-exchange-cards', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/exchange-cards?${queryString}`)
  })

  const cancelMutation = useMutation({
    mutationFn: (requestId: number) => requestJson<{ ok: boolean; message: string }>(`/api/react/management/exchange-cards/${requestId}/cancel`, { method: 'POST', body: {} }),
    onSuccess: (result) => {
      alert(result.message)
      queryClient.invalidateQueries({ queryKey: ['management-exchange-cards'] })
    }
  })

  const rows = ((query.data?.requests as unknown[]) ?? []) as Record<string, unknown>[]

  return (
    <section className="surface-card section-stack">
      <div className="pagination-row">
        <div className="section-title">{tr(t, 'menu_exchange_cards', 'Exchange Cards')}</div>
        <div className="filter-row">
          <input className="field-input" value={q} onChange={(event) => setQ(event.target.value)} placeholder={tr(t, 'label_search', 'Search')} />
          <input className="field-input" value={accountId} onChange={(event) => setAccountId(event.target.value)} placeholder={tr(t, 'account_id', 'Account ID')} />
          <input className="field-input" value={status} onChange={(event) => setStatus(event.target.value)} placeholder={tr(t, 'filter_status', 'Status')} />
          <Button type="button" size="sm" variant="outline" onClick={() => setPage(0)}>{tr(t, 'label_search', 'Search')}</Button>
        </div>
      </div>

      <div className="table-wrap">
        <table className="grid-table">
          <thead>
            <tr>
              <th>{tr(t, 'col_id', 'ID')}</th>
              <th>{tr(t, 'label_from_account', 'From Account')}</th>
              <th>{tr(t, 'col_friend_id', 'Friend ID')}</th>
              <th>{tr(t, 'col_card', 'Card')}</th>
              <th>{tr(t, 'col_status', 'Status')}</th>
              <th>{tr(t, 'col_time', 'Time')}</th>
              <th>{tr(t, 'col_actions', 'Actions')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center text-muted">{tr(t, 'label_no_data', 'No data')}</td>
              </tr>
            )}
            {rows.map((row) => (
              <tr key={toText(row.id, t)}>
                <td className="mono">{toText(row.id, t)}</td>
                <td>{toText(row.from_account_id, t)}</td>
                <td className="mono">{toText(row.to_friend_id, t)}</td>
                <td>{toText(row.target_card_id, t)}</td>
                <td>{exchangeStatusLabel(t, row.status)}</td>
                <td className="mono">{formatTime(row.created_at)}</td>
                <td>
                  {Boolean(row.can_cancel) ? (
                    <Button type="button" size="sm" variant="outline" onClick={() => cancelMutation.mutate(Number(row.id))}>{tr(t, 'btn_cancel_exchange_request', 'Cancel')}</Button>
                  ) : (
                    <span className="text-muted">-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Pager
        page={Number(query.data?.page ?? 0)}
        hasPrev={Boolean(query.data?.has_prev)}
        hasNext={Boolean(query.data?.has_next)}
        onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPage((prev) => prev + 1)}
        t={t}
      />
    </section>
  )
}

function NotificationsSection({ lang, t }: { lang: string; t: Record<string, string> }) {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(0)
  const [scene, setScene] = useState('')
  const [accountId, setAccountId] = useState('')
  const [isRead, setIsRead] = useState('')
  const [q, setQ] = useState('')
  const [configState, setConfigState] = useState<
    Record<string, { enabled: boolean; enabledWebhook: boolean; extraConfig: Record<string, unknown> }>
  >({})

  const queryString = useMemo(
    () => buildQuery({ lang, page, scene: scene || undefined, account_id: accountId || undefined, is_read: isRead || undefined, q }),
    [accountId, isRead, lang, page, q, scene]
  )

  const query = useQuery({
    queryKey: ['management-notifications', queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/notifications?${queryString}`)
  })

  const markReadMutation = useMutation({
    mutationFn: (notificationId: number) => requestJson<{ ok: boolean }>(`/api/react/management/notifications/${notificationId}/mark-read`, { method: 'POST', body: {} }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['management-notifications'] })
  })

  const markAllMutation = useMutation({
    mutationFn: () => requestJson<{ ok: boolean; message: string }>('/api/react/management/notifications/mark-all-read', {
      method: 'POST',
      body: {
        scene: scene || null,
        account_id: accountId || null
      }
    }),
    onSuccess: (result) => {
      alert(result.message)
      queryClient.invalidateQueries({ queryKey: ['management-notifications'] })
    }
  })

  const saveConfigMutation = useMutation({
    mutationFn: (payload: { scene: string; enabled: boolean; enabledWebhook: boolean; extraConfig: Record<string, unknown> }) =>
      requestJson<{ ok: boolean; message: string }>('/api/react/management/notifications/config', {
        method: 'POST',
        body: {
          scene: payload.scene,
          enabled: payload.enabled,
          enabled_webhook: payload.enabledWebhook,
          extra_config: payload.extraConfig
        }
      }),
    onSuccess: (result) => {
      alert(result.message)
      queryClient.invalidateQueries({ queryKey: ['management-notifications'] })
    }
  })

  const testWebhookMutation = useMutation({
    mutationFn: (notificationId: number | null) =>
      requestJson<{ ok: boolean; message: string }>('/api/react/management/notifications/test-webhook', {
        method: 'POST',
        body: {
          notification_id: notificationId
        }
      }),
    onSuccess: (result) => alert(result.message)
  })

  const notifications = useMemo(
    () => (((query.data?.notifications as unknown[]) ?? []) as Record<string, unknown>[]),
    [query.data?.notifications]
  )
  const configs = useMemo(
    () => (((query.data?.configs as unknown[]) ?? []) as Record<string, unknown>[]),
    [query.data?.configs]
  )
  const sceneOptions = useMemo(
    () =>
      (((query.data?.scene_options as unknown[]) ?? []) as Array<{ value: string; label: string }>),
    [query.data?.scene_options]
  )
  const taskTypeOptions = useMemo(
    () => (((query.data?.task_type_options as unknown[]) ?? []) as string[]),
    [query.data?.task_type_options]
  )
  const taskStatusOptions = useMemo(
    () => (((query.data?.task_status_options as unknown[]) ?? []) as string[]),
    [query.data?.task_status_options]
  )
  const rarityCodes = useMemo(
    () => (((query.data?.rarity_codes as unknown[]) ?? []) as string[]),
    [query.data?.rarity_codes]
  )
  const accountNameMap = useMemo(
    () => ((query.data?.account_name_map as Record<string, string> | undefined) ?? {}),
    [query.data?.account_name_map]
  )

  function updateExtraList(sceneKey: string, field: string, value: string, checked: boolean) {
    setConfigState((prev) => {
      const current = prev[sceneKey]
      if (!current) {
        return prev
      }
      const raw = current.extraConfig[field]
      const currentList = Array.isArray(raw) ? raw.map((item) => String(item)) : []
      const nextList = checked
        ? [...new Set([...currentList, value])]
        : currentList.filter((item) => item !== value)
      return {
        ...prev,
        [sceneKey]: {
          ...current,
          extraConfig: {
            ...current.extraConfig,
            [field]: nextList
          }
        }
      }
    })
  }

  useEffect(() => {
    const nextState: Record<
      string,
      { enabled: boolean; enabledWebhook: boolean; extraConfig: Record<string, unknown> }
    > = {}
    for (const config of configs) {
      const sceneKey = toText(config.scene)
      nextState[sceneKey] = {
        enabled: Boolean(config.enabled),
        enabledWebhook: Boolean(config.enabled_webhook),
        extraConfig: (config.extra_config as Record<string, unknown>) ?? {}
      }
    }
    setConfigState((prev) => {
      const prevKeys = Object.keys(prev)
      const nextKeys = Object.keys(nextState)
      if (prevKeys.length !== nextKeys.length) {
        return nextState
      }
      for (const key of nextKeys) {
        const prevItem = prev[key]
        const nextItem = nextState[key]
        if (!prevItem) {
          return nextState
        }
        if (prevItem.enabled !== nextItem.enabled || prevItem.enabledWebhook !== nextItem.enabledWebhook) {
          return nextState
        }
        if (JSON.stringify(prevItem.extraConfig) !== JSON.stringify(nextItem.extraConfig)) {
          return nextState
        }
      }
      return prev
    })
  }, [configs])

  return (
    <section className="surface-card section-stack">
      <div className="pagination-row">
        <div className="section-title">{tr(t, 'notification_center', 'Notifications')}</div>
        <div className="filter-row">
          <select className="field-select" value={scene} onChange={(event) => setScene(event.target.value)}>
            <option value="">{tr(t, 'label_all_scenes', 'All Scenes')}</option>
            {sceneOptions.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
          <input className="field-input" value={accountId} onChange={(event) => setAccountId(event.target.value)} placeholder={tr(t, 'account_id', 'Account ID')} />
          <select className="field-select" value={isRead} onChange={(event) => setIsRead(event.target.value)}>
            <option value="">{tr(t, 'label_all_status', 'All Status')}</option>
            <option value="false">{tr(t, 'label_unread', 'Unread')}</option>
            <option value="true">{tr(t, 'label_read', 'Read')}</option>
          </select>
          <input className="field-input" value={q} onChange={(event) => setQ(event.target.value)} placeholder={tr(t, 'notification_search_placeholder', 'Search title/content/account')} />
          <Button type="button" size="sm" variant="outline" onClick={() => setPage(0)}>{tr(t, 'label_search', 'Search')}</Button>
          <Button type="button" size="sm" onClick={() => markAllMutation.mutate()}>{tr(t, 'btn_mark_all_read', 'Mark All Read')}</Button>
          <Button type="button" size="sm" variant="outline" onClick={() => testWebhookMutation.mutate(null)}>{tr(t, 'btn_test_webhook', 'Test Webhook')}</Button>
        </div>
      </div>

      <div className="section-subtitle">{tr(t, 'page_notification_config', 'Notification Config')}</div>
      <div className="form-grid">
        {configs.map((config) => {
          const sceneKey = toText(config.scene)
          const current = configState[sceneKey] ?? {
            enabled: Boolean(config.enabled),
            enabledWebhook: Boolean(config.enabled_webhook),
            extraConfig: (config.extra_config as Record<string, unknown>) ?? {}
          }
          return (
            <div key={sceneKey} className="surface-card section-stack">
              <div className="section-title">{tr(t, `notification_scene_${sceneKey}`, sceneKey)}</div>
              <label className="filter-row">
                <input
                  type="checkbox"
                  checked={current.enabled}
                  onChange={(event) => {
                    const enabled = event.target.checked
                    const next = { ...current, enabled }
                    setConfigState((prev) => ({ ...prev, [sceneKey]: next }))
                    saveConfigMutation.mutate({
                      scene: sceneKey,
                      enabled,
                      enabledWebhook: current.enabledWebhook,
                      extraConfig: current.extraConfig
                    })
                  }}
                />
                <span>{tr(t, 'label_enabled', 'Enabled')}</span>
              </label>
              <label className="filter-row">
                <input
                  type="checkbox"
                  checked={current.enabledWebhook}
                  onChange={(event) => {
                    const enabledWebhook = event.target.checked
                    const next = { ...current, enabledWebhook }
                    setConfigState((prev) => ({ ...prev, [sceneKey]: next }))
                    saveConfigMutation.mutate({
                      scene: sceneKey,
                      enabled: current.enabled,
                      enabledWebhook,
                      extraConfig: current.extraConfig
                    })
                  }}
                />
                <span>{tr(t, 'label_webhook', 'Webhook')}</span>
              </label>
              {sceneKey === 'rare_card_obtained' && (
                <>
                  <div className="section-subtitle">{tr(t, 'label_notify_by_rarity', 'Notify by Rarity')}</div>
                  <div className="filter-row">
                    {rarityCodes.map((rarity) => {
                      const selectedList = Array.isArray(current.extraConfig.notify_by_rarity) ? current.extraConfig.notify_by_rarity.map((item) => String(item)) : []
                      const checked = selectedList.includes(rarity)
                      return (
                        <label key={`${sceneKey}-rarity-${rarity}`} className="filter-row">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(event) => updateExtraList(sceneKey, 'notify_by_rarity', rarity, event.target.checked)}
                          />
                          <span>{t[`rarity_${rarity}`] ?? rarity}</span>
                        </label>
                      )
                    })}
                  </div>
                  <input
                    className="field-input"
                    value={Array.isArray(current.extraConfig.notify_card_ids) ? current.extraConfig.notify_card_ids.map((item) => String(item)).join(',') : ''}
                    placeholder={tr(t, 'label_notify_card_ids', 'Target Cards') + ' (1,2,3)'}
                    onChange={(event) => {
                      const values = event.target.value
                        .split(',')
                        .map((item) => item.trim())
                        .filter((item) => /^\d+$/.test(item))
                        .map((item) => Number(item))
                      setConfigState((prev) => ({
                        ...prev,
                        [sceneKey]: {
                          ...current,
                          extraConfig: {
                            ...current.extraConfig,
                            notify_card_ids: values
                          }
                        }
                      }))
                    }}
                  />
                </>
              )}
              {sceneKey === 'task_status' && (
                <>
                  <div className="section-subtitle">{tr(t, 'label_notify_task_types', 'Task Types')}</div>
                  <div className="filter-row">
                    {taskTypeOptions.map((taskType) => {
                      const selectedList = Array.isArray(current.extraConfig.notify_task_types) ? current.extraConfig.notify_task_types.map((item) => String(item)) : []
                      const checked = selectedList.includes(taskType)
                      return (
                        <label key={`${sceneKey}-task-${taskType}`} className="filter-row">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(event) => updateExtraList(sceneKey, 'notify_task_types', taskType, event.target.checked)}
                          />
                          <span>{taskTypeLabel(t, taskType)}</span>
                        </label>
                      )
                    })}
                  </div>
                  <div className="section-subtitle">{tr(t, 'label_notify_on', 'Notify On')}</div>
                  <div className="filter-row">
                    {taskStatusOptions.map((status) => {
                      const selectedList = Array.isArray(current.extraConfig.notify_on) ? current.extraConfig.notify_on.map((item) => String(item)) : ['failed', 'blocked', 'timeout']
                      const checked = selectedList.includes(status)
                      return (
                        <label key={`${sceneKey}-status-${status}`} className="filter-row">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(event) => updateExtraList(sceneKey, 'notify_on', status, event.target.checked)}
                          />
                          <span>{statusLabel(t, status)}</span>
                        </label>
                      )
                    })}
                  </div>
                </>
              )}
              <div className="filter-row">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    saveConfigMutation.mutate({
                      scene: sceneKey,
                      enabled: current.enabled,
                      enabledWebhook: current.enabledWebhook,
                      extraConfig: current.extraConfig
                    })
                  }
                >
                  {tr(t, 'btn_save', 'Save')}
                </Button>
              </div>
            </div>
          )
        })}
      </div>

      <div className="table-wrap">
        <table className="grid-table">
          <thead>
            <tr>
              <th>{tr(t, 'col_id', 'ID')}</th>
              <th>{tr(t, 'col_scene', 'Scene')}</th>
              <th>{tr(t, 'col_title', 'Title')}</th>
              <th>{tr(t, 'col_description', 'Content')}</th>
              <th>{tr(t, 'col_account', 'Account')}</th>
              <th>{tr(t, 'label_read', 'Read')}</th>
              <th>{tr(t, 'col_time', 'Time')}</th>
              <th>{tr(t, 'col_actions', 'Actions')}</th>
            </tr>
          </thead>
          <tbody>
            {notifications.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center text-muted">{tr(t, 'notification_empty', 'No notifications')}</td>
              </tr>
            )}
            {notifications.map((row) => (
              <tr key={toText(row.id, t)}>
                <td className="mono">{toText(row.id, t)}</td>
                <td>{toText(row.scene_label, t) || tr(t, `notification_scene_${toText(row.scene, t)}`, toText(row.scene, t))}</td>
                <td>{toText(row.title, t)}</td>
                <td>
                  <div className="notification-row-content">
                    {String(row.image_url ?? '').length > 0 ? (
                      <img
                        src={String(row.image_url)}
                        alt={toText(row.title, t)}
                        className="notification-thumb"
                        loading="lazy"
                        decoding="async"
                        onError={(event) => {
                          const image = event.currentTarget
                          const webpUrl = String(row.image_webp_url ?? '')
                          if (webpUrl && image.dataset.webpTried !== '1') {
                            image.dataset.webpTried = '1'
                            image.src = webpUrl
                            return
                          }
                          image.style.display = 'none'
                        }}
                      />
                    ) : null}
                    <div className="notification-content-text" title={toText(row.content, t)}>
                      {toText(row.content, t)}
                    </div>
                  </div>
                </td>
                <td>
                  {toText(row.related_account_id, t) === '-'
                    ? '-'
                    : accountNameMap[String(row.related_account_id)] ?? toText(row.related_account_id, t)}
                </td>
                <td>{Boolean(row.is_read) ? tr(t, 'label_read', 'Read') : tr(t, 'label_unread', 'Unread')}</td>
                <td className="mono">{formatTime(row.created_at)}</td>
                <td>
                  <div className="filter-row">
                    {!Boolean(row.is_read) && (
                      <Button type="button" size="sm" variant="outline" onClick={() => markReadMutation.mutate(Number(row.id))}>{tr(t, 'btn_mark_read', 'Mark Read')}</Button>
                    )}
                    <Button type="button" size="sm" variant="outline" onClick={() => testWebhookMutation.mutate(Number(row.id))}>{tr(t, 'btn_test_send', 'Test')}</Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Pager
        page={Number(query.data?.page ?? 0)}
        hasPrev={Boolean(query.data?.has_prev)}
        hasNext={Boolean(query.data?.has_next)}
        onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPage((prev) => prev + 1)}
        t={t}
      />
    </section>
  )
}

function JsonSection({ endpoint, title, lang, t }: { endpoint: string; title: string; lang: string; t: Record<string, string> }) {
  const [page, setPage] = useState(0)
  const queryString = useMemo(() => buildQuery({ lang, page }), [lang, page])
  const query = useQuery({
    queryKey: ['management-generic', endpoint, queryString],
    queryFn: () => fetchJson<Record<string, unknown>>(`/api/react/management/${endpoint}?${queryString}`)
  })

  const rows = ((query.data?.items as unknown[]) ?? []) as Record<string, unknown>[]
  const columns = useMemo<ColumnDef[]>(() => {
    if (rows.length === 0) {
      return []
    }
    return Object.keys(rows[0]).slice(0, 8).map((key) => ({
      key,
      label: key,
      render: (row) => (key.includes('at') ? formatTime(row[key]) : toText(row[key]))
    }))
  }, [rows])

  return (
    <section className="surface-card section-stack">
      <div className="section-title">{title}</div>
      {query.isLoading && <div className="text-sm text-muted">{tr(t, 'label_loading', 'Loading...')}</div>}
      {query.isError && <div className="text-sm text-danger">{(query.error as Error).message}</div>}
      {columns.length > 0 && <DataGrid rows={rows} columns={columns} t={t} />}
      <Pager
        page={Number(query.data?.page ?? 0)}
        hasPrev={Boolean(query.data?.has_prev)}
        hasNext={Boolean(query.data?.has_next)}
        onPrev={() => setPage((prev) => Math.max(prev - 1, 0))}
        onNext={() => setPage((prev) => prev + 1)}
        t={t}
      />
    </section>
  )
}

function ManagementSectionRouter({ lang, sectionKey, t }: { lang: string; sectionKey: string; t: Record<string, string> }) {
  if (sectionKey === 'accounts') {
    return <AccountsSection lang={lang} t={t} />
  }
  if (sectionKey === 'plans') {
    return <PlansSection lang={lang} t={t} />
  }
  if (sectionKey === 'resources') {
    return <ResourcesSection lang={lang} t={t} />
  }
  if (sectionKey === 'tasks') {
    return <TasksSection lang={lang} t={t} />
  }
  if (sectionKey === 'metadata') {
    return <MetadataSection lang={lang} t={t} />
  }
  if (sectionKey === 'daily-gift') {
    return <DailyGiftSection lang={lang} t={t} />
  }
  if (sectionKey === 'friendships') {
    return <FriendshipsSection lang={lang} t={t} />
  }
  if (sectionKey === 'exchange-cards') {
    return <ExchangeCardsSection lang={lang} t={t} />
  }
  if (sectionKey === 'notifications') {
    return <NotificationsSection lang={lang} t={t} />
  }
  return <JsonSection endpoint={sectionKey} title={sectionKey} lang={lang} t={t} />
}

export function ManagementPage({ lang, t }: ManagementPageProps) {
  return (
    <section className="section-stack">
      <div className="surface-card tab-nav">
        {sections.map((section) => (
          <NavLink key={section.key} to={`/management/${section.key}`}>
            {({ isActive }) => (
              <Button variant={isActive ? 'default' : 'outline'} size="sm" type="button">
                {t[section.labelKey] ?? section.fallback}
              </Button>
            )}
          </NavLink>
        ))}
      </div>

      <Routes>
        <Route path="/" element={<Navigate to="/management/accounts" replace />} />
        {sections.map((section) => (
          <Route key={section.key} path={section.key} element={<ManagementSectionRouter lang={lang} sectionKey={section.key} t={t} />} />
        ))}
      </Routes>
    </section>
  )
}
