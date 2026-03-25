<template>
  <div class="generate-form-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-top-row">
        <el-button text @click="router.push('/generate')">
          <el-icon><ArrowLeft /></el-icon>
          返回选择
        </el-button>
        <div class="header-actions">
          <el-button size="small" @click="exportConfig">
            <el-icon><Download /></el-icon>
            导出配置
          </el-button>
          <el-button size="small" @click="triggerImport">
            <el-icon><Upload /></el-icon>
            导入配置
          </el-button>
          <input ref="importInputRef" type="file" accept=".json" style="display:none" @change="importConfig" />
        </div>
      </div>
      <div class="header-info">
        <el-icon :size="32" :style="{ color: currentModule?.color }">
          <component :is="currentModule?.icon" />
        </el-icon>
        <h1>{{ currentModule?.title }}</h1>
      </div>
      <p>{{ currentModule?.description }}</p>
    </div>
    
    <!-- 主体区域：左右分栏 -->
    <div class="main-container">
      <!-- 左侧：表单区域 -->
      <div class="left-panel">
        <div class="form-container">
          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-position="top"
            size="large"
          >
        <!-- 基本信息 -->
        <div class="form-section">
          <h3>基本信息</h3>
          
          <el-form-item label="标题/主题" prop="title">
            <el-input
              v-model="form.title"
              placeholder="请输入创意标题或主题"
            />
          </el-form-item>
          
          <el-form-item v-if="type !== 'print-ad' && type !== 'tvc'" label="目标受众" prop="target_audience">
            <el-input
              v-model="form.target_audience"
              placeholder="如：18-25岁年轻人"
            />
          </el-form-item>
        </div>
        
        <!-- 内容要求 -->
        <div class="form-section">
          <h3>内容要求</h3>
          
          <!-- 原创IP计划模块不显示此字段，使用独立的ip_description字段 -->
          <el-form-item v-if="type !== 'original-ip'" :label="type === 'script' || type === 'novel' ? '故事梗概' : '详细描述'" prop="description">
            <div class="description-input-wrapper">
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="4"
                :placeholder="type === 'script' ? '请描述故事的主要内容，包括背景设定、核心冲突、人物关系等' : type === 'novel' ? '请描述小说的故事梗概，包括世界观、主线剧情、人物关系等' : '请详细描述您的创意需求，包括背景、目标、关键元素等'"
              />
              <!-- 优化按钮 -->
              <div class="optimize-actions">
                <el-button 
                  type="primary" 
                  text
                  :loading="optimizing && optimizeTarget === 'description'"
                  :disabled="!form.description || form.description.length < 5"
                  @click="handleOptimizePrompt('description')"
                >
                  <el-icon><MagicStick /></el-icon>
                  {{ optimizing && optimizeTarget === 'description' ? '优化中...' : '优化输入' }}
                </el-button>
                <span class="optimize-tip" v-if="form.description && form.description.length < 5">
                  请至少输入5个字符
                </span>
              </div>
            </div>
          </el-form-item>
          
          <!-- ========== 短视频模块特殊字段 ========== -->
          <template v-if="type === 'short-video'">
            <!-- 生成模式选择（置顶） -->
            <el-form-item label="生成模式">
              <el-radio-group v-model="form.video_mode" @change="handleVideoModeChange">
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
                <span v-if="form.video_mode === 'real'">现实模式：生成详细分镜拍摄脚本，适合真人演绎拍摄</span>
                <span v-else>虚拟模式：生成简洁分镜剧情描述，适合AI视频生成流程</span>
              </div>
            </el-form-item>
            
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="视频时长" prop="duration">
                  <el-input
                    v-model="form.duration"
                    placeholder="如：15秒、30秒、60秒、3分钟"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="目标平台" prop="platform">
                  <el-select v-model="form.platform" placeholder="选择平台" style="width: 100%">
                    <el-option label="抖音" value="douyin" />
                    <el-option label="快手" value="kuaishou" />
                    <el-option label="视频号" value="weixin" />
                    <el-option label="B站" value="bilibili" />
                    <el-option label="小红书" value="xiaohongshu" />
                    <el-option label="YouTube Shorts" value="youtube" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            
            <!-- 风格类型（多选两级）- 直观一览式选择 -->
            <el-form-item label="风格类型">
              <div class="style-selector-grid">
                <div class="style-tip-text">可多选一级或二级选项，选一级即代表该分类，选二级则更精确</div>
                <div class="style-groups-container">
                  <div v-for="group in styleTypes" :key="group.name" class="style-group">
                    <div class="style-group-header">
                      <el-checkbox
                        v-model="form.style_types_level1"
                        :label="group.name"
                      >
                        <strong>{{ group.name }}</strong>
                      </el-checkbox>
                    </div>
                    <div class="style-group-children">
                      <el-checkbox
                        v-for="child in group.children"
                        :key="child"
                        v-model="form.style_types"
                        :label="child"
                        size="small"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </el-form-item>
            
            <!-- AI视频生成提示（仅虚拟模式显示） -->
            <el-form-item v-if="form.video_mode === 'virtual'" label="生成AI视频提示">
              <el-radio-group v-model="form.generate_ai_prompt">
                <el-radio :value="true">是</el-radio>
                <el-radio :value="false">否</el-radio>
              </el-radio-group>
              <span class="form-tip">选择"是"将额外生成适用于AI视频生成平台的提示词</span>
            </el-form-item>
            
            <el-form-item v-if="form.video_mode === 'virtual' && form.generate_ai_prompt" label="AI视频生成平台">
              <el-checkbox-group v-model="form.ai_platforms">
                <el-checkbox label="seedance2">Seedance 2</el-checkbox>
                <el-checkbox label="sora2">Sora 2</el-checkbox>
                <el-checkbox label="veo3">Veo 3.1</el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            
            <!-- 分镜图提示词（仅虚拟模式显示） -->
            <el-form-item v-if="form.video_mode === 'virtual'" label="生成分镜图提示词">
              <el-radio-group v-model="form.generate_storyboard_images">
                <el-radio :value="true">是</el-radio>
                <el-radio :value="false">否</el-radio>
              </el-radio-group>
              <span class="form-tip">为每个分镜生成AI绘图提示词，用于制作参考图</span>
            </el-form-item>
            
            <!-- 参考视频URL -->
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
            
            <!-- 参考资料上传 -->
            <el-form-item prop="reference_materials_file">
              <template #label>
                <span>参考资料</span>
                <el-tooltip content="上传包含创作参考素材的文本文件，AI将参考这些内容生成脚本" placement="top">
                  <el-icon style="margin-left: 4px; cursor: help;"><QuestionFilled /></el-icon>
                </el-tooltip>
              </template>
              <div class="outline-upload-wrapper">
                <el-upload
                  :action="uploadUrl"
                  :headers="uploadHeaders"
                  :on-success="handleReferenceMaterialsUploadSuccess"
                  :on-error="handleReferenceMaterialsUploadError"
                  :before-upload="beforeReferenceMaterialsUpload"
                  :show-file-list="false"
                  accept=".txt,.md,.doc,.docx,.pdf"
                  :disabled="uploading_reference_materials"
                >
                  <el-button type="primary" text :loading="uploading_reference_materials">
                    <el-icon v-if="!uploading_reference_materials"><Upload /></el-icon>
                    {{ uploading_reference_materials ? '上传中...' : (form.reference_materials ? '重新上传' : '上传参考资料（可选）') }}
                  </el-button>
                </el-upload>
                <!-- 上传进度 -->
                <div v-if="uploading_reference_materials" class="upload-progress">
                  <el-progress :percentage="reference_materials_upload_progress" :stroke-width="6" />
                </div>
                <!-- 已上传文件显示 -->
                <div v-if="form.reference_materials && !uploading_reference_materials" class="uploaded-file-info">
                  <el-tag type="success" closable @close="removeReferenceMaterialsFile">
                    <el-icon><Document /></el-icon>
                    {{ form.reference_materials_name || '已上传文件' }}
                  </el-tag>
                </div>
                <!-- Token 消耗提示 -->
                <div class="token-tip">
                  <el-icon><InfoFilled /></el-icon>
                  <span>支持 .txt, .md, .doc, .docx, .pdf 格式，文件内容将作为AI创作的参考素材</span>
                </div>
              </div>
            </el-form-item>
            
            <!-- 运营相关变量 -->
            <el-divider content-position="left">运营设置（自定义变量）</el-divider>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="账号调性" prop="account_tone">
                  <el-input
                    v-model="form.account_tone"
                    placeholder="如：专业干货型、搞笑娱乐型、情感治愈型"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="目标粉丝群体" prop="target_fans">
                  <el-input
                    v-model="form.target_fans"
                    placeholder="如：18-25岁女性、职场白领、宝妈群体"
                  />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="24">
                <el-form-item label="内容定位" prop="content_position">
                  <el-input
                    v-model="form.content_position"
                    placeholder="如：知识科普、生活记录、好物推荐、情感分享、技能教学等"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </template>
          
          <!-- ========== 剧本大纲模块 ========== -->
          <template v-if="type === 'script'">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="剧集类型" prop="series_type">
                  <el-select v-model="form.series_type" placeholder="选择剧集类型" style="width: 100%" @change="handleSeriesTypeChange">
                    <el-option v-for="st in seriesTypes" :key="st" :label="st" :value="st" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="题材类型" prop="genre">
                  <el-select v-model="form.genre" placeholder="选择题材" style="width: 100%">
                    <el-option v-for="g in genres" :key="g" :label="g" :value="g" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="投放平台" prop="platform">
                  <el-select v-model="form.platform" placeholder="选择投放平台" style="width: 100%">
                    <el-option v-for="p in platforms" :key="p" :label="p" :value="p" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="集数" prop="episode_count">
                  <el-input v-model="form.episode_count" placeholder="如：24集、40集，自定义填写" />
                </el-form-item>
              </el-col>
            </el-row>
            <!-- 剧本专业配置 -->
            <el-divider content-position="left">剧本专业配置</el-divider>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="每集时长" prop="episode_duration_range">
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <el-input-number v-model="form.episode_duration_range[0]" :min="1" :max="120" :step="5" style="width: 120px;" />
                    <span style="margin: 0 8px; font-weight: 500;">-</span>
                    <el-input-number v-model="form.episode_duration_range[1]" :min="1" :max="120" :step="5" style="width: 120px;" />
                    <span style="color: #909399; font-size: 12px; margin-left: 8px;">分钟</span>
                  </div>
                  <div v-if="seriesDurationHint" class="form-tip">{{ seriesDurationHint }}</div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="场景数/集" prop="scenes_per_episode_range">
                  <el-input v-model="form.scenes_per_episode_range" placeholder="如：10-20场，留空AI自动设计" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="剧本格式" prop="format_standard">
                  <el-select v-model="form.format_standard" placeholder="选择格式标准" style="width: 100%">
                    <el-option label="标准格式" value="标准格式" />
                    <el-option label="简格式" value="简格式" />
                    <el-option label="网络平台格式" value="网络平台格式" />
                    <el-option label="短剧格式" value="短剧格式" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="对白比例" prop="dialogue_narration_ratio">
                  <el-select v-model="form.dialogue_narration_ratio" placeholder="选择对白比例" style="width: 100%">
                    <el-option label="对话为主" value="对话为主" />
                    <el-option label="均衡" value="均衡" />
                    <el-option label="叙述为主" value="叙述为主" />
                    <el-option label="动作导向" value="动作导向" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="对标作品" prop="reference_works">
                  <el-input v-model="form.reference_works" placeholder="填写对标作品名称，如《狂飙》《隐秘的角落》" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="自写大纲" prop="custom_outline_file">
                  <div class="outline-upload-wrapper">
                    <el-upload
                      :action="uploadUrl"
                      :headers="uploadHeaders"
                      :on-success="handleOutlineUploadSuccess"
                      :on-error="handleOutlineUploadError"
                      :on-progress="handleOutlineProgress"
                      :before-upload="beforeOutlineUpload"
                      :show-file-list="false"
                      accept=".txt,.md,.doc,.docx,.pdf"
                      :disabled="uploading_outline"
                    >
                      <el-button type="primary" text :loading="uploading_outline">
                        <el-icon v-if="!uploading_outline"><Upload /></el-icon>
                        {{ uploading_outline ? '上传中...' : (form.custom_outline ? '重新上传' : '上传大纲文件（可选）') }}
                      </el-button>
                    </el-upload>
                    <!-- 上传进度 -->
                    <div v-if="uploading_outline" class="upload-progress">
                      <el-progress :percentage="outline_upload_progress" :stroke-width="6" />
                    </div>
                    <!-- 已上传文件显示 -->
                    <div v-if="form.custom_outline && !uploading_outline" class="uploaded-file-info">
                      <el-tag type="success" closable @close="removeOutlineFile">
                        <el-icon><Document /></el-icon>
                        {{ form.custom_outline_name || '已上传文件' }}
                      </el-tag>
                    </div>
                    <!-- Token 消耗提示 -->
                    <div class="token-tip">
                      <el-icon><InfoFilled /></el-icon>
                      <span>文件字符数量越多，消耗的token越多</span>
                    </div>
                  </div>
                </el-form-item>
              </el-col>
            </el-row>
          </template>
          
          <!-- ========== 小说模块 ========== -->
          <template v-if="type === 'novel'">
            <!-- 第一行：篇幅与类型 -->
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="篇幅体量" prop="length">
                  <el-select v-model="form.length" placeholder="选择篇幅" style="width: 100%">
                    <el-option label="长篇（50万字+）" value="long" />
                    <el-option label="中篇（10-50万字）" value="medium" />
                    <el-option label="短篇（10万字内）" value="short" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="类型标签" prop="genre">
                  <el-select v-model="form.genre" placeholder="选择类型（可多选）" style="width: 100%" multiple>
                    <el-option label="言情" value="言情" />
                    <el-option label="悬疑推理" value="悬疑推理" />
                    <el-option label="科幻" value="科幻" />
                    <el-option label="奇幻玄幻" value="奇幻玄幻" />
                    <el-option label="历史" value="历史" />
                    <el-option label="现实题材" value="现实题材" />
                    <el-option label="轻小说" value="轻小说" />
                    <el-option label="恐怖惊悚" value="恐怖惊悚" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            
            <!-- 第二行：目标读者/平台 -->
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="目标读者/平台" prop="target_platform">
                  <el-select v-model="form.target_platform" placeholder="选择目标平台" style="width: 100%">
                    <el-option label="网文平台-起点" value="起点" />
                    <el-option label="网文平台-晋江" value="晋江" />
                    <el-option label="网文平台-番茄" value="番茄" />
                    <el-option label="实体出版" value="实体出版" />
                    <el-option label="纯个人创作" value="纯个人创作" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="基调氛围" prop="tone">
                  <el-select v-model="form.tone" placeholder="选择基调" style="width: 100%">
                    <el-option label="正剧（严肃厚重）" value="正剧" />
                    <el-option label="喜剧（轻松解压）" value="喜剧" />
                    <el-option label="虐恋催泪" value="虐恋催泪" />
                    <el-option label="爽文（逆袭打脸）" value="爽文" />
                    <el-option label="治愈温暖" value="治愈温暖" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            
            <!-- 第三行：故事主题 -->
            <el-row :gutter="20">
              <el-col :span="24">
                <el-form-item label="故事主题" prop="theme">
                  <el-input
                    v-model="form.theme"
                    type="textarea"
                    :rows="2"
                    placeholder="你想通过这个故事表达什么？——关于爱、牺牲、正义、自由、欲望、人性的探讨？"
                  />
                </el-form-item>
              </el-col>
            </el-row>
            
            <!-- 第四行：独特卖点 -->
            <el-row :gutter="20">
              <el-col :span="24">
                <el-form-item label="独特卖点" prop="unique_selling_point">
                  <el-input
                    v-model="form.unique_selling_point"
                    type="textarea"
                    :rows="2"
                    placeholder="这个故事最吸引人的钩子是什么？——高概念设定、极致人设、社会热点映射、还是烧脑谜题？"
                  />
                </el-form-item>
              </el-col>
            </el-row>
            
            <!-- 第五行：章节数 + 自写大纲 -->
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="章节数" prop="chapter_count">
                  <el-input v-model="form.chapter_count" placeholder="如：100章、200章，自定义填写" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="自写大纲" prop="custom_outline_file">
                  <div class="outline-upload-wrapper">
                    <el-upload
                      :action="uploadUrl"
                      :headers="uploadHeaders"
                      :on-success="handleOutlineUploadSuccess"
                      :on-error="handleOutlineUploadError"
                      :on-progress="handleOutlineProgress"
                      :before-upload="beforeOutlineUpload"
                      :show-file-list="false"
                      accept=".txt,.md,.doc,.docx,.pdf"
                      :disabled="uploading_outline"
                    >
                      <el-button type="primary" text :loading="uploading_outline">
                        <el-icon v-if="!uploading_outline"><Upload /></el-icon>
                        {{ uploading_outline ? '上传中...' : (form.custom_outline ? '重新上传' : '上传大纲文件（可选）') }}
                      </el-button>
                    </el-upload>
                    <!-- 上传进度 -->
                    <div v-if="uploading_outline" class="upload-progress">
                      <el-progress :percentage="outline_upload_progress" :stroke-width="6" />
                    </div>
                    <!-- 已上传文件显示 -->
                    <div v-if="form.custom_outline && !uploading_outline" class="uploaded-file-info">
                      <el-tag type="success" closable @close="removeOutlineFile">
                        <el-icon><Document /></el-icon>
                        {{ form.custom_outline_name || '已上传文件' }}
                      </el-tag>
                    </div>
                    <!-- Token 消耗提示 -->
                    <div class="token-tip">
                      <el-icon><InfoFilled /></el-icon>
                      <span>文件字符数量越多，消耗的token越多</span>
                    </div>
                  </div>
                </el-form-item>
              </el-col>
            </el-row>
          </template>
          
          <!-- ========== 平面设计模块 ========== -->
          <template v-if="type === 'print-ad'">
            <!-- 第一行：设计类别 -->
            <el-row :gutter="20">
              <el-col :span="24">
                <el-form-item label="设计类别" prop="design_category">
                  <el-select v-model="form.design_category" placeholder="选择设计类别" style="width: 100%">
                    <el-option label="Logo设计" value="logo设计" />
                    <el-option label="商业广告" value="商业广告" />
                    <el-option label="宣传单页" value="宣传单页" />
                    <el-option label="公益广告" value="公益广告" />
                    <el-option label="政府宣传" value="政府宣传" />
                    <el-option label="海报设计" value="海报设计" />
                    <el-option label="展架设计" value="展架设计" />
                    <el-option label="包装设计" value="包装设计" />
                    <el-option label="其他设计" value="其他设计" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            
            <!-- 第二行：品牌/产品 + 广告目的 -->
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="品牌/产品名称" prop="brand_product">
                  <el-input v-model="form.brand_product" placeholder="具体品牌+产品（新品牌需说明调性）" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="广告目的" prop="ad_purpose">
                  <el-input v-model="form.ad_purpose" placeholder="如：新品上市、品牌升级、促销活动等" />
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
                      placeholder="如果受众看完只记住一件事，你希望是什么？必须用一句话说清楚"
                    />
                    <!-- 优化按钮 -->
                    <div class="optimize-actions">
                      <el-button 
                        type="primary" 
                        text
                        :loading="optimizing && optimizeTarget === 'core_message'"
                        :disabled="!form.core_message || form.core_message.length < 5"
                        @click="handleOptimizePrompt('core_message')"
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
            
            <!-- 第三行：受众特征 + 接触场景 -->
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="受众特征" prop="audience_profile">
                  <el-input
                    v-model="form.audience_profile"
                    type="textarea"
                    :rows="3"
                    placeholder="年龄+性别+学历+职业+收入+地域&#10;如：25-35岁+女性+本科+白领+月收入8K-15K+一二线城市"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="接触场景" prop="contact_scene">
                  <el-input
                    v-model="form.contact_scene"
                    type="textarea"
                    :rows="3"
                    placeholder="他们通常在哪里看到这则广告？&#10;如：地铁站台、微信朋友圈、电梯间、商场中庭"
                  />
                </el-form-item>
              </el-col>
            </el-row>
            
            <!-- 第四行：风格调性 -->
            <el-row :gutter="20">
              <el-col :span="24">
                <el-form-item label="风格调性" prop="style_tone">
                  <el-select v-model="form.style_tone" placeholder="选择风格" style="width: 100%">
                    <el-option label="视觉冲击" value="视觉冲击" />
                    <el-option label="极简留白" value="极简留白" />
                    <el-option label="幽默搞怪" value="幽默搞怪" />
                    <el-option label="温情走心" value="温情走心" />
                    <el-option label="功能直给" value="功能直给" />
                    <el-option label="复古怀旧" value="复古怀旧" />
                    <el-option label="科技感" value="科技感" />
                    <el-option label="高级感" value="高级感" />
                    <el-option label="国潮风" value="国潮风" />
                    <el-option label="赛博朋克" value="赛博朋克" />
                    <el-option label="手绘插画" value="手绘插画" />
                    <el-option label="摄影写实" value="摄影写实" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            
            <!-- 第五行：文案内容 + 具体尺寸 -->
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="文案内容" prop="copy_content">
                  <el-input v-model="form.copy_content" placeholder="已有文案可直接填写（可选）" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="具体尺寸" prop="size_spec">
                  <el-input v-model="form.size_spec" placeholder="如：1080x1920px、A4、3x4m等（可选）" />
                </el-form-item>
              </el-col>
            </el-row>
            
            <!-- 第七行：发布媒介 + AI平台 -->
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="发布媒介" prop="publish_media">
                  <el-input v-model="form.publish_media" placeholder="如：微信朋友圈、地铁灯箱、户外大屏等（可选）" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="AI提示词平台" prop="ai_platforms_ad">
                  <el-select v-model="form.ai_platforms_ad" placeholder="选择AI平台" style="width: 100%">
                    <el-option label="豆包" value="豆包" />
                    <el-option label="即梦" value="即梦" />
                    <el-option label="千问" value="千问" />
                    <el-option label="Gemini" value="Gemini" />
                    <el-option label="GPT" value="GPT" />
                    <el-option label="Grok" value="Grok" />
                    <el-option label="可灵" value="可灵" />
                    <el-option label="Midjourney" value="Midjourney" />
                    <el-option label="Stable Diffusion" value="Stable Diffusion" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            
            <!-- 第八行：参考图片（多模态） -->
            <el-row :gutter="20">
              <el-col :span="24">
                <el-form-item>
                  <template #label>
                    <span>参考图片</span>
                    <el-tag type="warning" size="small" style="margin-left: 8px;">仅支持多模态模型</el-tag>
                  </template>
                  <div class="image-upload-section">
                    <el-upload
                      :action="uploadUrl"
                      :headers="uploadHeaders"
                      :on-success="handleUploadSuccess"
                      :on-error="handleUploadError"
                      :before-upload="beforeUpload"
                      :file-list="imageFileList"
                      list-type="picture-card"
                      :limit="5"
                      accept="image/png,image/jpeg,image/jpg,image/gif,image/webp"
                      multiple
                    >
                      <el-icon><Plus /></el-icon>
                      <template #tip>
                        <div class="upload-tip">支持 png/jpg/gif/webp，最大10MB，最多5张</div>
                      </template>
                    </el-upload>
                    <div class="url-input-section">
                      <el-input
                        v-model="imageUrlInput"
                        placeholder="或输入图片URL，多个用逗号分隔"
                        @blur="parseImageUrls"
                      />
                      <div class="form-tip">URL需要资料直链，推荐使用图床网站获取直链</div>
                    </div>
                  </div>
                </el-form-item>
              </el-col>
            </el-row>
          </template>
          
          <!-- ========== TVC广告模块 ========== -->
          <template v-if="type === 'tvc'">
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
                        @click="handleOptimizePrompt('core_message')"
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
                    <el-option label="可灵" value="可灵" />
                    <el-option label="Seedance 2.0" value="Seedance 2.0" />
                    <el-option label="Sora 2" value="Sora 2" />
                    <el-option label="Veo 3.1" value="Veo 3.1" />
                    <el-option label="Runway" value="Runway" />
                    <el-option label="Pika" value="Pika" />
                    <el-option label="Wan 2.2" value="Wan 2.2" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            
            <!-- 参考视频URL -->
            <el-row :gutter="20">
              <el-col :span="24">
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
          
          <!-- ========== 原创IP计划模块 ========== -->
          <template v-if="type === 'original-ip'">
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
                    @click="handleOptimizePrompt('ip_description')"
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
        </div>
        
        <!-- 知识库增强开关 -->
        <div class="form-section">
          <h3>知识库增强</h3>
          <el-form-item>
            <div class="knowledge-switch-wrapper">
              <el-switch
                v-model="enableKnowledge"
                active-text="启用知识库增强"
                inactive-text="不使用知识库"
                :loading="loadingKnowledge"
              />
              <div class="knowledge-tip" v-if="enableKnowledge">
                <el-icon><InfoFilled /></el-icon>
                <span><strong>通用知识库</strong>将默认加载，提供基础理论支持</span>
              </div>
            </div>
          </el-form-item>
          
          <!-- 知识库类别选择（启用知识库后显示） -->
          <div v-if="enableKnowledge" class="kb-category-selector">
            <!-- 垂直领域知识库 -->
            <div class="kb-category-item">
              <div class="kb-category-header">
                <el-checkbox 
                  v-model="kbCategories.vertical.enabled"
                  @change="onKbCategoryChange('vertical')"
                >
                  <span class="category-title">垂直领域知识库</span>
                  <el-tag size="small" type="info">可选</el-tag>
                </el-checkbox>
                <span class="category-desc">行业专业知识、实际案例、成品脚本、策划案等实践性资料</span>
              </div>
              <div v-if="kbCategories.vertical.enabled" class="kb-list-selector">
                <el-select
                  v-model="kbCategories.vertical.ids"
                  multiple
                  collapse-tags
                  collapse-tags-tooltip
                  placeholder="选择垂直领域知识库"
                  :loading="loadingKbByCategory.vertical"
                  style="width: 100%"
                >
                  <el-option
                    v-for="kb in kbCategories.vertical.list"
                    :key="kb.id"
                    :label="kb.name"
                    :value="kb.id"
                  />
                </el-select>
                <div v-if="kbCategories.vertical.list.length === 0 && !loadingKbByCategory.vertical" class="kb-empty-tip">
                  暂无垂直领域知识库
                </div>
              </div>
            </div>
            
            <!-- 用户专属知识库 -->
            <div class="kb-category-item">
              <div class="kb-category-header">
                <el-checkbox 
                  v-model="kbCategories.userSpecific.enabled"
                  @change="onKbCategoryChange('userSpecific')"
                >
                  <span class="category-title">用户专属知识库</span>
                  <el-tag size="small" type="success">GraphRAG</el-tag>
                </el-checkbox>
                <span class="category-desc">存储用户个性化知识，针对小众人物、专有名词、专业知识、个人经验等优化</span>
              </div>
              <div v-if="kbCategories.userSpecific.enabled" class="kb-list-selector">
                <el-select
                  v-model="kbCategories.userSpecific.ids"
                  multiple
                  collapse-tags
                  collapse-tags-tooltip
                  placeholder="选择用户专属知识库"
                  :loading="loadingKbByCategory.userSpecific"
                  style="width: 100%"
                >
                  <el-option
                    v-for="kb in kbCategories.userSpecific.list"
                    :key="kb.id"
                    :label="kb.name"
                    :value="kb.id"
                  />
                </el-select>
                <div v-if="kbCategories.userSpecific.list.length === 0 && !loadingKbByCategory.userSpecific" class="kb-empty-tip">
                  暂无用户专属知识库
                </div>
              </div>
            </div>
            
            <!-- 官方手册知识库 -->
            <div class="kb-category-item">
              <div class="kb-category-header">
                <el-checkbox 
                  v-model="kbCategories.manual.enabled"
                  @change="onKbCategoryChange('manual')"
                >
                  <span class="category-title">官方手册知识库</span>
                  <el-tag size="small" type="warning">可选</el-tag>
                </el-checkbox>
                <span class="category-desc">官方规范、标准手册、产品文档、技术文档等参考资料</span>
              </div>
              <div v-if="kbCategories.manual.enabled" class="kb-list-selector">
                <el-select
                  v-model="kbCategories.manual.ids"
                  multiple
                  collapse-tags
                  collapse-tags-tooltip
                  placeholder="选择官方手册知识库"
                  :loading="loadingKbByCategory.manual"
                  style="width: 100%"
                >
                  <el-option
                    v-for="kb in kbCategories.manual.list"
                    :key="kb.id"
                    :label="kb.name"
                    :value="kb.id"
                  />
                </el-select>
                <div v-if="kbCategories.manual.list.length === 0 && !loadingKbByCategory.manual" class="kb-empty-tip">
                  暂无官方手册知识库
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 创作辅助搜索开关 -->
        <div class="form-section">
          <h3>创作辅助搜索</h3>
          <el-form-item>
            <div class="knowledge-switch-wrapper">
              <el-switch
                v-model="enableCreativeSearch"
                active-text="启用联网搜索"
                inactive-text="不使用联网搜索"
              />
              <div class="knowledge-tip" v-if="enableCreativeSearch">
                <el-icon><InfoFilled /></el-icon>
                <span>智能搜索创作素材和背景信息，如地理、历史、文化等资料，提升创作准确性</span>
              </div>
            </div>
          </el-form-item>
          <!-- 自定义搜索关键词 -->
          <el-form-item v-if="enableCreativeSearch" label="搜索关键词">
            <el-input
              v-model="searchKeywords"
              placeholder="输入自定义搜索关键词（可选，多个关键词用逗号分隔）"
              clearable
            >
              <template #prepend>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <div class="input-tip">
              <el-icon><InfoFilled /></el-icon>
              <span>留空则系统自动分析并提取关键词；填写后将使用您指定的关键词进行精准搜索</span>
            </div>
          </el-form-item>
        </div>
        
        <!-- 实时热点开关 -->
        <div class="form-section">
          <h3>实时热点</h3>
          <el-form-item>
            <div class="knowledge-switch-wrapper">
              <el-switch
                v-model="enableTrending"
                active-text="启用实时热点"
                inactive-text="不使用热点数据"
              />
              <div class="knowledge-tip" v-if="enableTrending">
                <el-icon><InfoFilled /></el-icon>
                <span>获取<strong>微博、知乎、抖音、B站</strong>等平台实时热点数据，为创意提供灵感参考</span>
              </div>
            </div>
          </el-form-item>
        </div>
        
        <!-- 提交按钮 -->
        <div class="form-actions">
          <el-button @click="resetForm">重置</el-button>
          <!-- 两阶段大纲生成模式：显示导入按钮 -->
          <el-button v-if="useTwoStageMode" @click="openImportDialog">
            <el-icon><Upload /></el-icon>
            导入已有大纲
          </el-button>
          <el-button type="primary" :loading="generating" @click="handleGenerate" :disabled="generating">
            <el-icon v-if="!generating"><MagicStick /></el-icon>
            {{ generating ? '生成中...' : '开始生成' }}
          </el-button>
          <el-button v-if="generating" type="danger" @click="handleStop">
            <el-icon><CircleClose /></el-icon>
            中断生成
          </el-button>
        </div>
      </el-form>
    </div>
  </div>
      
  <!-- 右侧：工作流程展示 -->
  <div class="right-panel">
    <div class="workflow-container" v-if="generating || workflowSteps.length > 0">
      <div class="workflow-header">
        <h3>
          <el-icon class="workflow-icon" :class="{ 'is-spinning': generating }"><Loading /></el-icon>
          Agent 工作流程
        </h3>
        <el-tag v-if="workflowComplete" type="success" size="small">已完成</el-tag>
        <el-tag v-else-if="generating" type="warning" size="small">执行中...</el-tag>
      </div>
      
      <div class="workflow-steps">
        <div 
          v-for="(step, index) in workflowSteps" 
          :key="step.step"
          class="workflow-step"
          :class="{
            'is-running': step.status === 'running',
            'is-done': step.status === 'done',
            'is-error': step.status === 'error'
          }"
        >
          <div class="step-icon">
            <el-icon v-if="step.status === 'running'" class="is-spinning"><Loading /></el-icon>
            <el-icon v-else-if="step.status === 'done'" color="#67C23A"><CircleCheck /></el-icon>
            <el-icon v-else-if="step.status === 'error'" color="#F56C6C"><CircleClose /></el-icon>
            <el-icon v-else><component :is="step.icon" /></el-icon>
          </div>
          <div class="step-content">
            <div class="step-message">{{ step.message }}</div>
          </div>
          <div class="step-status">
            <el-tag v-if="step.status === 'done'" type="success" size="small">完成</el-tag>
            <el-tag v-else-if="step.status === 'running'" type="warning" size="small">执行中</el-tag>
            <el-tag v-else-if="step.status === 'error'" type="danger" size="small">失败</el-tag>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 右侧空状态提示 -->
    <div class="workflow-empty" v-else>
      <el-empty description="填写表单后开始生成，工作流程将在此显示" />
    </div>
  </div>
