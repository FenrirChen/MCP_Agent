// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'
import DetailsView from '../views/DetailsView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: ChatView // 主聊天页面
    },
    {
      path: '/details',
      name: 'details',
      component: DetailsView // 数据报告详情页
    }
  ]
})

export default router
