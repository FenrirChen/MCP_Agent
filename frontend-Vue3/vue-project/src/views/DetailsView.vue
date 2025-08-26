<template>
  <div class="report-container">
    <header class="report-header">
      <h1>{{ pageTitle }}</h1>
      <p>由 AI 助手生成于 <span>{{ generationTimestamp }}</span></p>
    </header>

    <main class="report-body">
      <div v-if="isLoading" class="loading-state">
        <div class="spinner"></div>
        <p>正在加载报告数据...</p>
      </div>

      <div v-else-if="reportData && reportData.visualization_type">
        <div class="report-section">

          <div v-if="reportData.visualization_type === 'table'" v-html="tablesHTML"></div>

          <div v-else-if="reportData.visualization_type === 'bar'" class="chart-container" style="position: relative; height:400px">
            <Bar :data="reportData.chart_data" :options="chartOptions" />
          </div>

          <div v-else-if="reportData.visualization_type === 'pie'" class="chart-container" style="position: relative; height:400px; max-width: 400px; margin: auto;">
            <Pie :data="reportData.chart_data" :options="chartOptions" />
          </div>
        </div>
      </div>

      <div v-else class="loading-state">
        <p>{{ errorMessage }}</p>
      </div>
    </main>

    <footer class="report-footer">
        <p>请注意：本报告由 AI 生成，仅供参考，请结合实际业务情况进行核对。</p>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  BarElement,
  CategoryScale,
  LinearScale,
  ArcElement
} from 'chart.js';
import { Bar, Pie } from 'vue-chartjs';
ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, ArcElement);

const reportData = ref(null);
const isLoading = ref(true);
const errorMessage = ref("未能加载报告数据或报告中不包含表格。");
const generationTimestamp = ref(new Date().toLocaleString('zh-CN'));

// 问题2解决：定义 pageTitle 计算属性
const pageTitle = computed(() => {
  if (reportData.value && reportData.value.title) {
    return reportData.value.title;
  }
  return '金融查询报告'; // 默认标题
});

const chartOptions = ref({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'top',
    },
    title: {
      display: true,
      text: '图表',
    }
  }
});

// 问题1解决：增强版的生命周期钩子，用于控制页面滚动
const originalStyles = {
  html: { overflowY: '', height: '' },
  body: { overflowY: '', height: '' },
  app: { overflowY: '', height: '' }
};

onMounted(() => {
  console.log("--- 调试信息：报告组件 onMounted 钩子已执行 ---");

  console.log("报告组件已挂载，开始修改全局滚动样式...");
  const html = document.documentElement;
  const body = document.body;
  const app = document.getElementById('app');

  // 1. 保存原始样式
  originalStyles.html.overflowY = html.style.overflowY;
  originalStyles.html.height = html.style.height;
  originalStyles.body.overflowY = body.style.overflowY;
  originalStyles.body.height = body.style.height;
  if (app) {
    originalStyles.app.overflowY = app.style.overflowY;
    originalStyles.app.height = app.style.height;
  }

  // 2. 强制应用允许滚动的样式
  html.style.overflowY = 'auto';
  html.style.height = 'auto';
  body.style.overflowY = 'auto';
  body.style.height = 'auto';
  if (app) {
    app.style.overflowY = 'auto';
    app.style.height = 'auto';
  }

  // --- 原有的 onMounted 逻辑 ---
  const resultJSON = sessionStorage.getItem('latestAgentResult');
  if (resultJSON) {
    try {
      const parsedData = JSON.parse(resultJSON);
      reportData.value = parsedData;
      if (parsedData.title) {
        chartOptions.value.plugins.title.text = parsedData.title;
      }
    } catch (e) {
      console.error("JSON 解析失败:", e);
      errorMessage.value = "报告数据格式错误，无法解析。";
    }
  }
  isLoading.value = false;
});

onUnmounted(() => {
  const html = document.documentElement;
  const body = document.body;
  const app = document.getElementById('app');

  // 组件销毁时，恢复保存的原始样式
  html.style.overflowY = originalStyles.html.overflowY;
  html.style.height = originalStyles.html.height;
  body.style.overflowY = originalStyles.body.overflowY;
  body.style.height = originalStyles.body.height;
  if (app) {
    app.style.overflowY = originalStyles.app.overflowY;
    app.style.height = originalStyles.app.height;
  }
});

const tablesHTML = computed(() => {
  if (!reportData.value || !reportData.value.table_data || !reportData.value.table_data.tables) {
    return '';
  }
  // ... (这部分逻辑不变)
  const tables = reportData.value.table_data.tables;
  let html = '';
  tables.forEach(table => {
    html += '<div class="report-section">';
    if (table.title) {
      html += `<h3>${table.title}</h3>`;
    }
    html += '<table class="report-table">';
    if (table.headers && table.headers.length > 0) {
      html += '<thead><tr>';
      table.headers.forEach(header => {
        html += `<th>${header}</th>`;
      });
      html += '</tr></thead>';
    }
    html += '<tbody>';
    if (table.rows && table.rows.length > 0) {
      table.rows.forEach(row => {
        html += '<tr>';
        row.forEach(cell => {
          html += `<td>${cell}</td>`;
        });
        html += '</tr>';
      });
    } else {
      const colSpan = table.headers && table.headers.length > 0 ? table.headers.length : 1;
      html += `<tr><td colspan="${colSpan}" style="text-align: center; color: #888;">没有可显示的数据</td></tr>`;
    }
    html += '</tbody>';
    html += '</table></div>';
  });
  return html;
});
</script>


