<template>
  <el-table :data="sortedData" stripe style="width: 100%" v-loading="loading" @row-click="handleRowClick" @sort-change="handleSortChange">
    <el-table-column prop="rank" label="排名" width="80" align="center" sortable="custom">
      <template #default="{ row }">
        <el-tag v-if="row.rank <= 3" :type="rankTagType(row.rank)" effect="dark" size="small">
          {{ row.rank }}
        </el-tag>
        <span v-else>{{ row.rank }}</span>
      </template>
    </el-table-column>
    <el-table-column prop="stock_code" label="股票代码" width="120" />
    <el-table-column prop="stock_name" label="股票名称" width="100">
      <template #default="{ row }">
        <el-link type="primary" :underline="false">{{ row.stock_name }}</el-link>
      </template>
    </el-table-column>
    <el-table-column prop="close_price" label="当日收盘价" width="120" align="right" sortable="custom">
      <template #default="{ row }">
        <span v-if="row.close_price != null">{{ row.close_price.toFixed(2) }}</span>
        <span v-else class="no-data">-</span>
      </template>
    </el-table-column>
    <el-table-column prop="pre_close_price" label="前日收盘价" width="120" align="right" sortable="custom">
      <template #default="{ row }">
        <span v-if="row.pre_close_price != null">{{ row.pre_close_price.toFixed(2) }}</span>
        <span v-else class="no-data">-</span>
      </template>
    </el-table-column>
    <!-- <el-table-column prop="predicted_return" label="预测20日涨跌幅" width="160" align="right" sortable="custom">
      <template #default="{ row }">
        <span :style="{ color: getReturnColor(row.predicted_return) }">
          {{ formatPercent(row.predicted_return) }}
        </span>
      </template>
    </el-table-column> -->
    <el-table-column prop="predicted_return_1d" label="预测涨跌" width="160" align="right" sortable="custom">
      <template #default="{ row }">
        <span v-if="row.predicted_return_1d != null" :style="{ color: getReturnColor(row.predicted_return_1d) }">
          {{ formatPercent(row.predicted_return_1d) }}
        </span>
        <span v-else>--</span>
      </template>
    </el-table-column>
    <!-- <el-table-column label="实际20日涨跌幅" width="140" align="right" sortable="custom" prop="actual_return_20d">
      <template #default="{ row }">
        <span v-if="row.actual_return_20d != null" :style="{ color: getReturnColor(row.actual_return_20d) }">
          {{ formatPercent(row.actual_return_20d) }}
        </span>
        <span v-else class="no-data">-</span>
      </template>
    </el-table-column> -->
    <el-table-column label="实际涨跌" width="140" align="right" sortable="custom" prop="actual_return_1d">
      <template #default="{ row }">
        <span v-if="row.actual_return_1d != null" :style="{ color: getReturnColor(row.actual_return_1d) }">
          {{ formatPercent(row.actual_return_1d) }}
        </span>
        <span v-else class="no-data">-</span>
      </template>
    </el-table-column>
    <el-table-column prop="confidence" label="置信度" width="130" align="right" sortable="custom">
      <template #default="{ row }">
        <span v-if="row.confidence != null">{{ formatPercent(row.confidence) }}</span>
        <span v-else>--</span>
      </template>
    </el-table-column>
    <el-table-column prop="industry" label="行业" width="80">
      <template #default="{ row }">
        <el-tag v-if="row.industry" size="small">{{ row.industry }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="market_cap" label="总市值" width="150" align="right" sortable="custom">
      <template #default="{ row }">
        {{ formatMoney(row.market_cap) }}
      </template>
    </el-table-column>
    <el-table-column label="主力因子" min-width="200">
      <template #default="{ row }">
        <div class="factor-tags" v-if="row.top_factors">
          <el-tag
            v-for="(f, idx) in row.top_factors.slice(0, 5)"
            :key="idx"
            size="small"
            type="info"
            effect="plain"
          >
            {{ getFactorDisplayName(f.name) }}
          </el-tag>
        </div>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { RankingItem } from "~/types/api";
import { formatPercent, formatMoney } from "~/utils/format";
import { getFactorDisplayName } from "~/utils/constants";

const props = defineProps<{
  data: RankingItem[];
  loading?: boolean;
}>();

const emit = defineEmits<{
  (e: "row-click", code: string): void;
}>();

const sortBy = ref<string>("");
const sortOrder = ref<"ascending" | "descending">("ascending");

const tableData = computed(() => {
  return props.data.map((item: RankingItem, index: number) => ({
    ...item,
    rank: item.rank || index + 1,
  }));
});

const sortedData = computed(() => {
  if (!sortBy.value) return tableData.value;
  const data = [...tableData.value];
  data.sort((a: any, b: any) => {
    const aVal = a[sortBy.value] ?? 0;
    const bVal = b[sortBy.value] ?? 0;
    if (sortOrder.value === "ascending") {
      return aVal - bVal;
    } else {
      return bVal - aVal;
    }
  });
  return data;
});

function handleSortChange({ prop, order }: { prop: string | null; order: "ascending" | "descending" | null }) {
  sortBy.value = order && prop ? prop : "";
  sortOrder.value = order || "ascending";
}

function handleRowClick(row: any) {
  emit("row-click", row.stock_code);
}

function rankTagType(rank: number): "danger" | "warning" | "success" {
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

.no-data {
  color: #ccc;
}
</style>
