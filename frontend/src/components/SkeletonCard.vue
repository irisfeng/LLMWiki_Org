<template>
  <el-skeleton :rows="rows" animated :loading="loading">
    <template #default>
      <slot />
    </template>
  </el-skeleton>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ loading: boolean; rows?: number }>(), { rows: 3 })
</script>
