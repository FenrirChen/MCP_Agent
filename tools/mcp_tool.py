import json
from agno.tools import Toolkit
from typing import Dict, Any, Optional
from fastmcp import Client
import uuid
import math

class FinancialTools(Toolkit):

    def __init__(self):
        try:
            with open('api_def.json', 'r', encoding='utf-8') as f:
                self.api_definitions = json.load(f)
            print("[FinancialTools] 成功加载并解析 api_def.json。")
        except Exception as e:
            print(f"[FinancialTools] 警告：加载或解析api_def.json失败: {e}")
            self.api_definitions = {}
        # 重要的异步函数注册
        super().__init__(name="financial_tools",
                         tools=[self.list_financial_apis, self.get_financial_api_detail, self.call_financial_api])

        try:
            # 路径是相对于您项目根目录的
            with open('tools/mock_data.json', 'r', encoding='utf-8') as f:
                self.mock_data = json.load(f)
            print("[FinancialTools] 成功加载 MOCK DATA 文件。")
        except Exception as e:
            print(f"[FinancialTools] 警告：加载或解析 mock_data.json 失败: {e}")
            self.mock_data = {}  # 如果文件不存在或格式错误，创建一个空字典以防程序崩溃

        # 客户端将连接这个地址
        self.server_url = "http://mcp_service:7816/sse"
        print("[FinancialTools] 客户端已配置，将连接到", self.server_url)

    def _find_result_list_key(self, service_name: str) -> Optional[str]:
        """
        一个辅助函数，用于从api_def.json中查找并返回结果列表的键名。
        """
        service_info = None
        # 先通过大小写不敏感的方式找到对应的服务定义
        for key, info in self.api_definitions.items():
            if info.get("name", "").lower() == service_name.lower():
                service_info = info
                break

        if not service_info or "respFieldInfos" not in service_info:
            return None

        # 遍历响应体定义，找到类型为"List"的字段
        try:
            # 响应字段 -> body -> body的字段列表
            body_fields = next(field for field in service_info["respFieldInfos"] if field["name"] == "body")[
                "fieldInfos"]
            list_field = next(field for field in body_fields if field["fieldType"] == "List")
            return list_field["name"]
        except (StopIteration, KeyError):
            # 如果结构不匹配或找不到List字段，则返回None
            return None


    async def list_financial_apis(self) -> str:
        """列出财务系统中所有可用的API服务及其基本描述。"""
        print("--- [Official Client] 正在调用 list_financial_apis ---")
        try:
            async with Client(self.server_url) as client:
                # list_tools() 返回的是一个包含Tool对象的列表
                tool_objects_list = await client.list_tools()
                print(f"--- [Official Client] 已成功获取到 {len(tool_objects_list)} 个Tool对象 ---")

                serializable_tools = []
                for tool_obj in tool_objects_list:
                    tool_dict = {
                        "name": getattr(tool_obj, 'name', 'unknown_name'),
                        "description": getattr(tool_obj, 'description', 'No description available.'),
                    }
                    serializable_tools.append(tool_dict)

                # 对这个由简单字典组成的、安全的列表进行JSON序列化
                return json.dumps(serializable_tools, ensure_ascii=False, indent=2)

        except Exception as e:
            import traceback
            print(f"错误: {e}\n{traceback.format_exc()}")
            return json.dumps({"error": f"使用fastmcp.Client列出服务时出错: {e}"}, ensure_ascii=False)
    async def get_financial_api_detail(self, service_name: str) -> str:
        """获取财务系统中某个特定API服务的详细信息。"""
        print(f"--- [Local Definition] Getting details for {service_name} from api_def.json ---")

        # self.api_definitions 是我们在 __init__ 中从 api_def.json 加载的
        for key, service_info in self.api_definitions.items():
            if service_info.get("name", "").lower() == service_name.lower():
                print(f"--- [Local Definition] 成功匹配到服务: key='{key}', name='{service_info.get('name')}' ---")
                return json.dumps(service_info, ensure_ascii=False, indent=2)

            # 如果遍历完整个字典都没有找到匹配的 'name'，才真正报告错误
        print(f"--- [Local Definition] 遍历完成，未找到名为 '{service_name}' 的服务。 ---")
        return json.dumps({"error": f"在api_def.json中未找到服务 '{service_name}' 的定义。"}, ensure_ascii=False)

    async def call_financial_api(self, service: str, request: Dict[str, Any] = {}) -> str:
        print(f"--- [MOCK-ENGINE] 准备在 mock_data.json 中查找服务: {service} ---")

        # 检查此服务是否有任何模拟场景定义
        if service in self.mock_data:
            mock_scenarios = self.mock_data[service]
            agent_params = request.get('body', {})

            # 遍历该服务的所有模拟场景
            for scenario in mock_scenarios:
                match_params = scenario.get("match_params", {})

                # 处理默认/通配场景
                if match_params == "default":
                    print(f"--- [MOCK] 匹配到 '{service}' 的默认场景 ---")
                    return json.dumps(scenario["response"], ensure_ascii=False, indent=2)

                # 处理具体的参数匹配场景
                is_match = True
                # 遍历此场景需要匹配的所有条件
                for key, expected_value in match_params.items():
                    # 如果Agent传入的参数中，有任何一个key的值不匹配，则判定为不匹配
                    if agent_params.get(key) != expected_value:
                        is_match = False
                        break  # 中断对当前场景的检查，继续检查下一个场景

                # 如果所有条件都匹配成功
                if is_match:
                    print(f"--- [MOCK] 成功匹配到 '{service}' 的一个具体场景 ---")
                    return json.dumps(scenario["response"], ensure_ascii=False, indent=2)

        # 如果遍历完所有场景都没有找到匹配项，返回“查询无结果”
        print(f"--- [MOCK] 未在 mock_data.json 中找到 '{service}' 合适的模拟场景 ---")
        not_found_response = {
            "rspCode": "000000",
            "rspMsg": "查询成功【MOCK DATA - No Scene Found】",
            "body": {"detailList": [], "total": 0, "totalPages": 0}
        }
        return json.dumps(not_found_response, ensure_ascii=False, indent=2)