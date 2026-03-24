<template>
  <div class="tenant-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>租户管理</span>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            新建租户
          </el-button>
        </div>
      </template>
      
      <el-table :data="tenants" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="租户名称" />
        <el-table-column prop="code" label="租户编码" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'danger'">
              {{ row.status === 'active' ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const tenants = ref([])

const fetchTenants = async () => {
  loading.value = true
  try {
    // TODO: 调用API获取租户列表
    tenants.value = []
  } catch (error) {
    ElMessage.error('获取租户列表失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  ElMessage.info('新建租户功能开发中')
}

const handleEdit = (row) => {
  ElMessage.info('编辑功能开发中')
}

const handleDelete = (row) => {
  ElMessageBox.confirm('确定要删除该租户吗？', '提示', {
    type: 'warning'
  }).then(() => {
    ElMessage.success('删除成功')
    fetchTenants()
  }).catch(() => {})
}

onMounted(() => {
  fetchTenants()
})
</script>

<style scoped>
.tenant-management {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
