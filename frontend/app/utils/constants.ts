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