</div>
    
<!-- 底部：生成结果 -->
<div class="result-container" v-if="showResult">
  <!-- 两阶段大纲生成：阶段指示器 -->
  <div v-if="useTwoStageMode" class="outline-stages">
    <el-steps :active="outlineStage" align-center finish-status="success">
      <el-step title="全局大纲" description="世界观、人物、结构" />
      <el-step title="审核修改" description="确认全局大纲" />
      <el-step title="单元概述" description="章节/分集概要" />
      <el-step title="完成" description="可下载或导入" />
    </el-steps>
    <div class="stage-actions">
      <!-- 阶段1：全局大纲生成中，显示中断按钮 -->
      <el-button
        v-if="outlineStage === 1 && globalOutlineGenerating"
        type="danger"
        @click="handleStop"
      >
        <el-icon><CircleClose /></el-icon>
        中断生成
      </el-button>
      <!-- 阶段2：全局大纲完成，显示继续按钮 -->
      <el-button
        v-if="outlineStage === 2"
        type="primary"
        @click="handleGenerateUnitSummaries"
        :loading="unitSummariesGenerating"
      >
        确认全局大纲，继续生成单元概述
      </el-button>
      <!-- 阶段3：单元概述生成中，显示中断按钮 -->
      <el-button
        v-if="outlineStage === 3 && unitSummariesGenerating"
        type="danger"
        @click="cancelUnitSummariesGeneration"
      >
        <el-icon><VideoPause /></el-icon>
        中断生成
      </el-button>
      <!-- 阶段4：全部完成，显示下载按钮 -->
      <el-button
        v-if="outlineStage === 4"
        type="success"
        @click="downloadOutline"
      >
        <el-icon><Download /></el-icon>
        下载完整大纲
      </el-button>
      <el-button
        v-if="outlineStage === 4"
        @click="openStartUnitDialog"
      >
        <el-icon><Edit /></el-icon>
        从指定单元重新生成
      </el-button>
      <el-button
        v-if="outlineStage === 4"
        @click="resetTwoStageOutline"
      >
        重新开始
      </el-button>
    </div>
    
    <!-- 逻辑检测状态 -->
    <div v-if="logicChecking || logicCheckResult" class="logic-check-status">
      <div v-if="logicChecking" class="logic-checking">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在进行逻辑检测...</span>
      </div>
      <div v-else-if="logicCheckResult" class="logic-check-result">
        <div v-if="logicCheckResult.has_issues" class="has-issues">
          <el-icon><WarningFilled /></el-icon>
          <span>检测到 {{ logicCheckResult.issues?.length || 0 }} 个逻辑问题</span>
          <el-button size="small" text @click="showLogicIssuesDialog = true">
            查看详情
          </el-button>
        </div>
        <div v-else class="no-issues">
          <el-icon><CircleCheckFilled /></el-icon>
          <span>逻辑检测通过，未发现问题</span>
        </div>
      </div>
    </div>

  </div>

  <div class="result-header">
    <h3>{{ useTwoStageMode ? (outlineStage <= 2 ? '全局大纲' : '完整大纲') : '生成结果' }}</h3>
    <div class="result-meta">
      <el-tag v-if="generationDuration" type="info" size="small" class="duration-tag">
        <el-icon><Timer /></el-icon>
        耗时: {{ formatDuration(generationDuration) }}
      </el-tag>
      <div class="result-actions">
        <el-button text @click="copyResult">
          <el-icon><CopyDocument /></el-icon>
          复制
        </el-button>
        <el-button text @click="downloadResult">
          <el-icon><Download /></el-icon>
          下载
        </el-button>
        <el-button v-if="!useTwoStageMode" text @click="regenerate">
          <el-icon><Refresh /></el-icon>
          重新生成
        </el-button>
        <el-button v-if="useTwoStageMode && outlineStage > 0" text @click="resetTwoStageOutline">
          <el-icon><Refresh /></el-icon>
          重新开始
        </el-button>
      </div>
    </div>
  </div>
  
  <!-- 两阶段大纲生成：全局大纲编辑区（阶段2显示） -->
  <div v-if="useTwoStageMode && outlineStage === 2" class="global-outline-edit">
    <div class="edit-header">
      <span class="edit-tip"><el-icon><Edit /></el-icon> 您可以直接编辑全局大纲内容，修改后将用于生成单元概述</span>
      <div class="edit-actions">
        <el-button v-if="!editingGlobalOutline" type="primary" size="small" @click="startEditGlobalOutline">
          <el-icon><Edit /></el-icon> 编辑
        </el-button>
        <template v-else>
          <el-button type="success" size="small" @click="saveGlobalOutlineEdit">
            <el-icon><Check /></el-icon> 保存修改
          </el-button>
          <el-button size="small" @click="cancelEditGlobalOutline">
            <el-icon><Close /></el-icon> 取消
          </el-button>
        </template>
      </div>
    </div>
    <div class="edit-content">
      <el-input
        v-if="editingGlobalOutline"
        v-model="editingGlobalOutlineContent"
        type="textarea"
        :rows="20"
        placeholder="请输入全局大纲内容..."
      />
      <div v-else class="preview-content markdown-content" v-html="renderedGlobalOutline"></div>
    </div>
  </div>
  
  <!-- 两阶段大纲生成：单元概述列表（阶段4显示） -->
  <div v-if="useTwoStageMode && outlineStage === 4 && Object.keys(unitSummaries).length > 0" class="unit-summaries-list">
    <el-collapse>
      <el-collapse-item 
        v-for="(unit, num) in unitSummaries" 
        :key="num"
        :name="num"
      >
        <template #title>
          <div class="unit-title-wrapper">
            <span>第{{ unit.unit_number }}{{ type === 'novel' ? '章' : '集' }}：{{ unit.title }}</span>
            <el-tag v-if="unit.logic_fixed" type="success" size="small" class="fixed-tag">
              <el-icon><Check /></el-icon> 已修正
            </el-tag>
          </div>
        </template>
        <div class="unit-summary-content">
          <p v-if="editingUnitNumber !== num" :class="{ 'logic-fixed-content': unit.logic_fixed }">
            {{ unit.summary }}
          </p>
          <el-input 
            v-else
            v-model="editingUnitContent"
            type="textarea"
            :rows="4"
          />
          <div class="unit-actions">
            <el-button 
              v-if="unit.logic_fixed && editingUnitNumber !== num"
              size="small" 
              type="primary"
              text
              @click.stop="openRevisionDetail(parseInt(num))"
            >
              <el-icon><View /></el-icon> 查看修正
            </el-button>
            <el-button 
              v-if="editingUnitNumber !== num"
              size="small" 
              text 
              @click="editUnitSummary(parseInt(num))"
            >
              编辑
            </el-button>
            <template v-else>
              <el-button size="small" type="primary" @click="saveUnitSummary">保存</el-button>
              <el-button size="small" @click="cancelEditUnitSummary">取消</el-button>
            </template>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
  
  <!-- 默认渲染内容（阶段2时不显示，因为已有编辑区） -->
  <div v-if="!(useTwoStageMode && outlineStage === 2)" class="result-content markdown-content" v-html="renderedContent"></div>
