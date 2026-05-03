<template>
  <el-dialog 
    v-model="visible" 
    title="知识图谱" 
    width="80%" 
    top="5vh"
    destroy-on-close
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
            v-for="i in totalChapters" 
            :key="i" 
            :label="`第${i}${unitLabel}`" 
            :value="i" 
          />
        </el-select>
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
          <el-empty :image-size="100" description="暂无图谱数据" />
        </div>
        <div v-else class="graph-canvas">
          <!-- 节点列表视图 -->
          <div class="nodes-list-view">
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
                    @click="selectedNode = node"
                    :class="{ 'selected': selectedNode?.id === node.id }"
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
            <div class="edges-header">
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
            <p v-if="selectedNode.description"><strong>描述:</strong> {{ selectedNode.description }}</p>
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
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  projectId: { type: [Number, String], required: true },
  unitLabel: { type: String, default: '章' },
  totalChapters: { type: Number, default: 0 }
})

const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// 图谱状态
const graphType = ref('global')
const selectedUnitNumber = ref(1)
const graphData = ref({ nodes: [], edges: [], stats: null })
const loadingGraphData = ref(false)
const selectedNode = ref(null)
const expandedNodeTypes = ref([])

// 计算属性：按类型分组的节点
const groupedNodes = computed(() => {
  const groups = {}
  for (const node of graphData.value.nodes) {
    const type = node.type || 'unknown'
    if (!groups[type]) groups[type] = []
    groups[type].push(node)
  }
  return groups
})

// 计算属性：选中节点的相关边
const relatedEdges = computed(() => {
  if (!selectedNode.value) return []
  return graphData.value.edges.filter(
    edge => edge.source === selectedNode.value.id || edge.target === selectedNode.value.id
  )
})

// 监听 modelValue，打开时自动加载
watch(() => props.modelValue, (newVal) => {
  if (newVal) {
    loadKnowledgeGraph()
  }
})

// 加载知识图谱数据
async function loadKnowledgeGraph() {
  loadingGraphData.value = true
  selectedNode.value = null
  
  try {
    const unitNumber = graphType.value === 'unit' ? selectedUnitNumber.value : null
    const res = await novelWriterApi.getKnowledgeGraph(props.projectId, unitNumber)
    
    if (res.success) {
      graphData.value = res.data
      expandedNodeTypes.value = Object.keys(groupedNodes.value)
    }
  } catch (error) {
    ElMessage.error('加载知识图谱失败')
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
</script>
