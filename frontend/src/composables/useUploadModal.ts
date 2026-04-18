import { ref } from 'vue'

export const isUploadModalOpen = ref(false)

type UploadDoneHandler = () => void
const doneHandlers = new Set<UploadDoneHandler>()

export function openUploadModal() {
  isUploadModalOpen.value = true
}

export function closeUploadModal() {
  isUploadModalOpen.value = false
}

export function onUploadDone() {
  doneHandlers.forEach(h => h())
}

export function registerUploadDone(handler: UploadDoneHandler) {
  doneHandlers.add(handler)
  return () => { doneHandlers.delete(handler) }
}
