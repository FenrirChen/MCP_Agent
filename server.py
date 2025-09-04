

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
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
    isQuery: bool = False  # 新增 isQuery 字段，默认值为 False
    body: Optional[Dict[str, Any]] = None # 将原来的 params 改名为 body


def call_backend_api(service_name: str, params: Optional[Dict[str, Any]] = None, isQuery: bool = False) -> Any:
    """
    一个更智能的模拟函数，它会从加载的 MOCK_DATA 中查找匹配的响应。
    修正了 isQuery 的匹配逻辑和函数签名。
    """
    # 确保 params 在日志和后续逻辑中即使是 None 也能安全处理
    params = params or {}
    logger.info(f"正在模拟调用后端服务: {service_name}，参数: {params}，isQuery: {isQuery}")

    if not MOCK_DATA or service_name not in MOCK_DATA:
        logger.warning(f"⚠️ 在 mock_data.json 中未找到服务 {service_name} 的定义。")
        return None

    for scenario in MOCK_DATA[service_name]:
        match_params = scenario.get("match_params", {})

        # 【关键修正】使用 'isQuery' (驼峰) 来匹配 JSON 文件中的键
        if match_params.get("isQuery") != isQuery:
            continue

        # 匹配 body 参数
        mock_body_params = match_params.get("body", {})
        if all(item in params.items() for item in mock_body_params.items()):
            logger.info(f"✅ 找到匹配的mock场景，返回响应。")
            return scenario.get("response")

    logger.warning(f"⚠️ 未找到与参数 {params} 和 isQuery={isQuery} 匹配的mock场景。")
    return None


def enrich_data_with_probes(data: Any, service_name: str) -> Any:
    """
    根据导航图，为数据注入下一级的探针。
    最终修正版，确保对列表中的每个项目都能正确应用规则。
    """
    if not all([DRILLDOWN_ENRICHMENT_MAP, RESOURCE_API_MAP]):
        return data

    service_info = RESOURCE_API_MAP.get(service_name, {})
    resource_type = service_info.get("returns_resource_type")

    if not resource_type:
        return data

    rules = DRILLDOWN_ENRICHMENT_MAP.get(resource_type, {}).get("fields")
    if not rules:
        return data

    def process_item(item: Dict[str, Any]) -> Dict[str, Any]:
        enriched_item = item.copy()

        # 【关键修正】: 之前这里的逻辑有缺陷，现在我们对每条规则都进行独立判断

        # 规则1: 处理 __self__ 规则 (如果存在)
        if "__self__" in rules:
            rule = rules["__self__"]
            target_service = rule.get("target_service")
            source_id_field = rule.get("source_id_field")
            if target_service and source_id_field and source_id_field in item:
                target_param_name = RESOURCE_API_MAP.get(target_service, {}).get("primary_id_param_name")
                if target_param_name:
                    id_value = item[source_id_field]
                    probe = {
                        "probe_type": "API_CALL",
                        "service_name": target_service,
                        "params": {target_param_name: id_value}
                    }
                    enriched_item["drilldown_probe"] = probe

        # 规则2: 遍历处理所有其他字段规则
        for field, rule in rules.items():
            if field == "__self__":
                continue  # __self__ 已经处理过了，跳过

            if field in item:
                target_service = rule.get("target_service")
                source_id_field = rule.get("source_id_field")
                if not target_service or not source_id_field: continue

                target_param_name = RESOURCE_API_MAP.get(target_service, {}).get("primary_id_param_name")
                if not target_param_name: continue

                id_value = item[field] if source_id_field == "__self__" else item.get(source_id_field)

                if id_value is not None:
                    probe = {
                        "probe_type": "API_CALL",
                        "service_name": target_service,
                        "params": {target_param_name: id_value}
                    }
                    enriched_item[f"{field}_probe"] = probe

        return enriched_item

    # 下面的逻辑保持不变
    response_copy = json.loads(json.dumps(data))
    core_data = response_copy.get("body", {})
    list_key_found = next((key for key, value in core_data.items() if isinstance(value, list)), None)

    if list_key_found:
        original_list = core_data.get(list_key_found, [])
        processed_list = [process_item(item) for item in original_list]
        response_copy["body"][list_key_found] = processed_list
        return response_copy
    elif isinstance(core_data, dict) and core_data:
        processed_body = process_item(core_data)
        response_copy["body"] = processed_body
        return response_copy
    else:
        return response_copy