</div>
  </div>

  <!-- 导入已有大纲对话框 -->
  <el-dialog
    v-model="showImportDialog"
    title="导入已有大纲"
    width="700px"
    :close-on-click-modal="false"
  >
    <div class="import-dialog-content">
      <el-radio-group v-model="importType" class="import-type-selector">
        <el-radio value="global">
          <div class="import-type-option">
            <span class="title">仅全局大纲</span>
            <span class="desc">导入全局大纲后，继续生成单元概述</span>
          </div>
        </el-radio>
        <el-radio value="full">
          <div class="import-type-option">
            <span class="title">完整大纲</span>
            <span class="desc">包含全局大纲和单元概述的完整内容</span>
          </div>
        </el-radio>
      </el-radio-group>
      
      <div class="import-tips">
        <el-icon><InfoFilled /></el-icon>
        <span v-if="importType === 'global'">
          请粘贴全局大纲内容，系统将跳过第一阶段，直接进入审核修改阶段
        </span>
        <span v-else>
          请粘贴完整大纲内容（包含全局大纲和单元概述），系统将尝试解析并跳转到完成阶段
        </span>
      </div>
      
      <el-input
        v-model="importContent"
        type="textarea"
        :rows="15"
        placeholder="请在此粘贴大纲内容..."
        class="import-textarea"
      />
    </div>
    <template #footer>
      <el-button @click="showImportDialog = false">取消</el-button>
      <el-button type="primary" @click="confirmImport">确认导入</el-button>
    </template>
  </el-dialog>

  <!-- 从指定单元开始对话框 -->
  <el-dialog
    v-model="showStartUnitDialog"
    title="从指定单元重新生成"
    width="500px"
    :close-on-click-modal="false"
  >
    <div class="start-unit-dialog-content">
      <p class="start-unit-tip">
        选择从哪个单元开始重新生成。该单元及之后的所有单元概述将被重新生成，之前的单元概述将保留。
      </p>
      <el-form-item label="起始单元编号">
        <el-input-number
          v-model="startFromUnit"
          :min="1"
          :max="type === 'novel' ? (parseInt(form.chapter_count) || 50) : (parseInt(form.episode_count) || 24)"
          :step="1"
        />
      </el-form-item>
      <p class="start-unit-warning">
        <el-icon><WarningFilled /></el-icon>
        注意：从第 {{ startFromUnit }} 单元开始的所有内容将被覆盖
      </p>
    </div>
    <template #footer>
      <el-button @click="showStartUnitDialog = false">取消</el-button>
      <el-button type="primary" @click="handleGenerateFromUnit" :loading="unitSummariesGenerating">
        开始生成
      </el-button>
    </template>
  </el-dialog>

  <!-- 逻辑问题详情对话框 -->
  <el-dialog
    v-model="showLogicIssuesDialog"
    title="逻辑问题详情"
    width="600px"
  >
    <div class="logic-issues-dialog">
      <div v-for="(issue, index) in logicCheckResult?.issues" :key="index" class="issue-item">
        <div class="issue-header">
          <el-tag :type="issue.severity === 'high' ? 'danger' : issue.severity === 'medium' ? 'warning' : 'info'">
            {{ issue.type }}
          </el-tag>
          <span class="issue-unit">单元 {{ issue.unit_number }}</span>
        </div>
        <p class="issue-description">{{ issue.description }}</p>
      </div>
    </div>
    <template #footer>
      <el-button type="primary" @click="showLogicIssuesDialog = false">确定</el-button>
    </template>
  </el-dialog>

  <!-- 修正详情对话框 -->
  <el-dialog
    v-model="showRevisionDetailDialog"
    :title="`修正详情 - 第${currentRevisionUnit ? unitSummaries[currentRevisionUnit]?.unit_number : ''}${type === 'novel' ? '章' : '集'}`"
    width="800px"
    top="5vh"
  >
    <div v-if="currentRevisionUnit && unitSummaries[currentRevisionUnit]" class="revision-detail-container">
      <!-- 修正信息 -->
      <div class="revision-info-header">
        <el-tag type="success">逻辑修正</el-tag>
        <span class="revision-stats">
          原文 <strong>{{ unitSummaries[currentRevisionUnit]?.original_summary?.length || 0 }}</strong> 字 
          → 修正后 <strong>{{ unitSummaries[currentRevisionUnit]?.revised_summary?.length || 0 }}</strong> 字
        </span>
      </div>

      <!-- 视图切换 -->
      <div class="view-switch">
        <el-radio-group v-model="revisionViewMode" size="small">
          <el-radio-button value="diff">差异对比</el-radio-button>
          <el-radio-button value="side">左右对照</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 差异对比视图 -->
      <div v-if="revisionViewMode === 'diff'" class="diff-view">
        <div class="diff-legend">
          <span class="legend-item added"><span class="legend-color"></span>新增内容</span>
          <span class="legend-item removed"><span class="legend-color"></span>删除内容</span>
          <span class="legend-item unchanged"><span class="legend-color"></span>未修改</span>
        </div>
        <div class="diff-content" v-html="getRevisionDiffHtml(unitSummaries[currentRevisionUnit])"></div>
      </div>

      <!-- 左右对照视图 -->
      <div v-else class="compare-view">
        <div class="compare-panel">
          <div class="panel-header">
            <el-tag type="warning">原始内容</el-tag>
            <span class="panel-word-count">{{ unitSummaries[currentRevisionUnit]?.original_summary?.length || 0 }} 字</span>
          </div>
          <div class="panel-content">
            <el-input
              :model-value="unitSummaries[currentRevisionUnit]?.original_summary"
              type="textarea"
              :rows="15"
              readonly
            />
          </div>
        </div>
        
        <div class="compare-panel">
          <div class="panel-header">
            <el-tag type="success">修正后内容</el-tag>
            <span class="panel-word-count">{{ unitSummaries[currentRevisionUnit]?.revised_summary?.length || 0 }} 字</span>
          </div>
          <div class="panel-content">
            <el-input
              :model-value="unitSummaries[currentRevisionUnit]?.revised_summary"
              type="textarea"
              :rows="15"
              readonly
            />
          </div>
        </div>
      </div>
    </div>
    <template #footer>
      <el-button @click="showRevisionDetailDialog = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { ElMessage } from 'element-plus'
import { CREATIVE_MODULES } from '@/config'
import { generateApi, knowledgeApi } from '@/api'
import { useApiKeyStore } from '@/stores'
import { API_BASE_URL } from '@/config'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const apiKeyStore = useApiKeyStore()
const userStore = useUserStore()

const type = computed(() => route.params.type)
const currentModule = computed(() => 
  CREATIVE_MODULES.find(m => m.key === type.value)
)

const formRef = ref()
const generating = ref(false)
const showResult = ref(false)
const generatedContent = ref('')
const currentGenerationId = ref(null)  // 当前生成记录ID
const generationDuration = ref(null)  // 生成耗时（毫秒）
const currentEventSource = ref(null)  // 当前 EventSource 连接
const currentSessionId = ref(null)  // 当前会话ID

