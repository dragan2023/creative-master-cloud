<template>
  <!-- 核心描述 -->
  <el-form-item prop="ip_description">
    <template #label>
      <span style="font-size: 16px; font-weight: 600;">IP角色描述</span>
      <el-tag type="danger" size="small" style="margin-left: 8px;">必填</el-tag>
    </template>
    <div class="description-input-wrapper">
      <el-input
        v-model="form.ip_description"
        type="textarea"
        :rows="6"
        placeholder="请用一段话描述你想要创作的IP角色，AI将自动解析并补足所有必要信息。&#10;&#10;示例：一只生活在古代砚台里的小墨灵，像一团会动的墨汁，有时凝固成小猫形状，从王羲之洗笔的墨池里诞生，想找到自己的第一笔主人。&#10;&#10;描述越详细，AI生成的角色越符合你的预期。可以包含：角色名称、外形特征、性格特点、背景故事、特殊能力等。"
      />
      <div class="optimize-actions">
        <el-button 
          type="primary" 
          text
          :loading="optimizing && optimizeTarget === 'ip_description'"
          :disabled="!form.ip_description || form.ip_description.length < 10"
          @click="$emit('optimize', 'ip_description')"
        >
          <el-icon><MagicStick /></el-icon>
          {{ optimizing && optimizeTarget === 'ip_description' ? '优化中...' : '优化描述' }}
        </el-button>
        <span class="optimize-tip" v-if="form.ip_description && form.ip_description.length < 10">
          请至少输入10个字符
        </span>
      </div>
    </div>
  </el-form-item>
  
  <el-divider content-position="left">补充设置（可选）</el-divider>
  
  <!-- 目标平台 + 参考IP -->
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="目标平台" prop="target_platform">
        <el-select v-model="form.target_platform" placeholder="选择目标平台" style="width: 100%" clearable>
          <el-option label="漫画" value="漫画" />
          <el-option label="动画" value="动画" />
          <el-option label="游戏" value="游戏" />
          <el-option label="周边产品" value="周边产品" />
          <el-option label="短视频" value="短视频" />
          <el-option label="综合（多平台）" value="综合" />
        </el-select>
        <div class="form-tip">选择IP的主要开发方向</div>
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="参考IP" prop="reference_ip">
        <el-input 
          v-model="form.reference_ip" 
          placeholder="如：宝可梦、初音未来、熊本熊"
          clearable
        />
        <div class="form-tip">借鉴风格的知名IP（可选）</div>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 商业目标 -->
  <el-row :gutter="20">
    <el-col :span="24">
      <el-form-item label="商业目标" prop="commercial_goal">
        <el-input 
          v-model="form.commercial_goal" 
          placeholder="如：品牌代言、周边开发、内容IP化、游戏角色设计等"
          clearable
        />
        <div class="form-tip">IP的商业化方向（可选）</div>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 其他特殊要求 -->
  <el-row :gutter="20">
    <el-col :span="24">
      <el-form-item label="其他特殊要求" prop="custom_requirements">
        <el-input
          v-model="form.custom_requirements"
          type="textarea"
          :rows="2"
          placeholder="如有其他特殊要求，请在此说明（可选）"
        />
      </el-form-item>
    </el-col>
  </el-row>
</template>

<script setup>
import { MagicStick } from '@element-plus/icons-vue'

defineProps({
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
  }
})

defineEmits([
  'update:form',
  'optimize'
])
</script>

<style lang="scss" scoped>
.description-input-wrapper {
  width: 100%;
  
  .optimize-actions {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 8px;
    padding-top: 8px;
    
    .el-button {
      padding: 4px 8px;
      font-size: 13px;
      
      .el-icon {
        margin-right: 4px;
      }
    }
    
    .optimize-tip {
      font-size: 12px;
      color: #e6a23c;
    }
  }
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-left: 10px;
}
</style>
