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
        print(f"--- [Official Client] 准备调用工具: {service} with params: {request} ---")

        # --- 初始化分页循环所需的变量 ---
        result_list_key = self._find_result_list_key(service)
        # 如果找不到列表键，说明是操作型或简单的查询API，进入“简单调用”模式
        if not result_list_key:
            print(f"--- [Official Client] 未找到响应列表键，进入【简单调用】模式处理服务: {service} ---")
            try:
                # 准备请求体，操作型API通常也需要body
                full_payload = {
                    "serialNo": str(uuid.uuid4()),
                    "clientIp": "127.0.0.1",
                    "body": request.get('body', request)
                }

                async with Client(self.server_url) as client:
                    result = await client.call_tool(service, {"request_data": full_payload})
                    # 直接返回后端服务的真实响应
                    print(f"--- [Official Client] 已收到【简单调用】的响应 ---")
                    return json.dumps(result.data, ensure_ascii=False, indent=2)

            except Exception as e:
                import traceback
                return json.dumps({"error": f"执行简单调用时出错: {e}\n{traceback.format_exc()}"},
                                  ensure_ascii=False)

        else:  # 否则，说明是查询类API，进入“分页调用”模式
            print(f"--- [Official Client] 已动态识别结果列表键名为: '{result_list_key}'，进入【分页调用】模式 ---")
            ai_business_params = request.get('body', request).copy()
            current_page = 1
            total_pages = 1
            all_results = []

            print("--- [Official Client] 已启动自动分页数据获取模式 ---")

            while current_page <= total_pages:
                try:
                    body_payload = {"pageNo": str(current_page), "pageSize": "20"}
                    body_payload.update(ai_business_params)
                    full_payload = {"serialNo": str(uuid.uuid4()), "clientIp": "127.0.0.1", "body": body_payload}

                    print(f"--- [Official Client] 正在获取第 {current_page}/{total_pages} 页数据... ---")

                    async with Client(self.server_url) as client:
                        result = await client.call_tool(service, {"request_data": full_payload})
                        response_data = result.data

                    if not response_data or response_data.get('rspCode') != '000000':
                        return json.dumps(response_data or {"error": "后端返回了空响应"}, ensure_ascii=False, indent=2)

                    response_body = response_data.get('body', {})
                    # 使用动态获取的键名来提取数据
                    page_data = response_body.get(result_list_key)  # 首先尝试API定义中的原始键名

                    # 如果用原始键名没取到数据，但total>0，则尝试驼峰式(首字母小写)的键名
                    if not page_data and int(response_body.get('total', 0)) > 0:
                        camel_case_key = result_list_key[0].lower() + result_list_key[1:]
                        if camel_case_key != result_list_key:  # 避免重复尝试
                            print(
                                f"--- [Official Client] 警告: 未在 '{result_list_key}' 找到数据，尝试驼峰式键名 '{camel_case_key}'... ---")
                            page_data = response_body.get(camel_case_key, [])

                    page_data = page_data or []  # 确保page_data不是None
                    if page_data:
                        all_results.extend(page_data)

                    if current_page == 1:
                        total_records = int(response_body.get('total', 0))
                        page_size = int(response_body.get('pageSize', 20))
                        total_pages = math.ceil(total_records / page_size) if page_size > 0 else 1
                        if total_pages == 0: total_pages = 1
                        print(f"--- [Official Client] 检测到总记录数: {total_records}, 共 {total_pages} 页. ---")

                    current_page += 1

                except Exception as e:
                    import traceback
                    return json.dumps({"error": f"在获取第 {current_page} 页数据时出错: {e}\n{traceback.format_exc()}"},
                                      ensure_ascii=False)

            print(f"--- [Official Client] 所有 {total_pages} 页数据获取完毕，共聚合 {len(all_results)} 条记录。---")

            final_success_response = {
                "rspCode": "000000",
                "rspMsg": "查询成功（已合并所有分页数据）",
                "body": {
                    result_list_key: all_results,  # 【核心修改】在最终结果里也使用动态的键名
                    "total": len(all_results),
                    "totalPages": total_pages
                }
            }
            return json.dumps(final_success_response, ensure_ascii=False, indent=2)