// 工作流程状态
const workflowSteps = ref([])
const currentStep = ref('')
const workflowComplete = ref(false)

// 风格类型选择对话框
const showStyleDialog = ref(false)
const expandedStyleGroups = ref([])  // 默认展开的分组

// 大纲上传状态
const uploading_outline = ref(false)
const outline_upload_progress = ref(0)

// 提示词优化状态
const optimizing = ref(false)
const optimizeTarget = ref('')  // 当前优化的目标字段

// ==================== 两阶段大纲生成状态 ====================
// 是否使用两阶段生成模式（小说和剧本大纲）
const useTwoStageMode = computed(() => type.value === 'novel' || type.value === 'script')

// 当前阶段：0=未开始，1=全局大纲生成中，2=全局大纲完成（可编辑），3=单元概述生成中，4=全部完成
const outlineStage = ref(0)

// 全局大纲内容
const globalOutlineContent = ref('')
const globalOutlineGenerating = ref(false)

// 单元概述
const unitSummaries = ref({})
const unitSummariesGenerating = ref(false)

// 逻辑检测状态
const logicChecking = ref(false)
const logicCheckResult = ref(null)
const showLogicIssuesDialog = ref(false)

// 修正详情对话框状态
const showRevisionDetailDialog = ref(false)
const currentRevisionUnit = ref(null)  // 当前查看修正详情的单元
const revisionViewMode = ref('diff')  // 'diff' 或 'side'

// 当前编辑的单元
const editingUnitNumber = ref(null)
const editingUnitContent = ref('')

// 全局大纲编辑状态
const editingGlobalOutline = ref(false)
const editingGlobalOutlineContent = ref('')

// ==================== 灵活介入流程状态 ====================
// 导入对话框状态
const showImportDialog = ref(false)
const importType = ref('global')  // 'global' 或 'full'
const importContent = ref('')
const importingOutline = ref(false)

// 从指定单元开始生成
const startFromUnit = ref(1)
const showStartUnitDialog = ref(false)

// 渲染全局大纲（用于预览）
const renderedGlobalOutline = computed(() => {
  if (!globalOutlineContent.value) return ''
  return DOMPurify.sanitize(marked(globalOutlineContent.value))
})

// 开始编辑全局大纲
function startEditGlobalOutline() {
  editingGlobalOutlineContent.value = globalOutlineContent.value
  editingGlobalOutline.value = true
}

// 保存全局大纲编辑
function saveGlobalOutlineEdit() {
  globalOutlineContent.value = editingGlobalOutlineContent.value
  editingGlobalOutline.value = false
  ElMessage.success('全局大纲已修改')
}

// 取消编辑全局大纲
function cancelEditGlobalOutline() {
  editingGlobalOutline.value = false
  editingGlobalOutlineContent.value = ''
}

// 是否显示大纲预览对话框
const showOutlinePreviewDialog = ref(false)
const outlinePreviewContent = ref('')
const outlinePreviewTitle = ref('')

// 工作流程步骤图标映射
const stepIcons = {
  model: 'Cpu',
  prompt: 'Document',
  search: 'Search',
  knowledge: 'FolderOpened',
  preset_kb: 'Collection',
  webpage: 'Link',
  generate: 'ChatDotRound',
  evaluate: 'DataAnalysis',
  reflect: 'Refresh',
  verify: 'CircleCheck',
  correct: 'Edit',
  consistency: 'CircleCheckFilled',
  autofix: 'Tools'
}

// 风格类型配置（两级，独立选择）
const styleTypes = [
  { name: '反差', children: ['身份反差', '场景反差', '预期违背', '反转剧情'] },
  { name: '幽默/搞笑', children: ['冷幽默', '热梗模仿', '脱口秀', '无厘头', '讽刺', '谐音梗'] },
  { name: '情感共鸣', children: ['亲情', '友情', '爱情', '治愈', '励志', '怀旧', '遗憾', '孤独'] },
  { name: '知识科普', children: ['冷知识', '专业技能', '历史人文', '科学实验', '法律科普'] },
  { name: '生活Vlog', children: ['日常碎片', '学习打卡', '旅行日记', '做饭日常', '独居生活'] },
  { name: '测评/评测', children: ['数码测评', '美食探店', '好物开箱', '雷品吐槽', '实地测评'] },
  { name: '教程/教学', children: ['美妆教程', '穿搭教程', '手工DIY', '软件教学', '语言学习'] },
  { name: '采访/街访', children: ['随机采访', '情侣问答', '职场访谈', '挑战路人'] },
  { name: '才艺展示', children: ['唱歌', '跳舞', '乐器演奏', '绘画过程', '魔术表演', '杂技'] },
  { name: '解压/治愈', children: ['沉浸式整理', 'ASMR', '切肥皂', '手工制作', '风景大片'] },
  { name: '挑战/互动', children: ['挑战XX天', '粉丝点单', '投票选结局', '猜谜游戏'] },
  { name: '创意视觉', children: ['卡点变装', '运镜转场', 'AI生成画面', '特效合成'] },
  { name: '正能量/励志', children: ['凡人善举', '逆袭故事', '坚持梦想', '暖心瞬间'] },
  { name: '盘点/合集', children: ['年度盘点', 'XX种方法', '必看片单', '奇葩合集'] },
  { name: '观点/评论', children: ['热点辣评', '三观输出', '行业吐槽', '人生感悟'] },
  { name: '沉浸式体验', children: ['沉浸式回家', '沉浸式化妆', '沉浸式逛展', '第一人称视角'] }
]

const form = ref({
  title: '',
  description: '',
  target_audience: '',
  duration: '',
  platform: '',
  genre: [],
  length: '',
  ad_type: '',
  product: '',
  // 剧本大纲新增字段
  series_type: '',        // 剧集类型
  reference_works: '',    // 对标作品
  episode_count: '',      // 集数
  custom_outline: '',     // 自写大纲URL
  custom_outline_name: '', // 自写大纲文件名
  // 剧本专用配置参数（与正文生成板块对齐）
  episode_duration_range: [5, 15], // 每集时长区间（分钟）
  scenes_per_episode_range: '',    // 每集场景数范围
  format_standard: '标准格式',     // 剧本格式标准
  dialogue_narration_ratio: '均衡', // 对白与叙述比例
  target_broadcast: '',            // 目标投放平台
  // 小说新增字段
  target_platform: '',    // 目标读者/平台
  tone: '',               // 基调氛围
  theme: '',              // 故事主题
  unique_selling_point: '', // 独特卖点
  chapter_count: '',      // 章节数
  // 平面设计新增字段
  design_category: '',     // 设计类别
  brand_product: '',      // 品牌/产品名称
  ad_purpose: '',         // 广告目的
  core_message: '',       // 核心信息
  audience_profile: '',   // 受众特征
  contact_scene: '',      // 接触场景
  style_tone: '',         // 风格调性
  copy_content: '',       // 文案内容
  size_spec: '',          // 具体尺寸
  publish_media: '',      // 发布媒介
  ai_platforms_ad: '',    // AI提示词平台
  // TVC新增字段
  broadcast_platform: '', // 投放平台
  generate_ai_prompt_tvc: false, // 是否生成AI视频提示
  ai_platforms_tvc: '',   // AI视频平台
  // 多模态支持
  images: [],             // 图片URL列表
  reference_video: '',    // 参考视频URL（短视频和TVC共用）
  // 短视频新增字段
  video_mode: 'virtual',    // 生成模式，默认虚拟模式
  style_types: [],        // 二级选项
  style_types_level1: [], // 一级选项
  generate_ai_prompt: false,
  generate_storyboard_images: true, // 是否生成分镜图提示词，默认开启
  ai_platforms: [],
  // 短视频运营相关变量（自定义变量）
  account_tone: '',       // 账号调性
  target_fans: '',        // 目标粉丝群体
  content_position: '',   // 内容定位
  // 短视频参考资料上传
  reference_materials: '',     // 参考资料URL
  reference_materials_name: '', // 参考资料文件名
  // 原创IP计划字段
  ip_description: '',     // IP角色描述（核心输入）
  reference_ip: '',       // 参考IP
  commercial_goal: '',    // 商业目标
  custom_requirements: '' // 其他特殊要求
})

// 图片上传相关
const imageFileList = ref([])
const imageUrlInput = ref('')
// 上传URL：优先使用环境变量，否则使用相对路径（通过Vite代理）
const uploadUrl = computed(() => `${import.meta.env.VITE_API_BASE_URL || ''}/api/v1/generate/upload`)
const uploadHeaders = computed(() => {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
})

// 上传前验证（图片）
const beforeUpload = (file) => {
  const isImage = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'].includes(file.type)
  const isLt50M = file.size / 1024 / 1024 < 50
  
  if (!isImage) {
    ElMessage.error('只能上传图片文件！')
    return false
  }
  if (!isLt50M) {
    ElMessage.error('图片大小不能超过50MB！')
    return false
  }
  return true
}

// 上传前验证（大纲文件）
const beforeOutlineUpload = (file) => {
  const allowedExtensions = ['.txt', '.md', '.doc', '.docx', '.pdf']
  const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  
  if (!allowedExtensions.includes(fileExtension)) {
    ElMessage.error('只支持上传 .txt, .md, .doc, .docx, .pdf 格式的文件！')
    return false
  }
  if (file.size / 1024 / 1024 > 50) {
    ElMessage.error('文件大小不能超过50MB！')
    return false
  }
  // 设置上传状态
  uploading_outline.value = true
  outline_upload_progress.value = 0
  return true
}

// 大纲文件上传进度
const handleOutlineProgress = (event) => {
  outline_upload_progress.value = Math.round(event.percent)
}

// 大纲文件上传成功
const handleOutlineUploadSuccess = (response, file) => {
  uploading_outline.value = false
  outline_upload_progress.value = 100
  // 后端返回 code: 200 表示成功
  if ((response.code === 0 || response.code === 200) && response.data?.url) {
    form.value.custom_outline = response.data.url
    form.value.custom_outline_name = file.name
    ElMessage.success('大纲文件上传成功')
  } else {
    ElMessage.error(response.message || '上传失败')
  }
}

// 大纲文件上传失败
const handleOutlineUploadError = (error) => {
  uploading_outline.value = false
  outline_upload_progress.value = 0
  ElMessage.error('大纲文件上传失败：' + (error.message || '未知错误'))
}

// 删除已上传的大纲文件
const removeOutlineFile = () => {
  form.value.custom_outline = ''
  form.value.custom_outline_name = ''
  outline_upload_progress.value = 0
}

// ==================== 短视频参考资料上传功能 ====================
const uploading_reference_materials = ref(false)
const reference_materials_upload_progress = ref(0)

// 参考资料上传前处理
const beforeReferenceMaterialsUpload = (file) => {
  const allowedTypes = ['text/plain', 'text/markdown', 'application/pdf', 
    'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
  const allowedExtensions = ['.txt', '.md', '.doc', '.docx', '.pdf']
  const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
  
  if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
    ElMessage.error('只支持 .txt, .md, .doc, .docx, .pdf 格式的文件')
    return false
  }
  
  uploading_reference_materials.value = true
  reference_materials_upload_progress.value = 0
  
  // 模拟上传进度
  const progressInterval = setInterval(() => {
    if (reference_materials_upload_progress.value < 90) {
      reference_materials_upload_progress.value += 10
    }
  }, 200)
  
  // 存储interval以便在成功/失败时清除
  file.progressInterval = progressInterval
  return true
}

// 参考资料上传成功
const handleReferenceMaterialsUploadSuccess = (response, file) => {
  uploading_reference_materials.value = false
  reference_materials_upload_progress.value = 100
  
  // 清除进度模拟
  if (file.raw?.progressInterval) {
    clearInterval(file.raw.progressInterval)
  }
  
  if ((response.code === 0 || response.code === 200) && response.data?.url) {
    form.value.reference_materials = response.data.url
    form.value.reference_materials_name = file.name
    ElMessage.success('参考资料上传成功')
  } else {
    ElMessage.error(response.message || '上传失败')
  }
}

// 参考资料上传失败
const handleReferenceMaterialsUploadError = (error, file) => {
  uploading_reference_materials.value = false
  reference_materials_upload_progress.value = 0
  
  // 清除进度模拟
  if (file.raw?.progressInterval) {
    clearInterval(file.raw.progressInterval)
  }
  
  ElMessage.error('参考资料上传失败：' + (error.message || '未知错误'))
}

// 删除已上传的参考资料
const removeReferenceMaterialsFile = () => {
  form.value.reference_materials = ''
  form.value.reference_materials_name = ''
  reference_materials_upload_progress.value = 0
}

// ==================== 表单配置导出/导入功能 ====================
const importInputRef = ref(null)

// 格式化时间戳
function formatConfigTimestamp(date) {
  return date.toISOString().replace(/[-:T]/g, '').slice(0, 15)
}

// 导出表单配置
function exportConfig() {
  const config = {
    version: '1.0',
    module_type: type.value,
    created_at: new Date().toISOString(),
    form_data: { ...form.value }
  }
  
  const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${type.value}_config_${formatConfigTimestamp(new Date())}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('配置已导出')
}

// 触发导入文件选择
function triggerImport() {
  importInputRef.value?.click()
}

// 导入配置文件
async function importConfig(event) {
  const file = event.target.files[0]
  if (!file) return
  
  try {
    const text = await file.text()
    const config = JSON.parse(text)
    
    // 验证格式
    if (!config.version || !config.module_type || !config.form_data) {
      throw new Error('无效的配置文件格式')
    }
    
    // 验证模块匹配
    if (config.module_type !== type.value) {
      ElMessage.warning(`配置文件类型不匹配：${config.module_type}，当前模块：${type.value}`)
      return
    }
    
    // 填充表单（只填充存在的字段）
    Object.keys(config.form_data).forEach(key => {
      if (key in form.value) {
        form.value[key] = config.form_data[key]
      }
    })
    
    ElMessage.success('配置已导入')
  } catch (error) {
    ElMessage.error('导入失败：' + error.message)
  } finally {
    event.target.value = ''  // 重置input
  }
}

// 上传成功
const handleUploadSuccess = (response, file) => {
  // 后端返回 code: 200 表示成功
  if ((response.code === 0 || response.code === 200) && response.data?.url) {
    form.value.images.push(response.data.url)
    ElMessage.success('图片上传成功')
  } else {
    ElMessage.error(response.message || '上传失败')
  }
}

// 上传失败
const handleUploadError = (error) => {
  ElMessage.error('图片上传失败：' + (error.message || '未知错误'))
}

// 解析URL输入
const parseImageUrls = () => {
  if (imageUrlInput.value.trim()) {
    const urls = imageUrlInput.value.split(',').map(url => url.trim()).filter(url => url)
    urls.forEach(url => {
      if (!form.value.images.includes(url)) {
        form.value.images.push(url)
      }
    })
  }
}

// 知识库列表
const knowledgeBases = ref([])
const loadingKnowledge = ref(false)
const enableKnowledge = ref(false)  // 知识库开关
const enableCreativeSearch = ref(false)   // 创作辅助搜索开关
const searchKeywords = ref('')  // 用户自定义搜索关键词
const enableTrending = ref(false)  // 实时热点开关

// 知识库类别选择
const kbCategories = ref({
  vertical: { enabled: false, ids: [], list: [] },      // 垂直领域
  userSpecific: { enabled: false, ids: [], list: [] },   // 用户专属
  manual: { enabled: false, ids: [], list: [] }          // 官方手册
})
const loadingKbByCategory = ref({
  vertical: false,
  userSpecific: false,
  manual: false
})

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  description: [{ required: true, message: '请输入内容', trigger: 'blur' }],
  target_audience: [{ required: true, message: '请输入目标受众', trigger: 'blur' }],
  ip_description: [{ required: true, min: 10, message: '请至少输入10个字符的IP角色描述', trigger: 'blur' }]
}

