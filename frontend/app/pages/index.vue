<template>
  <div class="dashboard">

    <!-- 市场概览 -->
    <el-row :gutter="20" class="section">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>市场概览</span>
              <div class="header-right">
                <el-tag v-if="isTradingTime()" type="success" size="small" effect="dark">交易中</el-tag>
                <el-tag v-else type="info" size="small">盘后</el-tag>
                <el-tag type="info" size="small">{{ marketDate }}</el-tag>
                <el-tag v-if="nextRefreshSeconds > 0" type="warning" effect="plain">
                  {{ nextRefreshSeconds }}s
                </el-tag>
              </div>
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
              <div class="page-actions">
                <el-date-picker
                  v-model="selectedDate"
                  type="date"
                  placeholder="选择日期查看历史排名"
                  :clearable="true"
                  :disabled-date="disabledDate"
                  @change="handleDateChange"
                />
                <el-button :icon="ElIconRefresh" @click="refreshData" :loading="loading">刷新</el-button>
              </div>
            </div>
          </template>
          <RankingTable :data="topRankings" :loading="loading" @row-click="goToStock" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from "vue";
import { useRouter } from "vue-router";
import dayjs from "dayjs";
import { useApi } from "~/composables/useApi";
import type { RankingItem, MarketOverview } from "~/types/api";

const router = useRouter();
const { fetchRankings, fetchMarketOverview } = useApi();

const selectedDate = ref<Date | null>(null);
const loading = ref(true);
const topRankings = ref<RankingItem[]>([]);
const marketOverview = ref<MarketOverview>({
  market_index: { sh_index: 0, sh_change: 0, sz_index: 0, sz_change: 0, cyb_index: null, cyb_change: null, hs300_index: null, hs300_change: null, zz500_index: null, zz500_change: null, kc50_index: null, kc50_change: null },
  market_stats: { up_count: 0, down_count: 0, flat_count: 0, advance_decline_ratio: 0 },
  top_industries: [],
});

const marketDate = computed(() => {
  return dayjs().locale("zh-cn").format("YYYY年M月D日");
});

// ====== 高频定时刷新逻辑 ======
/** 市场概览刷新间隔（毫秒） */
const MARKET_REFRESH_INTERVAL = 10000; // 10秒
/** 倒计时显示 */
const nextRefreshSeconds = ref(0);
/** 刷新定时器引用 */
let marketTimer: ReturnType<typeof setTimeout> | null = null;
/** 倒计时定时器引用 */
let countdownTimer: ReturnType<typeof setInterval> | null = null;

/**
 * 判断当前是否为 A 股交易时间
 * 交易时段：9:30-11:30, 13:00-15:00（仅工作日）
 */
function isTradingTime(): boolean {
  const now = dayjs();
  const day = now.day();
  // 周末不交易
  if (day === 0 || day === 6) return false;

  const hour = now.hour();
  const minute = now.minute();
  const time = hour * 100 + minute;

  // 上午 9:30 - 11:30
  if (time >= 930 && time < 1130) return true;
  // 下午 13:00 - 15:00
  if (time >= 1300 && time < 1500) return true;

  return false;
}

/**
 * 获取当前动态刷新间隔
 * 交易时段高频 10s，非交易时段低频 60s
 */
function getRefreshInterval(): number {
  return isTradingTime() ? MARKET_REFRESH_INTERVAL : 60000;
}

/**
 * 加载市场概览数据
 */
async function loadMarketOverview() {
  try {
    const res = await fetchMarketOverview();
    if (res.data) {
      marketOverview.value = res.data;
    }
  } catch (e) {
    console.error("获取市场概览失败", e);
  }
}

/**
 * 启动定时刷新
 * 使用两个独立定时器：
 *  - countdownTimer: 每秒更新倒计时（只创建一次）
 *  - marketTimer: setTimeout 链式调度数据请求（动态间隔）
 */
function startAutoRefresh() {
  stopAutoRefresh();

  // 立即刷新一次
  loadMarketOverview();

  // 倒计时指示器：独立运行，每秒更新
  nextRefreshSeconds.value = Math.ceil(getRefreshInterval() / 1000);
  countdownTimer = setInterval(() => {
    if (nextRefreshSeconds.value <= 1) {
      // 下一轮即将刷新，重置倒计时
      nextRefreshSeconds.value = Math.ceil(getRefreshInterval() / 1000);
    } else {
      nextRefreshSeconds.value--;
    }
  }, 1000);

  // 数据刷新：setTimeout 链式调度，每次请求完后用最新间隔调度下次
  const scheduleRefresh = () => {
    loadMarketOverview();
    marketTimer = setTimeout(scheduleRefresh, getRefreshInterval());
  };
  marketTimer = setTimeout(scheduleRefresh, getRefreshInterval());
}

/**
 * 停止定时刷新
 */
function stopAutoRefresh() {
  if (marketTimer) {
    clearTimeout(marketTimer);
    marketTimer = null;
  }
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
}

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

  // 启动市场概览高频定时刷新
  startAutoRefresh();
});

onUnmounted(() => {
  stopAutoRefresh();
});

function disabledDate(time: Date): boolean {
  // 禁止选择未来日期和周末（非交易日）
  const day = time.getDay();
  return time.getTime() > Date.now() || day === 0 || day === 6;
}

function handleDateChange(date: Date | null) {
  if (date) {
    selectedDate.value = date;
    refreshData();
  }
}

async function refreshData() {
  loading.value = true;
  try {
    const res = await fetchRankings(dayjs(selectedDate.value).format("YYYY-MM-DD"));
    if (res.data?.rankings) {
      topRankings.value = res.data.rankings.slice(0, 10);
    }
  } catch (e) {
    console.error("刷新排名失败", e);
  } finally {
    loading.value = false;
  }
}

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

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-actions {
  display: flex;
  align-items: center;
  gap: 8px;
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