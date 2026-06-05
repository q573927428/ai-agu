<template>
  <el-container class="layout-container">
    <el-header class="app-header">
      <CommonAppHeader />
    </el-header>
    <el-main class="app-main">
      <slot />
    </el-main>
    <el-footer class="app-footer">
      <CommonAppFooter />
    </el-footer>
  </el-container>
</template>

<script setup lang="ts">
</script>

<style scoped>
.layout-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  padding: 0;
  background: var(--el-color-primary);
  color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  position: sticky;
  top: 0;
  z-index: 100;
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