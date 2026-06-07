<template>
  <div class="stock-detail">
    <div class="page-header">
      <h1 class="page-title" v-if="stockBasic">
        {{ stockBasic.stock_name }} ({{ stockBasic.stock_code }})
        <el-tag size="small" :type="marketTagType" class="market-tag">{{ stockBasic.market }}</el-tag>
      </h1>
      <el-button :icon="ElIconArrowLeft" @click="goBack" text>返回</el-button>
    </div>

    <el-skeleton :loading="loading" animated :rows="6">
      <div class="detail-layout">
        <!-- 左侧：信息卡片（合并为一张紧凑卡片） -->
        <div class="left-panel">
          <el-card shadow="hover" class="section info-card">
            <template #header>
              <span class="card-title">股票信息</span>
            </template>
            <div class="info-grid" v-if="stockBasic">
              <div class="info-row">
                <span class="info-label">行业</span>
                <span class="info-value">{{ stockBasic.industry || "--" }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">地区 / 交易所</span>
                <span class="info-value">{{ stockBasic.area || "--" }} / {{ stockBasic.market || "--" }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">上市日期</span>
                <span class="info-value">{{ stockBasic.list_date || "--" }}</span>
              </div>
            </div>
            <el-divider style="margin: 10px 0" />
            <div class="info-grid" v-if="stockDaily">
              <div class="info-row">
                <span class="info-label">开</span>
                <span class="info-value">{{ stockDaily.open ?? "--" }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">高</span>
                <span class="info-value">{{ stockDaily.high ?? "--" }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">低</span>
                <span class="info-value">{{ stockDaily.low ?? "--" }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">收</span>
                <span class="info-value">
                  {{ stockDaily.close ?? "--" }}
                </span>
              </div>
              <div class="info-row">
                <span class="info-label">涨跌幅</span>
                <span class="info-value">
                  <span :style="{ color: getChangeColor(stockDaily.pct_chg), marginLeft: '6px' }">
                    {{ formatChange(stockDaily.pct_chg) }}
                  </span>
                </span>
              </div>

              <div class="info-row">
                <span class="info-label">市盈率</span>
                <span class="info-value">{{ stockDaily.pe_ttm ?? "--" }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">市净率</span>
                <span class="info-value">{{ stockDaily.pb ?? "--" }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">换手率</span>
                <span class="info-value">{{ stockDaily.turnover_rate ?? "--" }}%</span>
              </div>
            </div>
            <el-divider style="margin: 10px 0" v-if="stockPrediction" />
            <div class="info-grid" v-if="stockPrediction">
              <div class="info-row">
                <span class="info-label">预测日期</span>
                <span class="info-value">{{ stockPrediction.predict_date }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">预测涨跌幅（20日）</span>
                <span class="info-value" :style="{ color: getReturnColor(stockPrediction.predicted_return) }">
                  {{ formatPercent(stockPrediction.predicted_return) }}
                </span>
              </div>
              <div class="info-row">
                <span class="info-label">预测涨跌幅（次日）</span>
                <span class="info-value" :style="{ color: getReturnColor(stockPrediction.predicted_return_1d) }">
                  {{ formatPercent(stockPrediction.predicted_return_1d) }}
                </span>
              </div>
              <div class="info-row">
                <span class="info-label">置信度</span>
                <span class="info-value">{{ formatConfidence(stockPrediction.confidence) }}</span>
              </div>
            </div>
          </el-card>
        </div>

        <!-- 右侧：K线图 -->
        <div class="right-panel">
          <el-card shadow="hover" class="section chart-card">
            <template #header>
              <div class="chart-header">
                <span class="card-title">日K线图</span>
                <el-radio-group v-model="klineLimit" size="small" @change="fetchKlineData">
                  <el-radio-button :value="60">近3月</el-radio-button>
                  <el-radio-button :value="120">近6月</el-radio-button>
                  <el-radio-button :value="250">近1年</el-radio-button>
                </el-radio-group>
              </div>
            </template>
            <div class="chart-container" ref="chartRef" v-loading="klineLoading">
              <v-chart v-if="!klineLoading" :option="chartOption" autoresize />
              <el-empty v-if="!klineLoading && !hasKlineData" description="暂无K线数据" />
            </div>
          </el-card>
        </div>
      </div>
    </el-skeleton>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useApi } from "~/composables/useApi";
import { formatPercent, formatConfidence, formatChange, getChangeColor } from "~/utils/format";
import type { StockBasic, StockDaily, StockPrediction } from "~/types/api";

// ECharts
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { CandlestickChart, BarChart, LineChart } from "echarts/charts";
import {
  TooltipComponent,
  GridComponent,
  DataZoomComponent,
  LegendComponent,
  MarkLineComponent,
} from "echarts/components";

use([CanvasRenderer, CandlestickChart, BarChart, LineChart, TooltipComponent, GridComponent, DataZoomComponent, LegendComponent, MarkLineComponent]);

const route = useRoute();
const router = useRouter();
const { fetchStockDetail, fetchStockKline } = useApi();

const loading = ref(true);
const stockBasic = ref<StockBasic | null>(null);
const stockDaily = ref<StockDaily | null>(null);
const stockPrediction = ref<StockPrediction | null>(null);

// K线图数据
const klineLoading = ref(false);
const klineLimit = ref(120);
const klineData = ref<any[]>([]);
const chartRef = ref<HTMLElement | null>(null);

const stockCode = computed(() => (route as any).params.code as string);

const marketTagType = computed(() => {
  if (stockBasic.value?.market === "SH") return "danger";
  if (stockBasic.value?.market === "SZ") return "success";
  return "info";
});

const hasKlineData = computed(() => klineData.value.length > 0);

// ECharts K线图配置
const chartOption = computed(() => {
  if (!hasKlineData.value) return {};

  const dates = klineData.value.map((d) => d.trade_date);
  const ohlcData = klineData.value.map((d) => [
    d.open ?? d.close ?? 0,
    d.close ?? d.open ?? 0,
    d.low ?? Math.min(d.open ?? 0, d.close ?? 0),
    d.high ?? Math.max(d.open ?? 0, d.close ?? 0),
  ]);
  const volumes = klineData.value.map((d) => d.volume);

  // 计算MA5/MA10/MA20
  const closes = klineData.value.map((d) => d.close);
  const ma5 = calcMA(5, closes);
  const ma10 = calcMA(10, closes);
  const ma20 = calcMA(20, closes);

  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      backgroundColor: "rgba(255, 255, 255, 0.9)",
      borderColor: "#ddd",
      borderWidth: 1,
      textStyle: { color: "#333", fontSize: 12 },
      formatter: function (params: any[]) {
        const date = params[0].axisValue;
        const candle = params.find((p: any) => p.seriesName === "K线");
        const vol = params.find((p: any) => p.seriesName === "成交量");
        const ma5v = params.find((p: any) => p.seriesName === "MA5");
        const ma10v = params.find((p: any) => p.seriesName === "MA10");
        const ma20v = params.find((p: any) => p.seriesName === "MA20");
        let res = `<div style="font-weight:bold;margin-bottom:4px">${date}</div>`;
        if (candle) {
          const d = candle.data;
          res += `开盘: ${d[1]}<br/>收盘: ${d[2]}<br/>最低: ${d[3]}<br/>最高: ${d[4]}<br/>`;
        }
        if (ma5v) res += `MA5: ${ma5v.value?.toFixed(2) || "--"}<br/>`;
        if (ma10v) res += `MA10: ${ma10v.value?.toFixed(2) || "--"}<br/>`;
        if (ma20v) res += `MA20: ${ma20v.value?.toFixed(2) || "--"}<br/>`;
        if (vol) res += `成交量: ${(vol.value / 10000).toFixed(0)}万股`;
        return res;
      },
    },
    legend: {
      top: 5,
      data: ["K线", "MA5", "MA10", "MA20", "成交量"],
      textStyle: { fontSize: 11 },
    },
    grid: [
      { left: "6%", right: "4%", top: "12%", height: "58%" },
      { left: "6%", right: "4%", top: "75%", height: "18%" },
    ],
    xAxis: [
      {
        type: "category",
        data: dates,
        gridIndex: 0,
        axisLine: { onZero: false },
        axisLabel: { rotate: 30, fontSize: 10 },
        splitLine: { show: false },
        min: "dataMin",
        max: "dataMax",
      },
      {
        type: "category",
        data: dates,
        gridIndex: 1,
        axisLine: { onZero: false },
        axisLabel: { show: false },
        splitLine: { show: false },
      },
    ],
    yAxis: [
      {
        type: "value",
        gridIndex: 0,
        scale: true,
        splitArea: { show: true, areaStyle: { color: ["rgba(250,250,250,0.3)", "rgba(200,200,200,0.1)"] } },
        splitLine: { show: true, lineStyle: { type: "dashed", color: "#eee" } },
      },
      {
        type: "value",
        gridIndex: 1,
        splitNumber: 3,
        axisLabel: { show: true, fontSize: 10, formatter: (v: number) => (v >= 10000 ? `${(v / 10000).toFixed(0)}万` : v) },
        splitLine: { show: false },
      },
    ],
    dataZoom: [
      {
        type: "inside",
        xAxisIndex: [0, 1],
        start: 0,
        end: 100,
      },
      {
        show: true,
        type: "slider",
        xAxisIndex: [0, 1],
        top: "94%",
        height: 16,
        borderColor: "#ddd",
        backgroundColor: "rgba(47,69,84,0.1)",
        fillerColor: "rgba(167,183,204,0.4)",
        handleStyle: { borderColor: "#aaa" },
        start: 0,
        end: 100,
      },
    ],
    series: [
      {
        name: "K线",
        type: "candlestick",
        data: ohlcData,
        barWidth: "60%",
        itemStyle: {
          color: "#ef232a",
          color0: "#14b143",
          borderColor: "#ef232a",
          borderColor0: "#14b143",
        },
      },
      {
        name: "MA5",
        type: "line",
        data: ma5,
        smooth: true,
        symbol: "none",
        lineStyle: { width: 1, color: "#7b7beb" },
      },
      {
        name: "MA10",
        type: "line",
        data: ma10,
        smooth: true,
        symbol: "none",
        lineStyle: { width: 1, color: "#f7b731" },
      },
      {
        name: "MA20",
        type: "line",
        data: ma20,
        smooth: true,
        symbol: "none",
        lineStyle: { width: 1, color: "#e056a0" },
      },
      {
        name: "成交量",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes.map((vol: number, idx: number) => ({
          value: vol,
          itemStyle: {
            color: (ohlcData[idx]?.[0] ?? 0) > (ohlcData[idx]?.[1] ?? 0) ? "#14b143" : "#ef232a",
          },
        })),
      },
    ],
  };
});

/** 计算移动平均线 */
function calcMA(period: number, data: number[]): (number | null)[] {
  return data.map((_, idx) => {
    if (idx < period - 1) return null;
    let sum = 0;
    for (let i = 0; i < period; i++) {
      sum += data[idx - i] ?? 0;
    }
    return +(sum / period).toFixed(2);
  });
}

async function fetchKlineData() {
  klineLoading.value = true;
  const result = await fetchStockKline(stockCode.value, klineLimit.value);
  if (result.data) {
    klineData.value = result.data.kline || [];
  }
  klineLoading.value = false;
}

onMounted(async () => {
  loading.value = true;
  const result = await fetchStockDetail(stockCode.value);
  if (result.data) {
    stockBasic.value = result.data.basic;
    stockDaily.value = result.data.latest_daily;
    stockPrediction.value = result.data.latest_prediction;
  }
  loading.value = false;

  // 加载K线数据
  await fetchKlineData();
});

function getReturnColor(value: number | null | undefined): string {
  if (!value) return "";
  if (value > 0.05) return "var(--el-color-danger)";
  if (value > 0) return "#e6a23c";
  return "var(--el-color-success)";
}

function goBack() {
  router.back();
}
</script>

<style scoped>

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.page-title {
  font-size: 24px;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.market-tag {
  font-size: 12px;
}

.detail-layout {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

.left-panel {
  width: 340px;
  flex-shrink: 0;
}

.right-panel {
  flex: 1;
  min-width: 0;
}

.section {
  margin-bottom: 16px;
}

.card-title {
  font-weight: 600;
}

.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chart-container {
  width: 100%;
  height: 520px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chart-container > * {
  width: 100%;
  height: 100%;
}

/* 信息卡片紧凑样式 */
.info-card {
  font-size: 13px;
}

.info-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-label {
  color: #909399;
  white-space: nowrap;
}

.info-value {
  color: #303133;
  text-align: right;
  font-weight: 500;
}

@media (max-width: 900px) {
  .detail-layout {
    flex-direction: column;
  }

  .left-panel {
    width: 100%;
  }

  .chart-container {
    height: 400px;
  }
}
</style>