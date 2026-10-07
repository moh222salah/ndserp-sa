<template>
  <div>
    <router-view :key="locale" />
    <Toast />
  </div>
</template>

<script setup>
import Toast from "@/components/common/Toast.vue"
import { useLocale } from "@/composables/useLocale"

const { locale } = useLocale()
</script>