const genres = ['爱情', '喜剧', '悬疑', '科幻', '奇幻', '动作', '剧情', '历史', '都市', '青春', '恐怖', '犯罪', '惊悚', '灾难']

// 剧集类型选项
const seriesTypes = ['院线电影', '网络电影', '长剧', '短剧', '微电影', '纪录片', '动画电影', '网络剧', '竖屏剧']

// 剧集类型对应的时长配置（与正文生成板块对齐）
const SERIES_DURATION_CONFIG = {
  '院线电影': { min: 90, max: 150, defaultMin: 100, defaultMax: 120, hint: '院线电影通常90-120分钟' },
  '网络电影': { min: 60, max: 120, defaultMin: 80, defaultMax: 100, hint: '网络电影通常80-100分钟' },
  '长剧': { min: 40, max: 60, defaultMin: 45, defaultMax: 50, hint: '长剧通常45-50分钟/集' },
  '短剧': { min: 3, max: 20, defaultMin: 5, defaultMax: 15, hint: '短剧通常5-15分钟/集' },
  '微电影': { min: 5, max: 40, defaultMin: 15, defaultMax: 30, hint: '微电影通常15-30分钟' },
  '纪录片': { min: 30, max: 60, defaultMin: 40, defaultMax: 50, hint: '纪录片通常40-50分钟/集' },
  '动画电影': { min: 80, max: 120, defaultMin: 90, defaultMax: 100, hint: '动画电影通常90-100分钟' },
  '网络剧': { min: 20, max: 50, defaultMin: 30, defaultMax: 45, hint: '网络剧通常30-45分钟/集' },
  '竖屏剧': { min: 2, max: 10, defaultMin: 3, defaultMax: 5, hint: '竖屏剧通常3-5分钟/集' }
}

// 投放平台选项
const platforms = ['央视', '地方卫视', '爱奇艺', '腾讯视频', '优酷', '芒果TV', 'B站', '抖音', '快手', '西瓜视频', '红果短剧', '河马剧场', 'Netflix', 'HBO', 'Disney+', '院线发行', '电影节展映']

// 剧集类型时长提示
const seriesDurationHint = computed(() => {
  const seriesType = form.value.series_type
  if (seriesType && SERIES_DURATION_CONFIG[seriesType]) {
    return SERIES_DURATION_CONFIG[seriesType].hint
  }
  return ''
})

// 处理剧集类型变化，自动设置时长默认值
const handleSeriesTypeChange = (value) => {
  if (value && SERIES_DURATION_CONFIG[value]) {
    const config = SERIES_DURATION_CONFIG[value]
    form.value.episode_duration_range = [config.defaultMin, config.defaultMax]
    // 根据类型自动设置格式标准
    if (value === '短剧' || value === '竖屏剧') {
      form.value.format_standard = '短剧格式'
    } else if (value === '网络剧' || value === '网络电影') {
      form.value.format_standard = '网络平台格式'
    } else {
      form.value.format_standard = '标准格式'
    }
  }
}

const renderedContent = computed(() => {
  if (!generatedContent.value) return ''
  // 使用DOMPurify净化HTML，防止XSS攻击
  return DOMPurify.sanitize(marked(generatedContent.value))
})

// 组合风格类型字符串（用于提示词嵌入）
const combinedStyleTypes = computed(() => {
  const level1 = form.value.style_types_level1 || []
  const level2 = form.value.style_types || []
  return [...level1, ...level2].join('+')
})

onMounted(async () => {
  await apiKeyStore.fetchApiKeys()
  // 加载知识库列表
  await loadKnowledgeBases()
  // 恢复保存的表单数据
  restoreFormData()
})

// 组件卸载前清理资源
onBeforeUnmount(() => {
  // 清理 EventSource 连接
  if (currentEventSource.value && currentEventSource.value.abort) {
    currentEventSource.value.abort()
    currentEventSource.value = null
  }
  // 清理生成状态
  generating.value = false
  globalOutlineGenerating.value = false
  unitSummariesGenerating.value = false
  logicChecking.value = false
})

// 加载知识库列表
async function loadKnowledgeBases() {
  loadingKnowledge.value = true
  try {
    const res = await knowledgeApi.list({ status: 'ready' })
    knowledgeBases.value = res.data || []
    // 按类别分组
    categorizeKnowledgeBases(res.data || [])
  } catch (error) {
    console.error('加载知识库列表失败:', error)
  } finally {
    loadingKnowledge.value = false
  }
}

// 按类别分组知识库
function categorizeKnowledgeBases(kbs) {
  // 垂直领域包括所有业务模块分类
  const verticalCategories = ['short-video', 'script', 'novel', 'print-ad', 'tvc']
  kbCategories.value.vertical.list = kbs.filter(kb => verticalCategories.includes(kb.category))
  kbCategories.value.userSpecific.list = kbs.filter(kb => kb.category === 'user-specific')
  kbCategories.value.manual.list = kbs.filter(kb => kb.category === 'manual')
}

// 加载指定类别的知识库
async function loadKbByCategory(category) {
  loadingKbByCategory.value[category] = true
  try {
    if (category === 'vertical') {
      // 垂直领域知识库：加载所有业务模块分类
      const verticalCategories = ['short-video', 'script', 'novel', 'print-ad', 'tvc']
      const allResults = []
      for (const cat of verticalCategories) {
        const res = await knowledgeApi.list({ status: 'ready', category: cat })
        if (res.data) {
          allResults.push(...res.data)
        }
      }
      kbCategories.value.vertical.list = allResults
    } else {
      // 其他类别直接查询
      const res = await knowledgeApi.list({ status: 'ready', category: category })
      if (category === 'userSpecific' || category === 'user-specific') {
        kbCategories.value.userSpecific.list = res.data || []
      } else if (category === 'manual') {
        kbCategories.value.manual.list = res.data || []
      }
    }
  } catch (error) {
    console.error(`加载${category}知识库失败:`, error)
  } finally {
    loadingKbByCategory.value[category] = false
  }
}

// 短视频模式切换处理
function handleVideoModeChange(mode) {
  if (mode === 'real') {
    // 现实模式：重置AI相关选项
    form.value.generate_ai_prompt = false
    form.value.generate_storyboard_images = false
    form.value.ai_platforms = []
  } else {
    // 虚拟模式：恢复默认值
    form.value.generate_storyboard_images = true
  }
}

// 提示词优化处理
async function handleOptimizePrompt(targetField = 'description') {
  // 获取要优化的文本
  let textToOptimize = ''
  if (targetField === 'description') {
    textToOptimize = form.value.description
  } else if (targetField === 'core_message') {
    textToOptimize = form.value.core_message
  } else if (targetField === 'ip_description') {
    textToOptimize = form.value.ip_description
  }
  
  // 验证输入
  if (!textToOptimize || textToOptimize.length < 5) {
    ElMessage.warning('请至少输入5个字符后再优化')
    return
  }
  
  optimizing.value = true
  optimizeTarget.value = targetField
  
  try {
    // 确定模块类型（将路由参数转换为后端模块名）
    const moduleMap = {
      'short-video': 'short_video',
      'script': 'script',
      'novel': 'novel',
      'print-ad': 'print_ad',
      'tvc': 'tvc',
      'original-ip': 'original_ip'
    }
    const module = moduleMap[type.value] || type.value
    
    const res = await generateApi.optimize({
      module: module,
      original_text: textToOptimize
    })
    
    if (res.success && res.data) {
      // 更新对应的字段
      if (targetField === 'description') {
        form.value.description = res.data.optimized_text
      } else if (targetField === 'core_message') {
        form.value.core_message = res.data.optimized_text
      } else if (targetField === 'ip_description') {
        form.value.ip_description = res.data.optimized_text
      }
      
      ElMessage.success(`优化完成！原文 ${res.data.original_length} 字 → 优化后 ${res.data.optimized_length} 字`)
    }
  } catch (error) {
    console.error('优化失败:', error)
    ElMessage.error(error.response?.data?.detail || '优化失败，请稍后重试')
  } finally {
    optimizing.value = false
    optimizeTarget.value = ''
  }
}

// 知识库类别勾选变化处理
function onKbCategoryChange(category) {
  // 如果启用该类别且列表为空，则加载该类别的知识库
  if (kbCategories.value[category].enabled && kbCategories.value[category].list.length === 0) {
    loadKbByCategory(category)
  }
  // 如果取消勾选，清空已选择的ID
  if (!kbCategories.value[category].enabled) {
    kbCategories.value[category].ids = []
  }
}

// 保存表单数据到 localStorage
function saveFormData() {
  const dataToSave = {
    form: form.value,
    timestamp: Date.now()
  }
  localStorage.setItem(`generate_form_${type.value}`, JSON.stringify(dataToSave))
}

// 从 localStorage 恢复表单数据
function restoreFormData() {
  const saved = localStorage.getItem(`generate_form_${type.value}`)
  if (saved) {
    try {
      const { form: savedForm, timestamp } = JSON.parse(saved)
      // 检查是否在24小时内保存的
      if (Date.now() - timestamp < 24 * 60 * 60 * 1000) {
        form.value = { ...form.value, ...savedForm }
        // 确保 genre 是数组格式（兼容旧数据）
        if (typeof form.value.genre === 'string') {
          form.value.genre = form.value.genre ? form.value.genre.split('、') : []
        }
      } else {
        // 过期则清除
        localStorage.removeItem(`generate_form_${type.value}`)
      }
    } catch (e) {
      console.error('恢复表单数据失败:', e)
    }
  }
}

// 监听表单变化自动保存
watch(form, () => {
  saveFormData()
}, { deep: true })

// 监听模块类型变化时恢复对应模块的表单数据
watch(type, () => {
  restoreFormData()
})

async function handleGenerate() {
  // 如果是小说或剧本大纲，使用两阶段生成
  if (useTwoStageMode.value) {
    await handleTwoStageGenerate()
    return
  }
  
  // 其他模块使用原有生成逻辑
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  
  if (!apiKeyStore.defaultKey) {
    const hasKeys = apiKeyStore.apiKeys.length > 0
    if (hasKeys) {
      ElMessage.warning('请在API Key管理页面设置一个默认Key')
    } else {
      ElMessage.warning('请先添加API Key')
    }
    router.push('/api-keys')
    return
  }
  
  generating.value = true
  showResult.value = true
  generatedContent.value = ''
  currentGenerationId.value = null
  
  // 生成唯一会话ID
  const sessionId = 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9)
  currentSessionId.value = sessionId
  
  // 重置工作流程状态
  workflowSteps.value = []
  currentStep.value = ''
  workflowComplete.value = false
  
  try {
    const apiMethod = {
      'short-video': generateApi.shortVideo,
      'script': generateApi.script,
      'novel': generateApi.novel,
      'print-ad': generateApi.printAd,
      'tvc': generateApi.tvc,
      'original-ip': generateApi.originalIp
    }[type.value]
    
    // 根据模块类型映射字段名
    let submitData = {}
    
    // 构建知识库类别参数
    const kbParams = {
      kb_vertical: kbCategories.value.vertical.enabled,
      kb_user_specific: kbCategories.value.userSpecific.enabled,
      kb_manual: kbCategories.value.manual.enabled,
      kb_vertical_ids: kbCategories.value.vertical.ids.length > 0 ? kbCategories.value.vertical.ids.join(',') : null,
      kb_user_specific_ids: kbCategories.value.userSpecific.ids.length > 0 ? kbCategories.value.userSpecific.ids.join(',') : null,
      kb_manual_ids: kbCategories.value.manual.ids.length > 0 ? kbCategories.value.manual.ids.join(',') : null,
      // 搜索关键词参数（用户自定义关键词）
      search_keywords: searchKeywords.value ? searchKeywords.value.split(/[,，]/).map(k => k.trim()).filter(k => k) : null
    }
    
    if (type.value === 'short-video') {
      submitData = {
        topic: form.value.title,
        audience: form.value.target_audience,
        description: form.value.description,
        platform: form.value.platform || '抖音',
        style: combinedStyleTypes.value || '轻松有趣',
        duration: parseInt(form.value.duration) || 60,
        mode: form.value.video_mode || 'virtual',
        generate_ai_prompt: form.value.video_mode === 'virtual' && form.value.generate_ai_prompt ? '是' : '否',
        generate_storyboard_images: form.value.video_mode === 'virtual' && form.value.generate_storyboard_images ? '是' : '否',
        ai_platforms: form.value.video_mode === 'virtual' ? (form.value.ai_platforms?.join(', ') || '无') : '无',
        reference_video: form.value.reference_video || null,
        // 参考资料上传
        reference_materials: form.value.reference_materials || null,
        // 运营相关自定义变量
        account_tone: form.value.account_tone || null,
        target_fans: form.value.target_fans || null,
        content_position: form.value.content_position || null,
        enable_knowledge: enableKnowledge.value,
        enable_creative_search: enableCreativeSearch.value,
        enable_trending: enableTrending.value,
        // 知识库类别参数
        ...kbParams
      }
    } else if (type.value === 'script') {
      submitData = {
        title: form.value.title,
        series_type: form.value.series_type || '网剧',
        theme: form.value.genre || '都市',
        audience: form.value.target_audience,
        platform: form.value.platform || '爱奇艺',
        reference_works: form.value.reference_works || '无',
        synopsis: form.value.description,
        episode_count: form.value.episode_count || null,
        custom_outline: form.value.custom_outline || null,
        // 剧本专业配置参数（关键修复：传递时长约束）
        episode_duration_range: `${form.value.episode_duration_range[0]}-${form.value.episode_duration_range[1]}分钟`,
        scenes_per_episode_range: form.value.scenes_per_episode_range || 'AI自动设计',
        format_standard: form.value.format_standard || '标准格式',
        dialogue_narration_ratio: form.value.dialogue_narration_ratio || '均衡',
        target_broadcast: form.value.target_broadcast || '未指定',
        enable_knowledge: enableKnowledge.value,
        enable_creative_search: enableCreativeSearch.value,
        enable_trending: enableTrending.value,
        // 知识库类别参数
        ...kbParams
      }
    } else if (type.value === 'novel') {
      const lengthMap = { 'short': '短篇', 'medium': '中篇', 'long': '长篇' }
      submitData = {
        title: form.value.title,
        length: lengthMap[form.value.length] || '中篇',
        genre: Array.isArray(form.value.genre) ? form.value.genre.join('、') : (form.value.genre || '言情'),
        target_platform: form.value.target_platform || '起点',
        tone: form.value.tone || '正剧',
        theme: form.value.theme || '',
        unique_selling_point: form.value.unique_selling_point || '',
        synopsis: form.value.description,
        chapter_count: form.value.chapter_count || null,
        custom_outline: form.value.custom_outline || null,
        enable_knowledge: enableKnowledge.value,
        enable_creative_search: enableCreativeSearch.value,
        enable_trending: enableTrending.value,
        // 知识库类别参数
        ...kbParams
      }
    } else if (type.value === 'print-ad') {
      submitData = {
        title: form.value.title,
        design_category: form.value.design_category || '商业广告',
        brand_product: form.value.brand_product,
        ad_purpose: form.value.ad_purpose,
        core_message: form.value.core_message,
        audience_profile: form.value.audience_profile,
        contact_scene: form.value.contact_scene,
        style_tone: form.value.style_tone || '视觉冲击',
        copy_content: form.value.copy_content || null,
        size_spec: form.value.size_spec || null,
        publish_media: form.value.publish_media || null,
        ai_platforms: form.value.ai_platforms_ad || '豆包',
        description: form.value.description || null,
        images: form.value.images.length > 0 ? form.value.images : null,
        enable_knowledge: enableKnowledge.value,
        enable_creative_search: enableCreativeSearch.value,
        enable_trending: enableTrending.value,
        // 知识库类别参数
        ...kbParams
      }
    } else if (type.value === 'tvc') {
      submitData = {
        title: form.value.title,
        brand_product: form.value.brand_product,
        ad_purpose: form.value.ad_purpose,
        core_message: form.value.core_message,
        audience_profile: form.value.audience_profile,
        broadcast_platform: form.value.broadcast_platform || '视频平台',
        style_tone: form.value.style_tone || '温情走心',
        duration: parseInt(form.value.duration) || 30,
        generate_ai_prompt: form.value.generate_ai_prompt_tvc ? '是' : '否',
        ai_platforms: form.value.ai_platforms_tvc || '可灵',
        reference_video: form.value.reference_video || null,
        description: form.value.description || null,
        enable_knowledge: enableKnowledge.value,
        enable_creative_search: enableCreativeSearch.value,
        enable_trending: enableTrending.value,
        // 知识库类别参数
        ...kbParams
      }
    } else if (type.value === 'original-ip') {
      submitData = {
        ip_description: form.value.ip_description,
        target_platform: form.value.target_platform || '综合',
        reference_ip: form.value.reference_ip || null,
        commercial_goal: form.value.commercial_goal || null,
        custom_requirements: form.value.custom_requirements || null,
        enable_search: enableCreativeSearch.value,
        // 知识库类别参数
        ...kbParams
      }
    }
    
    const result = await apiMethod(submitData, (fullContent, newContent) => {
      generatedContent.value = fullContent
    }, (workflowEvent) => {
      // 处理工作流程事件
      handleWorkflowEvent(workflowEvent)
    }, (eventSource) => {
      // 保存 EventSource 引用以便中断
      currentEventSource.value = eventSource
    }, sessionId)
    
    // 保存 generation_id 和耗时
    if (result) {
      if (result.generation_id) {
        currentGenerationId.value = result.generation_id
      }
      if (result.duration_ms) {
        generationDuration.value = result.duration_ms
      }
    }
    
    workflowComplete.value = true
    ElMessage.success('生成完成')
  } catch (error) {
    console.error('生成失败:', error)
    ElMessage.error('生成失败，请重试')
  } finally {
    generating.value = false
  }
}

