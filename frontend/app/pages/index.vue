<template>
  <div class="dashboard">
    <h1 class="page-title">首页仪表盘</h1>

    <!-- 市场概览 -->
    <el-row :gutter="20" class="section">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>市场概览</span>
              <el-tag type="info" size="small">{{ marketDate }}</el-tag>
            </div>
          </template>
          <div class="market-grid">
            <div class="market-item">
              <div class="label">上证指数</div>
              <div class="value">{{ marketOverview.market_index?.sh_index ?? "--" }}</div>
            </div>
            <div class="market-item">
              <div class="label">深证成指</div>
              <div class="value">{{ marketOverview.market_index?.sz_index ?? "--" }}</div>
            </div>
            <div class="market-item">
              <div class="label">创业板指</div>
              <div class="value">{{ marketOverview.market_index?.cyb_index ?? "--" }}</div>
            </div>
            <div class="market-item">
              <div class="label">沪深300</div>
              <div class="value">{{ marketOverview.market_index?.hs300_index ?? "--" }}</div>
            </div>
            <div class="market-item">
              <div class="label">中证500</div>
              <div class="value">{{ marketOverview.market_index?.zz500_index ?? "--" }}</div>
            </div>
            <div class="market-item">
              <div class="label">科创50</div>
              <div class="value">{{ marketOverview.market_index?.kc50_index ?? "--" }}</div>
            </div>
            <div class="market-item">
              <div class="label">上涨家数</div>
              <div class="value">{{ marketOverview.market_stats?.up_count ?? "--" }}</div>
            </div>
            <div class="market-item">
              <div class="label">下跌家数</div>
              <div class="value">{{ marketOverview.market_stats?.down_count ?? "--" }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- TOP10 预览 -->
    <el-row :gutter="20" class="section">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>TOP10 股票排名</span>
              <NuxtLink to="/rankings">
                <el-button text type="primary" size="small">
                  查看全部 <el-icon><ElIconArrowRight /></el-icon>
                </el-button>
              </NuxtLink>
            </div>
          </template>
          <RankingTable :data="topRankings" :loading="loading" @row-click="goToStock" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 模型状态 -->
    <el-row :gutter="20" class="section">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>模型状态</span>
            </div>
          </template>
          <el-descriptions :column="4" border>
            <el-descriptions-item label="模型版本">{{ modelStatus.model_version || "--" }}</el-descriptions-item>
            <el-descriptions-item label="最近训练">{{ modelStatus.last_train_date || "--" }}</el-descriptions-item>
            <el-descriptions-item label="最新 IC">{{ modelStatus.latest_ic != null ? modelStatus.latest_ic.toFixed(4) : "--" }}</el-descriptions-item>
            <el-descriptions-item label="模型状态">
              <el-tag :type="modelStatus.is_active ? 'success' : 'info'" size="small">
                {{ modelStatus.is_active ? "活跃" : "未训练" }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import dayjs from "dayjs";
import { useApi } from "~/composables/useApi";
import type { RankingItem, MarketOverview } from "~/types/api";

const router = useRouter();
const { fetchRankings, fetchMarketOverview } = useApi();

const loading = ref(true);
const topRankings = ref<RankingItem[]>([]);
const marketOverview = ref<MarketOverview>({
  market_index: { sh_index: 0, sh_change: 0, sz_index: 0, sz_change: 0, cyb_index: null, cyb_change: null, hs300_index: null, hs300_change: null, zz500_index: null, zz500_change: null, kc50_index: null, kc50_change: null },
  market_stats: { up_count: 0, down_count: 0, flat_count: 0, advance_decline_ratio: 0 },
  top_industries: [],
  model_status: {
    model_version: "",
    last_train_date: null,
    latest_ic: 0,
    is_active: false,
  },
});

const modelStatus = computed(() => marketOverview.value.model_status);

const marketDate = computed(() => {
  return dayjs().locale("zh-cn").format("YYYY年M月D日");
});

onMounted(async () => {
  loading.value = true;

  // 并发请求排名和市场概览
  const [rankingRes, overviewRes] = await Promise.all([
    fetchRankings(),
    fetchMarketOverview(),
  ]);

  if (rankingRes.data?.rankings) {
    topRankings.value = rankingRes.data.rankings.slice(0, 10);
  }

  if (overviewRes.data) {
    marketOverview.value = overviewRes.data;
  }

  loading.value = false;
});

function goToStock(code: string) {
  router.push(`/stock/${code}`);
}
</script>

<style scoped>
.page-title {
  font-size: 24px;
  margin-bottom: 20px;
  color: var(--el-text-color-primary);
}

.section {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.market-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  text-align: center;
}

.market-item {
  padding: 16px;
  border-radius: 8px;
  background: var(--el-color-info-light-9);
}

.market-item .label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.market-item .value {
  font-size: 24px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
</style>