import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import path from 'path'
import fs from 'fs'
import { createRequire } from 'module'

// 创建require函数（ESM环境兼容）
const require = createRequire(import.meta.url)

// 动态加载混淆插件（如果已安装）
// 云端部署时启用强混淆，本地开发可禁用以加快构建速度
let obfuscator = null
let viteCompression = null

// 尝试加载混淆插件（云端部署需要安装：npm install rollup-plugin-obfuscator --save-dev）
try {
  obfuscator = require('rollup-plugin-obfuscator').default
} catch (e) {
  // 混淆插件未安装，使用terser基础混淆
}

try {
  viteCompression = require('vite-plugin-compression').default
} catch (e) {
  // 压缩插件未安装
}

// 读取 version.json 获取版本号（支持 Docker 构建环境）
function getAppVersion() {
  const possiblePaths = [
    // 本地开发：项目根目录/version.json
    path.resolve(__dirname, '../version.json'),
    // Docker 构建环境：/app/version.json（前端工作目录是 /app/frontend）
    '/app/version.json',
    // 备选：构建上下文根目录
    '/version.json',
  ]
  
  for (const versionFile of possiblePaths) {
    try {
      if (fs.existsSync(versionFile)) {
        const versionData = JSON.parse(fs.readFileSync(versionFile, 'utf-8'))
        if (versionData.current_version) {
          console.log(`[Vite] 从 ${versionFile} 读取版本号`)
          return versionData.current_version
        }
      }
    } catch (e) {
      // 继续尝试下一个路径
    }
  }
  
  // 默认版本号
  console.warn('[Vite] 警告: 未找到 version.json，使用默认版本号')
  return '3.1.7'
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd(), '')
  const isProduction = mode === 'production'
  
  // 获取版本号（优先从 version.json 读取）
  const appVersion = getAppVersion()
  console.log(`[Vite] 应用版本号: ${appVersion}`)

  // 基础配置
  const config = {
    plugins: [
      vue(),
      // Element Plus 构建时按需导入：模板中的 el-xxx 组件与 v-loading 等指令
      // 由 resolver 自动注入导入语句和对应样式，取代入口全量注册
      AutoImport({
        resolvers: [ElementPlusResolver()],
        dts: false
      }),
      Components({
        resolvers: [ElementPlusResolver()],
        // 仅按需解析 Element Plus，不自动注册本地组件（保持显式导入约定）
        dirs: [],
        dts: false
      })
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src')
      }
    },
    // 定义全局常量，注入版本号到前端代码
    define: {
      __APP_VERSION__: JSON.stringify(appVersion),
    },
    // Vitest 单元测试配置
    test: {
      environment: 'jsdom',
      globals: true,
      include: ['src/**/*.spec.js', 'scripts/**/*.spec.mjs'],
      // 仅测试生效：public 静态资源在无静态服务器环境下按文件解析
      alias: {
        '/logo.png': path.resolve(__dirname, 'public/logo.png')
      },
      server: {
        deps: {
          // element-plus 及其样式由 Vitest 内联转换（Node 原生 ESM 无法加载其 .css 导入）
          inline: ['element-plus']
        }
      }
    },
    server: {
      host: '0.0.0.0',  // 监听所有网络接口
      port: parseInt(env.VITE_FRONTEND_PORT || '3001'),
      strictPort: true,  // 端口被占用时报错，不自动切换端口
      proxy: {
        // 使用正则边界 ^/api/：仅代理真实 API 请求（均为 /api/v1/... 形式），
        // 避免前缀误匹配前端页面路由（如 /api-keys 硬刷新被转发到后端返回旧构建 HTML 导致白屏）
        '^/api/': {
          target: env.VITE_BACKEND_URL || 'http://localhost:8002',
          changeOrigin: true,
          ws: true  // 支持 WebSocket 代理（写作任务实时进度）
        }
      },
      open: !env.BROWSER || env.BROWSER !== 'none',  // 容器内禁用自动打开
      // 文件监听限制（防止终端损坏）
      watch: {
        // 排除不需要监听的目录，减少文件监听器压力
        ignored: [
          '**/backend/logs/**',
          '**/backend/data/**',
          '**/node_modules/**',
          '**/dist/**',
          '**/.git/**',
          '**/__pycache__/**',
          '**/*.log',
          '**/*.zip',
          '**/docs/**'
        ],
        // Windows 下适当降低轮询频率，避免句柄耗尽
        interval: 800
      },
      // HMR 配置（热模块替换）- 关闭错误遮罩减少终端输出
      hmr: {
        overlay: false
      }
    }
  }

  // 生产环境配置：代码混淆 + 压缩
  if (isProduction) {
    // 混淆为显式开关：仅当 VITE_ENABLE_OBFUSCATION === 'true' 且插件可用时启用。
    // 普通 npm run build 默认不启用控制流平坦化，避免构建缓慢与运行时开销。
    const enableObfuscation = env.VITE_ENABLE_OBFUSCATION === 'true'
    if (enableObfuscation && obfuscator) {
      config.plugins.push(
        obfuscator({
          globalOptions: {
            compact: true,
            controlFlowFlattening: true,
            controlFlowFlatteningThreshold: 0.75,
            deadCodeInjection: true,
            deadCodeInjectionThreshold: 0.4,
            debugProtection: false,
            debugProtectionInterval: 0,
            disableConsoleOutput: false,
            identifierNamesGenerator: 'hexadecimal',
            identifierPrefix: '',
            inputFileName: '',
            log: false,
            numbersToExpressions: true,
            renameGlobals: false,
            reservedNames: [],
            reservedStrings: [],
            rotateStringArray: true,
            seed: 0,
            selfDefending: true,
            shuffleStringArray: true,
            splitStrings: true,
            splitStringsChunkLength: 10,
            stringArray: true,
            stringArrayEncoding: ['base64'],
            stringArrayIndexShift: true,
            stringArrayRotate: true,
            stringArrayShuffle: true,
            stringArrayWrappersCount: 2,
            stringArrayWrappersChainedCalls: true,
            stringArrayWrappersParametersMaxCount: 4,
            stringArrayWrappersType: 'function',
            stringArrayThreshold: 0.75,
            target: 'browser',
            transformObjectKeys: true,
            unicodeEscapeSequence: false
          }
        })
      )
    }

    // 添加压缩插件（如果可用）
    if (viteCompression) {
      config.plugins.push(
        // Gzip压缩
        viteCompression({
          algorithm: 'gzip',
          ext: '.gz',
          threshold: 10240,  // 大于10KB的文件才压缩
          deleteOriginFile: false
        })
      )
    }

    // 生产环境构建配置
    config.build = {
      // 输出到 backend/app/static 目录
      outDir: path.resolve(__dirname, '../backend/app/static'),
      emptyOutDir: true,  // 构建前清空目标目录
      // 禁用 source map（云端部署必须禁用）
      sourcemap: false,
      // 使用 esbuild 压缩（比 terser 更快更稳定）
      minify: 'esbuild',
      // 分块策略
      rollupOptions: {
        output: {
          manualChunks: {
            'element-plus': ['element-plus'],
            'antv': ['@antv/g6']
          }
        }
      }
    }
  }

  return config
})
