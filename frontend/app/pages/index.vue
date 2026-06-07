<template>
  <div class="dashboard">

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
              <div class="value" :class="changeColor(marketOverview.market_index?.sh_change)">{{ formatNumber(marketOverview.market_index?.sh_index) }}</div>
              <div class="change" :class="changeColor(marketOverview.market_index?.sh_change)">
                {{ formatChangePercent(marketOverview.market_index?.sh_change) }}
              </div>
            </div>
            <div class="market-item">
              <div class="label">深证成指</div>
              <div class="value" :class="changeColor(marketOverview.market_index?.sz_change)">{{ formatNumber(marketOverview.market_index?.sz_index) }}</div>
              <div class="change" :class="changeColor(marketOverview.market_index?.sz_change)">
                {{ formatChangePercent(marketOverview.market_index?.sz_change) }}
              </div>
            </div>
            <div class="market-item">
              <div class="label">创业板指</div>
              <div class="value" :class="changeColor(marketOverview.market_index?.cyb_change)">{{ formatNumber(marketOverview.market_index?.cyb_index) }}</div>
              <div class="change" :class="changeColor(marketOverview.market_index?.cyb_change)">
                {{ formatChangePercent(marketOverview.market_index?.cyb_change) }}
              </div>
            </div>
            <div class="market-item">
              <div class="label">沪深300</div>
              <div class="value" :class="changeColor(marketOverview.market_index?.hs300_change)">{{ formatNumber(marketOverview.market_index?.hs300_index) }}</div>
              <div class="change" :class="changeColor(marketOverview.market_index?.hs300_change)">
                {{ formatChangePercent(marketOverview.market_index?.hs300_change) }}
              </div>
            </div>
            <div class="market-item">
              <div class="label">中证500</div>
              <div class="value" :class="changeColor(marketOverview.market_index?.zz500_change)">{{ formatNumber(marketOverview.market_index?.zz500_index) }}</div>
              <div class="change" :class="changeColor(marketOverview.market_index?.zz500_change)">
                {{ formatChangePercent(marketOverview.market_index?.zz500_change) }}
              </div>
            </div>
            <div class="market-item">
              <div class="label">科创50</div>
              <div class="value" :class="changeColor(marketOverview.market_index?.kc50_change)">{{ formatNumber(marketOverview.market_index?.kc50_index) }}</div>
              <div class="change" :class="changeColor(marketOverview.market_index?.kc50_change)">
                {{ formatChangePercent(marketOverview.market_index?.kc50_change) }}
              </div>
            </div>
            <div class="market-item">
              <div class="label">上涨家数</div>
              <div class="value up">{{ marketOverview.market_stats?.up_count ?? "--" }}</div>
            </div>
            <div class="market-item">
              <div class="label">下跌家数</div>
              <div class="value down">{{ marketOverview.market_stats?.down_count ?? "--" }}</div>
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

    <!-- 模型状态（快速入口） -->
    <el-row :gutter="20" class="section">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>模型状态</span>
              <NuxtLink to="/models">
                <el-button text type="primary" size="small">
                  查看详情 <el-icon><ElIconArrowRight /></el-icon>
                </el-button>
              </NuxtLink>
            </div>
          </template>
          <div v-if="activeModels.length > 0" class="model-compact">
            <div class="model-info-row">
              <span class="info-label">当前模型：</span>
              <el-tag type="primary" size="small">{{ modelStatus.model_version || "--" }}</el-tag>
            </div>
            <div class="model-info-row">
              <span class="info-label">活跃模型：</span>
              <span class="info-value">{{ activeModels.length }} 个</span>
            </div>
            <div class="model-info-row">
              <span class="info-label">最新 IC：</span>
              <span class="info-value" :class="modelStatus.latest_ic > 0 ? 'ic-positive' : modelStatus.latest_ic < 0 ? 'ic-negative' : ''">
                {{ modelStatus.latest_ic != null ? modelStatus.latest_ic.toFixed(4) : "--" }}
              </span>
            </div>
            <div class="model-info-row">
              <span class="info-label">最近训练：</span>
              <span class="info-value">{{ modelStatus.last_train_date || "--" }}</span>
            </div>
          </div>
          <el-empty v-else description="暂无模型记录" :image-size="60" style="margin-top: 16px" />
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

const activeModels = computed(() => {
  return (modelStatus.value.models ?? []).filter((m) => m.is_active);
});

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

/** 格式化数字（保留2位小数） */
function formatNumber(val: number | null | undefined): string {
  if (val == null) return "--";
  return val.toFixed(2);
}

/** 根据涨跌幅返回颜色类名：上涨绿色，下跌红色，平盘灰色 */
function changeColor(val: number | null | undefined): string {
  if (val == null) return "";
  if (val > 0) return "up";
  if (val < 0) return "down";
  return "";
}

/** 格式化涨跌幅百分比（字段已是百分比值，如 -0.74 表示 -0.74%） */
function formatChangePercent(change: number | null | undefined): string {
  if (change == null) return "--";
  const prefix = change > 0 ? "+" : "";
  return `${prefix}${change.toFixed(2)}%`;
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
  grid-template-columns: repeat(8, 1fr);
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

.market-item .value.up,
.market-item .change.up {
  color: #4caf50;
}

.market-item .value.down,
.market-item .change.down {
  color: #f44336;
}

.market-item .change {
  font-size: 13px;
  margin-top: 4px;
  font-weight: 500;
}

.model-compact {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  padding: 8px 0;
}

.model-info-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.model-info-row .info-label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.model-info-row .info-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.model-info-row .ic-positive {
  color: #4caf50;
  font-weight: 600;
}

.model-info-row .ic-negative {
  color: #f44336;
  font-weight: 600;
}
</style>
