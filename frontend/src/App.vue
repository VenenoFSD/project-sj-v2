<template>
  <RouterView v-slot="{ Component }">
    <KeepAlive include="BackendView">
      <component :is="Component" />
    </KeepAlive>
  </RouterView>
</template>

<style>
html { scrollbar-gutter: stable; }
</style>