def format_as_report(data: Dict[str, Any], service_name: str) -> Dict[str, Any]:
    """
    一个更智能的函数，用于将任何输入数据包装成前端期望的标准报告格式。
    - 自动过滤 total, totalPages 等元数据。
    - 自动将 _probe 字段隐藏，不作为列展示。
    - 自动将列表数据渲染为子表格。
    """
    if "visualization_type" in data and data.get("visualization_type") != None:
        logger.info("数据已是标准报告格式，直接返回。")
        return data

    logger.info("数据为原始API格式，正在包装为标准报告...")

    body = data.get("body", {})
    if not isinstance(body, dict):
        body = {"content": body}

    report_tables = []

    # 1. 将 body 的键分为“简单属性”和“列表属性”
    simple_properties = {}
    list_properties = {}

    for key, value in body.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            list_properties[key] = value
        elif "_probe" not in key:  # 忽略所有探针字段
            simple_properties[key] = value

    # 2. 创建主信息表格（只包含简单属性）
    main_info_rows = []
    # 定义不应展示在主信息表中的元数据字段
    METADATA_KEYS = ['total', 'totalPages']

    for key, value in simple_properties.items():
        if key not in METADATA_KEYS:
            probe = body.get(f"{key}_probe")
            main_info_rows.append([
                {"value": key, "probe": None},
                {"value": value, "probe": probe}
            ])

    if main_info_rows:
        report_tables.append({
            "title": "详细信息",
            "headers": ["属性", "值"],
            "rows": main_info_rows
        })

    # 3. 为每个列表属性创建子表格
    for list_key, item_list in list_properties.items():
        # 从列表的第一项获取所有可能的列名，并过滤掉探针列
        headers = [key for key in item_list[0].keys() if "_probe" not in key]

        sub_table_rows = []
        for item in item_list:
            row_data = []
            for header in headers:
                probe_for_cell = item.get(f"{header}_probe")
                row_data.append({
                    "value": item.get(header, ""),
                    "probe": probe_for_cell
                })
            sub_table_rows.append(row_data)

        report_tables.append({
            "title": list_key,  # 使用列表的键名作为子表格标题
            "headers": headers,
            "rows": sub_table_rows
        })

    # 4. 构建最终报告
    report = {
        "visualization_type": "table",
        "title": f"'{service_name}' 查询结果",
        "table_data": {"tables": report_tables},
        "chart_data": None
    }
    return report

# --- API 端点定义 ---


@app.post("/api/execute_probe")
async def execute_probe(probe: ProbeRequest):  # 注意这里依然是 ProbeRequest
    if not all([RESOURCE_API_MAP, DRILLDOWN_ENRICHMENT_MAP, MOCK_DATA]):
        raise HTTPException(status_code=503, detail="服务暂时不可用：配置文件或模拟数据初始化失败。")

    logger.info(f"接收到探针，准备执行: {probe.service_name}，isQuery: {probe.isQuery}，参数: {probe.body}")

    # 1. 执行探针，获取原始数据 (传递 probe.body)
    # 根据 isQuery 参数，可以在这里添加额外的逻辑，例如选择不同的mock数据查找策略
    raw_response = call_backend_api(probe.service_name, probe.body, isQuery=probe.isQuery)  # 传递 isQuery

    if raw_response is None:
        raise HTTPException(status_code=404, detail=f"未能从后端服务 {probe.service_name} 获取到数据。")

    # 2. 对原始数据进行二次加工，注入探针
    enriched_response = enrich_data_with_probes(raw_response, probe.service_name)

    # 3. 将加工后的数据，统一包装成前端报告格式
    final_report = format_as_report(enriched_response, probe.service_name)

    logger.info("✅ 数据包装和加工完成，返回给前端。")
    return JSONResponse(content=final_report)




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