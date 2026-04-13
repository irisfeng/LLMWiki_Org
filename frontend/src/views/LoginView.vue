<template>
  <div class="login-container">
    <div class="login-card">
      <h1>团队知识库</h1>
      <p class="subtitle">请输入团队密码以继续</p>
      <el-form @submit.prevent="handleLogin">
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            style="width: 100%"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>
      <p v-if="error" class="error-msg">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const password = ref('')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  if (!password.value) {
    error.value = '请输入密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const resp = await axios.post('/api/auth/login', { password: password.value })
    localStorage.setItem('token', resp.data.access_token)
    router.push('/')
  } catch (e: any) {
    error.value = e.response?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #f5f7fa;
}
.login-card {
  background: white;
  padding: 40px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  width: 380px;
  text-align: center;
}
.login-card h1 {
  margin: 0 0 8px;
  font-size: 24px;
  color: #303133;
}
.subtitle {
  color: #909399;
  margin-bottom: 24px;
  font-size: 14px;
}
.error-msg {
  color: #f56c6c;
  font-size: 13px;
  margin-top: 0;
}
</style>
