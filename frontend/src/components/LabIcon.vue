<script setup lang="ts">
withDefaults(defineProps<{ name: string; size?: number }>(), { size: 20 })
const paths: Record<string, string> = {
 folder: 'M3 7h7l2 2h9v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Zm0 0V5a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v2',
 file: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Zm0 0v6h6M8 13h8M8 17h5',
 plus: 'M12 5v14M5 12h14',
 rename: 'm15 5 4 4M4 20l4-1L20 7a2.8 2.8 0 0 0-4-4L4 15v5Z',
 copy: 'M8 4h12v14H8V4Zm-4 4H3v13h13v-1',
 cut: 'M8 8 20 20M8 16 20 4M5 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6ZM5 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z',
 paste: 'M9 4H5v17h14V4h-4M9 2h6v4H9V2Zm0 9h6m-6 4h6',
 trash: 'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7',
 grid: 'M3 3h7v7H3V3Zm11 0h7v7h-7V3ZM3 14h7v7H3v-7Zm11 0h7v7h-7v-7Z',
 list: 'M8 5h13M8 12h13M8 19h13M3 5h.01M3 12h.01M3 19h.01',
 up: 'm5 12 7-7 7 7M12 5v15',
 arrow: 'm9 5 7 7-7 7',
 back: 'm15 5-7 7 7 7',
 check: 'm5 12 4 4L19 6',
 reset: 'M3 10a9 9 0 1 1 2 8M3 4v6h6',
 home: 'm3 10 9-7 9 7M5 9v12h5v-7h4v7h5V9',
 image: 'M3 3h18v18H3V3Zm0 14 6-6 4 4 3-3 5 5M15 7h.01',
 desktop: 'M3 3h18v13H3V3Zm5 18h8m-4-5v5',
 download: 'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',
 info: 'M12 11v6m0-10h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
 bulb: 'M9 18h6m-6 3h6M8 14a7 7 0 1 1 8 0l-1 2H9l-1-2Z',
 logout: 'M9 4H3v16h6m6-13 5 5-5 5M8 12h12',
 close: 'm6 6 12 12M6 18 18 6',
 book: 'M12 5C8 2 4 3 2 4v16c4-2 7-1 10 1m0-16c4-3 8-2 10-1v16c-4-2-7-1-10 1V5Z',
}
</script>
<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[name] ?? paths.file" /></svg>
</template>
