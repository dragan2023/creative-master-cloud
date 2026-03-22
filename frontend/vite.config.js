import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

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

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd(), '')
  const isProduction = mode === 'production'

  // 基础配置
  const config = {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src')
      }
    },
    server: {
      port: parseInt(env.VITE_FRONTEND_PORT || '5173'),
      strictPort: true,  // 端口被占用时报错，不自动切换端口
      proxy: {
        '/api': {
          target: env.VITE_BACKEND_URL || 'http://localhost:8000',
          changeOrigin: true
        }
      },
      open: true  // 启动时自动打开浏览器
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
      // 使用 terser 压缩
      minify: 'terser',
      terserOptions: {
        compress: {
          // 生产环境移除 console（云端部署建议开启）
          drop_console: true,  // 移除所有console
          drop_debugger: true,
          pure_funcs: ['console.log', 'console.info', 'console.debug', 'console.warn'],
          // 额外压缩选项
          passes: 2,  // 多次压缩提高效果
          unsafe: true,  // 启用不安全优化
          unsafe_comps: true,
          unsafe_math: true,
          unsafe_symbols: true,
          // 移除无用代码
          dead_code: true,
          unused: true,
          // 条件语句优化
          conditionals: true,
          evaluate: true,
          booleans: true,
          loops: true,
          // 内联优化
          inline: 2,
          // 变量合并
          collapse_vars: true,
          reduce_vars: true,
          // 属性访问优化
          properties: true,
          // 序列优化
          sequences: true,
          comparisons: true,
          // 其他优化
          hoist_funs: true,
          hoist_vars: false,
          if_return: true,
          join_vars: true,
          cascade: true,
          side_effects: true,
          negate_iife: true
        },
        mangle: {
          // 变量名混淆
          toplevel: true,  // 混淆顶层作用域变量
          safari10: true,
          properties: {
            // 属性名混淆（谨慎使用，可能影响某些库）
            regex: /^_/,  // 只混淆以_开头的属性
          }
        },
        format: {
          // 移除注释
          comments: false,
          // 移除空格
          beautify: false,
          // 紧凑输出
          compact: true
        }
      },
      // 分块策略
      rollupOptions: {
        input: {
          main: path.resolve(__dirname, 'index.html')
        },
        output: {
          // 文件名哈希（防止缓存）
          chunkFileNames: 'assets/[name]-[hash].js',
          entryFileNames: 'assets/[name]-[hash].js',
          assetFileNames: 'assets/[name]-[hash].[ext]',
          // 手动分块
          manualChunks: {
            'vendor': ['vue', 'vue-router', 'pinia'],
            'element-plus': ['element-plus', '@element-plus/icons-vue'],
            'charts': ['@antv/g6']
          }
        }
      },
      // 分块大小警告阈值
      chunkSizeWarningLimit: 1000,
      // CSS代码分割
      cssCodeSplit: true,
      // 启用模块预加载
      modulePreload: {
        polyfill: false
      }
    }
  }

  return config
})
