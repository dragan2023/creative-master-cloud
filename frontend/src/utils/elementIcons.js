/**
 * elementIcons - Element Plus 图标字符串名称解析器
 *
 * 背景：main.js 已取消 @element-plus/icons-vue 全量注册（阶段04首屏优化）。
 * 部分配置数据（菜单、创意模块、工作流步骤、Agent 流水线、干预选项等）
 * 以字符串形式保存图标名，模板中通过 <component :is="..."> 动态渲染。
 * 此模块集中显式导入这些图标，提供字符串 → 组件的解析函数。
 *
 * 约束：仅登记实际被字符串引用的图标；新增字符串图标时必须在此补充导入，
 * 严禁恢复全量遍历注册。
 */
import {
  // 主导航菜单（layouts/menuConfig.js）
  HomeFilled, MagicStick, Key, FolderOpened, Edit, Clock, User, Setting,
  // 创意模块卡片（config/modules.js）
  VideoCamera, Picture, Film, Avatar, Document, Notebook,
  // 应用文写作类型选择（views/generate/components/PracticalWritingFields.vue）
  Money, Files, TrendCharts, Checked, ChatLineSquare, List, Medal,
  Management, Promotion, Message, Present, Share, UserFilled, Tickets,
  ReadingLamp, Monitor, FirstAidKit, ShoppingCart, OfficeBuilding,
  Dish, Van, Sunny, Apple, Stamp, CaretRight, Service, Reading,
  // 生成工作流步骤（GenerateForm/useStreamHandler/useWorkflow）
  CircleClose, Cpu, CircleCheck, Warning, RefreshRight,
  // 质量分析维度卡片（views/novel-writer/QualityAnalysis.vue）
  DataAnalysis, Connection,
  // Agent 流水线（useAgentPipeline/useWebSocket/useWritingTask/agentConfig）
  EditPen, View, SetUp, DataLine,
  // 用户干预选项（stores/outline.js、useProjectDetailState.js）
  VideoPause
} from '@element-plus/icons-vue'

const ICON_COMPONENTS = Object.freeze({
  HomeFilled, MagicStick, Key, FolderOpened, Edit, Clock, User, Setting,
  VideoCamera, Picture, Film, Avatar, Document, Notebook,
  Money, Files, TrendCharts, Checked, ChatLineSquare, List, Medal,
  Management, Promotion, Message, Present, Share, UserFilled, Tickets,
  ReadingLamp, Monitor, FirstAidKit, ShoppingCart, OfficeBuilding,
  Dish, Van, Sunny, Apple, Stamp, CaretRight, Service, Reading,
  CircleClose, Cpu, CircleCheck, Warning, RefreshRight,
  DataAnalysis, Connection,
  EditPen, View, SetUp, DataLine,
  VideoPause
})

/**
 * 将图标名称字符串解析为图标组件。
 * @param {string} iconName - 图标名（如 'HomeFilled'）
 * @returns {object|null} 图标组件；未登记时返回 null 并在开发环境告警
 */
export function resolveElementIcon(iconName) {
  if (!iconName) return null
  const iconComponent = ICON_COMPONENTS[iconName] || null
  if (!iconComponent && import.meta.env.DEV) {
    console.warn(`[elementIcons] 未登记的图标名: ${iconName}，请在 utils/elementIcons.js 中补充导入`)
  }
  return iconComponent
}
