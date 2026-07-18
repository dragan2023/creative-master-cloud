<template>
  <!-- 文案类型选择器（多维度卡片式） -->
  <el-form-item label="文案类型" prop="doc_type" class="card-selector-form-item">
    <div class="card-selector">
      <el-tabs v-model="docTypeTab" class="doc-type-tabs">
        <el-tab-pane label="商务文书" name="business">
          <div class="card-grid">
            <div
              v-for="item in businessTypes"
              :key="item.value"
              :class="['card-item', { active: form.doc_type === item.value }]"
              @click="form.doc_type = item.value"
            >
              <el-icon :size="20"><component :is="resolveElementIcon(item.icon)" /></el-icon>
              <span>{{ item.label }}</span>
            </div>
          </div>
        </el-tab-pane>
        <el-tab-pane label="行政公文" name="admin">
          <div class="card-grid">
            <div
              v-for="item in adminTypes"
              :key="item.value"
              :class="['card-item', { active: form.doc_type === item.value }]"
              @click="form.doc_type = item.value"
            >
              <el-icon :size="20"><component :is="resolveElementIcon(item.icon)" /></el-icon>
              <span>{{ item.label }}</span>
            </div>
          </div>
        </el-tab-pane>
        <el-tab-pane label="传播文案" name="media">
          <div class="card-grid">
            <div
              v-for="item in mediaTypes"
              :key="item.value"
              :class="['card-item', { active: form.doc_type === item.value }]"
              @click="form.doc_type = item.value"
            >
              <el-icon :size="20"><component :is="resolveElementIcon(item.icon)" /></el-icon>
              <span>{{ item.label }}</span>
            </div>
          </div>
        </el-tab-pane>
        <el-tab-pane label="专业文档" name="professional">
          <div class="card-grid">
            <div
              v-for="item in professionalTypes"
              :key="item.value"
              :class="['card-item', { active: form.doc_type === item.value }]"
              @click="form.doc_type = item.value"
            >
              <el-icon :size="20"><component :is="resolveElementIcon(item.icon)" /></el-icon>
              <span>{{ item.label }}</span>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </el-form-item>

  <!-- 行业类型选择器 -->
  <el-form-item label="所属行业" prop="industry" class="card-selector-form-item">
    <div class="card-grid industry-grid">
      <div
        v-for="item in industryOptions"
        :key="item.value"
        :class="['card-item', { active: form.industry === item.value }]"
        @click="form.industry = item.value"
      >
        <el-icon :size="18"><component :is="resolveElementIcon(item.icon)" /></el-icon>
        <span>{{ item.label }}</span>
      </div>
    </div>
  </el-form-item>

  <!-- 文档长度 -->
  <el-form-item label="文档长度" prop="doc_length_custom">
    <el-input
      v-model="form.doc_length_custom"
      placeholder="自定义输入，如：5000字、10页、3-5页、2000-3000字等"
      clearable
    />
    <div class="form-tip">
      <el-text type="info" size="small">自由输入具体的字数或页数要求</el-text>
    </div>
  </el-form-item>

  <!-- 正式程度 -->
  <el-form-item label="正式程度" prop="formality">
    <el-radio-group v-model="form.formality">
      <el-radio value="正式">正式</el-radio>
      <el-radio value="半正式">半正式</el-radio>
      <el-radio value="非正式">非正式</el-radio>
    </el-radio-group>
  </el-form-item>

  <!-- 目标受众 -->
  <el-form-item label="目标受众" prop="target_audience">
    <el-select v-model="form.target_audience" placeholder="选择目标受众" style="width: 100%">
      <el-option label="上级领导/管理层" value="上级领导/管理层" />
      <el-option label="客户/合作伙伴" value="客户/合作伙伴" />
      <el-option label="下属/团队成员" value="下属/团队成员" />
      <el-option label="社会公众" value="社会公众" />
      <el-option label="特定群体" value="特定群体" />
    </el-select>
  </el-form-item>

  <!-- 语言风格 -->
  <el-form-item label="语言风格" prop="language_style">
    <el-select v-model="form.language_style" placeholder="选择语言风格" style="width: 100%">
      <el-option label="专业严谨" value="专业严谨" />
      <el-option label="简洁明了" value="简洁明了" />
      <el-option label="生动活泼" value="生动活泼" />
      <el-option label="说服力强" value="说服力强" />
      <el-option label="情感共鸣" value="情感共鸣" />
      <el-option label="数据驱动" value="数据驱动" />
    </el-select>
  </el-form-item>

  <!-- 附加要求 -->
  <el-form-item label="附加要求" prop="additional_requirements">
    <el-input
      v-model="form.additional_requirements"
      type="textarea"
      :rows="2"
      placeholder="补充其他特殊需求（可选）"
    />
  </el-form-item>

  <!-- 参考文档上传 -->
  <el-divider content-position="left">参考文档</el-divider>
  <el-form-item label="上传参考文档" prop="reference_document">
    <div class="outline-upload-wrapper">
      <el-upload
        :action="uploadUrl"
        :headers="uploadHeaders"
        :on-success="(res, file) => $emit('ref-doc-upload-success', { response: res, file })"
        :on-error="(err, file) => $emit('ref-doc-upload-error', { error: err, file })"
        :on-progress="(event) => $emit('ref-doc-progress', event)"
        :before-upload="beforeReferenceDocUpload"
        :show-file-list="false"
        accept=".txt,.md,.doc,.docx,.pdf,.xlsx"
        :disabled="uploadingRefDoc"
      >
        <el-button type="primary" text :loading="uploadingRefDoc">
          <el-icon v-if="!uploadingRefDoc"><Upload /></el-icon>
          {{ uploadingRefDoc ? '上传中...' : (form.reference_document ? '重新上传' : '上传参考文档（可选）') }}
        </el-button>
      </el-upload>
      <!-- 上传进度 -->
      <div v-if="uploadingRefDoc" class="upload-progress">
        <el-progress :percentage="refDocUploadProgress" :stroke-width="6" />
      </div>
      <!-- 已上传文件显示 -->
      <div v-if="form.reference_document && !uploadingRefDoc" class="uploaded-file-info">
        <el-tag type="success" closable @close="$emit('remove-ref-doc')">
          <el-icon><Document /></el-icon>
          {{ form.reference_document_name || '已上传文件' }}
        </el-tag>
      </div>
      <!-- 提示 -->
      <div class="token-tip">
        <el-icon><InfoFilled /></el-icon>
        <span>支持 .txt, .md, .doc, .docx, .pdf, .xlsx 格式，文件字符数量越多消耗的token越多。上传的文档将作为创作的核心参考资料，权重高于其他输入参数。</span>
      </div>
    </div>
  </el-form-item>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Document, Edit, Notebook,
  Money, Files, UserFilled, List,
  Medal, TrendCharts, Checked, ChatLineSquare,
  Message, Present, Promotion, Reading,
  Management, Tickets, Share, ReadingLamp,
  Monitor, FirstAidKit, Setting, ShoppingCart,
  OfficeBuilding, Dish, Van, Sunny, Apple,
  Film, Stamp, CaretRight, Service,
  Upload, InfoFilled
} from '@element-plus/icons-vue'
import { resolveElementIcon } from '@/utils/elementIcons'

