<template>
  <div class="stock-detail">
    <div class="page-header">
      <h1 class="page-title" v-if="stockBasic">
        {{ stockBasic.stock_name }} ({{ stockBasic.stock_code }})
        <el-tag size="small" :type="marketTagType" class="market-tag">{{ stockBasic.market }}</el-tag>
      </h1>
      <el-button :icon="ElIconArrowLeft" @click="goBack" text>返回</el-button>
    </div>

    <el-skeleton :loading="loading" animated :rows="10">
      <!-- 基础信息 -->
      <el-card shadow="hover" class="section">
        <template #header>
          <span class="card-title">基础信息</span>
        </template>
        <el-descriptions :column="4" border v-if="stockBasic">
          <el-descriptions-item label="行业">{{ stockBasic.industry || "--" }}</el-descriptions-item>
          <el-descriptions-item label="地区">{{ stockBasic.area || "--" }}</el-descriptions-item>
          <el-descriptions-item label="上市日期">{{ stockBasic.list_date || "--" }}</el-descriptions-item>
          <el-descriptions-item label="交易所">{{ stockBasic.market || "--" }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 最新行情 -->
      <el-card shadow="hover" class="section" v-if="stockDaily">
        <template #header>
          <span class="card-title">最新行情</span>
        </template>
        <el-descriptions :column="4" border>
          <el-descriptions-item label="收盘价">{{ stockDaily.close ?? "--" }}</el-descriptions-item>
          <el-descriptions-item label="市盈率TTM">{{ stockDaily.pe_ttm ?? "--" }}</el-descriptions-item>
          <el-descriptions-item label="市净率">{{ stockDaily.pb ?? "--" }}</el-descriptions-item>
          <el-descriptions-item label="换手率">{{ stockDaily.turnover_rate ?? "--" }}%</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 最新预测 -->
      <el-card shadow="hover" class="section" v-if="stockPrediction">
        <template #header>
          <span class="card-title">最新预测</span>
        </template>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="预测日期">{{ stockPrediction.predict_date }}</el-descriptions-item>
          <el-descriptions-item label="预测收益率">
            <span :style="{ color: getReturnColor(stockPrediction.predicted_return) }">
              {{ formatPercent(stockPrediction.predicted_return) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="置信度">
            {{ formatConfidence(stockPrediction.confidence) }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-skeleton>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useApi } from "~/composables/useApi";
import { formatPercent, formatConfidence } from "~/utils/format";
import type { StockBasic, StockDaily, StockPrediction } from "~/types/api";

const route = useRoute();
const router = useRouter();
const { fetchStockDetail } = useApi();

const loading = ref(true);
const stockBasic = ref<StockBasic | null>(null);
const stockDaily = ref<StockDaily | null>(null);
const stockPrediction = ref<StockPrediction | null>(null);

const stockCode = computed(() => (route as any).params.code as string);

const marketTagType = computed(() => {
  if (stockBasic.value?.market === "SH") return "danger";
  if (stockBasic.value?.market === "SZ") return "success";
  return "info";
});

onMounted(async () => {
  loading.value = true;
  const result = await fetchStockDetail(stockCode.value);
  if (result.data) {
    stockBasic.value = result.data.basic;
    stockDaily.value = result.data.latest_daily;
    stockPrediction.value = result.data.latest_prediction;
  }
  loading.value = false;
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

.section {
  margin-bottom: 20px;
}

.card-title {
  font-weight: 600;
}
</style>