import { tr } from '../../lib/i18n'

import {
  AccountIdentityCell,
  type ManagementColumnDef,
  renderDurationWithTooltip,
  renderRelativeTime,
  renderStatusBadgeWithReason,
  statusBadgeVariant,
  statusLabel,
  taskTypeLabel,
  toText
} from './shared'

export function buildTaskTableColumns({
  lang,
  t
}: {
  lang: string
  t: Record<string, string>
}): ManagementColumnDef[] {
  return [
    { key: 'id', label: tr(t, 'col_id', 'ID'), headerClassName: 'table-col-id', cellClassName: 'table-col-id' },
    {
      key: 'account_id',
      label: tr(t, 'col_account', 'Account'),
      headerClassName: 'table-col-account',
      cellClassName: 'table-col-account',
      render: (row) => (
        <AccountIdentityCell
          t={t}
          accountId={row.account_id}
          name={row.account_name}
          friendId={row.account_friend_id}
          gameId={row.account_game_id}
        />
      )
    },
    {
      key: 'task_type',
      label: tr(t, 'col_task', 'Task'),
      headerClassName: 'table-col-task',
      cellClassName: 'table-col-task',
      render: (row) => taskTypeLabel(t, row.task_type)
    },
    {
      key: 'status',
      label: tr(t, 'col_status', 'Status'),
      headerClassName: 'table-col-status',
      cellClassName: 'table-col-status',
      render: (row) => renderStatusBadgeWithReason(
        statusLabel(t, row.status),
        statusBadgeVariant(row.status),
        row.error_message
      )
    },
    {
      key: 'dispatch_rank',
      label: tr(t, 'col_dispatch_priority', 'Dispatch Priority'),
      sortKey: 'dispatch_priority',
      headerClassName: 'table-col-priority',
      cellClassName: 'table-col-priority',
      render: (row) => {
        const rank = Number(row.dispatch_rank ?? 0)
        const total = Number(row.dispatch_rank_total ?? 0)
        if (rank <= 0 || total <= 0) {
          return '-'
        }
        return `${rank}/${total}`
      }
    },
    {
      key: 'last_completed_at_iso',
      label: tr(t, 'col_last_completed', 'Last Completed'),
      sortKey: 'last_completed_at',
      headerClassName: 'table-col-time',
      cellClassName: 'table-col-time',
      render: (row) => renderRelativeTime(row.last_completed_at_iso, lang, t)
    },
    {
      key: 'last_duration_seconds',
      label: tr(t, 'col_last_duration', 'Last Duration'),
      sortKey: 'last_duration_seconds',
      headerClassName: 'table-col-duration',
      cellClassName: 'table-col-duration',
      render: (row) => renderDurationWithTooltip(row.last_duration_seconds)
    },
    {
      key: 'reset_type',
      label: tr(t, 'col_reset_type', 'Reset Type'),
      headerClassName: 'table-col-rule',
      cellClassName: 'table-col-rule',
      render: (row) => {
        const resetType = toText(row.reset_type, t)
        if (resetType === '-') {
          return '-'
        }
        return tr(t, `reset_type_${resetType}`, tr(t, 'label_unknown', 'Unknown'))
      }
    },
    {
      key: 'next_run_at_iso',
      label: tr(t, 'col_next_run', 'Next Run'),
      sortKey: 'next_run_at',
      headerClassName: 'table-col-time',
      cellClassName: 'table-col-time',
      render: (row) => renderRelativeTime(row.next_run_at_iso, lang, t)
    },
    { key: 'plan_name', label: tr(t, 'col_plan', 'Plan'), headerClassName: 'table-col-plan', cellClassName: 'table-col-plan' },
    { key: 'plan_priority', label: tr(t, 'label_priority', 'Priority'), headerClassName: 'table-col-priority', cellClassName: 'table-col-priority' },
    {
      key: 'target_pack_label',
      label: tr(t, 'col_target_pack', 'Target Pack'),
      headerClassName: 'table-col-pack',
      cellClassName: 'table-col-pack',
      render: (row) => {
        const value = toText(row.target_pack_label, t)
        if (value === '-') {
          return value
        }
        return Boolean(row.target_pack_auto) ? `${value} (${tr(t, 'label_auto', 'Auto')})` : value
      }
    }
  ]
}
