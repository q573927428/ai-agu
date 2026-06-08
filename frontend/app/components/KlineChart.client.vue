<template>
  <div class="chart-container" ref="chartRef" v-loading="klineLoading">
    <v-chart v-if="!klineLoading" :option="chartOption" autoresize />
    <el-empty v-if="!klineLoading && !hasKlineData" description="暂无K线数据" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
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
  const ohlcData = props.klineData.map((d: any) => [
    d.open ?? d.close ?? 0,
    d.close ?? d.open ?? 0,
    d.low ?? Math.min(d.open ?? 0, d.close ?? 0),
    d.high ?? Math.max(d.open ?? 0, d.close ?? 0),
  ]);
  const volumes = props.klineData.map((d: any) => d.volume);

  const closes = props.klineData.map((d: any) => d.close);
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
  height: 520px;
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
    height: 400px;
  }
}
</style>