// 中断生成
async function handleStop() {
  if (currentEventSource.value && currentEventSource.value.abort) {
    currentEventSource.value.abort()
    currentEventSource.value = null
  }
  
  // 发送取消请求到后端
  if (currentSessionId.value) {
    try {
      await fetch(`${API_BASE_URL}/api/v1/generate/cancel/${currentSessionId.value}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${userStore.token}`,
          'Content-Type': 'application/json'
        }
      })
    } catch (error) {
      console.warn('发送取消请求失败:', error)
    }
  }
  
  generating.value = false
  globalOutlineGenerating.value = false
  unitSummariesGenerating.value = false
  workflowComplete.value = true
  
  // 在工作流中添加中断标记
  workflowSteps.value.push({
    step: 'stopped',
    status: 'error',
    message: '生成已被用户中断',
    icon: 'CircleClose'
  })
  
  ElMessage.warning('已中断生成')
}

// ==================== 两阶段大纲生成方法 ====================

// 开始两阶段生成（第一阶段：全局大纲）
async function handleTwoStageGenerate() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  
  if (!apiKeyStore.defaultKey) {
    const hasKeys = apiKeyStore.apiKeys.length > 0
    if (hasKeys) {
      ElMessage.warning('请在API Key管理页面设置一个默认Key')
    } else {
      ElMessage.warning('请先添加API Key')
    }
    router.push('/api-keys')
    return
  }
  
  // 重置工作流程状态并添加初始步骤
  workflowSteps.value = [
    { step: 'model', status: 'running', message: '正在加载AI模型...', icon: 'Cpu' }
  ]
  workflowComplete.value = false
  
  // 开始第一阶段
  outlineStage.value = 1
  globalOutlineGenerating.value = true
  globalOutlineContent.value = ''
  showResult.value = true
  generatedContent.value = ''
  
  try {
    const inputParams = buildOutlineInputParams()
    
    // 模拟workflow步骤更新
    setTimeout(() => {
      if (globalOutlineGenerating.value) {
        const modelIndex = workflowSteps.value.findIndex(s => s.step === 'model')
        if (modelIndex >= 0) {
          workflowSteps.value[modelIndex] = { step: 'model', status: 'done', message: '已加载模型', icon: 'Cpu' }
        }
        workflowSteps.value.push({ step: 'prompt', status: 'running', message: '正在准备提示词...', icon: 'Document' })
      }
    }, 500)
    
    setTimeout(() => {
      if (globalOutlineGenerating.value) {
        const promptIndex = workflowSteps.value.findIndex(s => s.step === 'prompt')
        if (promptIndex >= 0) {
          workflowSteps.value[promptIndex] = { step: 'prompt', status: 'done', message: '提示词准备完成', icon: 'Document' }
        }
        workflowSteps.value.push({ step: 'generate', status: 'running', message: '正在生成全局大纲...', icon: 'MagicStick' })
      }
    }, 1000)
    
    const result = await generateApi.generateGlobalOutlineStream(
      {
        content_type: type.value,
        input_params: inputParams,
        provider: null,
        model: null,
        temperature: 0.7
      },
      (chunk, fullContent) => {
        globalOutlineContent.value = fullContent
        generatedContent.value = fullContent
      },
      (abortController) => {
        currentEventSource.value = abortController
      }
    )
    
    if (result && !result.cancelled) {
      // 更新workflow状态
      const generateIndex = workflowSteps.value.findIndex(s => s.step === 'generate')
      if (generateIndex >= 0) {
        workflowSteps.value[generateIndex] = { step: 'generate', status: 'done', message: '全局大纲生成完成', icon: 'MagicStick' }
      }
      workflowComplete.value = true
      
      outlineStage.value = 2
      ElMessage.success('全局大纲生成完成，请审核后继续生成单元概述')
    }
  } catch (error) {
    console.error('全局大纲生成失败:', error)
    // 更新workflow错误状态
    const runningStep = workflowSteps.value.find(s => s.status === 'running')
    if (runningStep) {
      runningStep.status = 'error'
      runningStep.message = '生成失败: ' + (error.message || '未知错误')
    }
    ElMessage.error('全局大纲生成失败：' + (error.message || '未知错误'))
    outlineStage.value = 0
  } finally {
    globalOutlineGenerating.value = false
  }
}

// 开始第二阶段：生成单元概述
async function handleGenerateUnitSummaries() {
  if (!globalOutlineContent.value) {
    ElMessage.warning('请先生成全局大纲')
    return
  }
  
  const unitCount = type.value === 'novel' 
    ? parseInt(form.value.chapter_count) || 50
    : parseInt(form.value.episode_count) || 24
  
  // 生成唯一的 session_id 用于中断
  currentSessionId.value = `unit_summaries_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  
  outlineStage.value = 3
  unitSummariesGenerating.value = true
  unitSummaries.value = {}
  
  try {
    const result = await generateApi.generateUnitSummariesStream(
      {
        content_type: type.value,
        global_outline: globalOutlineContent.value,
        unit_count: unitCount,
        series_type: type.value === 'script' ? form.value.series_type : null,
        episode_duration_range: type.value === 'script' 
          ? `${form.value.episode_duration_range[0]}-${form.value.episode_duration_range[1]}分钟` 
          : null,
        provider: null,
        model: null,
        temperature: 0.7
      },
      (chunk, fullContent) => {
        generatedContent.value = fullContent
      },
      (abortController) => {
        currentEventSource.value = abortController
      },
      currentSessionId.value
    )
    
    if (result && !result.cancelled) {
      // 解析单元概述
      unitSummaries.value = parseUnitSummariesFromContent(result.content)
      
      // 执行逻辑检测
      await performLogicCheck()
      
      outlineStage.value = 4
      ElMessage.success('单元概述生成完成')
    } else if (result && result.cancelled) {
      // 用户取消了生成
      ElMessage.info('生成已取消')
      // 如果有部分内容，仍然解析并显示
      if (result.content) {
        unitSummaries.value = parseUnitSummariesFromContent(result.content)
        outlineStage.value = 4
      } else {
        outlineStage.value = 2
      }
    }
  } catch (error) {
    console.error('单元概述生成失败:', error)
    ElMessage.error('单元概述生成失败：' + (error.message || '未知错误'))
    outlineStage.value = 2
  } finally {
    unitSummariesGenerating.value = false
    currentSessionId.value = null
  }
}

// 取消单元概述生成
async function cancelUnitSummariesGeneration() {
  if (!currentSessionId.value) {
    // 如果没有 session_id，直接中断前端连接
    if (currentEventSource.value && currentEventSource.value.abort) {
      currentEventSource.value.abort()
    }
    return
  }
  
  try {
    // 调用后端取消API
    await generateApi.cancelGeneration(currentSessionId.value)
    
    // 同时中断前端连接
    if (currentEventSource.value && currentEventSource.value.abort) {
      currentEventSource.value.abort()
    }
    
    ElMessage.info('正在取消生成...')
  } catch (error) {
    console.error('取消生成失败:', error)
    // 即使后端取消失败，也尝试中断前端连接
    if (currentEventSource.value && currentEventSource.value.abort) {
      currentEventSource.value.abort()
    }
  }
}

// 执行逻辑检测
async function performLogicCheck() {
  if (!globalOutlineContent.value || Object.keys(unitSummaries.value).length === 0) {
    return
  }
  
  logicChecking.value = true
  logicCheckResult.value = null
  
  try {
    console.log('[逻辑检测] 开始检测...')
    const response = await generateApi.checkOutlineLogic({
      content_type: type.value,
      global_outline: globalOutlineContent.value,
      unit_summaries: unitSummaries.value,
      provider: null,
      temperature: 0.7
    })
    
    if (response.success && response.data) {
      logicCheckResult.value = response.data
      
      if (response.data.has_issues) {
        console.log('[逻辑检测] 检测到问题:', response.data.issues)
        
        // 如果有修正内容，更新单元概述并保存原始内容用于差异对比
        if (response.data.revised_units && Object.keys(response.data.revised_units).length > 0) {
          // 保存原始内容和修正后内容
          const originalUnits = response.data.original_units || {}
          const revisedUnits = response.data.revised_units
          
          for (const [unitNum, revisedContent] of Object.entries(revisedUnits)) {
            if (unitSummaries.value[unitNum]) {
              // 保存原始内容
              unitSummaries.value[unitNum].original_summary = originalUnits[unitNum]?.summary || unitSummaries.value[unitNum].summary
              // 更新为修正后的内容
              unitSummaries.value[unitNum].summary = revisedContent
              unitSummaries.value[unitNum].logic_fixed = true
              // 保存修正后内容用于对比
              unitSummaries.value[unitNum].revised_summary = revisedContent
            }
          }
          ElMessage.success(`逻辑检测完成，已修正 ${Object.keys(revisedUnits).length} 个单元的问题`)
        } else {
          ElMessage.warning(`逻辑检测发现 ${response.data.issues?.length || 0} 个潜在问题`)
        }
      } else {
        console.log('[逻辑检测] 未检测到逻辑问题')
      }
    }
  } catch (error) {
    console.error('[逻辑检测] 检测失败:', error)
    // 逻辑检测失败不影响主流程
  } finally {
    logicChecking.value = false
  }
}


// ==================== 差异对比函数 ====================

/**
 * HTML 转义
 */
function escapeHtml(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
    .replace(/ /g, '&nbsp;')  // 保留空格
}

/**
 * 找出两个数组的最长公共子序列 (LCS)
 */
function findLCS(arr1, arr2) {
  const m = arr1.length, n = arr2.length
  const dp = Array(m + 1).fill(null).map(() => Array(n + 1).fill(0))
  
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (arr1[i - 1] === arr2[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
      }
    }
  }
  
  // 回溯找出 LCS
  const lcs = []
  let i = m, j = n
  while (i > 0 && j > 0) {
    if (arr1[i - 1] === arr2[j - 1]) {
      lcs.unshift(arr1[i - 1])
      i--
      j--
    } else if (dp[i - 1][j] > dp[i][j - 1]) {
      i--
    } else {
      j--
    }
  }
  
  return lcs
}

/**
 * 使用LCS算法计算差异（适用于小文本）
 */
function computeDiffWithLCS(oldParagraphs, newParagraphs) {
  const lcs = findLCS(oldParagraphs, newParagraphs)
  
  let html = ''
  let oldIdx = 0, newIdx = 0, lcsIdx = 0
  
  while (oldIdx < oldParagraphs.length || newIdx < newParagraphs.length) {
    if (lcsIdx < lcs.length && oldIdx < oldParagraphs.length && 
        oldParagraphs[oldIdx] === lcs[lcsIdx] &&
        newIdx < newParagraphs.length && newParagraphs[newIdx] === lcs[lcsIdx]) {
      // 相同段落
      html += `<div class="diff-paragraph unchanged">${escapeHtml(oldParagraphs[oldIdx])}</div>`
      oldIdx++
      newIdx++
      lcsIdx++
    } else if (newIdx < newParagraphs.length &&
               (lcsIdx >= lcs.length || newParagraphs[newIdx] !== lcs[lcsIdx])) {
      // 新增或修改的段落
      if (oldIdx < oldParagraphs.length &&
          (lcsIdx >= lcs.length || oldParagraphs[oldIdx] !== lcs[lcsIdx])) {
        // 修改：旧段落被删除，新段落是新增
        html += `<div class="diff-paragraph removed">${escapeHtml(oldParagraphs[oldIdx])}</div>`
        html += `<div class="diff-paragraph added">${escapeHtml(newParagraphs[newIdx])}</div>`
        oldIdx++
        newIdx++
      } else {
        // 纯新增
        html += `<div class="diff-paragraph added">${escapeHtml(newParagraphs[newIdx])}</div>`
        newIdx++
      }
    } else if (oldIdx < oldParagraphs.length &&
               (lcsIdx >= lcs.length || oldParagraphs[oldIdx] !== lcs[lcsIdx])) {
      // 纯删除
      html += `<div class="diff-paragraph removed">${escapeHtml(oldParagraphs[oldIdx])}</div>`
      oldIdx++
    }
  }
  
  return html
}

/**
 * 计算两段文本的差异，生成带高亮的 HTML
 */
function computeDiffHtml(oldText, newText) {
  if (!oldText && !newText) return ''
  if (!oldText) return `<div class="diff-paragraph added">${escapeHtml(newText)}</div>`
  if (!newText) return `<div class="diff-paragraph removed">${escapeHtml(oldText)}</div>`
  
  // 按段落分割
  const oldParagraphs = oldText.split(/\n+/).filter(p => p.trim())
  const newParagraphs = newText.split(/\n+/).filter(p => p.trim())
  
  // 对于小文本使用LCS
  if (oldParagraphs.length <= 50 && newParagraphs.length <= 50) {
    return computeDiffWithLCS(oldParagraphs, newParagraphs)
  } else {
    // 大文本简单对比
    const newSet = new Set(newParagraphs)
    let html = ''
    for (const para of oldParagraphs) {
      if (newSet.has(para)) {
        html += `<div class="diff-paragraph unchanged">${escapeHtml(para)}</div>`
      } else {
        html += `<div class="diff-paragraph removed">${escapeHtml(para)}</div>`
      }
    }
    const oldSet = new Set(oldParagraphs)
    for (const para of newParagraphs) {
      if (!oldSet.has(para)) {
        html += `<div class="diff-paragraph added">${escapeHtml(para)}</div>`
      }
    }
    return html
  }
}

/**
 * 计算修正差异 HTML（计算属性用）
 */
function getRevisionDiffHtml(unit) {
  if (!unit?.original_summary || !unit?.revised_summary) return ''
  return computeDiffHtml(unit.original_summary, unit.revised_summary)
}

/**
 * 打开修正详情对话框
 */
function openRevisionDetail(unitNum) {
  currentRevisionUnit.value = unitNum.toString()  // 使用字符串 key
  revisionViewMode.value = 'diff'
  showRevisionDetailDialog.value = true
}

// 构建大纲输入参数
function buildOutlineInputParams() {
  if (type.value === 'novel') {
    const lengthMap = { 'short': '短篇', 'medium': '中篇', 'long': '长篇' }
    return {
      length: lengthMap[form.value.length] || '中篇',
      genre: Array.isArray(form.value.genre) ? form.value.genre.join('、') : (form.value.genre || '言情'),
      target_platform: form.value.target_platform || '起点',
      tone: form.value.tone || '正剧',
      synopsis: form.value.description,
      theme: form.value.theme || '',
      unique_selling_point: form.value.unique_selling_point || '',
      chapter_count: form.value.chapter_count || '50',
      custom_outline: form.value.custom_outline || ''
    }
  } else if (type.value === 'script') {
    return {
      series_type: form.value.series_type || '网剧',
      theme: form.value.genre || '都市',
      audience: form.value.target_audience || '年轻观众',
      platform: form.value.platform || '爱奇艺',
      reference_works: form.value.reference_works || '无',
      synopsis: form.value.description,
      episode_count: form.value.episode_count || '24',
      custom_outline: form.value.custom_outline || '',
      episode_duration_range: `${form.value.episode_duration_range[0]}-${form.value.episode_duration_range[1]}分钟`,
      format_standard: form.value.format_standard || '标准格式',
      dialogue_narration_ratio: form.value.dialogue_narration_ratio || '均衡'
    }
  }
  return {}
}

// 从内容中解析单元概述
function parseUnitSummariesFromContent(content) {
  const result = {}
  const isMovie = content.includes('场') && !content.includes('集')
  
  // 匹配章节/场景标题
  const pattern = isMovie 
    ? /\*\*第(\d+)场[：:]\s*(.+?)(?:\n|$)/g
    : /###\s*第(\d+)(?:章|集)[：:]\s*(.+?)(?:\n|$)/g
  
  let match
  while ((match = pattern.exec(content)) !== null) {
    const unitNum = parseInt(match[1])
    const title = match[2].trim()
    
    // 提取概要
    const summaryPattern = isMovie
      ? new RegExp(`\\*\\*本场梗概\\*\\*[：:]\\s*(.+?)(?:\\n\\n|\\n\\*\\*|$)`, 's')
      : new RegExp(`\\*\\*本(?:章|集)梗概\\*\\*[：:]\\s*(.+?)(?:\\n\\n|\\n\\*\\*|$)`, 's')
    
    const summaryMatch = content.slice(match.index, match.index + 500).match(summaryPattern)
    const summary = summaryMatch ? summaryMatch[1].trim() : ''
    
    // 使用字符串作为 key，与后端保持一致
    result[unitNum.toString()] = {
      unit_number: unitNum,
      title: title,
      summary: summary,
      status: 'completed'
    }
  }
  
  return result
}

// 保存全局大纲修改
function saveGlobalOutline() {
  ElMessage.success('全局大纲已保存')
}

// 编辑单元概述
function editUnitSummary(unitNum) {
  editingUnitNumber.value = unitNum.toString()  // 使用字符串 key
  editingUnitContent.value = unitSummaries.value[unitNum.toString()]?.summary || ''
}

// 保存单元概述修改
function saveUnitSummary() {
  if (editingUnitNumber.value && unitSummaries.value[editingUnitNumber.value]) {
    unitSummaries.value[editingUnitNumber.value].summary = editingUnitContent.value
    editingUnitNumber.value = null
    editingUnitContent.value = ''
    ElMessage.success('单元概述已更新')
  }
}

// 取消编辑单元概述
function cancelEditUnitSummary() {
  editingUnitNumber.value = null
  editingUnitContent.value = ''
}

// 下载大纲
function downloadOutline() {
  // 阶段2（全局大纲阶段）使用编辑后的内容，其他阶段使用原始生成内容
  const content = outlineStage.value === 2 ? globalOutlineContent.value : generatedContent.value
  const blob = new Blob([content], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${form.value.title || '大纲'}_${outlineStage.value === 2 ? '全局大纲' : '完整大纲'}.md`
  a.click()
  URL.revokeObjectURL(url)
  trackAction('download')
}

