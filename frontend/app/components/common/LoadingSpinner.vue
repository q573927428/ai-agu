<template>
  <div class="loading-container">
    <el-skeleton :rows="rows" :animated="true" />
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ rows?: number }>(), {
  rows: 5,
});
</script>

<style scoped>
.loading-container {
  padding: 20px;
}
</style>