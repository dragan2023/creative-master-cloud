<!--
  认证页面共享布局组件
  功能：
  1. 提供登录/注册页面的统一布局（动态背景 + 左右分栏）
  2. 通过 CSS 自定义属性参数化配色方案（蓝/绿主题互换）
  3. 通过具名插槽注入差异化内容

  创建时间: 2026-04-26
-->
<template>
  <div class="auth-page" :style="cssVars">
    <!-- 动态背景 -->
    <div class="bg-animation">
      <div class="bg-gradient"></div>
      <div class="bg-particles">
        <span v-for="i in 20" :key="i" class="particle"></span>
      </div>
    </div>

    <div class="auth-container" :style="{ height: containerHeight }">
      <!-- 左侧装饰面板 -->
      <div class="auth-left">
        <div class="brand">
          <div class="brand-icon">
            <img src="/logo.png" alt="全能创意大师" class="brand-logo-img" />
          </div>
          <h1>全能创意大师</h1>
          <p><slot name="brand-subtitle">基于AI的智能创意生成平台</slot></p>
        </div>

        <div class="left-content">
          <slot name="left-content"></slot>
        </div>

        <div class="tech-decoration">
          <div class="tech-line"></div>
          <div class="tech-dot"></div>
        </div>
      </div>

      <!-- 右侧表单面板 -->
      <div class="auth-right">
        <div class="auth-form-container">
          <div class="form-header">
            <h2><slot name="form-title"></slot></h2>
            <p class="subtitle"><slot name="form-subtitle"></slot></p>
          </div>

          <slot name="form-content"></slot>

          <div class="footer">
            <slot name="footer"></slot>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  /** 主色调 hex，Login=#409EFF, Register=#00D4AA */
  accentColor: { type: String, default: '#409EFF' },
  /** 主色调 RGB 分量，用于 rgba() */
  accentRgb: { type: String, default: '64, 158, 255' },
  /** 辅助色 hex */
  secondaryColor: { type: String, default: '#00D4AA' },
  /** 辅助色 RGB 分量 */
  secondaryRgb: { type: String, default: '0, 212, 170' },
  /** 容器高度 */
  containerHeight: { type: String, default: '580px' }
})

const cssVars = computed(() => ({
  '--auth-accent': props.accentColor,
  '--auth-accent-rgb': props.accentRgb,
  '--auth-secondary': props.secondaryColor,
  '--auth-secondary-rgb': props.secondaryRgb
}))
</script>

<style lang="scss" scoped>
.auth-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

// 动态背景
.bg-animation {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 0;

  .bg-gradient {
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 30%, #16213e 60%, #0f0f1a 100%);
  }

  .bg-particles {
    position: absolute;
    inset: 0;
    overflow: hidden;

    .particle {
      position: absolute;
      width: 4px;
      height: 4px;
      background: rgba(var(--auth-accent-rgb), 0.6);
      border-radius: 50%;
      animation: float-up 15s linear infinite;

      &:nth-child(1) { left: 5%; animation-delay: -0.7s; animation-duration: 12s; opacity: 0.5; }
      &:nth-child(2) { left: 10%; animation-delay: -1.4s; animation-duration: 14s; opacity: 0.6; }
      &:nth-child(3) { left: 15%; animation-delay: -2.1s; animation-duration: 11s; opacity: 0.4; }
      &:nth-child(4) { left: 20%; animation-delay: -2.8s; animation-duration: 16s; opacity: 0.7; }
      &:nth-child(5) { left: 25%; animation-delay: -3.5s; animation-duration: 13s; opacity: 0.5; }
      &:nth-child(6) { left: 30%; animation-delay: -4.2s; animation-duration: 15s; opacity: 0.6; }
      &:nth-child(7) { left: 35%; animation-delay: -4.9s; animation-duration: 12s; opacity: 0.4; }
      &:nth-child(8) { left: 40%; animation-delay: -5.6s; animation-duration: 17s; opacity: 0.8; }
      &:nth-child(9) { left: 45%; animation-delay: -6.3s; animation-duration: 14s; opacity: 0.5; }
      &:nth-child(10) { left: 50%; animation-delay: -7s; animation-duration: 13s; opacity: 0.6; }
      &:nth-child(11) { left: 55%; animation-delay: -7.7s; animation-duration: 16s; opacity: 0.7; }
      &:nth-child(12) { left: 60%; animation-delay: -8.4s; animation-duration: 11s; opacity: 0.4; }
      &:nth-child(13) { left: 65%; animation-delay: -9.1s; animation-duration: 15s; opacity: 0.6; }
      &:nth-child(14) { left: 70%; animation-delay: -9.8s; animation-duration: 14s; opacity: 0.5; }
      &:nth-child(15) { left: 75%; animation-delay: -10.5s; animation-duration: 18s; opacity: 0.8; }
      &:nth-child(16) { left: 80%; animation-delay: -11.2s; animation-duration: 12s; opacity: 0.4; }
      &:nth-child(17) { left: 85%; animation-delay: -11.9s; animation-duration: 16s; opacity: 0.7; }
      &:nth-child(18) { left: 90%; animation-delay: -12.6s; animation-duration: 13s; opacity: 0.5; }
      &:nth-child(19) { left: 95%; animation-delay: -13.3s; animation-duration: 15s; opacity: 0.6; }
      &:nth-child(20) { left: 98%; animation-delay: -14s; animation-duration: 14s; opacity: 0.5; }
    }
  }
}

