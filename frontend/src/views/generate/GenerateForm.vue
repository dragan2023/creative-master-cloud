<template>
  <div class="generate-form-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <el-button text @click="router.push('/generate')">
        <el-icon><ArrowLeft /></el-icon>
        返回选择
      </el-button>
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
          
          <el-form-item :label="type === 'script' || type === 'novel' ? '故事梗概' : '详细描述'" prop="description">
            <el-input
              v-model="form.description"
              type="textarea"
              :rows="4"
              :placeholder="type === 'script' ? '请描述故事的主要内容，包括背景设定、核心冲突、人物关系等' : type === 'novel' ? '请描述小说的故事梗概，包括世界观、主线剧情、人物关系等' : '请详细描述您的创意需求，包括背景、目标、关键元素等'"
            />
          </el-form-item>
          
          <!-- ========== 短视频模块特殊字段 ========== -->
          <template v-if="type === 'short-video'">
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
            
            <!-- AI视频生成提示 -->
            <el-form-item label="生成AI视频提示">
              <el-radio-group v-model="form.generate_ai_prompt">
                <el-radio :value="true">是</el-radio>
                <el-radio :value="false">否</el-radio>
              </el-radio-group>
              <span class="form-tip">选择"是"将额外生成适用于AI视频生成平台的提示词</span>
            </el-form-item>
            
            <el-form-item v-if="form.generate_ai_prompt" label="AI视频生成平台">
              <el-checkbox-group v-model="form.ai_platforms">
                <el-checkbox label="seedance2">Seedance 2</el-checkbox>
                <el-checkbox label="sora2">Sora 2</el-checkbox>
                <el-checkbox label="veo3">Veo 3.1</el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            
            <!-- 参考视频URL -->
            <el-form-item prop="reference_video">
              <template #label>
                <span>参考视频</span>
                <el-tag type="warning" size="small" style="margin-left: 8px;">仅支持 Gemini 1.5 Pro/Flash</el-tag>
              </template>
              <el-input
                v-model="form.reference_video"
                placeholder="输入参考视频URL（可选，需要选择Gemini模型才能解析视频）"
              />
            </el-form-item>
          </template>
          
          <!-- ========== 剧本大纲模块 ========== -->
          <template v-if="type === 'script'">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="剧集类型" prop="series_type">
                  <el-select v-model="form.series_type" placeholder="选择剧集类型" style="width: 100%">
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
                  </div>
                </el-form-item>
              </el-col>
            </el-row>
          </template>
          
          <!-- ========== 平面广告模块 ========== -->
          <template v-if="type === 'print-ad'">
            <!-- 第一行：品牌/产品 + 广告目的 -->
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
                  <el-input
                    v-model="form.core_message"
                    type="textarea"
                    :rows="2"
                    placeholder="如果受众看完只记住一件事，你希望是什么？必须用一句话说清楚"
                  />
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
                <el-form-item label="参考图片">
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
                  <el-input
                    v-model="form.core_message"
                    type="textarea"
                    :rows="2"
                    placeholder="如果观众看完只记住一句话，你希望是什么？"
                  />
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
                    <el-tag type="warning" size="small" style="margin-left: 8px;">仅支持 Gemini 1.5 Pro/Flash</el-tag>
                  </template>
                  <el-input
                    v-model="form.reference_video"
                    placeholder="输入参考视频URL（可选，需要选择Gemini模型才能解析视频）"
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
                <span>Agent将自动按照 <strong>通用知识库 → 垂直领域知识库 → 官方手册</strong> 顺序检索相关内容，提升生成质量</span>
              </div>
            </div>
          </el-form-item>
        </div>
        
        <!-- 提交按钮 -->
        <div class="form-actions">
          <el-button @click="resetForm">重置</el-button>
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
  <div class="result-header">
    <h3>生成结果</h3>
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
        <el-button text @click="regenerate">
          <el-icon><Refresh /></el-icon>
          重新生成
        </el-button>
      </div>
    </div>
  </div>
  
  <div class="result-content markdown-content" v-html="renderedContent"></div>
