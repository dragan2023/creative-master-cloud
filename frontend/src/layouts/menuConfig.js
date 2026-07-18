/**
 * 主导航菜单唯一数据源
 *
 * 桌面端侧栏（el-aside）与移动端抽屉（el-drawer）共用本配置，
 * 禁止在组件内复制第二份菜单数据或权限判断。
 * 图标名对应 @element-plus/icons-vue 全局注册的组件名。
 */
export const MAIN_MENU_ITEMS = [
  { path: '/', title: '首页', icon: 'HomeFilled' },
  { path: '/generate', title: '创意生成', icon: 'MagicStick' },
  { path: '/api-keys', title: 'API Key管理', icon: 'Key' },
  { path: '/knowledge', title: '知识库', icon: 'FolderOpened' },
  { path: '/novel-writer', title: '小说/剧本生成', icon: 'Edit' },
  { path: '/history', title: '历史记录', icon: 'Clock' },
  { path: '/profile', title: '个人设置', icon: 'User' },
  { path: '/admin', title: '管理后台', icon: 'Setting', requiresSuperAdmin: true }
]

/**
 * 按用户权限过滤可见菜单项（唯一的菜单权限判断入口）
 * @param {boolean} isSuperAdmin 是否超级管理员
 * @returns {Array} 当前用户可见的菜单项
 */
export function getVisibleMenuItems(isSuperAdmin) {
  return MAIN_MENU_ITEMS.filter((item) => !item.requiresSuperAdmin || isSuperAdmin)
}
