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
              <span>TOP10 股票排名（20日预测）</span>
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
              <el-tag type="info" size="small" v-if="modelStatus.models">
                共 {{ modelStatus.models.length }} 个模型
              </el-tag>
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

          <!-- 所有模型记录列表 -->
          <div v-if="modelStatus.models && modelStatus.models.length > 0" style="margin-top: 16px">
            <el-table :data="modelStatus.models" stripe size="small" border style="width: 100%">
              <el-table-column type="index" label="#" width="50" />
              <el-table-column prop="model_version" label="模型版本" min-width="180" />
              <el-table-column prop="train_date" label="训练日期" width="120" />
              <el-table-column prop="valid_ic" label="IC" width="100" align="right">
                <template #default="{ row }">
                  {{ row.valid_ic != null ? row.valid_ic.toFixed(4) : "--" }}
                </template>
              </el-table-column>
              <el-table-column prop="num_samples" label="样本数" width="100" align="right">
                <template #default="{ row }">
                  {{ row.num_samples ?? "--" }}
                </template>
              </el-table-column>
              <el-table-column prop="num_features" label="特征数" width="80" align="right">
                <template #default="{ row }">
                  {{ row.num_features ?? "--" }}
                </template>
              </el-table-column>
              <el-table-column label="状态" width="80" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                    {{ row.is_active ? "活跃" : "非活跃" }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
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

/** 格式化涨跌值 */
function formatChange(val: number | null | undefined): string {
  if (val == null) return "--";
  return val > 0 ? `+${val.toFixed(2)}` : val.toFixed(2);
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
</style>
