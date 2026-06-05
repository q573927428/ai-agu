<template>
  <div class="header-content">
    <div class="header-left">
      <NuxtLink to="/" class="logo">
        <el-icon :size="28"><ElIconCoin /></el-icon>
        <span class="logo-text">A股量化选股平台</span>
      </NuxtLink>
    </div>
    <div class="header-center">
      <el-menu
        mode="horizontal"
        :ellipsis="false"
        router
        :default-active="route.path"
        background-color="transparent"
        text-color="rgba(255,255,255,0.8)"
        active-text-color="#fff"
      >
        <el-menu-item index="/">
          <el-icon><ElIconHomeFilled /></el-icon>
          首页
        </el-menu-item>
        <el-menu-item index="/rankings">
          <el-icon><ElIconTrendCharts /></el-icon>
          TOP50排名
        </el-menu-item>
      </el-menu>
    </div>
    <div class="header-right">
      <div class="market-status">
        <el-tag :type="isMarketOpen ? 'success' : 'info'" size="small" effect="dark">
          {{ isMarketOpen ? "交易中" : "已收盘" }}
        </el-tag>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from "vue-router";
import { ref, computed, onMounted } from "vue";

const route = useRoute();
const currentTime = ref(new Date());

// 判断是否在交易时间（9:30-15:00 周一至周五）
const isMarketOpen = computed(() => {
  const now = currentTime.value;
  const day = now.getDay();
  const hour = now.getHours();
  const minute = now.getMinutes();
  const time = hour * 100 + minute;
  return day >= 1 && day <= 5 && time >= 930 && time <= 1500;
});

// 每分钟更新一次时间（仅在客户端执行）
onMounted(() => {
  setInterval(() => {
    currentTime.value = new Date();
  }, 60000);
});
</script>

<style scoped>
.header-content {
  display: flex;
  align-items: center;
  height: 60px;
  padding: 0 20px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

.header-left {
  display: flex;
  align-items: center;
}

.logo {
  display: flex;
  align-items: center;
  text-decoration: none;
  color: white;
  gap: 8px;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  white-space: nowrap;
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.header-center .el-menu {
  border-bottom: none;
}

.header-center .el-menu-item {
  font-size: 14px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.market-status {
  display: flex;
  align-items: center;
}
</style>