const props = defineProps({
  form: {
    type: Object,
    required: true
  },
  optimizing: {
    type: Boolean,
    default: false
  },
  optimizeTarget: {
    type: String,
    default: ''
  },
  uploadUrl: {
    type: String,
    required: true
  },
  uploadHeaders: {
    type: Object,
    required: true
  },
  uploadingRefDoc: {
    type: Boolean,
    default: false
  },
  refDocUploadProgress: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits([
  'update:form',
  'optimize',
  'ref-doc-upload-success',
  'ref-doc-upload-error',
  'ref-doc-progress',
  'remove-ref-doc'
])

// 初始化默认值（仅在字段为空时设置，避免覆盖已保存的数据）
onMounted(() => {
  if (!props.form.target_audience) props.form.target_audience = '上级领导/管理层'
  if (!props.form.language_style) props.form.language_style = '专业严谨'
  if (!props.form.formality) props.form.formality = '半正式'
})

// 上传前验证（参考文档 - 支持更多格式）
const beforeReferenceDocUpload = (file) => {
  const allowedExtensions = ['.txt', '.md', '.doc', '.docx', '.pdf', '.xlsx']
  const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  
  if (!allowedExtensions.includes(fileExtension)) {
    ElMessage.error('只支持上传 .txt, .md, .doc, .docx, .pdf, .xlsx 格式的文件！')
    return false
  }
  if (file.size / 1024 / 1024 > 100) {
    ElMessage.error('文件大小不能超过100MB！')
    return false
  }
  return true
}

const docTypeTab = ref('business')

// 商务文书 (6)
const businessTypes = [
  { label: '商业计划书', value: '商业计划书', icon: 'Document' },
  { label: '财务报表', value: '财务报表', icon: 'Money' },
  { label: '标书', value: '标书', icon: 'Files' },
  { label: '市场调研报告', value: '市场调研报告', icon: 'TrendCharts' },
  { label: '可行性分析报告', value: '可行性分析报告', icon: 'Checked' },
  { label: '合同/协议', value: '合同/协议', icon: 'Edit' },
]

// 行政公文 (6)
const adminTypes = [
  { label: '会议纪要', value: '会议纪要', icon: 'Notebook' },
  { label: '通知/公告', value: '通知/公告', icon: 'ChatLineSquare' },
  { label: '工作总结', value: '工作总结', icon: 'List' },
  { label: '述职报告', value: '述职报告', icon: 'Medal' },
  { label: '规章制度', value: '规章制度', icon: 'Management' },
  { label: '培训方案', value: '培训方案', icon: 'Reading' },
]

// 传播文案 (5)
const mediaTypes = [
  { label: '演讲稿', value: '演讲稿', icon: 'Promotion' },
  { label: '新闻稿', value: '新闻稿', icon: 'Message' },
  { label: '邀请函', value: '邀请函', icon: 'Present' },
  { label: '感谢信/道歉信', value: '感谢信/道歉信', icon: 'Edit' },
  { label: '社交媒体文案', value: '社交媒体文案', icon: 'Share' },
]

// 专业文档 (4)
const professionalTypes = [
  { label: '求职信/简历', value: '求职信/简历', icon: 'UserFilled' },
  { label: '产品说明书', value: '产品说明书', icon: 'Document' },
  { label: '活动策划方案', value: '活动策划方案', icon: 'Tickets' },
  { label: '学术/白皮书', value: '学术/白皮书', icon: 'ReadingLamp' },
]

// 行业 (16)
const industryOptions = [
  { label: '金融/保险/证券', value: '金融/保险/证券', icon: 'Money' },
  { label: '信息技术/互联网', value: '信息技术/互联网', icon: 'Monitor' },
  { label: '教育培训', value: '教育培训', icon: 'Reading' },
  { label: '医疗健康/制药', value: '医疗健康/制药', icon: 'FirstAidKit' },
  { label: '制造业/工业', value: '制造业/工业', icon: 'Setting' },
  { label: '零售/电商', value: '零售/电商', icon: 'ShoppingCart' },
  { label: '房地产/建筑', value: '房地产/建筑', icon: 'OfficeBuilding' },
  { label: '法律/咨询', value: '法律/咨询', icon: 'Document' },
  { label: '餐饮/酒店', value: '餐饮/酒店', icon: 'Dish' },
  { label: '交通/物流', value: '交通/物流', icon: 'Van' },
  { label: '能源/环保', value: '能源/环保', icon: 'Sunny' },
  { label: '农业/食品', value: '农业/食品', icon: 'Apple' },
  { label: '文化传媒/广告', value: '文化传媒/广告', icon: 'Film' },
  { label: '政府/公共事业', value: '政府/公共事业', icon: 'Stamp' },
  { label: '汽车/出行', value: '汽车/出行', icon: 'CaretRight' },
  { label: '游戏/娱乐', value: '游戏/娱乐', icon: 'Service' }
]
</script>

<style lang="scss" scoped>
.card-selector-form-item {
  :deep(.el-form-item__content) {
    width: 100%;
  }
}

.card-selector {
  width: 100%;

  .doc-type-tabs {
    :deep(.el-tabs__header) {
      margin-bottom: 12px;
    }
  }
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;

  &.industry-grid {
    grid-template-columns: repeat(4, 1fr);
  }

  .card-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 12px 8px;
    border: 1.5px solid #e4e7ed;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    background: #fff;
    text-align: center;
    min-height: 64px;

    .el-icon {
      color: #909399;
      transition: color 0.2s;
    }

    span {
      font-size: 13px;
      color: #606266;
      line-height: 1.3;
      transition: color 0.2s;
    }

    &:hover {
      border-color: #2D8CF0;
      background: rgba(45, 140, 240, 0.05);

      .el-icon {
        color: #2D8CF0;
      }
    }

    &.active {
      border-color: #2D8CF0;
      background: rgba(45, 140, 240, 0.1);
      box-shadow: 0 2px 8px rgba(45, 140, 240, 0.15);

      .el-icon {
        color: #2D8CF0;
      }

      span {
        color: #2D8CF0;
        font-weight: 500;
      }
    }
  }
}

.outline-upload-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
  
  .upload-progress {
    width: 100%;
    max-width: 300px;
  }
  
  .uploaded-file-info {
    display: flex;
    align-items: center;
    
    .el-tag {
      display: flex;
      align-items: center;
      gap: 4px;
      
      .el-icon {
        margin-right: 4px;
      }
    }
  }
  
  .token-tip {
    display: flex;
    align-items: flex-start;
    gap: 4px;
    margin-top: 4px;
    font-size: 12px;
    color: #909399;
    line-height: 1.4;
    
    .el-icon {
      font-size: 14px;
      flex-shrink: 0;
      margin-top: 1px;
    }
  }
}
</style>
