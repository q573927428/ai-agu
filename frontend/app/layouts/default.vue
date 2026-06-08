<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="app-aside">
      <CommonAppHeader :is-collapse="isCollapse" @toggle="isCollapse = !isCollapse" />
    </el-aside>

    <!-- 右侧主体区域 -->
    <el-container class="main-container">
      <el-header class="app-header">
        <div class="header-left">
          <el-button
            :icon="isCollapse ? ElIconExpand : ElIconFold"
            text
            @click="isCollapse = !isCollapse"
            class="collapse-btn"
          />
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentTitle">{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <div class="market-status">
            <el-tag :type="isMarketOpen ? 'success' : 'info'" size="small" effect="dark">
              {{ isMarketOpen ? "交易中" : "已收盘" }}
            </el-tag>
          </div>
        </div>
      </el-header>
      <el-main class="app-main">
        <slot />
      </el-main>
      <el-footer class="app-footer">
        <CommonAppFooter />
      </el-footer>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { useRoute } from "vue-router";
import dayjs from "dayjs";
import { Expand, Fold } from "@element-plus/icons-vue";

const route = useRoute();
const isCollapse = ref(false);

// 获取当前页面标题（从路由 meta 或 path 推断）
const currentTitle = computed(() => {
  const r = route as any;
  const metaTitle = r.meta?.title;
  if (metaTitle) return metaTitle;
  if (r.path === "/") return "首页仪表盘";
  if (r.path === "/rankings") return "TOP10排名";
  if (r.path === "/models") return "模型状态";
  if (r.path.startsWith("/stock/")) return "股票详情";
  return "";
});

// 判断是否在交易时间（9:30-15:00 周一至周五）
const isMarketOpen = computed(() => {
  const now = dayjs();
  const day = now.day();
  const hour = now.hour();
  const minute = now.minute();
  const time = hour * 100 + minute;
  return day >= 1 && day <= 5 && time >= 930 && time <= 1500;
});
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
  display: flex;
}

.app-aside {
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
  transition: width 0.3s;
  overflow: hidden;
  height: 100vh;
  position: sticky;
  top: 0;
  z-index: 200;
}

.main-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  flex: 1;
}

.app-header {
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid var(--el-border-color-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.collapse-btn {
  font-size: 18px;
}

.app-main {
  flex: 1;
  background: var(--el-bg-color-page);
  padding: 20px;
}

.app-footer {
  padding: 0;
  background: var(--el-color-primary-light-9);
}
</style>