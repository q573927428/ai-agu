<template>
  <div class="stocks-page">
    <div class="page-header">
      <h2 class="page-title">全部股票</h2>
      <div class="page-total">共 {{ total }} 只股票</div>
    </div>

    <el-card shadow="hover">
      <el-table :data="stockList" v-loading="loading" stripe @row-click="goToStock" @sort-change="onSortChange" style="cursor: pointer" :default-sort="{ prop: 'pct_chg', order: 'descending' }">
        <el-table-column prop="stock_code" label="股票代码" width="110" sortable="custom" />
        <el-table-column prop="stock_name" label="股票名称" width="140" />
        <el-table-column prop="close_price" label="收盘价" width="100" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.close_price != null">{{ row.close_price.toFixed(2) }}</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="pct_chg" label="涨跌幅" width="100" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.pct_chg != null" :style="{ color: row.pct_chg > 0 ? '#4caf50' : row.pct_chg < 0 ? '#f44336' : '' }">
              {{ row.pct_chg > 0 ? '+' : '' }}{{ row.pct_chg.toFixed(2) }}%
            </span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="pe_ttm" label="市盈率" width="100" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.pe_ttm != null">{{ row.pe_ttm.toFixed(2) }}</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="pb" label="市净率" width="100" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.pb != null">{{ row.pb.toFixed(2) }}</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="turnover_rate" label="换手率" width="100" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.turnover_rate != null">{{ row.turnover_rate.toFixed(2) }}%</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="exchange" label="交易所" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.exchange === 'SH'" type="danger" size="small">沪</el-tag>
            <el-tag v-else-if="row.exchange === 'SZ'" type="success" size="small">深</el-tag>
            <el-tag v-else type="info" size="small">{{ row.exchange || "--" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="industry" label="行业" min-width="120">
          <template #default="{ row }">
            {{ row.industry || "--" }}
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="loadData"
          @size-change="onSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useApi } from "~/composables/useApi";

const router = useRouter();
const { fetchStockList } = useApi();

const loading = ref(false);
const stockList = ref<any[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(15);
const sortBy = ref<string | undefined>("pct_chg");
const sortOrder = ref<string | undefined>("desc");

onMounted(() => {
  loadData();
});

async function loadData() {
  loading.value = true;
  try {
    const res = await fetchStockList(currentPage.value, pageSize.value, sortBy.value, sortOrder.value);
    if (res.data) {
      stockList.value = res.data.items || [];
      total.value = res.data.total || 0;
    }
  } catch (e) {
    console.error("获取股票列表失败", e);
  } finally {
    loading.value = false;
  }
}

function onSizeChange() {
  currentPage.value = 1;
  loadData();
}

function onSortChange(data: { prop: string | null; order: string | null }) {
  const { prop, order } = data;
  // 排序字段映射：前端 prop 名 -> 后端 sort_by 参数
  const sortFieldMap: Record<string, string> = {
    stock_code: "stock_code",
    close_price: "close_price",
    pct_chg: "pct_chg",
    pe_ttm: "pe_ttm",
    pb: "pb",
    turnover_rate: "turnover_rate",
  };

  if (prop && order && sortFieldMap[prop]) {
    sortBy.value = sortFieldMap[prop];
    sortOrder.value = order === "ascending" ? "asc" : "desc";
  } else {
    sortBy.value = undefined;
    sortOrder.value = undefined;
  }

  currentPage.value = 1;
  loadData();
}

function goToStock(row: any) {
  router.push(`/stock/${row.stock_code}`);
}
</script>

<style scoped>
.stocks-page {
  padding: 0;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.page-title {
  font-size: 22px;
  margin: 0;
  color: var(--el-text-color-primary);
}

.page-total {
  font-size: 14px;
  color: var(--el-text-color-secondary);
}

.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
</style>