<!--
  一致性检查报告面板组件
  
  功能：
  1. 显示当前项目的知识图谱一致性状态
  2. 人物状态摘要（身份、位置、关系、能力、心理状态等）
  3. 设施状态摘要（运营状态、归属、物理状态等）
  4. 未完成事件跟踪
  5. 群体组织动态
  6. 道具归属情况
  7. 待回收伏笔提醒
  8. 世界规则约束
  9. 一致性警告和潜在冲突点

  依赖：
  - novelWriterApi
  - 父组件需提供 projectId

  创建时间: 2026-04-02
  版本: 1.0.0
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="一致性检查报告"
    width="85%"
    top="3vh"
    :close-on-click-modal="true"
    :close-on-press-escape="true"
    class="consistency-report-dialog"
  >
    <div class="consistency-report-container" v-loading="loading">
      <!-- 顶部控制栏 -->
      <div class="report-header">
        <div class="header-left">
          <el-radio-group v-model="viewMode" @change="handleViewModeChange">
            <el-radio-button value="summary">综合概览</el-radio-button>
            <el-radio-button value="characters">人物状态</el-radio-button>
            <el-radio-button value="entities">扩展实体</el-radio-button>
          </el-radio-group>
          <el-select
            v-model="selectedUnitNumber"
            placeholder="选择单元"
            @change="loadReport"
            style="margin-left: 12px; width: 120px;"
            clearable
          >
            <el-option label="全局" :value="null" />
            <el-option
              v-for="i in totalUnits"
              :key="i"
              :label="`第${i}${unitLabel}`"
              :value="i"
            />
          </el-select>
        </div>
        <div class="header-right">
          <el-button type="primary" plain @click="loadReport">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </div>

      <!-- 状态提示 -->
      <el-alert
        v-if="reportData.status === 'not_ready'"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 16px;"
      >
        <template #title>知识库尚未构建完成</template>
        {{ reportData.message || '请先构建项目知识库以获取一致性报告' }}
      </el-alert>

      <el-alert
        v-if="reportData.status === 'no_graph'"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px;"
      >
        <template #title>知识图谱不存在</template>
        {{ reportData.message || '请先构建知识图谱' }}
      </el-alert>

      <!-- 综合概览模式 -->
      <div v-if="viewMode === 'summary'" class="summary-view">
        <!-- 一致性警告 -->
        <el-card v-if="reportData.consistency_warnings?.length > 0" shadow="hover" class="warning-card">
          <template #header>
            <div class="card-header">
              <el-icon class="warning-icon"><Warning /></el-icon>
              <span>一致性警告</span>
              <el-tag type="danger" size="small">{{ reportData.consistency_warnings.length }}</el-tag>
            </div>
          </template>
          <div class="warnings-list">
            <div
              v-for="(warning, index) in reportData.consistency_warnings"
              :key="index"
              class="warning-item"
            >
              <el-icon><InfoFilled /></el-icon>
              <span>{{ warning }}</span>
            </div>
          </div>
        </el-card>

        <!-- 统计概览 -->
        <el-row :gutter="16" class="stats-row">
          <el-col :span="4">
            <el-statistic title="人物数量" :value="Object.keys(reportData.character_states || {}).length" />
          </el-col>
          <el-col :span="4">
            <el-statistic title="设施数量" :value="Object.keys(reportData.facility_states || {}).length" />
          </el-col>
          <el-col :span="4">
            <el-statistic title="未完成事件" :value="reportData.unfinished_events?.length || 0" />
          </el-col>
          <el-col :span="4">
            <el-statistic title="群体组织" :value="Object.keys(reportData.group_states || {}).length" />
          </el-col>
          <el-col :span="4">
            <el-statistic title="道具物品" :value="Object.keys(reportData.item_ownership || {}).length" />
          </el-col>
          <el-col :span="4">
            <el-statistic title="待回收伏笔" :value="reportData.pending_foreshadows?.length || 0" />
          </el-col>
        </el-row>

        <!-- 状态摘要网格 -->
        <div class="summary-grid">
          <!-- 人物状态 -->
          <el-card shadow="hover" class="summary-card">
            <template #header>
              <div class="card-header">
                <el-icon><User /></el-icon>
                <span>人物状态</span>
              </div>
            </template>
            <div class="entity-list">
              <div
                v-for="(state, name) in reportData.character_states"
                :key="name"
                class="entity-item"
              >
                <div class="entity-name">{{ name }}</div>
                <div class="entity-details">
                  <el-tag v-if="state.latest_identity" size="small" type="primary">
                    {{ state.latest_identity }}
                  </el-tag>
                  <el-tag v-if="state.latest_location" size="small" type="success">
                    📍 {{ state.latest_location }}
                  </el-tag>
                  <el-tag v-if="state.mental_state" size="small" type="warning">
                    {{ state.mental_state }}
                  </el-tag>
                  <el-tag v-for="(dev, idx) in (state.character_development || [])" :key="'dev'+idx" size="small" type="info">
                    🎭 {{ dev }}
                  </el-tag>
                  <el-tag v-for="(beh, idx) in (state.behavior_patterns || [])" :key="'beh'+idx" size="small" type="">
                    ⚡ {{ beh }}
                  </el-tag>
                  <el-tag v-for="(ability, idx) in (state.abilities || [])" :key="'abi'+idx" size="small" type="danger">
                    💪 {{ ability }}
                  </el-tag>
                </div>
              </div>
              <el-empty v-if="Object.keys(reportData.character_states || {}).length === 0" :image-size="60" description="暂无人物状态数据" />
            </div>
          </el-card>

          <!-- 设施状态 -->
          <el-card shadow="hover" class="summary-card">
            <template #header>
              <div class="card-header">
                <el-icon><OfficeBuilding /></el-icon>
                <span>设施状态</span>
              </div>
            </template>
            <div class="entity-list">
              <div
                v-for="(state, name) in reportData.facility_states"
                :key="name"
                class="entity-item"
              >
                <div class="entity-name">{{ name }}</div>
                <div class="entity-details">
                  <el-tag :type="getFacilityStatusType(state.status)" size="small">
                    {{ state.status }}
                  </el-tag>
                  <span v-if="state.manager" class="detail-text">负责人: {{ state.manager }}</span>
                </div>
              </div>
              <el-empty v-if="Object.keys(reportData.facility_states || {}).length === 0" :image-size="60" description="暂无设施状态数据" />
            </div>
          </el-card>

          <!-- 未完成事件 -->
          <el-card shadow="hover" class="summary-card">
            <template #header>
              <div class="card-header">
                <el-icon><Clock /></el-icon>
                <span>未完成事件</span>
              </div>
            </template>
            <div class="entity-list">
              <div
                v-for="(event, index) in reportData.unfinished_events"
                :key="index"
                class="entity-item"
              >
                <div class="entity-name">{{ event.name }}</div>
                <div class="entity-details">
                  <el-tag type="warning" size="small">{{ event.status }}</el-tag>
                  <span v-if="event.type" class="detail-text">{{ event.type }}</span>
                </div>
              </div>
              <el-empty v-if="(reportData.unfinished_events || []).length === 0" :image-size="60" description="没有未完成事件" />
            </div>
          </el-card>

          <!-- 群体组织 -->
          <el-card shadow="hover" class="summary-card">
            <template #header>
              <div class="card-header">
                <el-icon><Flag /></el-icon>
                <span>群体组织</span>
              </div>
            </template>
            <div class="entity-list">
              <div
                v-for="(state, name) in reportData.group_states"
                :key="name"
                class="entity-item"
              >
                <div class="entity-name">{{ name }}</div>
                <div class="entity-details">
                  <el-tag :type="state.status === '活跃' ? 'success' : 'info'" size="small">
                    {{ state.status }}
                  </el-tag>
                  <span v-if="state.leader" class="detail-text">领袖: {{ state.leader }}</span>
                  <span v-if="state.scale" class="detail-text">{{ state.scale }}</span>
                </div>
              </div>
              <el-empty v-if="Object.keys(reportData.group_states || {}).length === 0" :image-size="60" description="暂无群体组织数据" />
            </div>
          </el-card>

          <!-- 道具归属 -->
          <el-card shadow="hover" class="summary-card">
            <template #header>
              <div class="card-header">
                <el-icon><Box /></el-icon>
                <span>道具归属</span>
              </div>
            </template>
            <div class="entity-list">
              <div
                v-for="(state, name) in reportData.item_ownership"
                :key="name"
                class="entity-item"
              >
                <div class="entity-name">{{ name }}</div>
                <div class="entity-details">
                  <el-tag :type="getItemStatusType(state.status)" size="small">
                    {{ state.status }}
                  </el-tag>
                  <span v-if="state.owner" class="detail-text">持有: {{ state.owner }}</span>
                </div>
              </div>
              <el-empty v-if="Object.keys(reportData.item_ownership || {}).length === 0" :image-size="60" description="暂无道具归属数据" />
            </div>
          </el-card>

          <!-- 待回收伏笔 -->
          <el-card shadow="hover" class="summary-card">
            <template #header>
              <div class="card-header">
                <el-icon><Connection /></el-icon>
                <span>待回收伏笔</span>
              </div>
            </template>
            <div class="entity-list">
              <div
                v-for="(foreshadow, index) in reportData.pending_foreshadows"
                :key="index"
                class="entity-item"
              >
                <div class="entity-name">
                  <el-tag
                    v-if="foreshadow.importance === '重要'"
                    type="danger"
                    size="small"
                    effect="dark"
                  >重要</el-tag>
                  {{ foreshadow.name }}
                </div>
                <div class="entity-details">
                  <span class="detail-text">第{{ foreshadow.planted_chapter }}章埋设</span>
                </div>
              </div>
              <el-empty v-if="(reportData.pending_foreshadows || []).length === 0" :image-size="60" description="没有待回收伏笔" />
            </div>
          </el-card>

          <!-- 世界规则 -->
          <el-card shadow="hover" class="summary-card">
            <template #header>
              <div class="card-header">
                <el-icon><Document /></el-icon>
                <span>世界规则</span>
              </div>
            </template>
            <div class="entity-list">
              <div
                v-for="(rule, index) in reportData.active_rules"
                :key="index"
                class="entity-item"
              >
                <div class="entity-name">{{ rule.name }}</div>
                <div class="entity-details">
                  <span class="detail-text">{{ rule.description }}</span>
                </div>
              </div>
              <el-empty v-if="(reportData.active_rules || []).length === 0" :image-size="60" description="暂无世界规则数据" />
            </div>
          </el-card>

          <!-- 时间上下文 -->
          <el-card shadow="hover" class="summary-card">
            <template #header>
              <div class="card-header">
                <el-icon><Timer /></el-icon>
                <span>时间上下文</span>
              </div>
            </template>
            <div class="entity-list">
              <div
                v-for="(node, index) in reportData.time_context?.time_nodes"
                :key="index"
                class="entity-item"
              >
                <div class="entity-name">{{ node.name }}</div>
                <div class="entity-details">
                  <el-tag size="small" type="info">{{ node.type }}</el-tag>
                </div>
              </div>
              <el-empty v-if="(reportData.time_context?.time_nodes || []).length === 0" :image-size="60" description="暂无时间上下文" />
            </div>
          </el-card>
        </div>
      </div>

      <!-- 人物状态详情模式 -->
      <div v-if="viewMode === 'characters'" class="characters-view">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-card shadow="hover">
              <template #header>
                <div class="card-header">
                  <span>人物列表</span>
                  <el-input
                    v-model="characterFilter"
                    placeholder="搜索人物"
                    prefix-icon="Search"
                    size="small"
                    clearable
                    style="width: 150px;"
                  />
                </div>
              </template>
              <div class="character-list">
                <div
                  v-for="(state, name) in filteredCharacters"
                  :key="name"
                  class="character-item"
                  :class="{ selected: selectedCharacter === name }"
                  @click="selectCharacter(name)"
                >
                  <el-avatar :size="36" class="character-avatar">
                    {{ name.charAt(0) }}
                  </el-avatar>
                  <div class="character-info">
                    <div class="character-name">{{ name }}</div>
                    <div class="character-summary">
                      {{ state.latest_identity || '身份未知' }}
                    </div>
                  </div>
                </div>
                <el-empty v-if="Object.keys(filteredCharacters).length === 0" :image-size="60" description="暂无人物数据" />
              </div>
            </el-card>
          </el-col>
          <el-col :span="16">
            <el-card shadow="hover" v-if="selectedCharacter">
              <template #header>
                <div class="card-header">
                  <span>{{ selectedCharacter }} 状态详情</span>
                </div>
              </template>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="身份">
                  {{ characterStates.character_states?.identity_changes?.find(e => e.character === selectedCharacter)?.text || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="当前位置">
                  {{ characterStates.character_states?.location_changes?.find(e => e.character === selectedCharacter)?.text || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="心理状态">
                  {{ characterStates.character_states?.mental_states?.find(e => e.character === selectedCharacter)?.text || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="能力">
                  {{ characterStates.character_states?.ability_growth?.filter(e => e.character === selectedCharacter).map(e => e.text).join('、') || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="性格发展">
                  {{ characterStates.character_states?.character_development?.filter(e => e.character === selectedCharacter).map(e => e.text).join('、') || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="行为模式">
                  {{ characterStates.character_states?.behavior_patterns?.filter(e => e.character === selectedCharacter).map(e => e.text).join('、') || '-' }}
                </el-descriptions-item>
              </el-descriptions>
              
              <!-- 关系变化 -->
              <div class="relations-section" v-if="characterRelations.length > 0">
                <h4>人物关系</h4>
                <div class="relations-list">
                  <el-tag
                    v-for="(rel, index) in characterRelations"
                    :key="index"
                    size="small"
                    style="margin: 4px;"
                  >
                    {{ rel.text }}
                  </el-tag>
                </div>
              </div>
            </el-card>
            <el-empty v-else :image-size="100" description="选择左侧人物查看详情" />
          </el-col>
        </el-row>
      </div>

      <!-- 扩展实体模式 -->
      <div v-if="viewMode === 'entities'" class="entities-view">
        <el-tabs v-model="activeEntityType" @tab-change="loadEntities">
          <el-tab-pane label="设施" name="facility" />
          <el-tab-pane label="事件" name="event" />
          <el-tab-pane label="群体" name="group" />
          <el-tab-pane label="道具" name="item" />
          <el-tab-pane label="规则" name="rule" />
          <el-tab-pane label="时间线" name="timeline" />
          <el-tab-pane label="伏笔" name="foreshadow" />
        </el-tabs>

        <div class="entities-content" v-loading="loadingEntities">
          <el-table :data="entityTableData" stripe style="width: 100%">
            <el-table-column prop="name" label="名称" width="200" />
            <el-table-column prop="type" label="类型" width="120">
              <template #default="{ row }">
                <el-tag size="small">{{ row.type || '-' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" />
            <el-table-column prop="status" label="状态" width="120">
              <template #default="{ row }">
                <el-tag v-if="row.status" size="small" :type="getStatusType(row.status)">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="entityTableData.length === 0" :image-size="80" description="暂无数据" />
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Refresh, Warning, InfoFilled, User, OfficeBuilding,
  Clock, Flag, Box, Connection, Document, Timer
} from '@element-plus/icons-vue'
import { novelWriterApi } from '@/api/novel-writer'

// ==================== Props ====================
const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  projectId: {
    type: [Number, String],
    required: true
  },
  totalUnits: {
    type: Number,
    default: 0
  },
  unitLabel: {
    type: String,
    default: '章'
  }
})

// ==================== Emits ====================
const emit = defineEmits(['update:visible'])

// ==================== 状态 ====================
const loading = ref(false)
const loadingEntities = ref(false)
const viewMode = ref('summary')
const selectedUnitNumber = ref(null)
const reportData = ref({
  status: '',
  character_states: {},
  facility_states: {},
  unfinished_events: [],
  group_states: {},
  item_ownership: {},
  pending_foreshadows: [],
  active_rules: [],
  time_context: {},
  consistency_warnings: []
})

// 人物状态相关
const selectedCharacter = ref(null)
const characterFilter = ref('')
const characterStates = ref({
  character_states: {}
})

// 扩展实体相关
const activeEntityType = ref('facility')
const entitiesData = ref({})

// ==================== 监听弹窗打开 ====================
watch(() => props.visible, (newVal) => {
  if (newVal) {
    loadReport()
  }
})

// ==================== 计算属性 ====================

// 过滤后的人物列表
const filteredCharacters = computed(() => {
  const states = reportData.value.character_states || {}
  if (!characterFilter.value) return states
  
  const filtered = {}
  for (const [name, state] of Object.entries(states)) {
    if (name.includes(characterFilter.value)) {
      filtered[name] = state
    }
  }
  return filtered
})

// 选中人物的关系列表
const characterRelations = computed(() => {
  if (!selectedCharacter.value) return []
  return characterStates.value.character_states?.relationship_changes?.filter(
    e => e.character === selectedCharacter.value
  ) || []
})

// 实体表格数据
const entityTableData = computed(() => {
  const data = []
  const entities = entitiesData.value.entities || {}
  
  // 根据实体类型处理数据
  if (activeEntityType.value === 'facility') {
    for (const facility of (entities.facilities || [])) {
      data.push({
        name: facility.text,
        type: facility.attributes?.['功能类型'] || '-',
        description: facility.description || '',
        status: '正常'
      })
    }
    for (const state of (entities.facility_states || [])) {
      data.push({
        name: state.attributes?.['设施名称'] || '-',
        type: '状态变化',
        description: state.text,
        status: '-'
      })
    }
  } else if (activeEntityType.value === 'event') {
    for (const event of (entities.events || [])) {
      data.push({
        name: event.text,
        type: event.attributes?.['事件类型'] || '-',
        description: event.description || '',
        status: event.attributes?.['当前阶段'] || '进行中'
      })
    }
  } else if (activeEntityType.value === 'group') {
    for (const group of (entities.groups || [])) {
      data.push({
        name: group.text,
        type: group.attributes?.['性质'] || '-',
        description: `规模: ${group.attributes?.['规模'] || '-'}`,
        status: '活跃'
      })
    }
  } else if (activeEntityType.value === 'item') {
    for (const item of (entities.items || [])) {
      data.push({
        name: item.text,
        type: item.attributes?.['物品类型'] || '-',
        description: item.description || '',
        status: item.attributes?.['持有者'] ? `持有: ${item.attributes['持有者']}` : '-'
      })
    }
  } else if (activeEntityType.value === 'rule') {
    for (const rule of (entities.world_rules || [])) {
      data.push({
        name: rule.text,
        type: rule.attributes?.['规则类型'] || '-',
        description: rule.description || '-',
        status: '-'
      })
    }
  } else if (activeEntityType.value === 'timeline') {
    for (const node of (entities.time_nodes || [])) {
      data.push({
        name: node.text,
        type: node.attributes?.['时间类型'] || '-',
        description: '-',
        status: '-'
      })
    }
    for (const flow of (entities.time_flows || [])) {
      data.push({
        name: flow.text,
        type: '时间流逝',
        description: `第${flow.chapter}章`,
        status: '-'
      })
    }
  } else if (activeEntityType.value === 'foreshadow') {
    for (const foreshadow of (entities.foreshadows || [])) {
      data.push({
        name: foreshadow.text,
        type: foreshadow.attributes?.['重要程度'] || '普通',
        description: foreshadow.description || '-',
        status: foreshadow.chapter ? `第${foreshadow.chapter}章` : '-'
      })
    }
  }
  
  return data
})

// ==================== 方法 ====================

// 加载一致性报告
async function loadReport() {
  loading.value = true
  
  try {
    const res = await novelWriterApi.getConsistencyReport(
      props.projectId,
      selectedUnitNumber.value
    )
    
    if (res.success) {
      reportData.value = res.data || {}
    } else {
      reportData.value = {
        status: 'error',
        character_states: {},
        facility_states: {},
        unfinished_events: [],
        group_states: {},
        item_ownership: {},
        pending_foreshadows: [],
        active_rules: [],
        time_context: {},
        consistency_warnings: []
      }
    }
  } catch (error) {
    console.error('加载一致性报告失败:', error)
    ElMessage.warning('加载一致性报告失败')
  } finally {
    loading.value = false
  }
}

// 选择人物
async function selectCharacter(name) {
  selectedCharacter.value = name
  
  // 加载详细状态
  try {
    const res = await novelWriterApi.getCharacterStates(
      props.projectId,
      selectedUnitNumber.value,
      name
    )
    
    if (res.success) {
      characterStates.value = res.data || {}
    }
  } catch (error) {
    console.error('加载人物状态失败:', error)
  }
}

// 加载扩展实体
async function loadEntities() {
  loadingEntities.value = true
  
  try {
    const res = await novelWriterApi.getExtendedEntities(
      props.projectId,
      selectedUnitNumber.value,
      activeEntityType.value
    )
    
    if (res.success) {
      entitiesData.value = res.data || {}
    }
  } catch (error) {
    console.error('加载扩展实体失败:', error)
  } finally {
    loadingEntities.value = false
  }
}

// 视图模式切换
function handleViewModeChange(mode) {
  if (mode === 'characters' && !selectedCharacter.value) {
    // 默认选择第一个人物
    const names = Object.keys(reportData.value.character_states || {})
    if (names.length > 0) {
      selectCharacter(names[0])
    }
  } else if (mode === 'entities') {
    loadEntities()
  }
}

// 获取设施状态类型
function getFacilityStatusType(status) {
  const statusMap = {
    '正常运营': 'success',
    '关闭': 'danger',
    '暂停营业': 'warning',
    '损坏': 'danger',
    '建设中': 'info'
  }
  return statusMap[status] || 'info'
}

// 获取道具状态类型
function getItemStatusType(status) {
  const statusMap = {
    '完好': 'success',
    '损坏': 'warning',
    '丢失': 'danger',
    '销毁': 'danger'
  }
  return statusMap[status] || 'info'
}

// 获取通用状态类型
function getStatusType(status) {
  if (!status) return 'info'
  if (['完成', '已完成', '正常', '活跃', '完好'].includes(status)) return 'success'
  if (['进行中', '建设中'].includes(status)) return 'primary'
  if (['暂停', '损坏'].includes(status)) return 'warning'
  if (['关闭', '取消', '丢失', '销毁'].includes(status)) return 'danger'
  return 'info'
}
</script>

<style lang="scss" scoped>
.consistency-report-container {
  min-height: 400px;
  max-height: 70vh;
  overflow-y: auto;

  .report-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    .header-left {
      display: flex;
      align-items: center;
    }
  }

  .stats-row {
    margin-bottom: 16px;
    
    .el-statistic {
      text-align: center;
      padding: 12px;
      background: #f5f7fa;
      border-radius: 8px;
    }
  }

  .warning-card {
    margin-bottom: 16px;

    .card-header {
      display: flex;
      align-items: center;
      gap: 8px;

      .warning-icon {
        color: #e6a23c;
        font-size: 18px;
      }
    }

    .warnings-list {
      .warning-item {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        padding: 8px 0;
        border-bottom: 1px solid #f0f0f0;

        &:last-child {
          border-bottom: none;
        }

        .el-icon {
          color: #e6a23c;
          margin-top: 2px;
        }
      }
    }
  }

  .summary-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;

    @media (max-width: 1200px) {
      grid-template-columns: repeat(2, 1fr);
    }

    @media (max-width: 768px) {
      grid-template-columns: 1fr;
    }
  }

  .summary-card {
    .card-header {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 500;
    }

    .entity-list {
      max-height: 250px;
      overflow-y: auto;

      .entity-item {
        padding: 8px;
        margin: 4px 0;
        background: #f5f7fa;
        border-radius: 6px;

        .entity-name {
          font-weight: 500;
          margin-bottom: 4px;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .entity-details {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 6px;

          .detail-text {
            font-size: 12px;
            color: #909399;
          }
        }
      }
    }
  }

  // 人物状态视图
  .characters-view {
    .character-list {
      max-height: 500px;
      overflow-y: auto;

      .character-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px;
        margin: 4px 0;
        background: #f5f7fa;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.2s;

        &:hover {
          background: #ecf5ff;
        }

        &.selected {
          background: #ecf5ff;
          border-left: 3px solid #409eff;
        }

        .character-avatar {
          background: #409eff;
          color: white;
        }

        .character-info {
          .character-name {
            font-weight: 500;
          }

          .character-summary {
            font-size: 12px;
            color: #909399;
          }
        }
      }
    }

    .relations-section {
      margin-top: 16px;

      h4 {
        margin-bottom: 8px;
        color: #303133;
      }
    }
  }

  // 扩展实体视图
  .entities-view {
    .entities-content {
      margin-top: 16px;
    }
  }
}
</style>
