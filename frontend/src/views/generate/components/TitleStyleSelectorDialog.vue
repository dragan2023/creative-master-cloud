<!--
  标题风格选择器对话框
  功能：
  1. 展示26种标题风格供用户选择
  2. 分5大类：古典章回体、古典诗词化、现代严肃文学、网络流行风格、外国文学经典
  3. 选择后返回styleId和styleName

  创建时间: 2026-04-18
  版本: 1.0
-->
<template>
  <el-dialog
    v-model="dialogVisible"
    title="选择标题风格"
    width="700px"
    destroy-on-close
    :close-on-click-modal="false"
  >
    <div class="title-style-selector">
      <!-- 分类标签 -->
      <div class="category-tabs">
        <el-radio-group v-model="activeCategory" size="small">
          <el-radio-button
            v-for="cat in titleStyleCategories"
            :key="cat.id"
            :value="cat.id"
          >
            {{ cat.name }}
          </el-radio-button>
        </el-radio-group>
      </div>

      <!-- 风格卡片 -->
      <div class="style-grid">
        <div
          v-for="style in currentCategoryStyles"
          :key="style.id"
          class="style-card"
          :class="{ selected: selectedStyleId === style.id }"
          @click="selectStyle(style)"
        >
          <div class="style-check" v-if="selectedStyleId === style.id">
            <el-icon><CircleCheckFilled /></el-icon>
          </div>
          <h5 class="style-name">{{ style.name }}</h5>
          <p class="style-desc">{{ style.description }}</p>
          <div class="style-examples" v-if="style.examples && style.examples.length">
            <span class="example-label">示例:</span>
            <span class="example-text" v-for="(ex, idx) in style.examples" :key="idx">
              "{{ ex }}"
            </span>
          </div>
        </div>
      </div>

      <!-- 已选风格预览 -->
      <div class="selected-preview" v-if="selectedStyleId">
        <el-divider>已选风格</el-divider>
        <div class="preview-content">
          <el-tag type="success" size="large">{{ selectedStyleName }}</el-tag>
          <el-button size="small" text type="danger" @click="clearSelection">取消选择</el-button>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button
        type="primary"
        @click="confirmSelection"
        :disabled="!selectedStyleId"
      >
        确认选择
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { CircleCheckFilled } from '@element-plus/icons-vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  initialStyleId: { type: String, default: '' }
})

