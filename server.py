

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from typing import List,Optional
import json

from agent import FinancialAgent
from typing import List, Optional, Any, Union,Dict

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

try:
    with open("config/RESOURCE_API_MAP.json", "r", encoding="utf-8") as f:
        RESOURCE_API_MAP = json.load(f)
        logger.info("✅ resource_api_map.json 加载成功！")
    with open("config/DRILLDOWN_ENRICHMENT_MAP.json", "r", encoding="utf-8") as f:
        DRILLDOWN_ENRICHMENT_MAP = json.load(f)
        logger.info("✅ drilldown_enrichment_map.json 加载成功！")
    with open('tools/mock_data.json', 'r', encoding='utf-8') as f:
        MOCK_DATA = json.load(f)
        logger.info("✅ tools/mock_data.json 加载成功！")

    # 构建一个从服务名到资源类型的反向映射，方便后续查找
    # 注意：这个简单的反向映射假设一个服务只对应一个资源类型，在当前场景下成立
    SERVICE_TO_RESOURCE_TYPE_MAP = {
        "RecordProjectService": "project",
        "FinishPayPaymentService": "project_invoices",  # 这是一个列表，特殊处理
        "PendingSalesInvoiceQuoteService": "invoice",
    }
    logger.info("✅ 配置文件加载成功！")
except FileNotFoundError as e:
    logger.error(f"❌ 配置文件加载失败: {e}。请确保 resource_api_map.json 和 drilldown_enrichment_map.json 文件存在。")
    RESOURCE_API_MAP = None
    DRILLDOWN_ENRICHMENT_MAP = None


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

class ProbeRequest(BaseModel):
    service_name: str
    params: Dict[str, Any]


def call_backend_api(service_name: str, params: Dict[str, Any]) -> Any:
    """
    模拟函数，从加载的 MOCK_DATA 中查找匹配的响应。
    """
    logger.info(f"正在模拟调用后端服务: {service_name}，参数: {params}")

    if not MOCK_DATA or service_name not in MOCK_DATA:
        logger.warning(f"⚠️ 在 mock_data.json 中未找到服务 {service_name} 的定义。")
        return None

    # 遍历该服务的所有mock场景
    for scenario in MOCK_DATA[service_name]:
        match_params = scenario.get("match_params", {})

        # 简单匹配逻辑：检查请求的params是否是match_params中body的超集
        # 注意：isQuery等其他匹配逻辑可以按需在此扩展
        if "body" in match_params:
            if all(item in params.items() for item in match_params["body"].items()):
                logger.info(f"✅ 找到匹配的mock场景，返回响应。")
                return scenario.get("response")  # 返回完整的response对象
        # 增加一个处理无body参数的通用匹配（例如查询所有）
        elif not match_params.get("body") and not params:
            logger.info(f"✅ 找到匹配的mock场景（无参数），返回响应。")
            return scenario.get("response")

    logger.warning(f"⚠️ 未找到与参数 {params} 匹配的mock场景。")
    return None


def enrich_data_with_probes(data: Any, service_name: str) -> Any:
    if not all([DRILLDOWN_ENRICHMENT_MAP, RESOURCE_API_MAP]):
        logger.warning("无法加工数据：配置文件未加载。")
        return data

    service_info = RESOURCE_API_MAP.get(service_name, {})
    resource_type = service_info.get("returns_resource_type")

    logger.info(f"服务 '{service_name}' 返回的资源类型被识别为: '{resource_type}'")

    if not resource_type:
        logger.info("资源类型为空，跳过加工。")
        return data

    rules = DRILLDOWN_ENRICHMENT_MAP.get(resource_type, {}).get("fields")
    if not rules:
        logger.info(f"资源类型 '{resource_type}' 没有定义加工规则，跳过加工。")
        return data

    logger.info(f"找到适用于 '{resource_type}' 的加工规则: {rules}")

    def process_item(item: Dict[str, Any]) -> Dict[str, Any]:
        enriched_item = item.copy()
        logger.debug(f"  正在处理项目: {item}")
        for field, rule in rules.items():
            target_service = rule.get("target_service")
            source_id_field = rule.get("source_id_field")
            if not target_service or not source_id_field: continue

            target_param_name = RESOURCE_API_MAP.get(target_service, {}).get("primary_id_param_name")
            if not target_param_name: continue

            id_value = None
            if field == "__self__":
                id_value = item.get(source_id_field)
            elif field in item:
                id_value = item[field] if source_id_field == "__self__" else item.get(source_id_field)

            if id_value is not None:
                probe = {
                    "probe_type": "API_CALL",
                    "service_name": target_service,
                    "params": {target_param_name: id_value}
                }
                probe_field_name = "drilldown_probe" if field == "__self__" else f"{field}_probe"
                enriched_item[probe_field_name] = probe
                logger.debug(f"    - 成功为字段 '{field}' 生成探针: {probe}")
        return enriched_item

    # 逻辑修正: 直接对原始数据进行深拷贝操作，避免引用问题
    response_copy = json.loads(json.dumps(data))
    core_data = response_copy.get("body", {})

    list_key_found = next((key for key, value in core_data.items() if isinstance(value, list)), None)

    if list_key_found:
        logger.info(f"数据类型被识别为列表 (在字段 '{list_key_found}' 中)。开始逐项加工...")
        original_list = core_data.get(list_key_found, [])
        processed_list = [process_item(item) for item in original_list]
        response_copy["body"][list_key_found] = processed_list
        return response_copy
    elif isinstance(core_data, dict) and core_data:
        logger.info("数据类型被识别为单个对象。开始加工...")
        processed_body = process_item(core_data)
        response_copy["body"] = processed_body
        return response_copy
    else:
        logger.info("未在body中找到可加工的列表或对象。")
        return response_copy


# --- API 端点定义 ---


@app.post("/api/execute_probe")
async def execute_probe(probe: ProbeRequest):
    """
    执行探针并返回加工后数据的端点
    """
    if not all([RESOURCE_API_MAP, DRILLDOWN_ENRICHMENT_MAP, MOCK_DATA]):
        raise HTTPException(status_code=503, detail="服务暂时不可用：配置文件或模拟数据初始化失败。")

    logger.info(f"接收到探针，准备执行: {probe.service_name} with params {probe.params}")

    # 1. 执行探针，调用后端API获取原始数据
    raw_response = call_backend_api(probe.service_name, probe.params)

    if raw_response is None:
        raise HTTPException(status_code=404, detail=f"未能从后端服务 {probe.service_name} 获取到数据。")

    # 2. 对原始数据进行二次加工，注入下一级的探针
    enriched_response = enrich_data_with_probes(raw_response, probe.service_name)

    logger.info("✅ 数据加工完成，返回给前端。")
    return JSONResponse(content=enriched_response)




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


@app.get("/")
def read_root():
    return {"status": "Financial Agent server is running."}


# --- 启动服务器 ---
if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 启动 FastAPI 服务器...")
    # 监听 0.0.0.0 表示允许来自局域网的访问，port=8000 是你JS里配置的端口
    uvicorn.run(app, host="0.0.0.0", port=8000)