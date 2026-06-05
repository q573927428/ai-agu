/** 数字/日期格式化工具 */

/**
 * 格式化数字为百分比
 */
export function formatPercent(value: number | null | undefined, decimals: number = 2): string {
  if (value === null || value === undefined) return "--";
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * 格式化数字为带单位的字符串
 */
export function formatNumber(value: number | null | undefined, decimals: number = 2): string {
  if (value === null || value === undefined) return "--";
  if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(decimals)}万亿`;
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(decimals)}亿`;
  if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(decimals)}万`;
  return value.toFixed(decimals);
}

/**
 * 格式化日期
 */
export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "--";
  const date = new Date(dateStr);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

/**
 * 格式化货币
 */
export function formatMoney(value: number | null | undefined): string {
  if (value === null || value === undefined) return "--";
  return `¥${formatNumber(value)}`;
}

/**
 * 格式化涨跌幅颜色
 */
export function getChangeColor(value: number | null | undefined): string {
  if (value === null || value === undefined) return "";
  if (value > 0) return "var(--el-color-danger)";
  if (value < 0) return "var(--el-color-success)";
  return "";
}

/**
 * 格式化涨跌幅符号
 */
export function formatChange(value: number | null | undefined): string {
  if (value === null || value === undefined) return "--";
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(2)}%`;
}