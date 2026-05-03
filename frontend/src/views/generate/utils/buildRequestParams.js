/**
 * 构建大纲生成请求参数
 * 根据内容类型（小说/剧本）构建对应的输入参数
 */

/**
 * 构建大纲生成的输入参数
 * @param {string} contentType - 内容类型 ('novel' | 'script' | 'movie-outline' | 'series-outline')
 * @param {Object} formData - 表单数据
 * @param {Object} styleData - 文风数据 { styleIds, styleNames, intensity, styleGuide }
 * @param {Object} titleStyleData - 标题风格数据 { styleId, styleName }
 * @returns {Object} 大纲生成的输入参数
 */
export function buildOutlineInputParams(contentType, formData, styleData = {}, titleStyleData = {}) {
  if (contentType === 'novel') {
    const lengthMap = { 'short': '短篇', 'medium': '中篇', 'long': '长篇' }
    return {
      title: formData.title || '',
      length: lengthMap[formData.length] || '中篇',
      target_platform: formData.target_platform || '起点',
      synopsis: formData.description,
      chapter_count: formData.chapter_count || '50',
      custom_outline: formData.custom_outline || '',
      // 文风参数
      style_ids: styleData.styleIds || [],
      style_names: styleData.styleNames || [],
      style_intensity: styleData.intensity || 0.7,
      style_guide: styleData.styleGuide || null,
      // 标题风格参数
      title_style: titleStyleData.styleId || '',
      title_style_name: titleStyleData.styleName || ''
    }
  } else if (contentType === 'movie-outline') {
    const base = {
      title: formData.title || '',
      movie_type: formData.movie_type || '院线电影',
      theme: formData.genre || '剧情',
      audience: formData.target_audience || '年轻观众',
      platform: formData.platform || '院线发行',
      reference_works: formData.reference_works || '无',
      synopsis: formData.description,
      scene_count: formData.scene_count || null,
      custom_outline: formData.custom_outline || '',
      duration_range: `${formData.duration_range?.[0] || 90}-${formData.duration_range?.[1] || 120}分钟`,
      scene_count_range: formData.scene_count_range || 'AI自动设计',
      format_standard: formData.format_standard || '标准格式',
      dialogue_narration_ratio: formData.dialogue_narration_ratio || '均衡',
      script_mode: formData.script_mode || 'real',
      // 标题风格参数
      title_style: titleStyleData.styleId || '',
      title_style_name: titleStyleData.styleName || ''
    }
    // 电影多维风格参数
    if (styleData.styleType === 'movie' && styleData.selectedNames && styleData.selectedNames.length > 0) {
      base.script_style_dimensions = styleData.dimensions || {}
      base.script_style_names = styleData.selectedNames || []
      base.script_style_intensity = styleData.intensity || 0.7
      base.script_style_type = 'movie'
    } else if (styleData.styleIds && styleData.styleIds.length > 0) {
      // 兼容旧文风格式
      base.style_ids = styleData.styleIds || []
      base.style_names = styleData.styleNames || []
      base.style_intensity = styleData.intensity || 0.7
      base.style_guide = styleData.styleGuide || null
    }
    return base
  } else if (contentType === 'series-outline') {
    const base = {
      title: formData.title || '',
      series_type: formData.series_type || '电视剧',
      theme: formData.genre || '都市',
      audience: formData.target_audience || '年轻观众',
      platform: formData.platform || '爱奇艺',
      reference_works: formData.reference_works || '无',
      synopsis: formData.description,
      episode_count: formData.episode_count || '24',
      custom_outline: formData.custom_outline || '',
      episode_duration_range: `${formData.episode_duration_range?.[0] || 25}-${formData.episode_duration_range?.[1] || 35}分钟`,
      scenes_per_episode_range: formData.scenes_per_episode_range || 'AI自动设计',
      format_standard: formData.format_standard || '标准格式',
      dialogue_narration_ratio: formData.dialogue_narration_ratio || '均衡',
      script_mode: formData.script_mode || 'real',
      // 标题风格参数
      title_style: titleStyleData.styleId || '',
      title_style_name: titleStyleData.styleName || ''
    }
    // 剧集多维风格参数
    if (styleData.styleType === 'series' && styleData.selectedNames && styleData.selectedNames.length > 0) {
      base.script_style_dimensions = styleData.dimensions || {}
      base.script_style_names = styleData.selectedNames || []
      base.script_style_intensity = styleData.intensity || 0.7
      base.script_style_type = 'series'
      base.script_series_sub_type = styleData.seriesSubType || 'long'
    } else if (styleData.styleIds && styleData.styleIds.length > 0) {
      // 兼容旧文风格式
      base.style_ids = styleData.styleIds || []
      base.style_names = styleData.styleNames || []
      base.style_intensity = styleData.intensity || 0.7
      base.style_guide = styleData.styleGuide || null
    }
    return base
  }
  return {}
}
