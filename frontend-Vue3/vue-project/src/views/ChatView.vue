<template>
  <div class="page-wrapper">
    <aside class="sidebar">
      <div class="sidebar-header">
        <button @click="startNewChat" id="new-chat-btn" class="sidebar-button">
          <i class="fas fa-plus"></i> 新建对话
        </button>
      </div>
      <nav class="chat-history-nav">
        <p>历史会话</p>
        <ul id="chat-history-list">
          </ul>
      </nav>
    </aside>

    <main class="chat-container">
      <div class="chat-messages" ref="chatMessagesContainer" @click="handleWorkflowClick">

        <div v-if="messages.length === 0" class="message welcome-message">
          <div class="avatar ai-avatar"><i class="fas fa-robot"></i></div>
          <div class="content">
            <h2>Agent</h2>
            <p>您好！我是您的专属金融助手。随时可以向我提问，例如：</p>
            <div class="example-prompts">
              <button @click="runPrompt" class="prompt-chip">查出应收账款逾期时间大于90天的项目详细信息</button>
              <button @click="runPrompt" class="prompt-chip">查询借款单 JKD20250804014</button>
            </div>
          </div>
        </div>

        <div v-for="(msg, index) in messages" :key="index" :class="['message', msg.role + '-message']">
          <div :class="['avatar', msg.role + '-avatar']">
            <i :class="['fas', msg.role === 'user' ? 'fa-user' : 'fa-robot']"></i>
          </div>
          <div class="content">
            <div v-if="msg.role === 'ai'" class="agent-response-container">
              <div class="final-answer" v-html="msg.final_answer.replace(/\n/g, '<br>')"></div>
              <div v-if="msg.execution_steps && msg.execution_steps.length > 0" class="buttons-container">
                <button @click.stop="toggleWorkflow(msg)" class="toggle-workflow-btn">
                  {{ msg.showWorkflow ? '隐藏工作过程 ▴' : '显示工作过程 ▾' }}
                </button>
                <button @click.stop="openDetailsPage(msg)" class="toggle-workflow-btn">
                  查看数据报告 ↗
                </button>
              </div>
              <div v-if="msg.showWorkflow" v-html="renderWorkflow(msg.execution_steps)"></div>
            </div>
            <div v-else v-html="msg.content.replace(/\n/g, '<br>')"></div>
          </div>
        </div>

        <div v-if="isLoading" class="message ai-message">
          <div class="avatar ai-avatar"><i class="fas fa-robot"></i></div>
          <div class="content">
            <div class="typing-indicator"><span></span><span></span><span></span></div>
          </div>
        </div>
      </div>

      <div class="chat-input-area">
        <div class="input-wrapper">
          <textarea v-model="userInput" @input="autoResizeTextarea" @keydown.enter.exact.prevent="sendMessage" placeholder="请输入您的任务..." rows="1"></textarea>
          <button @click="sendMessage" :disabled="isLoading" title="发送">
            <i class="fas fa-paper-plane"></i>
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue';

const userInput = ref('');
const messages = ref([]);
const isLoading = ref(false);
const chatMessagesContainer = ref(null);

const API_ENDPOINT = 'http://127.0.0.1:8000/chat';

const scrollToBottom = () => {
  nextTick(() => {
    if (chatMessagesContainer.value) {
      chatMessagesContainer.value.scrollTop = chatMessagesContainer.value.scrollHeight;
    }
  });
};

const startNewChat = () => {
  messages.value = [];
};

const runPrompt = (event) => {
    userInput.value = event.target.textContent;
    sendMessage();
};

const autoResizeTextarea = (event) => {
    const textarea = event.target;
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
};

const sendMessage = async () => {
  const task = userInput.value.trim();
  if (!task || isLoading.value) return;

  messages.value.push({ role: 'user', content: task });
  userInput.value = '';
  const textarea = document.querySelector('.input-wrapper textarea');
  if (textarea) textarea.style.height = 'auto';

  scrollToBottom();
  isLoading.value = true;

  try {
    const response = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: task })
    });
    if (!response.ok) throw new Error((await response.json()).detail || '请求失败');

    const result = await response.json();
    messages.value.push({ role: 'ai', ...result, showWorkflow: false });

  } catch (error) {
    messages.value.push({
      role: 'ai',
      final_answer: `出现错误: ${error.message}`,
      execution_steps: []
    });
  } finally {
    isLoading.value = false;
    scrollToBottom();
  }
};

const toggleWorkflow = (message) => {
  message.showWorkflow = !message.showWorkflow;
};

const openDetailsPage = (messageData) => {
  sessionStorage.setItem('latestAgentResult', JSON.stringify(messageData));
  window.open('/details', '_blank');
};


const renderWorkflow = (steps) => {
  let html = '<div class="workflow-container" style="display: block;">';
  steps.forEach(step => {
    let icon = '', title = '', details = '';
    switch (step.type) {
        case 'thought':
            icon = '💭'; title = '思考过程'; details = `<p>${step.content}</p>`;
            break;
        case 'tool_call':
            icon = '🔧'; title = `调用工具: <strong>${step.tool_name}</strong>`;
            try {
                const formattedArgs = JSON.stringify(JSON.parse(step.tool_args), null, 2);
                details = `<div class="step-title">输入参数:</div><pre><code>${formattedArgs}</code></pre>`;
            } catch { details = `<div class="step-title">输入参数:</div><pre><code>${step.tool_args}</code></pre>`; }
            break;
        case 'tool_output':
            icon = '📄'; title = `工具返回: <strong>${step.tool_name}</strong>`;
            details = `
                <div class="output-preview">${step.output_preview.replace(/</g, "&lt;")}</div>
                <button class="toggle-output-btn">查看/隐藏完整数据</button>
                <div class="output-full" style="display: none;"><pre><code>${step.output_full.replace(/</g, "&lt;")}</code></pre></div>
            `;
            break;
    }
    html += `<div class="workflow-step"><div class="step-icon">${icon}</div><div class="step-content"><div class="step-title">${title}</div>${details}</div></div>`;
  });
  html += '</div>';
  return html;
};

const handleWorkflowClick = (event) => {
  // 检查被点击的元素是否是我们的“查看/隐藏”按钮
  if (event.target.classList.contains('toggle-output-btn')) {
    // 找到按钮旁边的完整数据容器
    const fullOutputDiv = event.target.nextElementSibling;
    if (fullOutputDiv && fullOutputDiv.classList.contains('output-full')) {
      // 切换它的显示状态
      const isHidden = fullOutputDiv.style.display === 'none';
      fullOutputDiv.style.display = isHidden ? 'block' : 'none';
    }
  }
};
</script>

<style scoped>
.page-wrapper {
  height: 100vh;
}
.buttons-container {
    display: flex;
    gap: 10px;
    margin-top: 10px;
}
</style>
