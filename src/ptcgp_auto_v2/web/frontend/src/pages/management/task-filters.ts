interface ManagementTaskAccountFilter {
  selectedAccountId: string
  selectedAccountQuery: string
}

interface BuildResetCompletedTasksPayloadOptions {
  status: string
  taskType: string
  accountKeyword: string
}

export function resolveManagementTaskAccountFilter(accountKeyword: string): ManagementTaskAccountFilter {
  const normalizedAccountKeyword = accountKeyword.trim()
  const selectedAccountMatch = normalizedAccountKeyword.match(/^(\d+)/)

  return {
    selectedAccountId: selectedAccountMatch?.[1] ?? '',
    selectedAccountQuery: selectedAccountMatch ? '' : normalizedAccountKeyword
  }
}

export function buildResetCompletedTasksPayload({
  status,
  taskType,
  accountKeyword
}: BuildResetCompletedTasksPayloadOptions) {
  const { selectedAccountId, selectedAccountQuery } = resolveManagementTaskAccountFilter(accountKeyword)

  return {
    status: status ? [status] : [],
    task_type: taskType ? [taskType] : [],
    account_id: selectedAccountId || null,
    account_q: selectedAccountQuery
  }
}
