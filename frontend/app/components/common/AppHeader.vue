<template>
  <div class="sidebar-container">
    <!-- Logo 区域 -->
    <div class="sidebar-logo" :class="{ collapsed: isCollapse }">
      <NuxtLink to="/" class="logo-link">
        <el-icon :size="28"><ElIconCoin /></el-icon>
        <span v-show="!isCollapse" class="logo-text">A股量化选股平台</span>
      </NuxtLink>
    </div>

    <!-- 菜单区域 -->
    <el-menu
      :default-active="activeMenu"
      :collapse="isCollapse"
      router
      class="sidebar-menu"
      background-color="transparent"
      text-color="var(--el-text-color-primary)"
      active-text-color="var(--el-color-primary)"
    >
      <el-menu-item index="/">
        <el-icon><ElIconHomeFilled /></el-icon>
        <template #title>首页</template>
      </el-menu-item>
      <el-menu-item index="/rankings">
        <el-icon><ElIconTrendCharts /></el-icon>
        <template #title>TOP10排名</template>
      </el-menu-item>
      <el-menu-item index="/models">
        <el-icon><ElIconDataAnalysis /></el-icon>
        <template #title>模型状态</template>
      </el-menu-item>
    </el-menu>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

const props = defineProps<{
  isCollapse: boolean;
}>();

const emit = defineEmits<{
  toggle: [];
}>();

const route = useRoute();

const activeMenu = computed(() => {
  const r = route as any;
  return r.path;
});
</script>

<style scoped>
.sidebar-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.sidebar-logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid var(--el-border-color-light);
  padding: 0 12px;
  transition: padding 0.3s;
}

.sidebar-logo.collapsed {
  padding: 0;
}

.logo-link {
  display: flex;
  align-items: center;
  text-decoration: none;
  color: var(--el-text-color-primary);
  gap: 8px;
  overflow: hidden;
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  overflow-y: auto;
  overflow-x: hidden;
}

.sidebar-menu:not(.el-menu--collapse) {
  width: 220px;
}

.sidebar-menu.el-menu--collapse {
  width: 64px;
}

.el-menu-item {
  font-size: 14px;
  height: 48px;
  line-height: 48px;
}

.el-menu-item.is-active {
  font-weight: 600;
}
</style>