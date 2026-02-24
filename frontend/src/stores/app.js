import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(localStorage.getItem('sidebarCollapsed') === 'true')
  const darkMode = ref(localStorage.getItem('darkMode') === 'true')

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
    localStorage.setItem('sidebarCollapsed', sidebarCollapsed.value)
  }

  function toggleDarkMode() {
    darkMode.value = !darkMode.value
    localStorage.setItem('darkMode', darkMode.value)
    document.documentElement.classList.toggle('dark', darkMode.value)
  }

  return {
    sidebarCollapsed,
    darkMode,
    toggleSidebar,
    toggleDarkMode
  }
})
