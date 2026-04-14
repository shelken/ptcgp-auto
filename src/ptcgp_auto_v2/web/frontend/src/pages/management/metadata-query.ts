import { buildQuery } from '../../lib/api'

interface MetadataQuerySource {
  lang: string
  uiStep: 1 | 2 | 3
  nodeType: string
  nodeId: string
  setCode?: string
  packName?: string
  action: string
  snapshotId?: string
}

interface MetadataRequestSource {
  nodeType: string
  nodeId: string
  setCode?: string
  packName?: string
  action: string
  snapshotId?: string
}

interface MetadataPreviewSource {
  action: string
  nodeType: string
  nodeId: string
  forceRefresh: boolean
  snapshotId?: string
}

interface MetadataRequestContext {
  selected_node_type: string
  selected_node_id: string
  selected_set_code?: string
  selected_pack_name?: string
  current_action: string
  snapshot_id?: string
}

function buildMetadataQueryParams(source: MetadataQuerySource) {
  return {
    lang: source.lang,
    ui_step: source.uiStep,
    ...buildMetadataRequestContext(source)
  }
}

export function buildMetadataRequestContext(source: MetadataRequestSource): MetadataRequestContext {
  const context: Partial<MetadataRequestContext> = {
    selected_node_type: source.nodeType,
    selected_node_id: source.nodeId
  }

  if (source.setCode) {
    context.selected_set_code = source.setCode
  }

  if (source.packName) {
    context.selected_pack_name = source.packName
  }

  context.current_action = source.action

  if (source.snapshotId) {
    context.snapshot_id = source.snapshotId
  }

  return context as MetadataRequestContext
}

export function buildMetadataQueryString(source: MetadataQuerySource) {
  return buildQuery(buildMetadataQueryParams(source))
}

export function buildMetadataPreviewPayload(source: MetadataPreviewSource) {
  return {
    action: source.action,
    node_type: source.nodeType,
    node_id: source.nodeId,
    force_refresh: source.forceRefresh,
    ...(source.snapshotId ? { snapshot_id: source.snapshotId } : {})
  }
}

export function buildMetadataExecutePayload(snapshotId: string) {
  return {
    snapshot_id: snapshotId
  }
}