@keyframes float-up {
  0% {
    transform: translateY(100vh) scale(0);
    opacity: 0;
  }
  10% {
    opacity: 1;
  }
  90% {
    opacity: 1;
  }
  100% {
    transform: translateY(-100px) scale(1);
    opacity: 0;
  }
}

.auth-container {
  display: flex;
  width: 960px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 24px;
  overflow: hidden;
  box-shadow:
    0 25px 80px rgba(0, 0, 0, 0.5),
    0 0 0 1px rgba(var(--auth-accent-rgb), 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(20px);
  position: relative;
  z-index: 1;
}

.auth-left {
  width: 420px;
  padding: 50px 40px;
  background: linear-gradient(
    135deg,
    rgba(var(--auth-accent-rgb), 0.15) 0%,
    rgba(var(--auth-secondary-rgb), 0.1) 100%
  );
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    right: 0;
    width: 1px;
    height: 100%;
    background: linear-gradient(180deg, transparent, rgba(var(--auth-accent-rgb), 0.5), transparent);
  }

  .brand {
    text-align: center;
    color: #fff;
    position: relative;
    z-index: 1;

    .brand-icon {
      width: 80px;
      height: 80px;
      margin: 0 auto 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, var(--auth-accent) 0%, var(--auth-secondary) 100%);
      border-radius: 12px;
      box-shadow: 0 8px 32px rgba(var(--auth-accent-rgb), 0.4);
      animation: icon-pulse 3s ease-in-out infinite;

      .brand-logo-img {
        width: 48px;
        height: 48px;
        object-fit: contain;
      }
    }

    h1 {
      margin: 0 0 10px;
      font-size: 26px;
      font-weight: 700;
      background: linear-gradient(90deg, #fff, var(--auth-accent), var(--auth-secondary));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    p {
      opacity: 0.8;
      font-size: 14px;
      color: rgba(255, 255, 255, 0.7);
    }
  }

  .left-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    margin-top: 40px;
    position: relative;
    z-index: 1;

    // 共享列表项样式 —— Login(.feature-item) / Register(.benefit-icon li) 统一
    .auth-list-item {
      display: flex;
      align-items: center;
      gap: 14px;
      color: #fff;
      font-size: 14px;
      padding: 14px 20px;
      background: rgba(255, 255, 255, 0.05);
      border-radius: 12px;
      border: 1px solid rgba(var(--auth-accent-rgb), 0.15);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

      & + .auth-list-item {
        margin-top: 10px;
      }

      &:hover {
        background: rgba(var(--auth-accent-rgb), 0.15);
        border-color: rgba(var(--auth-accent-rgb), 0.4);
        transform: translateX(8px);

        .auth-list-icon {
          background: linear-gradient(135deg, var(--auth-accent), var(--auth-secondary));
          box-shadow: 0 4px 15px rgba(var(--auth-accent-rgb), 0.4);
        }
      }

      .auth-list-icon {
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(var(--auth-accent-rgb), 0.2);
        border-radius: 10px;
        transition: all 0.3s;
        flex-shrink: 0;

        .el-icon {
          color: var(--auth-accent);
        }

        // 小号变体（Register 页使用 32px 图标）
        &.small {
          width: 32px;
          height: 32px;
          border-radius: 8px;

          .el-icon {
            font-size: 16px;
          }
        }
      }
    }

    // 列表标题（Register 的 h3）
    .auth-list-title {
      color: #fff;
      font-size: 16px;
      margin-bottom: 20px;
      text-align: center;
      font-weight: 500;
    }
  }

  .tech-decoration {
    position: absolute;
    bottom: 30px;
    left: 40px;
    right: 40px;
    display: flex;
    align-items: center;
    gap: 10px;

    .tech-line {
      flex: 1;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(var(--auth-accent-rgb), 0.5), transparent);
    }

    .tech-dot {
      width: 8px;
      height: 8px;
      background: var(--auth-accent);
      border-radius: 50%;
      animation: dot-pulse 2s ease-in-out infinite;
    }
  }
}

