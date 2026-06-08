/** 常量定义 */

/** API 路径 */
export const API_PATHS = {
  HEALTH: "/api/v1/health",
  RANKINGS: "/api/v1/rankings",
  MARKET_OVERVIEW: "/api/v1/market/overview",
  MODEL_STATUS: "/api/v1/model/status",
  FACTOR_IMPORTANCE: "/api/v1/factors/importance",
  STOCK_SEARCH: "/api/v1/stocks/search",
  STOCK_DETAIL: (code: string) => `/api/v1/stocks/${code}`,
  STOCK_FACTORS: (code: string) => `/api/v1/stocks/${code}/factors`,
  STOCK_FINANCIAL: (code: string) => `/api/v1/stocks/${code}/financial`,
  STOCK_PREDICTION: (code: string) => `/api/v1/stocks/${code}/prediction`,
} as const;

/** 行业列表 */
export const INDUSTRIES = [
  "全部",
  "电子",
  "计算机",
  "食品饮料",
  "医药生物",
  "银行",
  "非银金融",
  "房地产",
  "汽车",
  "机械设备",
  "电力设备",
  "化工",
  "有色金属",
  "钢铁",
  "建筑材料",
  "建筑装饰",
  "交通运输",
  "通信",
  "传媒",
  "国防军工",
  "公用事业",
] as const;

/** 市场选项 */
export const MARKET_OPTIONS = [
  { label: "全部", value: "" },
  { label: "沪市", value: "SH" },
  { label: "深市", value: "SZ" },
  { label: "北交所", value: "BJ" },
] as const;

/** 预测收益率颜色阈值 */
export const RETURN_THRESHOLDS = {
  HIGH: 0.05, // >=5% 红色
  MID: 0, // >=0% 橙色
  LOW: -0.05, // >=-5% 绿色
} as const;

/** 因子字段名 → 中文名称映射 */
export const FACTOR_NAME_MAP: Record<string, string> = {
  // 宏观因子
  macro_gdp_yoy: "GDP同比",
  macro_cpi_yoy: "CPI同比",
  macro_ppi_yoy: "PPI同比",
  macro_pmi: "制造业PMI",
  macro_m2_yoy: "M2同比",
  macro_shibor_on: "隔夜Shibor",
  macro_shibor_1m: "1月Shibor",
  macro_usdcny: "美元/人民币",
  macro_hgt: "沪股通净流入",
  macro_sgt: "深股通净流入",
  macro_north_flow: "北向资金净流入",
  macro_margin_balance: "两融余额",
  macro_us_y3m: "美债3月",
  macro_us_y2y: "美债2年",
  macro_us_y10y: "美债10年",
  // 市场因子
  market_idx_return_5d: "大盘5日收益",
  market_idx_return_20d: "大盘20日收益",
  market_idx_volatility_20d: "大盘波动率",
  market_turnover_ma5: "市场换手率",
  market_advance_decline_ratio: "涨跌比",
  market_volume_ratio: "市场量比",
  market_breadth_20d: "市场宽度",
  market_vix_proxy: "恐慌指数",
  market_style_momentum: "风格动量",
  market_style_value: "风格价值",
  // 行业因子
  industry_return_5d: "行业5日收益",
  industry_return_20d: "行业20日收益",
  industry_return_volatility: "行业波动率",
  industry_pe_percentile: "行业PE分位",
  industry_pb_percentile: "行业PB分位",
  industry_roe_median: "行业ROE中位",
  industry_momentum_rank: "行业动量排名",
  industry_reversal_signal: "行业反转信号",
  industry_fund_flow: "行业资金流",
  industry_dispersion: "行业离散度",
  // 个股因子
  stock_return_1d: "1日收益",
  stock_return_5d: "5日收益",
  stock_return_20d: "20日收益",
  stock_volatility_20d: "20日波动率",
  stock_volatility_60d: "60日波动率",
  stock_volume_ratio_5d: "5日量比",
  stock_turnover_rate_5d: "5日换手率",
  stock_pe_ttm: "滚动市盈率",
  stock_pb: "市净率",
  stock_ps_ttm: "市销率",
  stock_roe_ttm: "净资产收益率",
  stock_roa_ttm: "总资产收益率",
  stock_revenue_yoy: "营收同比",
  stock_profit_yoy: "利润同比",
  stock_gross_margin: "毛利率",
  stock_debt_ratio: "资产负债率",
  stock_momentum_20d: "20日动量",
  stock_reversal_5d: "5日反转",
  stock_size_factor: "规模因子",
  stock_illiquidity: "非流动性",
};

/** 获取因子中文名 */
export function getFactorDisplayName(name: string): string {
  return FACTOR_NAME_MAP[name] || name;
}