</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { marked } from 'marked'
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
  // 小说新增字段
  target_platform: '',    // 目标读者/平台
  tone: '',               // 基调氛围
  theme: '',              // 故事主题
  unique_selling_point: '', // 独特卖点
  chapter_count: '',      // 章节数
  // 平面广告新增字段
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
  style_types: [],        // 二级选项
  style_types_level1: [], // 一级选项
  generate_ai_prompt: false,
  ai_platforms: []
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

const rules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  description: [{ required: true, message: '请输入内容', trigger: 'blur' }],
  target_audience: [{ required: true, message: '请输入目标受众', trigger: 'blur' }]
}

const genres = ['爱情', '喜剧', '悬疑', '科幻', '奇幻', '动作', '剧情', '历史', '都市', '青春', '恐怖', '犯罪', '惊悚', '灾难']

// 剧集类型选项
const seriesTypes = ['院线电影', '网络电影', '长剧', '短剧', '微电影', '纪录片', '动画电影', '网络剧', '竖屏剧']

// 投放平台选项
const platforms = ['央视', '地方卫视', '爱奇艺', '腾讯视频', '优酷', '芒果TV', 'B站', '抖音', '快手', '西瓜视频', '红果短剧', '河马剧场', 'Netflix', 'HBO', 'Disney+', '院线发行', '电影节展映']

const renderedContent = computed(() => {
  if (!generatedContent.value) return ''
  return marked(generatedContent.value)
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

// 加载知识库列表
async function loadKnowledgeBases() {
  loadingKnowledge.value = true
  try {
    const res = await knowledgeApi.list({ status: 'ready' })
    knowledgeBases.value = res.data || []
  } catch (error) {
    console.error('加载知识库列表失败:', error)
  } finally {
    loadingKnowledge.value = false
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
      'tvc': generateApi.tvc
    }[type.value]
    
    // 根据模块类型映射字段名
    let submitData = {}
    
    if (type.value === 'short-video') {
      submitData = {
        topic: form.value.title,
        audience: form.value.target_audience,
        description: form.value.description,
        platform: form.value.platform || '抖音',
        style: combinedStyleTypes.value || '轻松有趣',
        duration: parseInt(form.value.duration) || 60,
        generate_ai_prompt: form.value.generate_ai_prompt ? '是' : '否',
        ai_platforms: form.value.ai_platforms?.join(', ') || '无',
        reference_video: form.value.reference_video || null,
        enable_knowledge: enableKnowledge.value
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
        enable_knowledge: enableKnowledge.value
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
        enable_knowledge: enableKnowledge.value
      }
    } else if (type.value === 'print-ad') {
      submitData = {
        title: form.value.title,
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
        images: form.value.images.length > 0 ? form.value.images : null,
        enable_knowledge: enableKnowledge.value
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
        enable_knowledge: enableKnowledge.value
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

// 处理工作流程事件
function handleWorkflowEvent(event) {
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
  form.value.generate_ai_prompt = false
  form.value.ai_platforms = []
  form.value.series_type = ''
  form.value.reference_works = ''
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
  
  .header-info {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 20px 0 10px;
    
    h1 {
      font-size: 24px;
      color: #303133;
      font-weight: 600;
    }
  }
  
  p {
    color: #909399;
    font-size: 14px;
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
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    border: 1px solid #e4e7ed;
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
      background: #dcdfe6;
      border-radius: 3px;
      
      &:hover {
        background: #c0c4cc;
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
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    border: 1px solid #e4e7ed;
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
      background: #dcdfe6;
      border-radius: 3px;
      
      &:hover {
        background: #c0c4cc;
      }
    }
  }
  
  .workflow-empty {
    background: #fff;
    border-radius: 12px;
    padding: 60px 24px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    border: 1px solid #e4e7ed;
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
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  border: 1px solid #e4e7ed;
  margin-bottom: 24px;
}

.form-container {
  background: #fff;
  border-radius: 12px;
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
    border-bottom: 2px solid #f0f2f5;
    display: flex;
    align-items: center;
    gap: 8px;
    
    &::before {
      content: '';
      width: 4px;
      height: 16px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
  border-top: 1px solid #f0f2f5;
  
  .el-button {
    min-width: 100px;
    font-weight: 500;
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
</style>