@keyframes icon-pulse {
  0%, 100% {
    box-shadow: 0 8px 32px rgba(var(--auth-accent-rgb), 0.4);
  }
  50% {
    box-shadow: 0 8px 48px rgba(var(--auth-accent-rgb), 0.6), 0 0 60px rgba(var(--auth-secondary-rgb), 0.3);
  }
}

@keyframes dot-pulse {
  0%, 100% {
    opacity: 0.5;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.5);
  }
}

.auth-right {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 50px;
  background: rgba(255, 255, 255, 0.02);

  .auth-form-container {
    width: 100%;
    max-width: 340px;

    .form-header {
      margin-bottom: 32px;

      h2 {
        font-size: 28px;
        color: #fff;
        margin-bottom: 8px;
        font-weight: 600;
      }

      .subtitle {
        color: rgba(255, 255, 255, 0.6);
        font-size: 14px;
      }
    }

    :deep(.el-form-item) {
      margin-bottom: 24px;

      .el-input {
        --el-input-bg-color: rgba(255, 255, 255, 0.05);
        --el-input-border-color: rgba(var(--auth-accent-rgb), 0.2);
        --el-input-text-color: #fff;
        --el-input-placeholder-color: rgba(255, 255, 255, 0.4);
        --el-input-hover-border-color: rgba(var(--auth-accent-rgb), 0.5);
        --el-input-focus-border-color: var(--auth-accent);

        .el-input__wrapper {
          border-radius: 10px;
          padding: 4px 16px;
          box-shadow: none;
          transition: all 0.3s;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(var(--auth-accent-rgb), 0.2);

          &:hover {
            border-color: rgba(var(--auth-accent-rgb), 0.5);
            background: rgba(255, 255, 255, 0.08);
          }

          &.is-focus {
            border-color: var(--auth-accent);
            box-shadow: 0 0 0 3px rgba(var(--auth-accent-rgb), 0.15);
            background: rgba(255, 255, 255, 0.1);
          }
        }

        .el-input__prefix {
          color: rgba(255, 255, 255, 0.5);
        }
      }
    }

    :deep(.auth-submit-btn) {
      width: 100%;
      height: 48px;
      font-size: 16px;
      font-weight: 600;
      border-radius: 10px;
      background: linear-gradient(135deg, var(--auth-accent) 0%, var(--auth-secondary) 100%);
      border: none;
      box-shadow: 0 4px 20px rgba(var(--auth-accent-rgb), 0.4);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(var(--auth-accent-rgb), 0.5);
      }

      &:active {
        transform: translateY(0);
      }
    }

    .footer {
      text-align: center;
      margin-top: 24px;
      color: rgba(255, 255, 255, 0.5);
      font-size: 14px;

      a {
        color: var(--auth-accent);
        text-decoration: none;
        margin-left: 5px;
        font-weight: 500;
        transition: all 0.3s;

        &:hover {
          color: var(--auth-secondary);
          text-decoration: underline;
        }
      }
    }
  }
}
</style>
