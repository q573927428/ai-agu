/** API 响应类型 */
export interface ApiResponse<T = any> {
  code: number;
  data: T | null;
  message: string;
}

/** 排名项 */
export interface RankingItem {
  rank: number;
  stock_code: string;
  stock_name: string;
  predicted_return: number;
  predicted_return_1d: number | null;
  confidence: number | null;
  industry: string | null;
  market_cap: number | null;
  top_factors: Array<{ name: string; contribution: number }> | null;
}

/** 排名数据 */
export interface RankingData {
  date: string;
  rankings: RankingItem[];
  total: number;
}

/** 股票基础信息 */
export interface StockBasic {
  stock_code: string;
  stock_name: string;
  industry: string | null;
  sub_industry: string | null;
  area: string | null;
  market: string | null;
  list_date: string | null;
  is_active: number;
}

/** 股票日数据 */
export interface StockDaily {
  stock_code: string;
  trade_date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  pre_close: number | null;
  volume: number | null;
  amount: number | null;
  pct_chg: number | null;
  turnover_rate: number | null;
  pe_ttm: number | null;
  pb: number | null;
  total_mv: number | null;
  float_mv: number | null;
}

/** 股票预测 */
export interface StockPrediction {
  predict_date: string;
  predicted_return: number | null;
  predicted_return_1d: number | null;
  confidence: number | null;
  model_version: string | null;
}

/** 股票详情 */
export interface StockDetail {
  basic: StockBasic;
  latest_daily: StockDaily | null;
  latest_prediction: StockPrediction | null;
}

/** 因子值 */
export interface FactorValue {
  name: string;
  value: number;
}

/** 因子重要性 */
export interface FactorImportance {
  factor_name: string;
  importance: number;
  rank: number;
}

/** 市场概览 */
export interface MarketOverview {
  market_index: {
    sh_index: number;
    sh_change: number;
    sz_index: number;
    sz_change: number;
    cyb_index: number | null;
    cyb_change: number | null;
    hs300_index: number | null;
    hs300_change: number | null;
    zz500_index: number | null;
    zz500_change: number | null;
    kc50_index: number | null;
    kc50_change: number | null;
  };
  market_stats: {
    up_count: number;
    down_count: number;
    flat_count: number;
    advance_decline_ratio: number;
  };
  top_industries: Array<{ industry: string; return_5d: number }>;
  model_status: {
    model_version: string;
    last_train_date: string | null;
    latest_ic: number;
    is_active: boolean;
    models?: Array<{
      id: number;
      model_version: string;
      train_date: string | null;
      valid_ic: number;
      num_samples: number | null;
      num_features: number | null;
      is_active: boolean;
    }>;
  };
}