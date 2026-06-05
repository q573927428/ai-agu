<template>
  <div class="footer-content">
    <div class="footer-text">
      <span>A股量化选股平台 v1.0</span>
      <el-divider direction="vertical" />
      <span>数据来源: AkShare</span>
      <el-divider direction="vertical" />
      <span>模型: LightGBM</span>
    </div>
    <div class="footer-disclaimer">
      ⚠️ 本系统仅供研究学习使用，不构成任何投资建议
    </div>
  </div>
</template>

<style scoped>
.footer-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 60px;
  gap: 4px;
  padding: 0 20px;
}

.footer-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.footer-disclaimer {
  font-size: 11px;
  color: var(--el-color-warning);
}
</style>