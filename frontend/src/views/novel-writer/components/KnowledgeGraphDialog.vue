<!--
  知识图谱弹窗组件
  
  功能：
  1. 全局大纲图谱展示
  2. 单元图谱展示
  3. 节点列表和关系列表
  4. 单元图谱重建功能

  依赖：
  - novelWriterApi
  - 父组件需提供 projectId

  创建时间: 2026-03-30
  版本: 1.0.0
-->
<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="知识图谱"
    width="80%"
    top="5vh"
    :close-on-click-modal="true"
    :close-on-press-escape="true"
    class="knowledge-graph-dialog"
  >
    <div class="knowledge-graph-container">
      <!-- 图谱类型切换 -->
      <div class="graph-type-selector">
        <el-radio-group v-model="graphType" @change="loadKnowledgeGraph">
          <el-radio-button value="global">全局大纲图谱</el-radio-button>
          <el-radio-button value="unit">单元图谱</el-radio-button>
        </el-radio-group>
        <el-select
          v-if="graphType === 'unit'"
          v-model="selectedUnitNumber"
          placeholder="选择单元"
          @change="loadKnowledgeGraph"
          style="margin-left: 12px; width: 120px;"
        >
          <el-option
            v-for="i in totalUnits"
            :key="i"
            :label="`第${i}${unitLabel}`"
            :value="i"
          />
        </el-select>
        <el-button
          v-if="graphType === 'unit'"
          type="primary"
          plain
          style="margin-left: 12px;"
          @click="showUnitRebuildDialog"
        >
          <el-icon><Refresh /></el-icon>
          重建图谱
        </el-button>
      </div>

      <!-- 图谱统计信息 -->
      <div class="graph-stats" v-if="graphData.stats">
        <el-tag type="info" size="small">
          节点: {{ graphData.stats.node_count || 0 }}
        </el-tag>
        <el-tag type="info" size="small" style="margin-left: 8px;">
          边: {{ graphData.stats.edge_count || 0 }}
        </el-tag>
        <el-tag type="info" size="small" style="margin-left: 8px;" v-if="graphData.stats.entity_types">
          实体类型: {{ graphData.stats.entity_types?.join(', ') || '-' }}
        </el-tag>
      </div>

      <!-- 图谱可视化区域 -->
      <div class="graph-visualization" v-loading="loadingGraphData">
        <div v-if="graphData.nodes.length === 0 && !loadingGraphData" class="graph-empty">
          <el-empty :image-size="100" description="暂无图谱数据，请先构建知识库">
            <el-button type="primary" @click="$emit('build-knowledge-base')">
              构建知识库
            </el-button>
          </el-empty>
        </div>
        <div v-else class="graph-canvas">
          <!-- 节点列表视图 -->
          <div class="nodes-list-view">
            <div class="view-header">
              <el-icon><Collection /></el-icon>
              <span>实体列表</span>
              <el-tag size="small" type="info">{{ graphData.nodes.length }}</el-tag>
            </div>
            <el-collapse v-model="expandedNodeTypes">
              <el-collapse-item
                v-for="(nodes, type) in groupedNodes"
                :key="type"
                :name="type"
              >
                <template #title>
                  <div class="node-type-header">
                    <el-tag :type="getNodeTypeTag(type)" size="small">{{ type }}</el-tag>
                    <span class="node-count">({{ nodes.length }})</span>
                  </div>
                </template>
                <div class="node-list">
                  <div
                    v-for="node in nodes"
                    :key="node.id"
                    class="node-item"
                    @click="selectNode(node)"
                    :class="{ selected: selectedNode?.id === node.id }"
                  >
                    <span class="node-name">{{ node.name }}</span>
                    <span class="node-desc" v-if="node.description">{{ node.description }}</span>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>

          <!-- 关系列表视图 -->
          <div class="edges-list-view">
            <div class="view-header">
              <el-icon><Connection /></el-icon>
              <span>关系列表</span>
              <el-tag size="small" type="info">{{ graphData.edges.length }}</el-tag>
            </div>
            <div class="edges-list">
              <div
                v-for="(edge, index) in graphData.edges"
                :key="index"
                class="edge-item"
              >
                <span class="edge-source">{{ getNodeName(edge.source) }}</span>
                <span class="edge-relation">{{ edge.relation }}</span>
                <span class="edge-target">{{ getNodeName(edge.target) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 选中节点详情 -->
      <div v-if="selectedNode" class="node-detail-panel">
        <el-card shadow="never">
          <template #header>
            <div class="detail-header">
              <el-tag :type="getNodeTypeTag(selectedNode.type)" size="small">
                {{ selectedNode.type }}
              </el-tag>
              <span class="detail-name">{{ selectedNode.name }}</span>
            </div>
          </template>
          <div class="detail-content">
            <p v-if="selectedNode.description">
              <strong>描述:</strong> {{ selectedNode.description }}
            </p>
            <p v-if="selectedNode.attributes">
              <strong>属性:</strong>
              <el-tag
                v-for="(value, key) in selectedNode.attributes"
                :key="key"
                size="small"
                style="margin: 2px;"
              >
                {{ key }}: {{ value }}
              </el-tag>
            </p>
            <!-- 相关关系 -->
            <div v-if="relatedEdges.length > 0" class="related-edges">
              <strong>相关关系:</strong>
              <div v-for="edge in relatedEdges" :key="edge.id" class="related-edge">
                <span v-if="edge.source === selectedNode.id">
                  → {{ getNodeName(edge.target) }} ({{ edge.relation }})
                </span>
                <span v-else>
                  {{ getNodeName(edge.source) }} → ({{ edge.relation }})
                </span>
              </div>
            </div>
          </div>
        </el-card>
      </div>
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">关闭</el-button>
    </template>
  </el-dialog>

  <!-- 单元图谱重建弹窗 -->
  <el-dialog
    v-model="unitGraphRebuildVisible"
    title="重建单元知识图谱"
    width="600px"
    destroy-on-close
  >
    <div class="unit-graph-rebuild-content">
      <!-- 状态概览 -->
      <div class="unit-status-overview" v-if="unitGraphsStatus.loaded">
        <el-statistic title="已构建" :value="unitGraphsStatus.built_count" suffix="个" />
        <el-statistic title="待构建" :value="unitGraphsStatus.unbuilt_count" suffix="个" />
        <el-statistic title="总计" :value="unitGraphsStatus.total_units" suffix="个" />
      </div>

      <el-divider />

      <!-- 构建选项 -->
      <div class="rebuild-options">
        <h4>选择构建范围</h4>
        <el-radio-group v-model="unitRebuildMode">
          <el-radio value="all">全部重建（覆盖已有图谱）</el-radio>
          <el-radio value="unbuilt">仅构建未构建的单元</el-radio>
          <el-radio value="select">选择指定单元</el-radio>
        </el-radio-group>

        <!-- 单元选择器 -->
        <div v-if="unitRebuildMode === 'select'" class="unit-selector">
          <el-transfer
            v-model="selectedUnitsForRebuild"
            :data="availableUnitsForRebuild"
            :titles="['可选单元', '已选单元']"
            :props="{ key: 'value', label: 'label' }"
            filterable
            filter-placeholder="搜索单元"
          />
        </div>

        <!-- 待构建单元列表 -->
        <div
          v-if="unitRebuildMode === 'unbuilt' && unitGraphsStatus.unbuilt_units?.length > 0"
          class="unbuilt-units-list"
        >
          <el-tag
            v-for="unit in unitGraphsStatus.unbuilt_units"
            :key="unit.unit_number"
            type="info"
            style="margin: 2px;"
          >
            第{{ unit.unit_number }}{{ unitLabel }}
          </el-tag>
        </div>
      </div>

      <!-- 构建进度 -->
      <div v-if="buildingUnitGraphs" class="build-progress">
        <el-progress :percentage="unitBuildProgress" :status="unitBuildStatus" />
        <p class="progress-message">{{ unitBuildMessage }}</p>
      </div>
    </div>

    <template #footer>
      <el-button @click="unitGraphRebuildVisible = false">取消</el-button>
      <el-button
        type="primary"
        @click="executeUnitGraphRebuild"
        :loading="buildingUnitGraphs"
      >
        开始构建
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Collection, Connection } from '@element-plus/icons-vue'
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
const emit = defineEmits(['update:visible', 'build-knowledge-base'])

// ==================== 知识图谱相关状态 ====================
const graphType = ref('global')
const selectedUnitNumber = ref(1)
const graphData = ref({
  nodes: [],
  edges: [],
  stats: null
})
const loadingGraphData = ref(false)
const selectedNode = ref(null)
const expandedNodeTypes = ref([])

// ==================== 单元图谱重建相关状态 ====================
const unitGraphRebuildVisible = ref(false)
const unitGraphsStatus = ref({
  loaded: false,
  built_count: 0,
  unbuilt_count: 0,
  total_units: 0,
  unbuilt_units: []
})
const unitRebuildMode = ref('unbuilt')
const selectedUnitsForRebuild = ref([])
const buildingUnitGraphs = ref(false)
const unitBuildProgress = ref(0)
const unitBuildStatus = ref('')
const unitBuildMessage = ref('')

// ==================== 监听弹窗打开 ====================
watch(() => props.visible, (newVal) => {
  if (newVal) {
    loadKnowledgeGraph()
  }
})

// ==================== 计算属性 ====================

// 按类型分组的节点
const groupedNodes = computed(() => {
  const groups = {}
  for (const node of graphData.value.nodes) {
    const type = node.type || 'unknown'
    if (!groups[type]) {
      groups[type] = []
    }
    groups[type].push(node)
  }
  return groups
})

// 选中节点的相关边
const relatedEdges = computed(() => {
  if (!selectedNode.value) return []
  return graphData.value.edges.filter(
    edge => edge.source === selectedNode.value.id || edge.target === selectedNode.value.id
  )
})

// 可用单元列表（用于重建选择）
const availableUnitsForRebuild = computed(() => {
  return Array.from({ length: props.totalUnits }, (_, i) => ({
    value: i + 1,
    label: `第${i + 1}${props.unitLabel}`
  }))
})

// ==================== 方法 ====================

// 加载知识图谱数据
async function loadKnowledgeGraph() {
  loadingGraphData.value = true
  selectedNode.value = null

  try {
    const unitNumber = graphType.value === 'unit' ? selectedUnitNumber.value : null
    const res = await novelWriterApi.getKnowledgeGraph(props.projectId, unitNumber)

    if (res.success) {
      graphData.value = res.data || { nodes: [], edges: [], stats: null }
      if (graphData.value.nodes.length > 0) {
        expandedNodeTypes.value = Object.keys(groupedNodes.value)
      }
    } else {
      graphData.value = { nodes: [], edges: [], stats: null }
      if (res.message) {
        ElMessage.warning(res.message || '知识图谱不存在')
      }
    }
  } catch (error) {
    console.error('加载知识图谱失败:', error)
    graphData.value = { nodes: [], edges: [], stats: null }
    ElMessage.warning('知识图谱不存在，请先构建知识库')
  } finally {
    loadingGraphData.value = false
  }
}

// 获取节点类型标签颜色
function getNodeTypeTag(type) {
  const typeColors = {
    '人物': 'primary',
    '地点': 'success',
    '事件': 'warning',
    '物品': 'info',
    '概念': 'danger',
    '组织': '',
    '时间': 'warning'
  }
  return typeColors[type] || 'info'
}

// 获取节点名称
function getNodeName(nodeId) {
  const node = graphData.value.nodes.find(n => n.id === nodeId)
  return node ? node.name : nodeId
}

// 选择节点
function selectNode(node) {
  selectedNode.value = node
}

// 显示单元重建弹窗
async function showUnitRebuildDialog() {
  await loadUnitGraphsStatus()
  unitGraphRebuildVisible.value = true
}

// 加载单元图谱状态
async function loadUnitGraphsStatus() {
  try {
    const res = await novelWriterApi.getUnitGraphsStatus(props.projectId)
    if (res.success) {
      unitGraphsStatus.value = {
        loaded: true,
        ...res.data
      }
    }
  } catch (error) {
    console.error('加载单元图谱状态失败:', error)
  }
}

// 执行单元图谱重建
async function executeUnitGraphRebuild() {
  buildingUnitGraphs.value = true
  unitBuildProgress.value = 0
  unitBuildStatus.value = ''

  try {
    let unitNumbers = null
    if (unitRebuildMode.value === 'select') {
      unitNumbers = selectedUnitsForRebuild.value
    } else if (unitRebuildMode.value === 'unbuilt') {
      unitNumbers = unitGraphsStatus.value.unbuilt_units?.map(u => u.unit_number) || []
    }
    // 对于 'all' 模式，unitNumbers 为 null，会构建所有单元

    const res = await novelWriterApi.buildAllUnitKnowledgeGraphs(props.projectId, unitNumbers)

    if (res.success) {
      unitBuildProgress.value = 100
      unitBuildStatus.value = 'success'
      unitBuildMessage.value = '图谱重建成功'
      ElMessage.success('单元图谱重建成功')
      
      // 刷新图谱数据
      setTimeout(() => {
        unitGraphRebuildVisible.value = false
        loadKnowledgeGraph()
      }, 1000)
    }
  } catch (error) {
    unitBuildStatus.value = 'exception'
    unitBuildMessage.value = '重建失败: ' + (error.message || '未知错误')
    ElMessage.error('单元图谱重建失败')
  } finally {
    buildingUnitGraphs.value = false
  }
}
</script>

<style lang="scss" scoped>
.knowledge-graph-container {
  min-height: 400px;

  .graph-type-selector {
    display: flex;
    align-items: center;
    margin-bottom: 16px;
  }

  .graph-stats {
    margin-bottom: 16px;
  }

  .graph-visualization {
    min-height: 300px;

    .graph-empty {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 300px;
    }

    .graph-canvas {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;

      .nodes-list-view,
      .edges-list-view {
        max-height: 400px;
        overflow-y: auto;
        border: 1px solid #e4e7ed;
        border-radius: 8px;
        padding: 12px;

        .view-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 12px;
          font-weight: 500;
          color: #303133;
        }
      }

      .node-type-header {
        display: flex;
        align-items: center;
        gap: 8px;

        .node-count {
          color: #909399;
          font-size: 12px;
        }
      }

      .node-list {
        .node-item {
          padding: 8px 12px;
          margin: 4px 0;
          background: #f5f7fa;
          border-radius: 4px;
          cursor: pointer;
          transition: all 0.2s;

          &:hover {
            background: #ecf5ff;
          }

          &.selected {
            background: #ecf5ff;
            border-left: 3px solid #409eff;
          }

          .node-name {
            display: block;
            font-weight: 500;
            color: #303133;
          }

          .node-desc {
            display: block;
            font-size: 12px;
            color: #909399;
            margin-top: 2px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
        }
      }

      .edges-list {
        .edge-item {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 12px;
          margin: 4px 0;
          background: #f5f7fa;
          border-radius: 4px;
          font-size: 13px;

          .edge-source,
          .edge-target {
            color: #409eff;
          }

          .edge-relation {
            color: #67c23a;
            font-weight: 500;
          }
        }
      }
    }
  }

  .node-detail-panel {
    margin-top: 16px;

    .detail-header {
      display: flex;
      align-items: center;
      gap: 8px;

      .detail-name {
        font-size: 16px;
        font-weight: 600;
      }
    }

    .detail-content {
      p {
        margin: 8px 0;
        line-height: 1.6;
      }

      .related-edges {
        margin-top: 12px;

        .related-edge {
          padding: 4px 0;
          color: #606266;
          font-size: 13px;
        }
      }
    }
  }
}

// 单元图谱重建样式
.unit-graph-rebuild-content {
  .unit-status-overview {
    display: flex;
    justify-content: space-around;
    padding: 16px 0;
  }

  .rebuild-options {
    h4 {
      margin-bottom: 12px;
      color: #303133;
    }

    .el-radio-group {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .unit-selector {
      margin-top: 16px;
    }

    .unbuilt-units-list {
      margin-top: 12px;
      max-height: 150px;
      overflow-y: auto;
    }
  }

  .build-progress {
    margin-top: 16px;

    .progress-message {
      text-align: center;
      margin-top: 8px;
      color: #606266;
    }
  }
}
</style>
