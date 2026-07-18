import { createApp } from 'vue'
import { createPinia } from 'pinia'

// Element Plus 组件与样式由 unplugin-vue-components 按需自动导入（见 vite.config.js）。
// ElMessage / ElMessageBox / ElNotification 属于指令式 API，业务代码中为显式导入，
// 不经过模板按需解析，因此在入口统一引入其样式。
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/es/components/notification/style/css'

import App from './App.vue'
import router from './router'
import './styles/index.scss'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
