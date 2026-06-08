<template>
  <div class="stock-detail">
    <div class="page-header">
      <el-button :icon="ElIconArrowLeft" @click="goBack" text></el-button>
      <h1 class="page-title" v-if="stockBasic">
        {{ stockBasic.stock_name }} ({{ stockBasic.stock_code }})
        <el-tag size="small" :type="marketTagType" class="market-tag">{{ stockBasic.market }}</el-tag>
      </h1>
    </div>

    <el-skeleton :loading="loading" animated :rows="6">
      <div class="detail-layout">
        <!-- 左侧：信息卡片 -->
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
                <span class="info-label">地区</span>
                <span class="info-value">{{ stockBasic.area || "--" }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">交易所</span>
                <span class="info-value">{{ stockBasic.market || "--" }}</span>
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
          </el-card>
          <el-card shadow="hover" class="section info-card">
            <template #header>
              <span class="card-title">预测信息</span>
            </template>
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
                  <el-radio-button :value="750">近3年</el-radio-button>
                  <el-radio-button :value="3000">全部</el-radio-button>
                </el-radio-group>
              </div>
            </template>
            <KlineChart :kline-data="klineData" :kline-loading="klineLoading" />
          </el-card>
        </div>
      </div>
    </el-skeleton>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useApi } from "~/composables/useApi";
import { formatPercent, formatConfidence, formatChange, getChangeColor } from "~/utils/format";
import type { StockBasic, StockDaily, StockPrediction } from "~/types/api";

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

const stockCode = computed(() => (route as any).params.code as string);

const marketTagType = computed(() => {
  if (stockBasic.value?.market === "SH") return "danger";
  if (stockBasic.value?.market === "SZ") return "success";
  return "info";
});

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
}
</style>