const emit = defineEmits(['update:visible', 'confirm'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const activeCategory = ref('classical_chapter')
const selectedStyleId = ref('')
const selectedStyleName = ref('')

// 26种标题风格数据（与后端title_style_guidance.py对应）
const titleStyleCategories = [
  { id: 'classical_chapter', name: '古典章回体' },
  { id: 'classical_poetry', name: '古典诗词化' },
  { id: 'modern', name: '现代严肃文学' },
  { id: 'network', name: '网络流行风格' },
  { id: 'foreign', name: '外国文学经典' }
]

const titleStyles = [
  // 古典章回体 (3种)
  {
    id: 'classical_chapter_narrative',
    name: '叙史型回目',
    category: 'classical_chapter',
    description: '重故事情节，七字或八字对仗偶句，概括全章内容',
    examples: ['宴桃园豪杰三结义，斩黄巾英雄首立功', '张翼德怒鞭督邮，何国舅谋诛宦竖']
  },
  {
    id: 'classical_chapter_meaning',
    name: '括意型回目',
    category: 'classical_chapter',
    description: '重思想意义的提炼概括，含蓄而富有哲理',
    examples: ['甄士隐梦幻识通灵，贾雨村风尘怀闺秀', '游幻境指迷十二钗，饮仙醪曲演红楼梦']
  },
  {
    id: 'classical_chapter_hint',
    name: '暗示型回目',
    category: 'classical_chapter',
    description: '通过意象、典故暗示章节走向，意境深远',
    examples: ['鲁提辖拳打镇关西', '林教头风雪山神庙']
  },

  // 古典诗词化 (6种)
  {
    id: 'classical_poetry_2char',
    name: '二字简洁体',
    category: 'classical_poetry',
    description: '严格2个汉字，极简风格，干净利落',
    examples: ['初遇', '别离']
  },
  {
    id: 'classical_poetry_3char',
    name: '三字古韵体',
    category: 'classical_poetry',
    description: '严格3个汉字，取乐府旧题或词牌名为章节名',
    examples: ['长相思', '蝶恋花']
  },
  {
    id: 'classical_poetry_4char',
    name: '四字成语体',
    category: 'classical_poetry',
    description: '四字成语或四字短语标题，工整有力',
    examples: ['风起云涌', '初露锋芒']
  },
  {
    id: 'classical_poetry_5char',
    name: '五字意境体',
    category: 'classical_poetry',
    description: '五字短语标题，意境悠远',
    examples: ['明月松间照', '空山新雨后']
  },
  {
    id: 'classical_poetry_7char',
    name: '七言诗句体',
    category: 'classical_poetry',
    description: '以七言诗句为标题，韵律工整，意境悠远',
    examples: ['长风万里送秋雁', '桃花依旧笑春风']
  },
  {
    id: 'classical_poetry_couplet',
    name: '对仗联句体',
    category: 'classical_poetry',
    description: '严格对仗的对联形式标题，平仄相对',
    examples: ['风起云涌天地变', '雷鸣电闪鬼神惊']
  },

  // 现代严肃文学 (5种)
  {
    id: 'modern_number_only',
    name: '数字简约型',
    category: 'modern',
    description: '仅以"第N章"标识，简约至极',
    examples: ['第一章', '第二章']
  },
  {
    id: 'modern_narrative',
    name: '叙事概括型',
    category: 'modern',
    description: '直接概括该章核心事件，简洁明了',
    examples: ['平凡的世界', '蛙']
  },
  {
    id: 'modern_meaning',
    name: '括意提炼型',
    category: 'modern',
    description: '提炼章节思想意义，含蓄而深刻',
    examples: ['活着', '围城']
  },
  {
    id: 'modern_hint',
    name: '暗示型',
    category: 'modern',
    description: '以象征性意象暗示章节走向',
    examples: ['白鹿原', '红高粱']
  },

  // 网络流行风格 (7种)
  {
    id: 'network_hotspot',
    name: '网文热点型',
    category: 'network',
    description: '直白有吸引力，带悬念的现代网文标题',
    examples: ['穿越之初，系统激活', '重生归来，王者归来']
  },
  {
    id: 'network_suspense',
    name: '悬念型',
    category: 'network',
    description: '制造悬念和反转的标题，吸引读者继续阅读',
    examples: ['你以为的真相不是真相', '他竟然还活着']
  },
  {
    id: 'network_action',
    name: '动作型',
    category: 'network',
    description: '短促有力，强调动作和冲突',
    examples: ['一剑封喉', '绝地反击']
  },
  {
    id: 'network_quote',
    name: '引文体',
    category: 'network',
    description: '以引用或独白为章节标题',
    examples: ['"一切幸福的家庭都是相似的"', '"call me Ishmael"']
  },
  {
    id: 'network_hint',
    name: '暗示型',
    category: 'network',
    description: '以暗示手法引发好奇心',
    examples: ['那个秘密', '真相大白']
  },
  {
    id: 'network_passionate',
    name: '中二热血型',
    category: 'network',
    description: '热血少年感强，语感夸张有力',
    examples: ['九天雷动', '一剑斩天骄']
  },
  {
    id: 'network_minimal',
    name: '极简无标题',
    category: 'network',
    description: '仅以"第N章"或简单数字标识',
    examples: ['第7章', '第8章']
  },

  // 外国文学经典 (6种)
  {
    id: 'foreign_number',
    name: '数字简约型',
    category: 'foreign',
    description: '仅以Chapter+数字标注，简约至极',
    examples: ['Chapter One', 'Chapter 2']
  },
  {
    id: 'foreign_theme',
    name: '主题概括型',
    category: 'foreign',
    description: '以短语概括该章核心事件或主题',
    examples: ['鸡鸣', '南塔基特']
  },
  {
    id: 'foreign_metaphor',
    name: '诗意隐喻型',
    category: 'foreign',
    description: '富有诗意与想象力的隐喻标题',
    examples: ['兔子洞', '泪水池']
  },
  {
    id: 'foreign_time_location',
    name: '时间/地点标识型',
    category: 'foreign',
    description: '以时间节点或地点场景标记章节',
    examples: ['1820年冬', '巴黎']
  },
  {
    id: 'foreign_perspective',
    name: '人物视角型',
    category: 'foreign',
    description: '以人物名字或视角作为章节标题',
    examples: ['于连', '爱玛']
  },
  {
    id: 'foreign_reference',
    name: '互文致敬型',
    category: 'foreign',
    description: '引用其他文学经典作为章节标题',
    examples: ['红与黑', '洛丽塔']
  }
]

const currentCategoryStyles = computed(() => {
  return titleStyles.filter(s => s.category === activeCategory.value)
})

function selectStyle(style) {
  if (selectedStyleId.value === style.id) {
    // 取消选择
    selectedStyleId.value = ''
    selectedStyleName.value = ''
  } else {
    selectedStyleId.value = style.id
    selectedStyleName.value = style.name
  }
}

function clearSelection() {
  selectedStyleId.value = ''
  selectedStyleName.value = ''
}

function confirmSelection() {
  if (!selectedStyleId.value) return

  emit('confirm', {
    styleId: selectedStyleId.value,
    styleName: selectedStyleName.value
  })

  dialogVisible.value = false
}

// 恢复之前的选择
watch(() => props.visible, (val) => {
  if (val) {
    if (props.initialStyleId) {
      selectedStyleId.value = props.initialStyleId
      const style = titleStyles.find(s => s.id === props.initialStyleId)
      selectedStyleName.value = style?.name || ''
      // 切换到对应分类
      if (style?.category) {
        activeCategory.value = style.category
      }
    } else {
      selectedStyleId.value = ''
      selectedStyleName.value = ''
    }
  }
})
</script>

<style lang="scss">
/* 非scoped：el-dialog会teleport内容到body，scoped样式会失效 */
.title-style-selector {
  .category-tabs {
    margin-bottom: 16px;
    overflow-x: auto;
  }

  .style-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 10px;
    max-height: 400px;
    overflow-y: auto;
    padding: 4px;
  }

  .style-card {
    padding: 12px;
    border: 2px solid #e4e7ed;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;

    &::after {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: radial-gradient(circle at center, rgba(230, 162, 60, 0.08) 0%, transparent 70%);
      opacity: 0;
      transition: opacity 0.3s;
      pointer-events: none;
    }

    &:hover {
      border-color: #e6a23c;
      box-shadow: 0 4px 16px rgba(230, 162, 60, 0.2);
      transform: translateY(-2px);

      &::after { opacity: 1; }
    }

    &:active {
      transform: translateY(0) scale(0.98);
    }

    &.selected {
      border-color: #e6a23c;
      background: linear-gradient(135deg, #fdf6ec 0%, #faecd8 100%);
      box-shadow: 0 2px 12px rgba(230, 162, 60, 0.3);
      animation: titleSelectPulse 0.4s ease;
    }

    .style-check {
      position: absolute;
      top: 6px;
      right: 6px;
      color: #e6a23c;
      font-size: 18px;
      animation: checkPop 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }

    .style-name {
      margin: 0 0 4px;
      font-size: 14px;
      font-weight: 600;
      color: #303133;
    }

    .style-desc {
      margin: 0 0 6px;
      font-size: 12px;
      color: #606266;
      line-height: 1.5;
    }

    .style-examples {
      font-size: 11px;
      color: #909399;
      line-height: 1.6;

      .example-label { margin-right: 2px; }

      .example-text {
        margin-right: 4px;
        font-style: italic;
      }
    }
  }

  .selected-preview {
    margin-top: 12px;

    .preview-content {
      display: flex;
      align-items: center;
      gap: 12px;
    }
  }
}

@keyframes titleSelectPulse {
  0% { box-shadow: 0 0 0 0 rgba(230, 162, 60, 0.4); }
  70% { box-shadow: 0 0 0 8px rgba(230, 162, 60, 0); }
  100% { box-shadow: 0 2px 12px rgba(230, 162, 60, 0.3); }
}

@keyframes checkPop {
  0% { transform: scale(0); }
  50% { transform: scale(1.3); }
  100% { transform: scale(1); }
}
</style>
