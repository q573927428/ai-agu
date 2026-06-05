/** API 请求封装 */
import type { ApiResponse, RankingData, StockDetail, MarketOverview, FactorImportance } from "~/types/api";

export function useApi() {
  const config = useRuntimeConfig();
  const baseURL = config.public.apiBase;

  /**
   * 通用请求方法
   */
  async function request<T>(path: string, options: Record<string, any> = {}): Promise<ApiResponse<T>> {
    try {
      const url = `${baseURL}${path}`;
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      };

      const response = await fetch(url, {
        method: options.method || "GET",
        headers,
        ...(options.body ? { body: JSON.stringify(options.body) } : {}),
      });

      return await response.json();
    } catch (error: any) {
      console.error(`API 请求失败: ${path}`, error);
      return {
        code: -1,
        data: null,
        message: error.message || "网络请求失败",
      };
    }
  }

  /**
   * 获取 TOP50 排名
   */
  async function fetchRankings(date?: string): Promise<ApiResponse<RankingData>> {
    const params = date ? `?snapshot_date=${date}` : "";
    return request<RankingData>(`/api/v1/rankings${params}`);
  }

  /**
   * 获取股票详情
   */
  async function fetchStockDetail(code: string): Promise<ApiResponse<StockDetail>> {
    return request<StockDetail>(`/api/v1/stocks/${code}`);
  }

  /**
   * 获取股票因子数据
   */
  async function fetchStockFactors(code: string): Promise<ApiResponse<any>> {
    return request<any>(`/api/v1/stocks/${code}/factors`);
  }

  /**
   * 获取股票财务数据
   */
  async function fetchStockFinancial(code: string): Promise<ApiResponse<any>> {
    return request<any>(`/api/v1/stocks/${code}/financial`);
  }

  /**
   * 获取股票预测历史
   */
  async function fetchStockPrediction(code: string): Promise<ApiResponse<any>> {
    return request<any>(`/api/v1/stocks/${code}/prediction`);
  }

  /**
   * 获取市场概览
   */
  async function fetchMarketOverview(): Promise<ApiResponse<MarketOverview>> {
    return request<MarketOverview>("/api/v1/market/overview");
  }

  /**
   * 获取因子重要性排名
   */
  async function fetchFactorImportance(): Promise<ApiResponse<FactorImportance[]>> {
    return request<FactorImportance[]>("/api/v1/factors/importance");
  }

  /**
   * 搜索股票
   */
  async function searchStocks(keyword: string): Promise<ApiResponse<any>> {
    return request<any>(`/api/v1/stocks/search?keyword=${encodeURIComponent(keyword)}`);
  }

  return {
    fetchRankings,
    fetchStockDetail,
    fetchStockFactors,
    fetchStockFinancial,
    fetchStockPrediction,
    fetchMarketOverview,
    fetchFactorImportance,
    searchStocks,
  };
}