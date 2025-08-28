

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from typing import List,Optional

from agent import FinancialAgent
from typing import List, Optional, Any, Union

from schemas import VisualChatResponse


# --- FastAPI 应用设置 ---

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# 配置 CORS 中间件，允许前端页面(从文件打开)访问后端
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，为了本地开发方便
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有HTTP头
)

# --- Agent 初始化 ---


logger.info("正在创建 Financial Operator Agent 实例...")
try:
    agent = FinancialAgent()
    logger.info("✅ Agent 实例创建成功！")
except Exception as e:
    logger.error(f"❌ 创建 Agent 实例时发生严重错误: {e}", exc_info=True)
    agent = None



# --- API 请求和响应的数据模型 ---

'''多会话管理，目前暂不实现
# 定义前端发送过来的 message 结构
class Message(BaseModel):
    role: str
    content: str


# 定义 /chat 端点接收的完整请求体
class ChatRequest(BaseModel):
    messages: List[Message]
'''

class ChatRequest(BaseModel):
    message: str





# --- API 端点定义 ---

@app.post("/chat", response_model=VisualChatResponse)
async def handle_chat(request: ChatRequest):
    """
    处理来自前端的聊天请求的主函数。
    """
    if not agent:
        logger.error("请求被拒绝，因为 Agent 未能成功初始化。")
        raise HTTPException(status_code=503, detail="服务暂时不可用：AI助手初始化失败。")

    # 从对话历史中，提取最新的用户消息作为当前任务
    last_user_message = request.message

    if not last_user_message:
        logger.warning("收到的请求中没有找到有效的用户消息。")
        raise HTTPException(status_code=400, detail="请求数据中未包含用户消息。")

    logger.info(f"接收到任务: \"{last_user_message}\"")

    try:
        # 调用 Agent 的核心方法来执行任务
        result_dict = await agent.get_response(last_user_message)

        logger.info(f"Agent 已返回结构化结果。")

        # 使用新的响应模型来构建和返回 JSON 数据
        return VisualChatResponse(**result_dict)

    except Exception as e:
        logger.error(f"处理任务 '{last_user_message}' 时发生错误: {e}", exc_info=True)
        # 将详细错误信息返回给前端，方便调试
        raise HTTPException(status_code=500, detail=f"AI助手在处理请求时遇到内部错误: {e}")


@app.post("/chat/stream")
async def handle_chat_stream(request: ChatRequest):
    """
    处理来自前端的聊天请求，并以流式响应 (NDJSON) 返回 Agent 的执行过程。
    """
    # 步骤 1: 复用和原有端点一样的安全检查
    if not agent:
        logger.error("请求被拒绝，因为 Agent 未能成功初始化。")
        # 对于流式端点，如果还没开始流就出错了，可以直接抛出 HTTPException
        raise HTTPException(status_code=503, detail="服务暂时不可用：AI助手初始化失败。")

    user_message = request.message
    if not user_message:
        logger.warning("收到的请求中没有找到有效的用户消息。")
        raise HTTPException(status_code=400, detail="请求数据中未包含用户消息。")

    logger.info(f"接收到流式任务: \"{user_message}\"")

    # 步骤 2: 核心改动 - 调用流式方法并返回 StreamingResponse
    try:
        # 注意这里：我们调用的是 get_response_stream 方法
        # 这个调用会返回一个异步生成器对象，我们直接把它传递给 StreamingResponse
        # 不需要在这里使用 await agent.get_response_stream(...)
        agent_generator = agent.get_response_stream(user_message)

        return StreamingResponse(agent_generator, media_type="application/x-ndjson")

    except Exception as e:
        # 这个 try/except 主要捕获在开始流之前的、预料之外的错误
        # 流过程中的错误已经在 get_response_stream 内部被捕获并 yield 出去了
        logger.error(f"在准备流式响应时发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI助手在准备流时遇到内部错误: {e}")


@app.get("/")
def read_root():
    return {"status": "Financial Agent server is running."}


# --- 启动服务器 ---
if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 启动 FastAPI 服务器...")
    # 监听 0.0.0.0 表示允许来自局域网的访问，port=8000 是你JS里配置的端口
    uvicorn.run(app, host="0.0.0.0", port=8000)