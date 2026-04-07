import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import fs from 'fs'

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
    plugins: [vue()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src')
      }
    },
    // 定义全局常量，注入版本号到前端代码
    define: {
      __APP_VERSION__: JSON.stringify(appVersion),
    },
    server: {
      host: '0.0.0.0',  // 监听所有网络接口
      port: parseInt(env.VITE_FRONTEND_PORT || '5173'),
      strictPort: true,  // 端口被占用时报错，不自动切换端口
      proxy: {
        '/api': {
          target: env.VITE_BACKEND_URL || 'http://localhost:7000',
          changeOrigin: true,
          ws: true  // 支持 WebSocket 代理（写作任务实时进度）
        }
      },
      open: !env.BROWSER || env.BROWSER !== 'none',  // 容器内禁用自动打开
      // HMR 配置（热模块替换）
      // Docker 容器中需要配置 clientPort: 80
      // 本地开发时使用默认配置即可
    }
  }

  // 生产环境配置：代码混淆 + 压缩
  if (isProduction) {
    // 注意：默认禁用 javascript-obfuscator，因为它会导致构建非常慢
    // 如果需要代码混淆，可以使用 terser 的压缩功能（已启用）
    // Terser 会压缩、混淆变量名、移除死代码，提供基础的保护
    // 如果确实需要更强的混淆保护，可以安装并启用 obfuscator 插件
    if (obfuscator) {
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
