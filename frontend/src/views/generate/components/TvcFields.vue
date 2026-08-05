<template>
  <!-- 生成模式选择 -->
  <el-form-item label="生成模式">
    <el-radio-group v-model="form.tvc_mode">
      <el-radio value="real">
        <span>现实模式</span>
        <el-tag size="small" type="info" style="margin-left: 4px;">真人拍摄</el-tag>
      </el-radio>
      <el-radio value="virtual">
        <span>虚拟模式</span>
        <el-tag size="small" type="success" style="margin-left: 4px;">AI生成</el-tag>
      </el-radio>
    </el-radio-group>
    <div class="form-tip">
      <el-text type="info" size="small">虚拟模式将简化分镜复杂度，更适合AI视频生成</el-text>
    </div>
  </el-form-item>
  
  <!-- 第一行：品牌/产品 + 广告目的 -->
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="品牌/产品名称" prop="brand_product">
        <el-input v-model="form.brand_product" placeholder="具体品牌+产品线" />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="广告目的" prop="ad_purpose">
        <el-select v-model="form.ad_purpose" placeholder="选择广告目的" style="width: 100%">
          <el-option label="品牌认知" value="品牌认知" />
          <el-option label="产品推广" value="产品推广" />
          <el-option label="节日营销" value="节日营销" />
          <el-option label="形象升级" value="形象升级" />
          <el-option label="促销活动" value="促销活动" />
          <el-option label="公益宣传" value="公益宣传" />
        </el-select>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第二行：核心信息 -->
  <el-row :gutter="20">
    <el-col :span="24">
      <el-form-item label="核心信息" prop="core_message">
        <div class="description-input-wrapper">
          <el-input
            v-model="form.core_message"
            type="textarea"
            :rows="2"
            placeholder="如果观众看完只记住一句话，你希望是什么？"
          />
          <!-- 优化按钮 -->
          <div class="optimize-actions">
            <el-button 
              type="primary" 
              text
              :loading="optimizing && optimizeTarget === 'core_message'"
              :disabled="!form.core_message || form.core_message.length < 5"
              @click="$emit('optimize', 'core_message')"
            >
              <el-icon><MagicStick /></el-icon>
              {{ optimizing && optimizeTarget === 'core_message' ? '优化中...' : '优化输入' }}
            </el-button>
            <span class="optimize-tip" v-if="form.core_message && form.core_message.length < 5">
              请至少输入5个字符
            </span>
          </div>
        </div>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第三行：受众特征 + 投放平台 -->
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="受众特征" prop="audience_profile">
        <el-input
          v-model="form.audience_profile"
          type="textarea"
          :rows="3"
          placeholder="年龄+性别+学历+职业+收入+地域&#10;如：25-45岁+女性+本科+中产家庭+月收入15K-30K+一二线城市"
        />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="投放平台" prop="broadcast_platform">
        <el-select v-model="form.broadcast_platform" placeholder="选择投放平台" style="width: 100%">
          <el-option label="电视台-央视" value="电视台-央视" />
          <el-option label="电视台-卫视" value="电视台-卫视" />
          <el-option label="电视台-地方台" value="电视台-地方台" />
          <el-option label="视频平台-爱奇艺" value="视频平台-爱奇艺" />
          <el-option label="视频平台-腾讯视频" value="视频平台-腾讯视频" />
          <el-option label="视频平台-优酷" value="视频平台-优酷" />
          <el-option label="视频平台-芒果TV" value="视频平台-芒果TV" />
          <el-option label="视频平台-B站" value="视频平台-B站" />
          <el-option label="网络贴片广告" value="网络贴片广告" />
          <el-option label="户外大屏-商圈" value="户外大屏-商圈" />
          <el-option label="户外大屏-机场" value="户外大屏-机场" />
          <el-option label="户外大屏-高铁站" value="户外大屏-高铁站" />
          <el-option label="电梯广告" value="电梯广告" />
          <el-option label="影院映前广告" value="影院映前广告" />
          <el-option label="社交媒体-抖音" value="社交媒体-抖音" />
          <el-option label="社交媒体-快手" value="社交媒体-快手" />
          <el-option label="社交媒体-视频号" value="社交媒体-视频号" />
        </el-select>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第四行：风格调性 -->
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="风格调性" prop="style_tone">
        <el-select v-model="form.style_tone" placeholder="选择风格" style="width: 100%">
          <el-option label="温情走心" value="温情走心" />
          <el-option label="幽默搞怪" value="幽默搞怪" />
          <el-option label="视觉冲击" value="视觉冲击" />
          <el-option label="极简留白" value="极简留白" />
          <el-option label="功能直给" value="功能直给" />
          <el-option label="史诗大气" value="史诗大气" />
          <el-option label="悬疑烧脑" value="悬疑烧脑" />
          <el-option label="热血励志" value="热血励志" />
          <el-option label="复古怀旧" value="复古怀旧" />
          <el-option label="科技感" value="科技感" />
          <el-option label="高级感" value="高级感" />
          <el-option label="纪实风格" value="纪实风格" />
        </el-select>
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="广告时长" prop="duration">
        <el-input v-model="form.duration" placeholder="输入时长秒数，如：15、30、60、90" />
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 第五行：AI视频生成选项 -->
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="生成AI视频提示" prop="generate_ai_prompt_tvc">
        <el-switch
          v-model="form.generate_ai_prompt_tvc"
          active-text="是"
          inactive-text="否"
        />
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item label="AI视频平台" prop="ai_platforms_tvc">
        <el-select v-model="form.ai_platforms_tvc" placeholder="选择AI视频平台" style="width: 100%">
          <el-option label="Seedance 2.0" value="Seedance 2.0" />
          <el-option label="MiniMax H3" value="MiniMax H3" />
        </el-select>
        <div class="form-tip">Seedance 2.0 与 MiniMax H3 均支持多模态参考（图片/音频素材）</div>
      </el-form-item>
    </el-col>
  </el-row>
  
  <!-- 画幅尺寸 + 参考视频URL -->
  <el-row :gutter="20">
    <el-col :span="12">
      <el-form-item label="画幅尺寸" prop="aspect_ratio_tvc">
        <el-select v-model="form.aspect_ratio_tvc" placeholder="选择画幅比例" style="width: 100%" allow-create filterable>
          <el-option label="16:9 横屏（电视/网络视频）" value="16:9" />
          <el-option label="9:16 竖屏（手机/社交媒体）" value="9:16" />
          <el-option label="1:1 方形（信息流）" value="1:1" />
          <el-option label="21:9 影院宽屏" value="21:9" />
          <el-option label="3:4 竖屏" value="3:4" />
          <el-option label="4:3 标清" value="4:3" />
        </el-select>
        <div class="form-tip">如：16:9横屏、9:16竖屏、21:9影院宽屏，可自定义输入</div>
      </el-form-item>
    </el-col>
    <el-col :span="12">
      <el-form-item prop="reference_video">
        <template #label>
          <span>参考视频</span>
          <el-tag type="warning" size="small" style="margin-left: 8px;">仅支持多模态模型</el-tag>
        </template>
        <el-input
          v-model="form.reference_video"
          placeholder="输入参考视频URL（可选）"
        />
        <div class="form-tip">URL需要资料直链，推荐使用图床网站获取直链</div>
      </el-form-item>
    </el-col>
  </el-row>
</template>

<script setup>
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
.form-tip {
  font-size: 12px;
  color: #909399;
  margin-left: 10px;
}

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
</style>
