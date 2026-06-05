<template>
  <el-table :data="tableData" stripe style="width: 100%" v-loading="loading" @row-click="handleRowClick">
    <el-table-column prop="rank" label="排名" width="80" align="center">
      <template #default="{ row }">
        <el-tag v-if="row.rank <= 3" :type="rankTagType(row.rank)" effect="dark" size="small">
          {{ row.rank }}
        </el-tag>
        <span v-else>{{ row.rank }}</span>
      </template>
    </el-table-column>
    <el-table-column prop="stock_code" label="股票代码" width="120" />
    <el-table-column prop="stock_name" label="股票名称" min-width="150">
      <template #default="{ row }">
        <el-link type="primary" :underline="false">{{ row.stock_name }}</el-link>
      </template>
    </el-table-column>
    <el-table-column prop="predicted_return" label="预测收益率" width="140" align="right">
      <template #default="{ row }">
        <span :style="{ color: getReturnColor(row.predicted_return) }">
          {{ formatPercent(row.predicted_return) }}
        </span>
      </template>
    </el-table-column>
    <el-table-column prop="industry" label="行业" width="120">
      <template #default="{ row }">
        <el-tag v-if="row.industry" size="small">{{ row.industry }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="market_cap" label="总市值" width="140" align="right">
      <template #default="{ row }">
        {{ formatMoney(row.market_cap) }}
      </template>
    </el-table-column>
    <el-table-column label="主力因子" min-width="200">
      <template #default="{ row }">
        <div class="factor-tags" v-if="row.top_factors">
          <el-tag
            v-for="(f, idx) in row.top_factors.slice(0, 3)"
            :key="idx"
            size="small"
            type="info"
            effect="plain"
          >
            {{ f.name }}
          </el-tag>
        </div>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import type { RankingItem } from "~/types/api";
import { formatPercent, formatMoney } from "~/utils/format";

const props = defineProps<{
  data: RankingItem[];
  loading?: boolean;
}>();

const emit = defineEmits<{
  (e: "row-click", code: string): void;
}>();

const tableData = computed(() => {
  return props.data.map((item, index) => ({
    ...item,
    rank: item.rank || index + 1,
  }));
});

function handleRowClick(row: any) {
  emit("row-click", row.stock_code);
}

function rankTagType(rank: number): string {
  if (rank === 1) return "danger";
  if (rank === 2) return "warning";
  return "success";
}

function getReturnColor(value: number): string {
  if (value > 0.05) return "var(--el-color-danger)";
  if (value > 0) return "#e6a23c";
  if (value > -0.05) return "var(--el-color-success)";
  return "var(--el-color-info)";
}
</script>

<style scoped>
.factor-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.el-table {
  cursor: pointer;
}
</style>