// 重置两阶段生成状态
function resetTwoStageOutline() {
  outlineStage.value = 0
  globalOutlineContent.value = ''
  unitSummaries.value = {}
  globalOutlineGenerating.value = false
  unitSummariesGenerating.value = false
  showResult.value = false
  generatedContent.value = ''
  // 重置灵活介入状态
  startFromUnit.value = 1
}

// ==================== 灵活介入流程方法 ====================

// 打开导入对话框
function openImportDialog() {
  importType.value = 'global'
  importContent.value = ''
  showImportDialog.value = true
}

// 确认导入内容
function confirmImport() {
  if (!importContent.value.trim()) {
    ElMessage.warning('请粘贴要导入的大纲内容')
    return
  }
  
  if (importType.value === 'global') {
    // 导入全局大纲，跳转到阶段2
    globalOutlineContent.value = importContent.value.trim()
    generatedContent.value = importContent.value.trim()
    outlineStage.value = 2
    showResult.value = true
    ElMessage.success('全局大纲已导入，您可以编辑后继续生成单元概述')
  } else {
    // 导入完整大纲，尝试解析并跳转到阶段4
    try {
      const parsed = parseUnitSummariesFromContent(importContent.value)
      if (Object.keys(parsed).length > 0) {
        unitSummaries.value = parsed
        // 尝试提取全局大纲部分（通常在开头）
        const globalOutlineMatch = importContent.value.match(/^([\s\S]*?)(?=###\s*第\d+章|###\s*第\d+集|\*\*第\d+集)/)
        if (globalOutlineMatch) {
          globalOutlineContent.value = globalOutlineMatch[1].trim()
        } else {
          globalOutlineContent.value = importContent.value.split('###')[0].trim()
        }
        generatedContent.value = importContent.value
        outlineStage.value = 4
        showResult.value = true
        ElMessage.success('完整大纲已导入，您可以编辑后下载')
      } else {
        // 无法解析单元概述，当作全局大纲处理
        globalOutlineContent.value = importContent.value.trim()
        generatedContent.value = importContent.value.trim()
        outlineStage.value = 2
        showResult.value = true
        ElMessage.warning('无法解析单元概述，已作为全局大纲导入')
      }
    } catch (error) {
      console.error('解析导入内容失败:', error)
      globalOutlineContent.value = importContent.value.trim()
      generatedContent.value = importContent.value.trim()
      outlineStage.value = 2
      showResult.value = true
      ElMessage.warning('导入内容已作为全局大纲处理')
    }
  }
  
  showImportDialog.value = false
}

// 打开从指定单元开始的对话框
function openStartUnitDialog() {
  const unitCount = type.value === 'novel'
    ? parseInt(form.value.chapter_count) || 50
    : parseInt(form.value.episode_count) || 24
  startFromUnit.value = Math.min(startFromUnit.value, unitCount)
  showStartUnitDialog.value = true
}

// 从指定单元开始生成（保留已有单元概述）
async function handleGenerateFromUnit() {
  if (!globalOutlineContent.value) {
    ElMessage.warning('请先导入或生成全局大纲')
    return
  }
  
  const unitCount = type.value === 'novel'
    ? parseInt(form.value.chapter_count) || 50
    : parseInt(form.value.episode_count) || 24
  
  if (startFromUnit.value < 1 || startFromUnit.value > unitCount) {
    ElMessage.warning(`请输入有效的单元编号（1-${unitCount}）`)
    return
  }
  
  showStartUnitDialog.value = false
  outlineStage.value = 3
  unitSummariesGenerating.value = true
  
  try {
    // 构建已有单元概述的上下文
    let existingContext = ''
    if (Object.keys(unitSummaries.value).length > 0) {
      existingContext = '\n\n【已生成的单元概述】\n'
      for (const [num, unit] of Object.entries(unitSummaries.value)) {
        if (parseInt(num) < startFromUnit.value) {
          existingContext += `单元${num}: ${unit.title}\n${unit.summary}\n\n`
        }
      }
    }
    
    // 修改全局大纲，添加已有上下文和起始位置提示
    const modifiedOutline = globalOutlineContent.value + existingContext +
      `\n\n【生成要求】从第${startFromUnit.value}单元开始生成后续单元概述。`
    
    const result = await generateApi.generateUnitSummariesStream(
      {
        content_type: type.value,
        global_outline: modifiedOutline,
        unit_count: unitCount - startFromUnit.value + 1,  // 只生成剩余单元
        series_type: type.value === 'script' ? form.value.series_type : null,
        episode_duration_range: type.value === 'script'
          ? `${form.value.episode_duration_range[0]}-${form.value.episode_duration_range[1]}分钟`
          : null,
        provider: null,
        model: null,
        temperature: 0.7
      },
      (chunk, fullContent) => {
        generatedContent.value = fullContent
      },
      (abortController) => {
        currentEventSource.value = abortController
      }
    )
    
    if (result && !result.cancelled) {
      // 解析新生成的单元概述
      const newUnits = parseUnitSummariesFromContent(result.content)
      // 合并到已有单元概述
      for (const [num, unit] of Object.entries(newUnits)) {
        const actualNum = parseInt(num) + startFromUnit.value - 1
        unitSummaries.value[actualNum.toString()] = {
          ...unit,
          unit_number: actualNum
        }
      }
      outlineStage.value = 4
      ElMessage.success(`从第${startFromUnit.value}单元开始的生成已完成`)
    }
  } catch (error) {
    console.error('单元概述生成失败:', error)
    ElMessage.error('单元概述生成失败：' + (error.message || '未知错误'))
    outlineStage.value = 2
  } finally {
    unitSummariesGenerating.value = false
  }
}

// 处理工作流程事件
function handleWorkflowEvent(event) {
  console.log('[Workflow] 收到事件:', event)
  if (event.type === 'start') {
    workflowSteps.value = []
  } else if (event.type === 'step') {
    const existingIndex = workflowSteps.value.findIndex(s => s.step === event.step)
    const stepData = {
      step: event.step,
      status: event.status,
      message: event.message,
      icon: event.icon || stepIcons[event.step] || 'Loading'
    }
    
    if (existingIndex >= 0) {
      workflowSteps.value[existingIndex] = stepData
    } else {
      workflowSteps.value.push(stepData)
    }
    
    if (event.status === 'running') {
      currentStep.value = event.step
    }
  } else if (event.type === 'complete') {
    workflowComplete.value = true
  } else if (event.type === 'error') {
    workflowSteps.value.push({
      step: 'error',
      status: 'error',
      message: event.message,
      icon: 'Warning'
    })
  }
}

// 移除风格类型标签
function removeStyleTag(level, tag) {
  if (level === 'level1') {
    form.value.style_types_level1 = form.value.style_types_level1.filter(t => t !== tag)
  } else {
    form.value.style_types = form.value.style_types.filter(t => t !== tag)
  }
}

// 清空所有风格选择
function clearAllStyles() {
  form.value.style_types = []
  form.value.style_types_level1 = []
}

function resetForm() {
  formRef.value.resetFields()
  form.value.style_types = []
  form.value.style_types_level1 = []
  form.value.video_mode = 'virtual' // 重置为默认虚拟模式
  form.value.generate_ai_prompt = false
  form.value.generate_storyboard_images = true // 重置为默认开启
  form.value.ai_platforms = []
  form.value.series_type = ''
  form.value.reference_works = ''
  searchKeywords.value = ''  // 清空搜索关键词
  showResult.value = false
  generatedContent.value = ''
  generationDuration.value = null
}

async function copyResult() {
  try {
    await navigator.clipboard.writeText(generatedContent.value)
    ElMessage.success('已复制到剪贴板')
    // 追踪复制行为
    trackAction('copy')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

function downloadResult() {
  const blob = new Blob([generatedContent.value], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${form.value.title || '创意内容'}.md`
  a.click()
  URL.revokeObjectURL(url)
  // 追踪下载行为
  trackAction('download')
}

function regenerate() {
  // 追踪重新生成行为
  trackAction('regenerate')
  handleGenerate()
}

// 格式化耗时显示
function formatDuration(ms) {
  if (!ms || ms < 0) return ''
  
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  
  if (minutes > 0) {
    return `${minutes}分${remainingSeconds}秒`
  } else {
    return `${remainingSeconds}秒`
  }
}

// 追踪用户行为
async function trackAction(actionType) {
  try {
    const { actionApi } = await import('@/api')
    await actionApi.track({
      generation_id: currentGenerationId.value,
      module: type.value,  // 使用 .value 获取 computed ref 的值
      action: actionType,
      content_snippet: generatedContent.value?.substring(0, 100)
    })
  } catch (error) {
    console.error('追踪行为失败:', error)
  }
}
</script>

<style lang="scss" scoped>
.generate-form-page {
  width: 100%;
  max-width: 1600px;
  margin: 0 auto;
  padding: 0 20px;
}

.page-header {
  margin-bottom: 24px;
  background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
  border-radius: 16px;
  padding: 20px 24px;
  position: relative;
  overflow: hidden;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: 
      radial-gradient(ellipse at 20% 50%, rgba(64, 158, 255, 0.1) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 50%, rgba(0, 212, 170, 0.08) 0%, transparent 50%);
    pointer-events: none;
  }
  
  .header-top-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: relative;
    z-index: 1;
  }
  
  .header-actions {
    display: flex;
    gap: 8px;
    
    .el-button {
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid rgba(64, 158, 255, 0.2);
      color: rgba(255, 255, 255, 0.8);
      border-radius: 8px;
      
      &:hover {
        background: rgba(64, 158, 255, 0.2);
        border-color: rgba(64, 158, 255, 0.4);
        color: #fff;
      }
    }
  }
  
  .header-info {
    display: flex;
    align-items: center;
    gap: 14px;
    margin: 20px 0 10px;
    position: relative;
    z-index: 1;
    
    .el-icon {
      color: #409EFF;
    }
    
    h1 {
      font-size: 24px;
      background: linear-gradient(90deg, #fff, #409EFF, #00D4AA);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      font-weight: 600;
    }
  }
  
  p {
    color: rgba(255, 255, 255, 0.6);
    font-size: 14px;
    position: relative;
    z-index: 1;
  }
}

// 主体区域：左右分栏
.main-container {
  display: flex;
  gap: 24px;
  margin-bottom: 24px;
  align-items: flex-start;
}

// 左侧面板：表单区域
.left-panel {
  flex: 1;
  min-width: 0;
  
  .form-container {
    background: #fff;
    border-radius: 16px;
    padding: 28px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
    border: 1px solid rgba(64, 158, 255, 0.08);
    max-height: calc(100vh - 200px);
    overflow-y: auto;
    
    // 滚动条样式
    &::-webkit-scrollbar {
      width: 6px;
    }
    
    &::-webkit-scrollbar-track {
      background: #f5f7fa;
      border-radius: 3px;
    }
    
    &::-webkit-scrollbar-thumb {
      background: linear-gradient(180deg, #409EFF, #00D4AA);
      border-radius: 3px;
      
      &:hover {
        background: #409EFF;
      }
    }
  }
}

// 右侧面板：工作流程
.right-panel {
  width: 420px;
  flex-shrink: 0;
  
  .workflow-container {
    background: #fff;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
    border: 1px solid rgba(64, 158, 255, 0.08);
    position: sticky;
    top: 20px;
    max-height: calc(100vh - 200px);
    overflow-y: auto;
    
    // 滚动条样式
    &::-webkit-scrollbar {
      width: 6px;
    }
    
    &::-webkit-scrollbar-track {
      background: #f5f7fa;
      border-radius: 3px;
    }
    
    &::-webkit-scrollbar-thumb {
      background: linear-gradient(180deg, #409EFF, #00D4AA);
      border-radius: 3px;
      
      &:hover {
        background: #409EFF;
      }
    }
  }
  
  .workflow-empty {
    background: #fff;
    border-radius: 16px;
    padding: 60px 24px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
    border: 1px solid rgba(64, 158, 255, 0.08);
    text-align: center;
    min-height: 300px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}

// 底部：生成结果
.result-container {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(64, 158, 255, 0.08);
  margin-bottom: 24px;
}

.form-container {
  background: #fff;
  border-radius: 16px;
  padding: 30px;
  margin-bottom: 20px;
}

.form-section {
  margin-bottom: 28px;
  
  &:last-child {
    margin-bottom: 0;
  }
  
  h3 {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 2px solid rgba(64, 158, 255, 0.1);
    display: flex;
    align-items: center;
    gap: 10px;
    
    &::before {
      content: '';
      width: 4px;
      height: 18px;
      background: linear-gradient(180deg, #409EFF, #00D4AA);
      border-radius: 2px;
    }
  }
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-left: 10px;
}

// 大纲上传组件样式
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
    align-items: center;
    gap: 4px;
    margin-top: 4px;
    font-size: 12px;
    color: #909399;
    
    .el-icon {
      font-size: 14px;
    }
  }
}

.label-tip {
  font-size: 12px;
  color: #909399;
  margin-left: 8px;
  font-weight: normal;
}

// 风格类型样式（直观一览式）
.style-selector-grid {
  .style-tip-text {
    font-size: 12px;
    color: #909399;
    margin-bottom: 12px;
  }
  
  .style-groups-container {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    max-height: 400px;
    overflow-y: auto;
    padding: 8px;
    
    @media (max-width: 1200px) {
      grid-template-columns: repeat(3, 1fr);
    }
    
    @media (max-width: 900px) {
      grid-template-columns: repeat(2, 1fr);
    }
  }
  
  .style-group {
    border: 1px solid #e4e7ed;
    border-radius: 6px;
    padding: 8px;
    background: #fafafa;
    
    .style-group-header {
      margin-bottom: 6px;
      
      :deep(.el-checkbox__label) {
        font-size: 13px;
      }
    }
    
    .style-group-children {
      display: flex;
      flex-wrap: wrap;
      gap: 4px 8px;
      
      :deep(.el-checkbox) {
        margin-right: 0;
      }
      
      :deep(.el-checkbox__label) {
        font-size: 12px;
        color: #606266;
      }
    }
  }
}

// 旧风格类型样式（保留兼容）
.style-selector {
  .selected-tags {
    display: flex;
    flex-wrap: wrap;
    margin-bottom: 8px;
    min-height: 24px;
  }
  
  .style-placeholder {
    color: #909399;
    font-size: 13px;
    margin-bottom: 8px;
  }
}

// 风格类型对话框样式
.style-collapse {
  max-height: 400px;
  overflow-y: auto;
  margin-top: 12px;
  
  .style-tip {
    font-size: 12px;
    color: #909399;
  }
  
  .group-count {
    font-size: 12px;
    color: #909399;
    margin-left: 4px;
    font-weight: normal;
  }
  
  .style-children {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 16px;
    padding: 8px 0 8px 28px;
    
    :deep(.el-checkbox) {
      margin-right: 0;
    }
    
    :deep(.el-checkbox__label) {
      font-size: 13px;
      color: #606266;
    }
  }
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 24px;
  margin-top: 24px;
  border-top: 1px solid rgba(64, 158, 255, 0.1);
  
  .el-button {
    min-width: 100px;
    font-weight: 500;
    border-radius: 10px;
  }
  
  .el-button--primary {
    background: linear-gradient(135deg, #409EFF 0%, #00D4AA 100%);
    border: none;
    box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
    
    &:hover {
      box-shadow: 0 6px 20px rgba(64, 158, 255, 0.4);
      transform: translateY(-1px);
    }
  }
}

// 工作流程容器样式
.workflow-container {
  .workflow-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 2px solid #f0f2f5;
    
    h3 {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0;
      
      .workflow-icon {
        color: #667eea;
        
        &.is-spinning {
          animation: spin 1s linear infinite;
        }
      }
    }
  }
  
  .workflow-steps {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  
  .workflow-step {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    background: #f8f9fa;
    border-radius: 8px;
    transition: all 0.3s ease;
    border: 1px solid transparent;
    
    &.is-running {
      background: linear-gradient(135deg, #fff5e6 0%, #ffe8cc 100%);
      border-color: #ffd591;
      box-shadow: 0 2px 8px rgba(255, 213, 145, 0.3);
    }
    
    &.is-done {
      background: linear-gradient(135deg, #f0f9ff 0%, #e6f4ff 100%);
      border-color: #91d5ff;
    }
    
    &.is-error {
      background: linear-gradient(135deg, #fff1f0 0%, #ffccc7 100%);
      border-color: #ffa39e;
    }
    
    .step-icon {
      flex-shrink: 0;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      background: #fff;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
      
      .el-icon {
        font-size: 18px;
        
        &.is-spinning {
          animation: spin 1s linear infinite;
        }
      }
    }
    
    .step-content {
      flex: 1;
      min-width: 0;
      
      .step-message {
        font-size: 14px;
        color: #303133;
        line-height: 1.5;
        word-break: break-word;
      }
    }
    
    .step-status {
      flex-shrink: 0;
    }
  }
}

// 结果容器样式
.result-container {
  .result-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 2px solid #f0f2f5;
    
    h3 {
      font-size: 18px;
      font-weight: 600;
      color: #303133;
      margin: 0;
      display: flex;
      align-items: center;
      gap: 8px;
      
      &::before {
        content: '✨';
        font-size: 20px;
      }
    }
    
    .result-meta {
      display: flex;
      align-items: center;
      gap: 16px;
      
      .duration-tag {
        display: flex;
        align-items: center;
        gap: 4px;
      }
      
      .result-actions {
        display: flex;
        gap: 8px;
        
        .el-button {
          font-weight: 500;
        }
      }
    }
  }
  
  .result-content {
    background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
    border-radius: 8px;
    padding: 24px;
    border: 1px solid #e4e7ed;
    min-height: 200px;
  }
}

// 知识库开关样式
.knowledge-switch-wrapper {
  display: flex;
  flex-direction: column;
  gap: 12px;
  
  .knowledge-tip {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px;
    background: #f0f9ff;
    border: 1px solid #bfdbfe;
    border-radius: 6px;
    font-size: 13px;
    color: #1e40af;
    
    strong {
      font-weight: 600;
      color: #1e3a8a;
    }
    
    // 搜索策略提示样式
    &.search-tip {
      flex-direction: column;
      align-items: flex-start;
      background: #f0fdf4;
      border-color: #bbf7d0;
      color: #166534;
      
      strong {
        color: #15803d;
      }
      
      .search-strategy-info {
        width: 100%;
        
        .strategy-steps {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 8px;
          
          .strategy-step {
            display: inline-flex;
            align-items: center;
            gap: 4px;
          }
          
          .strategy-arrow {
            color: #9ca3af;
            font-weight: bold;
          }
        }
        
        .strategy-note {
          margin-top: 8px;
          font-size: 12px;
          color: #6b7280;
        }
      }
    }
  }
}

// 输入提示样式
.input-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  
  .el-icon {
    font-size: 14px;
    color: #409eff;
  }
}

// 知识库类别选择器样式
.kb-category-selector {
  margin-top: 16px;
  padding: 16px;
  background: #fafbfc;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  
  .kb-category-item {
    padding: 12px;
    margin-bottom: 12px;
    background: #fff;
    border-radius: 6px;
    border: 1px solid #ebeef5;
    transition: all 0.3s;
    
    &:last-child {
      margin-bottom: 0;
    }
    
    &:hover {
      border-color: #c0c4cc;
    }
    
    .kb-category-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      
      .category-title {
        font-weight: 500;
        margin-right: 8px;
      }
      
      .category-desc {
        font-size: 12px;
        color: #909399;
      }
    }
    
    .kb-list-selector {
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px dashed #e4e7ed;
    }
    
    .kb-empty-tip {
      margin-top: 8px;
      font-size: 12px;
      color: #909399;
      text-align: center;
      padding: 8px;
      background: #f5f7fa;
      border-radius: 4px;
    }
  }
}

// 知识库选择器空提示
.empty-tip {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 13px;
  color: #909399;
}

// 图片上传区域
.image-upload-section {
  width: 100%;
  
  .upload-tip {
    font-size: 12px;
    color: #909399;
    margin-top: 8px;
  }
  
  .url-input-section {
    margin-top: 12px;
  }
}

// 提示词优化按钮样式
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

// 两阶段大纲生成样式
.outline-stages {
  margin-bottom: 24px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
  
  .el-steps {
    margin-bottom: 20px;
  }
  
  .stage-actions {
    display: flex;
    justify-content: center;
    gap: 12px;
    margin-top: 16px;
  }
}

.global-outline-edit {
  margin-bottom: 24px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  
  .edit-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: #f5f7fa;
    border-bottom: 1px solid #e4e7ed;
    
    .edit-tip {
      font-size: 14px;
      color: #606266;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    
    .edit-actions {
      display: flex;
      gap: 8px;
    }
  }
  
  .edit-content {
    padding: 16px;
    
    .el-textarea {
      font-family: monospace;
    }
    
    .preview-content {
      max-height: 500px;
      overflow-y: auto;
      padding: 8px;
    }
  }
}

.unit-summaries-list {
  margin-bottom: 24px;
  
  .el-collapse {
    border: 1px solid #e4e7ed;
    border-radius: 8px;
  }
  
  .unit-title-wrapper {
    display: flex;
    align-items: center;
    gap: 12px;
    
    .fixed-tag {
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
  }
  
  .unit-summary-content {
    padding: 12px;
    
    p {
      margin: 0 0 12px;
      line-height: 1.6;
      color: #606266;
      
      &.logic-fixed-content {
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        padding: 8px 12px;
        border-radius: 6px;
        border-left: 3px solid #28a745;
      }
    }
    
    .unit-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
    }
  }
}

// 导入对话框样式
.import-dialog-content {
  .import-type-selector {
    display: flex;
    gap: 24px;
    margin-bottom: 20px;
    
    .el-radio {
      height: auto;
      padding: 16px;
      border: 1px solid #e4e7ed;
      border-radius: 8px;
      margin-right: 0;
      
      &.is-checked {
        border-color: var(--el-color-primary);
        background: var(--el-color-primary-light-9);
      }
    }
    
    .import-type-option {
      display: flex;
      flex-direction: column;
      gap: 4px;
      
      .title {
        font-weight: 500;
        font-size: 14px;
      }
      
      .desc {
        font-size: 12px;
        color: #909399;
      }
    }
  }
  
  .import-tips {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: #f4f4f5;
    border-radius: 6px;
    margin-bottom: 16px;
    font-size: 13px;
    color: #606266;
    
    .el-icon {
      color: #909399;
    }
  }
  
  .import-textarea {
    .el-textarea__inner {
      font-family: monospace;
      font-size: 13px;
      line-height: 1.5;
    }
  }
}

// 从指定单元开始对话框样式
.start-unit-dialog-content {
  .start-unit-tip {
    color: #606266;
    line-height: 1.6;
    margin-bottom: 20px;
  }
  
  .start-unit-warning {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: #fdf6ec;
    border-radius: 6px;
    margin-top: 16px;
    font-size: 13px;
    color: #e6a23c;
    
    .el-icon {
      font-size: 16px;
    }
  }
}

// 逻辑检测状态样式
.logic-check-status {
  margin-top: 16px;
  padding: 12px 16px;
  border-radius: 8px;
  
  .logic-checking {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #409eff;
    font-size: 14px;
    
    .el-icon {
      font-size: 16px;
    }
  }
  
  .logic-check-result {
    .has-issues {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #e6a23c;
      font-size: 14px;
      
      .el-icon {
        font-size: 16px;
      }
    }
    
    .no-issues {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #67c23a;
      font-size: 14px;
      
      .el-icon {
        font-size: 16px;
      }
    }
  }
}

// 逻辑检测测试按钮样式
.logic-check-test {
  margin-top: 12px;
  display: flex;
  gap: 12px;
}

// 逻辑问题详情对话框样式
.logic-issues-dialog {
  .issue-item {
    padding: 12px;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    margin-bottom: 12px;
    
    &:last-child {
      margin-bottom: 0;
    }
    
    .issue-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 8px;
      
      .issue-unit {
        font-size: 13px;
        color: #909399;
      }
    }
    
    .issue-description {
      margin: 0;
      font-size: 14px;
      color: #606266;
      line-height: 1.6;
    }
  }
}

// 修正详情对话框样式
.revision-detail-container {
  .revision-info-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: #f5f7fa;
    border-radius: 8px;
    margin-bottom: 16px;
    
    .revision-stats {
      font-size: 14px;
      color: #606266;
      
      strong {
        color: #303133;
      }
    }
  }
  
  .view-switch {
    margin-bottom: 16px;
  }
  
  .diff-view {
    .diff-legend {
      display: flex;
      gap: 16px;
      margin-bottom: 12px;
      padding: 8px 12px;
      background: #f5f7fa;
      border-radius: 6px;
      
      .legend-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        color: #606266;
        
        .legend-color {
          width: 16px;
          height: 16px;
          border-radius: 3px;
        }
        
        &.added .legend-color {
          background: #d4edda;
          border: 1px solid #c3e6cb;
        }
        
        &.removed .legend-color {
          background: #f8d7da;
          border: 1px solid #f5c6cb;
        }
        
        &.unchanged .legend-color {
          background: transparent;
          border: 1px solid #dcdfe6;
        }
      }
    }
    
    .diff-content {
      padding: 16px;
      font-family: 'Microsoft YaHei', sans-serif;
      line-height: 1.8;
      font-size: 14px;
      max-height: 400px;
      overflow-y: auto;
      border: 1px solid #e4e7ed;
      border-radius: 8px;
      
      :deep(.diff-paragraph) {
        padding: 8px 12px;
        margin-bottom: 8px;
        border-radius: 4px;
        white-space: pre-wrap;
        word-break: break-word;
        
        &.unchanged {
          background: transparent;
          color: #303133;
        }
        
        &.added {
          background: #d4edda;
          border-left: 4px solid #28a745;
          color: #155724;
        }
        
        &.removed {
          background: #f8d7da;
          border-left: 4px solid #dc3545;
          color: #721c24;
          text-decoration: line-through;
          opacity: 0.8;
        }
      }
    }
  }
  
  .compare-view {
    display: flex;
    gap: 16px;
    
    .compare-panel {
      flex: 1;
      display: flex;
      flex-direction: column;
      border: 1px solid #e4e7ed;
      border-radius: 8px;
      overflow: hidden;
      
      .panel-header {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 16px;
        background: #f5f7fa;
        border-bottom: 1px solid #e4e7ed;
        
        .panel-word-count {
          font-size: 13px;
          color: #909399;
        }
      }
      
      .panel-content {
        flex: 1;
        overflow: hidden;
        
        .el-textarea {
          height: 100%;
          
          :deep(.el-textarea__inner) {
            height: 300px !important;
            min-height: 300px !important;
            border: none;
            border-radius: 0;
            font-family: 'Microsoft YaHei', sans-serif;
            line-height: 1.8;
          }
        }
      }
    }
  }
}
</style>
