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

interface MetadataPreviewSource {
  action: string
  nodeType: string
  nodeId: string
  forceRefresh: boolean
}

function buildMetadataQueryParams(source: MetadataQuerySource) {
  return {
    lang: source.lang,
    ui_step: source.uiStep,
    selected_node_type: source.nodeType,
    selected_node_id: source.nodeId,
    selected_set_code: source.setCode || undefined,
    selected_pack_name: source.packName || undefined,
    current_action: source.action,
    snapshot_id: source.snapshotId || undefined
  }
}

export function buildMetadataQueryString(source: MetadataQuerySource) {
  return buildQuery(buildMetadataQueryParams(source))
}

export function buildMetadataPreviewPayload(source: MetadataPreviewSource) {
  return {
    action: source.action,
    node_type: source.nodeType,
    node_id: source.nodeId,
    force_refresh: source.forceRefresh
  }
}

export function buildMetadataExecutePayload(snapshotId: string) {
  return {
    snapshot_id: snapshotId
  }
}
