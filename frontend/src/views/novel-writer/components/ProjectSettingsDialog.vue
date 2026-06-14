<!--
  组件: ProjectSettingsDialog
  自动生成于: 脚本批量拆分
-->
<template>
<el-form :model="settingsForm" label-width="120px">
        <el-form-item label="项目标题">
          <el-input v-model="settingsForm.title" />
        </el-form-item>
        <el-form-item label="题材">
          <el-input v-model="settingsForm.genre" />
        </el-form-item>
        
        <el-divider content-position="left">生成配置</el-divider>
        
        <!-- 小说设置 -->
        <template v-if="project?.content_type === 'novel'">
          <el-form-item label="投放平台">
            <el-input v-model="settingsForm.novel_config.target_platform" placeholder="如：起点中文网、豆瓣阅读" />
          </el-form-item>
          <el-form-item label="每章字数">
            <el-input-number v-model="settingsForm.novel_config.words_per_chapter" :min="1000" :max="10000" :step="500" />
          </el-form-item>
          <el-form-item label="叙事视角">
            <el-select v-model="settingsForm.novel_config.narrative_perspective">
              <el-option label="第一人称" value="第一人称" />
              <el-option label="第三人称" value="第三人称" />
            </el-select>
          </el-form-item>
          <el-form-item label="基调风格">
            <el-select v-model="settingsForm.novel_config.tone">
              <el-option label="正剧" value="正剧" />
              <el-option label="轻松" value="轻松" />
              <el-option label="幽默" value="幽默" />
              <el-option label="严肃" value="严肃" />
              <el-option label="温馨" value="温馨" />
              <el-option label="热血" value="热血" />
            </el-select>
          </el-form-item>
        </template>
        
        <!-- 剧集剧本设置 -->
        <template v-else-if="project?.content_type === 'series_script'">
          <el-form-item label="剧集类型">
            <el-select v-model="settingsForm.series_script_config.series_type">
              <el-option label="电视剧" value="电视剧" />
              <el-option label="网络剧" value="网络剧" />
              <el-option label="短剧" value="短剧" />
              <el-option label="微短剧" value="微短剧" />
            </el-select>
          </el-form-item>
          <el-form-item label="叙事模式">
            <el-radio-group v-model="settingsForm.series_script_config.narrative_mode">
              <el-radio value="serialized">连续剧（各集情节连贯）</el-radio>
              <el-radio value="episodic_with_arc">主线串联单元剧（各集独立故事，共享主线发展）</el-radio>
              <el-radio value="episodic">纯单元剧（每集完全独立）</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="每集时长">
            <div style="display: flex; align-items: center; gap: 10px;">
              <el-input-number v-model="settingsForm.series_script_config.episode_duration_range[0]" :min="1" :max="120" :step="5" style="width: 100px;" />
              <span>-</span>
              <el-input-number v-model="settingsForm.series_script_config.episode_duration_range[1]" :min="1" :max="120" :step="5" style="width: 100px;" />
              <span style="color: #909399;">分钟</span>
            </div>
          </el-form-item>
          <el-form-item label="剧本格式">
            <el-select v-model="settingsForm.series_script_config.format_standard">
              <el-option label="标准格式" value="标准格式" />
              <el-option label="简格式" value="简格式" />
              <el-option label="网络平台格式" value="网络平台格式" />
              <el-option label="短剧格式" value="短剧格式" />
            </el-select>
          </el-form-item>
          <el-form-item label="对白比例">
            <el-select v-model="settingsForm.series_script_config.dialogue_narration_ratio">
              <el-option label="对话为主" value="对话为主" />
              <el-option label="均衡" value="均衡" />
              <el-option label="叙述为主" value="叙述为主" />
              <el-option label="动作导向" value="动作导向" />
            </el-select>
          </el-form-item>
          <el-form-item label="投放平台">
            <el-input v-model="settingsForm.series_script_config.target_broadcast" placeholder="如：爱奇艺、腾讯视频" />
          </el-form-item>
        </template>
        
        <!-- 电影剧本设置 -->
        <template v-else-if="project?.content_type === 'movie_script'">
          <el-form-item label="电影类型">
            <el-select v-model="settingsForm.movie_script_config.movie_type">
              <el-option label="院线电影" value="院线电影" />
              <el-option label="网络电影" value="网络电影" />
              <el-option label="微电影" value="微电影" />
              <el-option label="纪录片" value="纪录片" />
            </el-select>
          </el-form-item>
          <el-form-item label="叙事模式">
            <el-radio-group v-model="settingsForm.movie_script_config.narrative_mode">
              <el-radio value="serialized">连续叙事（情节连贯推进）</el-radio>
              <el-radio value="episodic_with_arc">主线串联单元电影（各段独立，共享主线发展）</el-radio>
              <el-radio value="episodic">纯单元电影/短片合集（各段完全独立）</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="电影时长">
            <el-input-number v-model="settingsForm.movie_script_config.total_duration" :min="5" :max="180" :step="5" />
            <span style="color: #909399; margin-left: 10px;">分钟</span>
          </el-form-item>
          <el-form-item label="剧本格式">
            <el-select v-model="settingsForm.movie_script_config.format_standard">
              <el-option label="标准格式" value="标准格式" />
              <el-option label="影院格式" value="影院格式" />
              <el-option label="电视电影格式" value="电视电影格式" />
            </el-select>
          </el-form-item>
          <el-form-item label="对白比例">
            <el-select v-model="settingsForm.movie_script_config.dialogue_narration_ratio">
              <el-option label="对话为主" value="对话为主" />
              <el-option label="均衡" value="均衡" />
              <el-option label="叙述为主" value="叙述为主" />
              <el-option label="动作导向" value="动作导向" />
            </el-select>
          </el-form-item>
        </template>
        
        <el-divider content-position="left">项目专属知识库</el-divider>
        
        <el-alert
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 16px;"
        >
          <template #title>
            <span style="font-size: 13px;">项目专属知识库完全独立于公共知识库，仅存储本项目大纲的实体和关系。</span>
          </template>
        </el-alert>
        
        <!-- 项目知识库状态 -->
        <el-form-item label="知识库状态">
          <div class="kb-setting-status">
            <el-tag :type="kbStatus.status === 'ready' ? 'success' : kbStatus.status === 'building' ? 'warning' : kbStatus.status === 'failed' ? 'danger' : 'info'" size="small">
              {{ kbStatus.status === 'ready' ? '已就绪' : kbStatus.status === 'building' ? '构建中' : kbStatus.status === 'failed' ? '构建失败' : '未构建' }}
            </el-tag>
            <el-button
              v-if="kbStatus.status !== 'ready' && kbStatus.status !== 'building'"
              type="primary"
              size="small"
              :disabled="!project.outline_content"
              :loading="buildingKb"
              @click="$emit('build-knowledge-base')"
              style="margin-left: 8px;"
            >
              构建知识库
            </el-button>
            <el-button
              v-if="kbStatus.status === 'ready'"
              type="warning"
              size="small"
              :loading="buildingKb"
              @click="$emit('build-knowledge-base')"
              style="margin-left: 8px;"
            >
              重建知识库
            </el-button>
            <span v-if="!project.outline_content" class="form-tip warn">（需先上传大纲）</span>
          </div>
        </el-form-item>
        
        <el-form-item label="GraphRAG增强">
          <el-switch v-model="settingsForm.graphrag_enabled" />
          <span class="form-tip">启用知识图谱增强检索（自动从大纲提取人物、事件等实体关系）</span>
        </el-form-item>
        
        <el-form-item v-if="kbStatus.status === 'ready' && kbStatus.progress" label="图谱统计">
          <div class="kb-stats-info">
            <span>实体: {{ kbStatus.progress.entity_count || 0 }}</span>
            <span style="margin-left: 16px;">关系: {{ kbStatus.progress.relation_count || 0 }}</span>
          </div>
        </el-form-item>
        
        <el-divider content-position="left">公共知识库（可选参考）</el-divider>
        
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          style="margin-bottom: 16px;"
        >
          <template #title>
            <span style="font-size: 13px;">公共知识库用于正文生成时参考创意理论、案例技巧等，与项目专属知识库完全独立。</span>
          </template>
        </el-alert>
        
        <el-form-item label="垂直领域知识库">
          <el-switch v-model="settingsForm.kb_vertical_enabled" />
          <span class="form-tip">小说/剧本案例、技巧等</span>
        </el-form-item>
        
        <el-form-item label="用户专属知识库">
          <el-switch v-model="settingsForm.kb_user_specific_enabled" />
          <span class="form-tip">您上传的个性化知识</span>
        </el-form-item>
        
        <el-form-item label="官方手册">
          <el-switch v-model="settingsForm.kb_manual_enabled" />
          <span class="form-tip">官方规范、标准手册</span>
        </el-form-item>
        
        <el-divider content-position="left">合规审核</el-divider>
        
        <el-alert
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 16px;"
        >
          <template #title>
            <span style="font-size: 13px;">合规审核会标记正文中的敏感词、敏感地名、名人姓名等潜在问题，供您参考修改。</span>
          </template>
        </el-alert>
        
        <el-form-item label="启用合规审核">
          <el-switch v-model="settingsForm.compliance_enabled" />
          <span class="form-tip">生成后自动检测并标记潜在问题</span>
        </el-form-item>
        
        <el-form-item v-if="settingsForm.compliance_enabled" label="审核级别">
          <el-radio-group v-model="settingsForm.compliance_level">
            <el-radio value="strict">严格模式</el-radio>
            <el-radio value="normal">标准模式</el-radio>
            <el-radio value="loose">宽松模式</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <el-form-item v-if="settingsForm.compliance_enabled" label="目标平台">
          <el-select v-model="settingsForm.compliance_platform" placeholder="选择目标发布平台" style="width: 200px;">
            <el-option label="通用" value="" />
            <el-option label="起点中文网" value="起点中文网" />
            <el-option label="晋江文学城" value="晋江文学城" />
            <el-option label="番茄小说" value="番茄小说" />
            <el-option label="飞卢小说" value="飞卢小说" />
            <el-option label="纵横中文网" value="纵横中文网" />
            <el-option label="17K小说网" value="17K小说网" />
            <el-option label="其他平台" value="其他" />
          </el-select>
          <span class="form-tip">不同平台有不同的内容规范</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" @click="saveSettings" :loading="savingSettings">保存</el-button>
      </template>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
    visible: { type: Boolean, default: false },
    project: { type: Object },
    settingsForm: { type: Object },
    kbStatus: { type: Object, default: () => ({}) },
    buildingKb: { type: Boolean, default: false },
    savingSettings: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'save', 'build-knowledge-base'])
const handleClose = () => emit('update:visible', false)

</script>
