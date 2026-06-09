<template>
  <div class="stocks-page">
    <div class="page-header">
      <h2 class="page-title">全部股票</h2>
      <div class="page-header-right">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索股票代码或名称"
          clearable
          size="default"
          style="width: 260px"
          @input="onSearchInput"
          @clear="onSearchClear"
          @keyup.enter="doSearch"
        >
          <template #prefix>
            <el-icon><ElIconSearch /></el-icon>
          </template>
        </el-input>
        <div class="page-total">共 {{ total }} 只股票</div>
      </div>
    </div>

    <el-card shadow="hover">
      <el-table :data="stockList" v-loading="loading" stripe @row-click="goToStock" @sort-change="onSortChange" style="cursor: pointer" :default-sort="{ prop: 'pct_chg', order: 'descending' }">
        <el-table-column prop="stock_code" label="股票代码" width="110" sortable="custom" />
        <el-table-column prop="stock_name" label="股票名称" width="140" />
        <el-table-column prop="close_price" label="收盘价" width="120" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.close_price != null">{{ row.close_price.toFixed(2) }}</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="pct_chg" label="涨跌幅" width="110" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.pct_chg != null" :style="{ color: row.pct_chg > 0 ? '#4caf50' : row.pct_chg < 0 ? '#f44336' : '' }">
              {{ row.pct_chg > 0 ? '+' : '' }}{{ row.pct_chg.toFixed(2) }}%
            </span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="pe_ttm" label="市盈率" width="110" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.pe_ttm != null">{{ row.pe_ttm.toFixed(2) }}</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="pb" label="市净率" width="110" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.pb != null">{{ row.pb.toFixed(2) }}</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="ps_ttm" label="市销率" width="110" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.ps_ttm != null">{{ row.ps_ttm.toFixed(2) }}</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="dv_ratio" label="股息率" width="110" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.dv_ratio != null">{{ row.dv_ratio.toFixed(2) }}%</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="turnover_rate" label="换手率" width="110" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.turnover_rate != null">{{ row.turnover_rate.toFixed(2) }}%</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="volume_ratio" label="量比" width="110" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.volume_ratio != null">{{ row.volume_ratio.toFixed(2) }}</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="total_mv" label="总市值" width="120" sortable="custom">
          <template #default="{ row }">
            <span v-if="row.total_mv != null">{{ row.total_mv.toLocaleString() }}</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        <el-table-column prop="exchange" label="交易所" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.exchange === 'SH'" type="danger" size="small">沪</el-tag>
            <el-tag v-else-if="row.exchange === 'SZ'" type="success" size="small">深</el-tag>
            <el-tag v-else type="info" size="small">{{ row.exchange || "--" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="industry" label="行业" width="120">
          <template #default="{ row }">
            {{ row.industry || "--" }}
          </template>
        </el-table-column>
        <el-table-column prop="trade_date" label="最新行情日期" min-width="130" sortable="custom">
          <template #default="{ row }">
            {{ row.trade_date || "--" }}
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
import { Search as ElIconSearch } from "@element-plus/icons-vue";

const router = useRouter();
const { fetchStockList, searchStocks } = useApi();

const loading = ref(false);
const stockList = ref<any[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(15);
const sortBy = ref<string | undefined>("pct_chg");
const sortOrder = ref<string | undefined>("desc");
const searchKeyword = ref("");
let searchTimer: ReturnType<typeof setTimeout> | null = null;

onMounted(() => {
  loadData();
});

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    doSearch();
  }, 300);
}

function onSearchClear() {
  searchKeyword.value = "";
  currentPage.value = 1;
  loadData();
}

async function doSearch() {
  const keyword = searchKeyword.value.trim();
  if (!keyword) {
    onSearchClear();
    return;
  }
  if (searchTimer) {
    clearTimeout(searchTimer);
    searchTimer = null;
  }
  loading.value = true;
  try {
    const res = await searchStocks(keyword);
    if (res.data && res.data.results) {
      stockList.value = res.data.results;
      total.value = res.data.results.length;
    }
  } catch (e) {
    console.error("搜索股票失败", e);
  } finally {
    loading.value = false;
  }
}

async function loadData() {
  if (searchKeyword.value.trim()) {
    doSearch();
    return;
  }
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
    volume_ratio: "volume_ratio",
    ps_ttm: "ps_ttm",
    dv_ratio: "dv_ratio",
    total_mv: "total_mv",
    trade_date: "trade_date",
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

.page-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-size: 22px;
  margin: 0;
  color: var(--el-text-color-primary);
}

.page-total {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.pagination-wrap {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
</style>