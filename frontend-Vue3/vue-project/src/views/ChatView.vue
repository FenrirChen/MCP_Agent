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
              <button @click="runPrompt" class="prompt-chip">用条形图展示本单位今年毛利率排名前十的经营项目</button>
              <button @click="runPrompt" class="prompt-chip">公司车辆管理系统2022-2024年软件许可采购项目收入与支出的详情数据</button>
            </div>
          </div>
        </div>

        <div v-for="(msg, index) in messages" :key="index" :class="['message', msg.role + '-message']">
          <div :class="['avatar', msg.role + '-avatar']">
            <i :class="['fas', msg.role === 'user' ? 'fa-user' : 'fa-robot']"></i>
          </div>
          <div class="content">
            <div v-if="msg.role === 'ai'" class="agent-response-container">

              <div v-if="msg.final_answer" class="final-answer" v-html="msg.final_answer.replace(/\n/g, '<br>')"></div>
              <div v-if="msg.isStreaming && !hasContent(msg)" class="typing-indicator">
                <span></span><span></span><span></span>
              </div>

              <div v-if="msg.showWorkflow">
                <div v-if="msg.execution_steps.length > 0" v-html="renderWorkflow(msg.execution_steps)"></div>
                <div v-if="msg.streaming_thought" class="workflow-step">
                    <div class="step-icon">💭</div>
                    <div class="step-content">
                        <div class="step-title">思考过程</div>
                        <p v-html="msg.streaming_thought.replace(/\n/g, '<br>')"></p>
                    </div>
                </div>
              </div>

              <div v-if="!msg.isStreaming && msg.execution_steps.length > 0" class="buttons-container">
                <button @click.stop="toggleWorkflow(msg)" class="toggle-workflow-btn">
                  {{ msg.showWorkflow ? '隐藏工作过程 ▴' : '显示工作过程 ▾' }}
                </button>
                <button v-if="msg.visualization_type" @click.stop="openDetailsPage(msg)" class="toggle-workflow-btn">
                  查看数据报告 ↗
                </button>
              </div>

            </div>
            <div v-else v-html="msg.content.replace(/\n/g, '<br>')"></div>
          </div>
        </div>
      </div>

      <div class="chat-input-area">
        <div class="input-wrapper">
          <textarea v-model="userInput" @input="autoResizeTextarea" @keydown.enter.exact.prevent="sendMessage" placeholder="请输入您的任务..." rows="1"></textarea>
          <button @click="sendMessage" :disabled="isSending" title="发送">
            <i class="fas fa-paper-plane"></i>
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, nextTick, computed } from 'vue';

const userInput = ref('');
const messages = ref([]);
const chatMessagesContainer = ref(null);

const API_ENDPOINT = '/api/chat/stream'; // 使用相对路径指向Nginx代理

// 计算属性，用于在流式传输期间禁用发送按钮
const isSending = computed(() => {
    if (messages.value.length === 0) return false;
    const lastMessage = messages.value[messages.value.length - 1];
    return lastMessage.role === 'ai' && lastMessage.isStreaming;
});

const hasContent = (msg) => {
    return msg.streaming_thought || msg.execution_steps.length > 0 || msg.final_answer;
};

const scrollToBottom = () => {
  nextTick(() => {
    if (chatMessagesContainer.value) {
      chatMessagesContainer.value.scrollTop = chatMessagesContainer.value.scrollHeight;
    }
  });
};

// startNewChat, runPrompt, autoResizeTextarea (无变动)
const startNewChat = () => { messages.value = []; };
const runPrompt = (event) => { userInput.value = event.target.textContent; sendMessage(); };
const autoResizeTextarea = (event) => { const textarea = event.target; textarea.style.height = 'auto'; textarea.style.height = textarea.scrollHeight + 'px'; };

