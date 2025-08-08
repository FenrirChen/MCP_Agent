<template>
  <div class="report-container">
    <header class="report-header">
      <h1>查询报告</h1>
      <p>生成于 <span>{{ generationTimestamp }}</span></p>
    </header>

    <main class="report-body" v-if="reportData">
      <div v-html="parsedReportHTML"></div>
    </main>

    <div v-else class="loading-state">
      <div class="spinner"></div>
      <p>正在加载报告数据...</p>
    </div>


  </div>
</template>

<script setup>

import { ref, onMounted, computed } from 'vue';

const reportData = ref(null);
const generationTimestamp = ref(new Date().toLocaleString('zh-CN'));

// onMounted 是Vue的生命周期钩子，组件加载后执行
onMounted(() => {
  const resultJSON = sessionStorage.getItem('latestAgentResult');
  if (resultJSON) {
    try {
      reportData.value = JSON.parse(resultJSON);
    } catch (e) {
      reportData.value = { final_answer: "报告数据格式错误。" };
    }
  } else {
    reportData.value = { final_answer: "未能加载报告数据。" };
  }
});

// 使用计算属性来动态生成报告HTML
const parsedReportHTML = computed(() => {
  if (!reportData.value) return '';
  const text = reportData.value.final_answer;

  let html = '';
  const lines = text.split('\n').filter(line => line.trim() !== '');
  let inSection = false;

  lines.forEach(line => {
    line = line.trim();
    if (line.startsWith('### ')) {
      if (inSection) html += `</div></div>`;
      html += `<div class="report-section"><h3>${line.substring(4)}</h3><div class="data-grid">`;
      inSection = true;
    } else if (line.startsWith('**') && line.includes('**:')) {
      const parts = line.split('**:');
      const key = parts[0].substring(2).trim();
      const value = parts[1].trim();
      html += `<span class="data-key">${key}</span><span class="data-value">${value}</span>`;
    } else {
      if (!inSection) {
           html += `<div class="report-section"><div class="data-grid">`;
           inSection = true;
      }
      html += `<span style="grid-column: 1 / -1;">${line}</span>`;
    }
  });
  if (inSection) html += `</div></div>`;
  return html;
});

</script>
