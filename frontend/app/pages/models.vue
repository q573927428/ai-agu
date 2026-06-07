<template>
  <div class="models-page">
    <el-row :gutter="20" class="section">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>模型状态</span>
              <div class="header-right">
              <el-tag :type="modelStatus?.is_active ? 'success' : 'info'" size="small">
                  {{ modelStatus?.is_active ? "模型在线" : "模型离线" }}
                </el-tag>
                <el-tag type="success" size="small" v-if="allModels.length">
                  共 {{ allModels.length }} 个模型记录
                </el-tag>
                <el-button :icon="ElIconRefresh" @click="loadData" :loading="loading" size="small">刷新</el-button>
              </div>
            </div>
          </template>

          <!-- 最新模型概览 -->
          <el-descriptions :column="4" border size="small" class="model-summary">
            <el-descriptions-item label="当前模型版本" label-width="100">
              <el-tag type="primary" size="small">{{ modelStatus?.model_version || "--" }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="最近训练日期" label-width="110">
              {{ modelStatus?.last_train_date || "--" }}
            </el-descriptions-item>
            <el-descriptions-item label="最新 IC" label-width="80">
              <span :class="icClass">{{ modelStatus?.latest_ic != null ? modelStatus?.latest_ic.toFixed(4) : "--" }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="活跃模型数" label-width="100">
              {{ activeModels.length }}
            </el-descriptions-item>
          </el-descriptions>

          <!-- 全部模型记录列表 -->
          <template v-if="allModels.length > 0">
            <div style="margin-top: 20px">
              <div class="sub-title">全部模型记录</div>
              <el-table :data="allModels" stripe size="small" border style="width: 100%">
                <el-table-column type="index" label="#" width="50" />
                <el-table-column prop="model_version" label="模型版本" min-width="180">
                  <template #default="{ row }">
                    <span class="version-cell">{{ row.model_version }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="train_date" label="训练日期" width="120" />
                <el-table-column prop="valid_ic" label="IC" width="120" align="right">
                  <template #default="{ row }">
                    <span :class="icValueClass(row.valid_ic)">
                      {{ row.valid_ic != null ? row.valid_ic.toFixed(4) : "--" }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="num_samples" label="样本数" width="110" align="right">
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
          </template>
          <el-empty v-else-if="!loading" description="暂无模型记录" :image-size="60" style="margin-top: 16px" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useApi } from "~/composables/useApi";
import type { MarketOverview } from "~/types/api";

const { fetchMarketOverview } = useApi();

const loading = ref(true);
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

const allModels = computed(() => {
  return modelStatus.value?.models ?? [];
});

const activeModels = computed(() => {
  return allModels.value.filter((m) => m.is_active);
});

const icClass = computed(() => {
  const ic = modelStatus.value?.latest_ic;
  if (ic == null) return "";
  return ic > 0 ? "ic-positive" : ic < 0 ? "ic-negative" : "";
});

function icValueClass(ic: number | null | undefined): string {
  if (ic == null) return "";
  return ic > 0 ? "ic-positive" : ic < 0 ? "ic-negative" : "";
}

onMounted(() => {
  loadData();
});

async function loadData() {
  loading.value = true;
  const res = await fetchMarketOverview();
  if (res.data) {
    marketOverview.value = res.data;
  }
  loading.value = false;
}
</script>

<style scoped>
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
  gap: 8px;
  align-items: center;
}

.model-summary {
  margin-bottom: 0;
}

.sub-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.version-cell {
  font-family: monospace;
  font-size: 13px;
}

.ic-positive {
  color: #4caf50;
  font-weight: 600;
}

.ic-negative {
  color: #f44336;
  font-weight: 600;
}
</style>