// ***** 重写 sendMessage 函数以支持累加器模式 *****
const sendMessage = async () => {
  const task = userInput.value.trim();
  if (!task || isSending.value) return;

  messages.value.push({ role: 'user', content: task });
  userInput.value = '';
  const textarea = document.querySelector('.input-wrapper textarea');
  if (textarea) textarea.style.height = 'auto';
  scrollToBottom();

  // 添加一个“空的”、带累加器属性的 AI 消息对象
  messages.value.push({
    role: 'ai',
    execution_steps: [],
    streaming_thought: "",
    final_answer: "",
    isStreaming: true,
    showWorkflow: true,
    visualization_type: null,
    title: null,
    table_data: null,
    chart_data: null,
  });
  scrollToBottom();

  try {
    const response = await fetch(API_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: task })
    });
    if (!response.ok) throw new Error((await response.json()).detail || '请求失败');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    const aiMessage = messages.value[messages.value.length - 1];

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        // 在流自然结束后，如果stream_end事件没发过来，也做一次最终清理
        if (aiMessage.isStreaming) {
          aiMessage.isStreaming = false;
          if (aiMessage.streaming_thought) {
              aiMessage.execution_steps.push({ type: 'thought', content: aiMessage.streaming_thought });
              aiMessage.streaming_thought = "";
          }
          if (aiMessage.execution_steps.length > 0) aiMessage.showWorkflow = false;
        }
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');

      for (let i = 0; i < lines.length - 1; i++) {
        const line = lines[i].trim();
        if (line) {
          try {
            const event = JSON.parse(line);
            switch (event.type) {
                case 'thought_chunk':
                    aiMessage.streaming_thought += event.data.content;
                    break;

                case 'final_answer':
                    aiMessage.final_answer = event.data.content;
                    break;

                case 'tool_call':
                    if (aiMessage.streaming_thought) {
                        aiMessage.execution_steps.push({ type: 'thought', content: aiMessage.streaming_thought });
                        aiMessage.streaming_thought = "";
                    }
                    aiMessage.execution_steps.push({ ...event.data, type: 'tool_call' });
                    break;

                case 'tool_output':
                    aiMessage.execution_steps.push({ ...event.data, type: 'tool_output' });
                    break;

                case 'visualization_data':
                    Object.assign(aiMessage, event.data);
                    break;

                case 'stream_end':
                    aiMessage.isStreaming = false;
                    if (aiMessage.streaming_thought) {
                        aiMessage.execution_steps.push({ type: 'thought', content: aiMessage.streaming_thought });
                        aiMessage.streaming_thought = "";
                    }
                    if (aiMessage.execution_steps.length > 0) {
                        aiMessage.showWorkflow = false;
                    }
                    break;
            }
          } catch (error) {
            console.error('JSON 解析失败:', line, error);
          }
        }
      }
      buffer = lines[lines.length - 1];
      const el = chatMessagesContainer.value;
      const isScrolledToBottom = el ? (el.scrollHeight - el.clientHeight <= el.scrollTop + 100) : true;

      await nextTick();

      if (isScrolledToBottom) {
        scrollToBottom();
      }
    }

  } catch (error) {
    const aiMessage = messages.value[messages.value.length - 1];
    aiMessage.final_answer = `请求失败: ${error.message}`;
    aiMessage.isStreaming = false;
  }
};

// toggleWorkflow, openDetailsPage, renderWorkflow, handleWorkflowClick (无变动)
const toggleWorkflow = (message) => { message.showWorkflow = !message.showWorkflow; };
const openDetailsPage = (messageData) => { sessionStorage.setItem('latestAgentResult', JSON.stringify(messageData)); window.open('/details', '_blank'); };
const renderWorkflow = (steps) => {
  let html = '<div class="workflow-container">';
  steps.forEach(step => {
    let icon = '', title = '', details = '';
    switch (step.type) {
        case 'thought':
            icon = '💭'; title = '思考过程'; details = `<p>${step.content.replace(/\n/g, '<br>')}</p>`;
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
                <div class="output-preview">${String(step.output_preview || '').replace(/</g, "&lt;")}</div>
                <button class="toggle-output-btn">查看/隐藏完整数据</button>
                <div class="output-full" style="display: none;"><pre><code>${String(step.output_full || '').replace(/</g, "&lt;")}</code></pre></div>
            `;
            break;
    }
    html += `<div class="workflow-step"><div class="step-icon">${icon}</div><div class="step-content"><div class="step-title">${title}</div>${details}</div></div>`;
  });
  html += '</div>';
  return html;
};
const handleWorkflowClick = (event) => {
  if (event.target.classList.contains('toggle-output-btn')) {
    const fullOutputDiv = event.target.nextElementSibling;
    if (fullOutputDiv && fullOutputDiv.classList.contains('output-full')) {
      const isHidden = fullOutputDiv.style.display === 'none';
      fullOutputDiv.style.display = isHidden ? 'block' : 'none';
    }
  }
};
</script>

<style scoped>
/* 您的样式 (无变动) */
.page-wrapper {
  height: 100vh;
}
.buttons-container {
    display: flex;
    gap: 10px;
    margin-top: 10px;
}
</style>
