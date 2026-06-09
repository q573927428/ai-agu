<template>
  <div class="chart-container" ref="chartRef" v-loading="klineLoading">
    <v-chart v-if="!klineLoading" :option="chartOption" autoresize />
    <el-empty v-if="!klineLoading && !hasKlineData" description="暂无K线数据" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
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

const props = defineProps<{
  klineData: any[];
  klineLoading: boolean;
  klineEvents?: any[]; // 事件标记数据
  prediction?: {
    predicted_return?: number | null;
    confidence?: number | null;
    predict_date?: string;
  } | null;
}>();

const klineLoading = computed(() => props.klineLoading);
const chartRef = ref<HTMLElement | null>(null);

const hasKlineData = computed(() => props.klineData.length > 0);

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

const chartOption = computed(() => {
  if (!hasKlineData.value) return {};

  const dates = props.klineData.map((d: any) => d.trade_date);
  let ohlcData: any[] = props.klineData.map((d: any) => [
    d.open ?? d.close ?? 0,
    d.close ?? d.open ?? 0,
    d.low ?? Math.min(d.open ?? 0, d.close ?? 0),
    d.high ?? Math.max(d.open ?? 0, d.close ?? 0),
  ]);
  let volumes = props.klineData.map((d: any) => d.volume);

  const closes = props.klineData.map((d: any) => d.close);

  // 预测K线索引（如果有）
  const predIdx = props.prediction?.predicted_return != null && dates.length > 0
    ? dates.length
    : -1;

  // 预测价格（用作虚线）
  const predPrice = props.prediction?.predicted_return != null && closes.length > 0
    ? +(closes[closes.length - 1] * (1 + props.prediction.predicted_return!)).toFixed(2)
    : null;

  // 添加预测K线（灰色实体）
  const pred = props.prediction;
  if (pred && pred.predicted_return != null && dates.length > 0) {
    const lastClose = closes[closes.length - 1];
    const predReturn = pred.predicted_return; // 小数形式，如 0.0367 表示 +3.67%
    const predOpen = lastClose;
    const predClose = +(lastClose * (1 + predReturn)).toFixed(2);
    const predLow = +(lastClose * 0.98).toFixed(2);
    const predHigh = +(predClose * 1.02).toFixed(2);
    const predDate = pred.predict_date ? `预测 ${pred.predict_date}` : "预测次日";

    dates.push(predDate);
    ohlcData.push({
      value: [predOpen, predClose, predLow, predHigh],
      itemStyle: {
        color: "#999999",
        color0: "#999999",
        borderColor: "#999999",
        borderColor0: "#999999",
      },
    });
    volumes.push(0);
  }
  const ma5 = calcMA(5, closes);
  const ma10 = calcMA(10, closes);
  const ma20 = calcMA(20, closes);

  // 过滤出在K线日期范围内的事件
  const events = (props.klineEvents || []).filter((e: any) => {
    return dates.includes(e.ex_date);
  });

  // 事件标记：默认在底部显示 🔀 文字，鼠标经过时 crosshair 自动显示竖线
  const eventMarkLines = events.map((e: any) => ({
    xAxis: e.ex_date,
    label: {
      formatter: `🔀 ${e.description || ""}`,
      position: "start" as const,
      color: "#e6a23c",
      fontSize: 10,
      fontWeight: "bold" as const,
      backgroundColor: "rgba(255,255,255,0.85)",
      padding: [1, 3],
      borderRadius: 2,
    },
    // 不画线，由 axisPointer crosshair 在鼠标经过时自动显示竖线
    lineStyle: { width: 0 },
  }));

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

        // 检查是否有事件
        const dayEvent = events.find((e: any) => e.ex_date === date);
        if (dayEvent) {
          res += `<div style="color:#e6a23c;font-weight:bold;margin-bottom:4px">📢 ${dayEvent.description || "除权除息"}</div>`;
        }

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
      { left: "6%", right: "6%", top: "12%", height: "58%" },
      { left: "6%", right: "6%", top: "75%", height: "18%" },
    ],
    xAxis: [
      {
        type: "category",
        data: dates,
        gridIndex: 0,
        axisLine: { onZero: false },
        axisLabel: {
          rotate: 30,
          fontSize: 10,
          interval: Math.floor(dates.length / 12),
        },
        splitLine: { show: false },
        max: dates.length + 8,
      },
      {
        type: "category",
        data: dates,
        gridIndex: 1,
        axisLine: { onZero: false },
        axisLabel: { show: false },
        splitLine: { show: false },
        max: dates.length + 8,
      },
    ],
    yAxis: [
      {
        type: "value",
        gridIndex: 0,
        position: "right",
        scale: true,
        splitArea: { show: true, areaStyle: { color: ["rgba(250,250,250,0.3)", "rgba(200,200,200,0.1)"] } },
        splitLine: { show: true, lineStyle: { type: "dashed", color: "#eee" } },
        axisLabel: { show: true, fontSize: 10, formatter: (v: number) => v.toFixed(2) },
      },
      {
        type: "value",
        gridIndex: 1,
        position: "right",
        splitNumber: 3,
        axisLabel: { show: true, fontSize: 10, formatter: (v: number) => (v >= 10000 ? `${(v / 10000).toFixed(0)}万` : v) },
        splitLine: { show: false },
      },
    ],
    dataZoom: [
      { type: "inside", xAxisIndex: [0, 1], start: 0, end: 100 },
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
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { type: "dashed", color: "#f56c6c", width: 1 },
          label: {
            show: true,
            position: "end",
            color: "#ffffff",
            fontSize: 11,
            backgroundColor: "#f56c6c",
            padding: [2, 5],
            borderRadius: 3,
            formatter: () => `${closes[closes.length - 1]?.toFixed(2)}`,
          },
          data: [
            { yAxis: closes[closes.length - 1] ?? 0 },
            // 预测价格虚线（灰色）
            ...(predPrice != null
              ? [{
                  yAxis: predPrice,
                  lineStyle: { type: "dashed", color: "#999999", width: 1 },
                  label: {
                    show: true,
                    position: "end",
                    color: "#ffffff",
                    fontSize: 11,
                    backgroundColor: "#888888",
                    padding: [2, 5],
                    borderRadius: 3,
                    formatter: () => `${predPrice}`,
                  },
                }]
              : []),
            // 事件标记（仅底部文字，鼠标经过时 crosshair 自动显示竖线）
            ...eventMarkLines,
          ],
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
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: 558px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.chart-container > * {
  width: 100%;
  height: 100%;
}
@media (max-width: 900px) {
  .chart-container {
    height: 430px;
  }
}
</style>