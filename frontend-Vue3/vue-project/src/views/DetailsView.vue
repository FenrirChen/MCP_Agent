<template>
  <div class="report-container" @click="handleContainerClick"> <header class="report-header">
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
            <Bar ref="chartRef" :data="reportData.chart_data" :options="chartOptions" />
          </div>

          <div v-else-if="reportData.visualization_type === 'pie'" class="chart-container" style="position: relative; height:400px; max-width: 400px; margin: auto;">
            <Pie ref="chartRef" :data="reportData.chart_data" :options="chartOptions" />
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

// --- 新增：API端点常量 ---
const PROBE_API_ENDPOINT = 'http://127.0.0.1:8000/api/execute_probe';

const reportData = ref(null);
const isLoading = ref(true);
const errorMessage = ref("未能加载报告数据或报告中不包含表格。");
const generationTimestamp = ref(new Date().toLocaleString('zh-CN'));
// --- 新增：图表组件的引用 ---
const chartRef = ref(null);


// --- 新增：处理探针点击的核心逻辑 ---

const handleDrillDown = async (probe) => {
  if (!probe) return;

  console.log("即将执行探针:", probe);
  isLoading.value = true;
  errorMessage.value = '';

  try {
    // 构造请求体
    const requestBody = {
      service_name: probe.service_name,
      // 根据您的要求，添加 isQuery 参数
      isQuery: true,
      // 将 probe.params 放入 body 字段
      body: probe.params
    };

    const response = await fetch(PROBE_API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody) // 发送构造好的请求体
    });
    if (!response.ok) {
      const errData = await response.json();
      throw new Error(errData.detail || '探针执行失败');
    }
    const result = await response.json();

    reportData.value = result;

    if (result.title) {
      chartOptions.value.plugins.title.text = result.title;
    }
    generationTimestamp.value = new Date().toLocaleString('zh-CN');

  } catch (error) {
    console.error("探针执行出错:", error);
    errorMessage.value = `数据下钻失败: ${error.message}`;
  } finally {
    isLoading.value = false;
  }
};

const handleContainerClick = (event) => {
  // 检查当前显示的是表格还是图表
  if (reportData.value?.visualization_type === 'table') {
    // 如果是表格，则执行表格的点击逻辑
    handleTableClick(event);
  } else {
    // 如果是图表，则执行图表的点击逻辑
    handleChartClick(event);
  }
};

// --- 修改后的 handleTableClick (只保留内部逻辑) ---
const handleTableClick = (event) => {
  const cell = event.target.closest('.clickable-cell');
  if (cell && cell.dataset.probe) {
    try {
      const probe = JSON.parse(cell.dataset.probe);
      handleDrillDown(probe);
    } catch (e) {
      console.error("解析探针失败:", e);
    }
  }
};

// --- 修改后的 handleChartClick (只保留内部逻辑) ---
const handleChartClick = (event) => {
  const chart = chartRef.value?.chart;
  if (!chart) return;

  const points = chart.getElementsAtEventForMode(event, 'nearest', { intersect: true }, true);

  if (points.length) {
    const firstPoint = points[0];
    const datasetIndex = firstPoint.datasetIndex;
    const dataIndex = firstPoint.index;

    const probe = reportData.value?.chart_data?.datasets[datasetIndex]?.probes?.[dataIndex];

    if (probe) {
      handleDrillDown(probe);
    }
  }
};


// --- 您已有的代码 (保持不变) ---

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

const originalStyles = {
  html: { overflowY: '', height: '' },
  body: { overflowY: '', height: '' },
  app: { overflowY: '', height: '' }
};

onMounted(() => {
  console.log("--- 调试信息：报告组件 onMounted 钩子已执行 ---");
  // ... (此部分生命周期钩子代码保持不变)
  const html = document.documentElement;
  const body = document.body;
  const app = document.getElementById('app');

  originalStyles.html.overflowY = html.style.overflowY;
  originalStyles.html.height = html.style.height;
  originalStyles.body.overflowY = body.style.overflowY;
  originalStyles.body.height = body.style.height;
  if (app) {
    originalStyles.app.overflowY = app.style.overflowY;
    originalStyles.app.height = app.style.height;
  }
  html.style.overflowY = 'auto';
  html.style.height = 'auto';
  body.style.overflowY = 'auto';
  body.style.height = 'auto';
  if (app) {
    app.style.overflowY = 'auto';
    app.style.height = 'auto';
  }

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
  // ... (此部分生命周期钩子代码保持不变)
  const html = document.documentElement;
  const body = document.body;
  const app = document.getElementById('app');
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
  try { // <--- 新增 try 块
    if (!reportData.value || !reportData.value.table_data || !reportData.value.table_data.tables) {
      return '';
    }

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
            let displayValue = cell;
            let probe = null;
            if (typeof cell === 'object' && cell !== null && Object.hasOwn(cell, 'value')) {
              displayValue = cell.value;
              probe = cell.probe;
            }
            if (probe) {
              const probeString = JSON.stringify(probe).replace(/'/g, '&apos;');
              html += `<td class="clickable-cell" data-probe='${probeString}'>${displayValue}</td>`;
            } else {
              html += `<td>${displayValue}</td>`;
            }
          });
          html += '</tr>';
        });
      } else {
        const colSpan = table.headers && table.headers.length > 0 ? table.headers.length : 1;
        html += `<tr><td colspan="${colSpan}" style="text-align: center; color: #888;">没有可显示的数据</td></tr>`;
      }
      html += '</tbody></table></div>';
    });

    return html;

  } catch (error) { // <--- 新增 catch 块
    console.error("!!! tablesHTML 渲染时发生致命错误:", error);
    // 返回一个错误的HTML，这样页面就不会空白，而是会显示错误信息
    return `<div class="error-message">渲染表格时出现错误，请检查控制台获取详细信息。</div>`;
  }
});
</script>
<style scoped>
.report-container :deep(table td.clickable-cell) {
  color: #007bff !important;
  text-decoration: underline !important;
  cursor: pointer;
  transition: color 0.2s;
}

.report-container :deep(table td.clickable-cell:hover) {
  color: #0056b3 !important;
}

</style>

