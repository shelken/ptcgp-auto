/**
 * Select 空值占位，避免 Radix SelectItem 不接受空字符串 value
 */
const SELECT_EMPTY_VALUE = '__PTCGP_SELECT_EMPTY__'

/**
 * 将业务值映射为 Select 可用值
 */
export function encodeSelectValue(value: string): string {
  return value === '' ? SELECT_EMPTY_VALUE : value
}

/**
 * 将 Select 值还原为业务值
 */
export function decodeSelectValue(value: string): string {
  return value === SELECT_EMPTY_VALUE ? '' : value
}
