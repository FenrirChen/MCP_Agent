import json
from fastmcp import FastMCP
from typing import Dict, Any, List
from datetime import datetime
import uuid
import httpx  # 我们需要httpx来发出真实的后端请求

# 创建FastMCP应用实例
app = FastMCP("财务系统【混合模式】API服务", port=7816)

# 加载API定义
with open('api_def.json', 'r', encoding='utf-8') as f:
    api_definitions = json.load(f)


def generate_standard_response(success=True, message="【模拟】操作成功，真实数据库未受影响。") -> Dict[str, Any]:
    """生成标准响应格式"""
    return {
        "tranDate": datetime.now().strftime("%Y-%m-%d"),
        "serSeqNo": str(uuid.uuid4()),
        "rspCode": "000000" if success else "999999",
        "rspMsg": message
    }


# 为所有API服务创建工具函数
service_count = 0
for service_key, service_info in api_definitions.items():
    # 获取服务的所有信息
    service_name = service_info["name"]
    service_desc = service_info["desc"]
    module_name = service_info.get("moduleName", "未知")
    req_path = service_info.get("reqPath", "")
    # 获取服务类型，用于后续判断
    service_type = service_info.get("serviceTypeEnum", "OPERATION")

    tool_description = f"[{module_name}] {service_desc}"


    def make_service_function(s_name=service_name, s_desc=tool_description, s_type=service_type, s_path=req_path):
        def service_function(request_data: Dict[str, Any]) -> Dict[str, Any]:
            print(f"\n--- [混合服务] 接收到对【{s_name}】的调用 (类型: {s_type}) ---")
            print(f"--- [混合服务] 参数: {json.dumps(request_data, ensure_ascii=False, indent=2)} ---")
            try:
                # 使用httpx发出真实的后端网络请求
                response = httpx.post(
                    s_path,
                    json=request_data,
                    timeout=30.0
                )
                response.raise_for_status()  # 检查HTTP错误

                # 直接返回后端服务的真实响应
                print(f"--- [混合服务] 已收到真实后端响应 ---")
                return response.json()

            except httpx.RequestError as e:
                print(f"--- [混合服务] 错误：真实后端请求失败: {e} ---")
                return {"error": f"请求后端服务失败: {e}", "rspCode": "999999", "rspMsg": "远程服务调用失败"}
            except json.JSONDecodeError:
                return {"error": "后端服务返回了非JSON格式的响应", "rspCode": "999999",
                        "rspMsg": "远程服务响应格式错误"}



        service_function.__doc__ = s_desc
        service_function.__name__ = service_name
        return service_function


    tool_name = service_name
    func = make_service_function()
    app.tool(tool_name)(func)

    service_count += 1



@app.tool("listAllServices")
def list_all_services() -> List[Dict[str, str]]:
    apis = []
    for service_key, service_info in api_definitions.items():
        apis.append({
            "name": service_info["name"],
            "description": service_info["desc"],
            "module": service_info.get("moduleName", service_info.get("module", "未知")),
            "path": service_info["reqPath"],
            "serviceType": service_info.get("serviceTypeEnum", "UNKNOWN")
        })
    # 确保返回的是可列化的数据结构
    return apis

@app.tool("getServiceDetail")
def get_service_detail(serviceName: str) -> Dict[str, Any]:
    if serviceName in api_definitions:
        return api_definitions[serviceName]
    else:
        return {"error": "Service not found"}


@app.tool("getServicesByModule")
def get_services_by_module(module_name: str) -> List[Dict[str, str]]:

    apis = []
    for service_key, service_info in api_definitions.items():
        if service_info.get("moduleName", "").lower() == module_name.lower() or \
                service_info.get("module", "").lower() == module_name.lower():
            apis.append({
                "name": service_info["name"],
                "description": service_info["desc"],
                "path": service_info["reqPath"]
            })
    return apis


if __name__ == "__main__":


    print("FastMCP【混合代理/模拟】服务启动中...")

    print(f"总共加载了 {service_count} 个API服务")
    modules = {}
    for service_key, service_info in api_definitions.items():
        module = service_info.get("moduleName", service_info.get("module", "未知"))
        if module not in modules:
            modules[module] = 0
        modules[module] += 1
    print("\n按模块分组的服务统计:")
    for module, count in modules.items():
        print(f"  {module}: {count}个服务")
    print("\n【混合代理/模拟】服务已就绪，等待调用...")
    app.run(host="0.0.0.0",transport="sse")
