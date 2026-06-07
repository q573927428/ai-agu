<template>
  <div class="rankings-page">
    <div class="page-header">
      <h1 class="page-title">TOP50 股票排名</h1>
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

    <RankingTable :data="rankings" :loading="loading" @row-click="goToStock" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import dayjs from "dayjs";
import { useApi } from "~/composables/useApi";
import type { RankingItem } from "~/types/api";

const router = useRouter();
const { fetchRankings } = useApi();

const rankings = ref<RankingItem[]>([]);
const loading = ref(true);
const selectedDate = ref<string | null>(null);

onMounted(() => {
  loadData();
});

async function loadData() {
  loading.value = true;
  const dateStr = selectedDate.value ? dayjs(selectedDate.value).format("YYYY-MM-DD") : undefined;
  const result = await fetchRankings(dateStr);
  if (result.data?.rankings) {
    rankings.value = result.data.rankings;
  } else {
    rankings.value = [];
  }
  loading.value = false;
}

function refreshData() {
  selectedDate.value = null;
  loadData();
}

function handleDateChange() {
  loadData();
}

function disabledDate(time: Date) {
  return time > dayjs().toDate();
}

function goToStock(code: string) {
  router.push(`/stock/${code}`);
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  font-size: 24px;
  margin: 0;
  color: var(--el-text-color-primary);
}

.page-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}
</style>