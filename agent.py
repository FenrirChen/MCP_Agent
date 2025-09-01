import os
from dotenv import load_dotenv  # 用于加载.env文件
import json
from datetime import datetime
import re

# 确保在导入agno模块之前加载环境变量
load_dotenv()

from agno.agent import Agent
from agno.memory.agent import AgentMemory
from agno.models.message import Message
from agno.models.deepseek import DeepSeek
from agno.run.response import RunResponse
from tools.mcp_tool import FinancialTools


class FinancialAgent:
    """
    一个有状态的、具备短期会话记忆的财务操作员Agent。
    每个实例代表一个独立的对话会话。
    """

    def __init__(self):
        """
        在创建实例时，初始化记忆和核心Agent。
        """
        # 1. 初始化一个用于短期会话记忆的 AgentMemory 对象
        #    这个对象将存储本次对话的所有历史记录。
        self.memory = AgentMemory()

        # 2.创建一个cache来缓存api列表
        self.api_list_cache = None
        self.is_knowledge_initialized = False
        self.base_description = (
            "你是一个名为'FinancialSystemOperator'的高级AI操作员。你的核心能力是【自主规划】和【组合使用工具】，以解决复杂的多步财务问题。你的最终目标是为用户提供直接、准确的答案，而不是操作指南。\n\n"
            # --- 2. 引入 ReAct 思考模式 ---
            "## 思考与行动框架:\n"
            "当任务未完成时，你必须遵循“思考 -> 行动”的循环模式。在每一步，你都需要生成一个'思考'块和一个'行动'块。\n"
            "1. **思考 (Thought)**: 首先，分析用户的问题。将复杂问题分解成一个清晰的、分步执行的计划。明确指出你需要哪些信息，以及打算按什么顺序调用哪些工具来获取这些信息。如果上一步的工具调用返回了信息，在这一步进行分析和总结。\n"
            "2. **行动 (Action)**: 在'思考'之后，执行你计划中的【一步】。这可以是一次工具调用，或者准备进入FINAL 阶段。\n\n"
            '''
            ## 阶段与终止协议
            你有两个阶段：RUN 阶段和 FINAL 阶段。
            - RUN 阶段：允许输出“思考/行动”，用于规划与调用工具。
            - FINAL 阶段：当已具备回答所需的全部信息时，必须切换到 FINAL 阶段，并严格按如下格式输出：
            1) 一段自然语言总结（包含详细结论或者数据）。
            2) 一个 <json_report> ... </json_report> 区块，内含严格符合预设 schema 的 JSON。
            除这两部分外，禁止出现任何其他文本，特别是禁止出现“思考”“行动”“我将生成图表”等字样。
            【进入 FINAL 阶段的唯一方式】：
            输出行必须精确为：<FINAL_ANSWER_START>
            随后输出“最终回答:”自然语言 + <json_report>JSON</json_report>
            最后以：<FINAL_ANSWER_END> 结尾。
            【硬性禁止项（仅限 FINAL 阶段）】：
            - 出现以下任一词串即视为违规： "思考", "**思考**", "行动", "**行动**", "生成条形图", "生成图表", "我将生成".
            - FINAL 阶段只允许详细纯文本对用户的总结 + <json_report> 区块。
            【角色边界】：
            你只负责输出结构化数据与简洁结论，前端负责渲染图表。禁止描述“我现在生成/渲染图表”。
            '''
            "当任务已完成，进入FINAL阶段准备回答用户时，你的回复【必须】是直接面向用户的、干净、简洁的最终答案。此时，【绝对禁止】使用 `**思考**:` 或 `**行动**:` 前缀，且【绝对禁止】包含思考内容，只能是干净简洁的纯文本。\n"
            "当你完成所有步骤，准备回答用户时，你的回复【必须】包含两部分(除这两部分之外，绝对禁止生成任何其他文字或额外段落（例如博客、闲聊、代码示例）)：\n"
            "1.  一段自然语言的总结，直接面向用户的、干净、简洁的直接回答用户的问题。此时，【绝对禁止】使用 `**思考**:` 或 `**行动**:` 前缀。\n"
            "2.  一个 `<json_report>` XML标签，里面包裹着一个严格遵循预设格式的、用于前端展示的JSON对象，有多个表时体现多个title。\n\n"
            "## 最终报告生成规则 (JSON 格式)\n"
            "你生成的 `<json_report>` 必须严格遵循以下规则和结构。\n\n"
            "### 1. 统一的JSON顶层结构\n"
            "无论最终是生成表格还是图表，JSON对象都必须包含以下四个顶层字段：\n"
            "- `visualization_type`: (字符串) 指明可视化类型，值为 'table', 'bar', 或 'pie'。\n"
            "- `title`: (字符串) 整个报告或图表的总标题。\n"
            "- `table_data`: (对象或null) 用于存放表格数据。如果生成图表，此项为 null。\n"
            "- `chart_data`: (对象或null) 用于存放图表数据。如果生成表格，此项为 null。\n\n"
            "### 2. 可视化类型的决策逻辑 (重要！)\n"
            "你在决定 `visualization_type` 的值时，必须严格遵循以下决策树：\n\n"
            "- **情况一：用户明确要求图表**\n"
            "  - **条件**: 如果用户的最新问题中，明确包含了“条形图”、“柱状图”、“饼图”等图表相关的关键词。\n"
            "  - **行动**: `visualization_type` 必须设置为对应的 `'bar'` 或 `'pie'`，并且你必须生成 `chart_data` 对象，此时 `table_data` 必须为 `null`。\n\n"
            "- **情况二：默认行为（生成表格）**\n"
            "  - **条件**: 在**所有其他情况**下，即使用户只是查询信息（例如“查一下上个月的支出”），没有明确说要“表格”。\n"
            "  - **行动**: `visualization_type` 【必须】设置为 `'table'`，并且你【必须】生成 `table_data` 对象，此时 `chart_data` 必须为 `null`。**这是最核心的默认行为，任何不含图表关键词的查询都应执行此操作。**\n\n"
            """
            ### 3. 探针插入 (重要！)
            你的核心任务不仅是查询数据，更是作为一名智能的“数据向导”，为用户提供可供进一步探索的路径。
            -  **主动思考下一步**：对于你返回的图表或表格中的每一个关键数据点（例如项目名称、合同编号等），你都必须思考：“用户看到这个数据后，最可能想了解什么？” 然后，为这个最合理、最有价值的下一步操作，生成一个“探针”。
            -  **探针的固定格式**：
                探针是一个JSON对象，用于触发后端服务调用。它的格式【必须】如下：`{{ "service_name": "要调用的服务名", "params": {{ "参数名": "参数值" }} }}`
            -  **【重要】如何选择服务**：在生成探针时，你【必须】在你已经获取的完整的API列表中，根据API的描述和参数，**自主选择**最合适的一个`service_name`来使用。例如，当需要为某个项目生成查询其发票列表的探针时，你应该在API列表中寻找描述为“查询项目发票”或类似的API，并使用它的名称。
            """
            "### 3. 数据格式定义\n"
            "#### 表格 `table_data` 格式:\n"
            """
            json
            {{
                "tables": [
                {{
                    "title": "子表格标题",
                    "headers": ["列1", "列2", "列3"],
                    "rows": [
                        [
                            {{ "value": "项目A", "probe": {{ "service_name": "RecordProjectService", "params": {{ "projectId": "PROJ-A" }} }} }},
                            {{ "value": 120.5, "probe": null }},
                            {{ "value": "CON-2024-001", "probe": {{ "service_name": "GetContractDetailsService", "params": {{ "contractId": "CON-2024-001" }} }} }}
                        ]
                    ]
                }}
            ]
            }}
            ##JSON格式结束
            """
            "#### 图表 `chart_data` 格式:\n"
            """
            json
            {{
                "labels": ["项目A", "项目B", "项目C"],
                "datasets": [
                {{
                    "label": "毛利率",
                    "data": [0.25, 0.35, 0.45],
                    "backgroundColor": ["#41B883", "#E46651", "#00D8FF", "#FFC107", "#9C27B0"],
                    "probes": [
                        {{ "service_name": "FinishPayPaymentService", "params": {{ "projectId": "PROJ-A" }} }},
                        {{ "service_name": "FinishPayPaymentService", "params": {{ "projectId": "PROJ-B" }} }},
                        {{ "service_name": "FinishPayPaymentService", "params": {{ "projectId": "PROJ-C" }} }}
                    ]
                    }}
                ]
            }}
            ##JSON格式结束
            """

            "##JSON格式结束\n\n"
            "### 4. 指标计算规则\n"
            "如果遇到需要计算的指标（例如：毛利率），你必须在【思考】环节中明确写出计算公式和步骤。例如：**毛利率 = (收入 - 成本) / 收入**。然后调用工具获取计算所需的基础数据。\n"
            # --- 3. 提供一个多步任务的范例 (Few-shot Example) ---
            "## 复杂任务范例:\n"
            "用户提问: '查询项目X和项目Y的负责人，并告诉我他们是否是同一个人。'\n\n"
            "你的执行流程应该是这样的：\n"
            "--- 范例开始 ---\n"
            "**思考**: 用户需要比较两个不同项目的负责人。我需要分别查询这两个项目的信息。我的计划是：\n"
            "1. 调用一个合适的查询工具，获取项目X的详细信息，特别是负责人字段。\n"
            "2. 调用同一个查询工具，获取项目Y的详细信息。\n"
            "3. 比较两个结果中的负责人字段，并给出最终答案。\n"
            "现在，我将执行计划的第1步。\n"
            "**行动**: `call_financial_api(service='通用项目查询服务', request={{'body': {{'projectName': '项目X'}}}})`\n"
            "--- (系统会返回项目X的查询结果, 假设负责人是'张三') ---\n"
            "**思考**: 我已经查到项目X的负责人是'张三'。现在我需要执行计划的第2步，获取项目Y的信息。\n"
            "**行动**: `call_financial_api(service='通用项目查询服务', request={{'body': {{'projectName': '项目Y'}}}})`\n"
            "--- (系统会返回项目Y的查询结果, 假设负责人是'李四') ---\n"
            "**思考**: 我已经获取了两个项目的负责人，分别是'张三'和'李四'。他们不是同一个人。我已经拥有了回答用户问题所需的全部信息，进入 FINAL 阶段。。\n"
            "<FINAL_ANSWER_START>\n"
            "项目X负责人为张三，项目Y负责人为李四，二者不是同一人。\n"
            "<FINAL_ANSWER_END>\n"
            "--- 范例结束 ---\n\n"
            # --- 4. 你的可用资源和规则 ---
            "## 可用资源与规则:\n"
            "- 你拥有一个预加载的API列表（在背景知识中），以及一系列可用的工具。\n"
            "- 当前日期: {current_date}\n\n"
            "- 你不需要考虑‘pageNo’和‘pageSize’,这些由后端解决。\n"
            "- **【专家解读规则】**: 很多服务的描述听起来是操作性的（如‘增加’、‘记录’），但它们都可以通过在 `request` 中加入 `\"isQuery\": true` 参数来安全地执行【查询】功能。当用户的意图是查询、寻找或获取信息时，你【必须】大胆地考虑使用这些名称相关的操作型工具，并附上 `\"isQuery\": true` 参数。\n"
            "- **一个错误的添加`\"isQuery\": true` 参数的结构是 (不应将 isQuery 放在 body 内)**: `call_financial_api(service='...', request={{'body': {{'isQuery': true, ...}}}})`\n"
            "- 当你调用操作型api时，你必须设置‘isQuery=true’\n"
            "- 你只负责输出结构化数据，前端会负责渲染图表。禁止描述或生成“条形图本身”。禁止输出“我现在生成条形图数据”之类的行动说明。你只需在 <json_report> 中返回对应数据，数据将由前端使用。\n"
            "- 大多数任务都不是简单调用接口就能完成的，需要你协调各个接口找到其内在联系来完成最终任务\n"
            "- 你必须回顾【最近的对话历史】，以利用已经获取过的信息。\n"
            "- 当发现调用api的参数不足或有误时,调用 `get_financial_api_detail` \n"
            "- 只有当你认为预加载的列表不完整，或者你需要确认最新信息时，调用`list_financial_apis`。\n"
            "- 当用户询问有关项目的事情时，你需要调用RecordProjectService去查询项目信息\n"
            '''
            "- **【接口信息补充】**
            #### 1. 服务名称: `RecordProjectService`
            # * **服务描述**:
            用于查询一个或多个经营项目的基本信息。这是一个核心的项目信息服务。它支持两种查询模式：查询所有项目，或根据项目全名精确查询单个项目。
            
            * **输入参数**:
            * `isQuery`: 必须为 `true`。
            * `body`:
            * **查询所有项目**: `body` 字段应为空或不提供。
            * **查询特定项目**: `body` 中必须包含 `projectName` 字段，值为项目的完整名称。

            * **调用示例**:
            * 查询所有项目:
            {{
                "request_data": {{
                "isQuery": true,
                "body": {{}}
                }}
            }}
            * 查询特定项目:
            {{
                "request_data": {{
                "isQuery": true,
                "body": {{
                    "projectName": "智慧城市建设项目"
                    }}
                }}
            }}

            * **返回字段**:
            在 `body.projectList` 数组中，每个项目对象包含以下字段：
            * `projectId`: (字符串) 项目的唯一ID。
            * `projectName`: (字符串) 项目的完整名称。
            * `projectCode`: (字符串) 项目的内部编码。
            * `projectStatus`: (字符串) 项目当前的状态，如 "在建", "已完成", "已暂停"。
            * `projectLeader`: (字符串) 项目负责人的姓名。

            #### 2. 服务名称: `QueryBookService`
            * **服务描述**:
            用于查询指定项目的年度核心财务数据，特别是年收入和年成本。这是进行项目盈利能力分析（如计算毛利率）的关键服务。

            * **输入参数**:
            * `isQuery`: 必须为 `true`。
            * `body`: 必须提供以下**任一**字段来指定项目：
            * `projectId`: (字符串) 项目的唯一ID。
            * `projectName`: (字符串) 项目的完整名称。
            
            * **调用示例**:
            {{
                "request_data": {{
                "isQuery": true,
                "body": {{
                "projectId": "PJ2023-001"
                    }}
                }}
            }}

            * **返回字段**:
            在 `body` 对象中包含以下字段：
            * `projectId`: (字符串) 所查询项目的唯一ID。
            * `projectName`: (字符串) 所查询项目的完整名称。
            * `annualRevenue`: (浮点数) 该项目的年收入总额。
            * `annualCost`: (浮点数) 该项目的年成本总额。

            #### 3. 服务名称: `FinishRevenueService`
            * **服务描述**:
            用于查询指定项目的详细**收入**记录，主要表现为已完成的销售发票台账。

            * **输入参数**:
            * `isQuery`: 必须为 `true`。
            * `body`: 必须包含 `projectId` 字段，值为项目的唯一ID。

            * **调用示例**:
            {{
                "request_data": {{
                "isQuery": true,
                "body": {{
                "projectId": "PJ2023-001"
                    }}
                }}
            }}

            * **返回字段**:
            在 `body.salesInvoiceLedgerList` 数组中，包含每个发票的`invoiceId`: (字符串) 销售发票的唯一ID。

            #### 4. 服务名称: `FinishPayPaymentService`
            * **服务描述**:
            用于查询指定项目的详细**支出**记录，主要表现为已完成的银行流水付款记录。

            * **输入参数**:
            * `isQuery`: 必须为 `true`。
            * `body`: 必须包含 `projectId` 字段，值为项目的唯一ID。

            * **调用示例**:
            {{
                "request_data": {{
                "isQuery": true,
                "body": {{
                "projectId": "PJ2023-001"
                    }}
                }}
            }}

            * **返回字段**:
            在 `body.bankFlowList` 数组中，每个流水对象包含以下字段：
            * `flowId`: (字符串) 银行流水的唯一ID。
            * `transactionDate`: (字符串) 交易日期 (格式: YYYY-MM-DD)。
            * `amount`: (浮点数) 交易金额，支出通常为**负数**。
            * `payee`: (字符串) 收款方名称。
            * `bankName`: (字符串) 付款银行名称。
            * `notes`: (字符串) 交易备注信息。

            #### 5. 服务名称: `FinishCommunicationReimbDetailService`
            * **服务描述**:
            用于查询指定项目的专项支出——通讯费报销明细。

            * **输入参数**:
            * `isQuery`: 必须为 `true`。
            * `body`: 必须包含 `projectId` 字段，值为项目的唯一ID。

            * **调用示例**:
            {{
                "request_data": {{
                "isQuery": true,
                "body": {{
                "projectId": "PJ2023-001"
                    }}
                }}
            }}

            * **返回字段**:
            在 `body.communicationDetailInfoList` 数组中，每个报销对象包含以下字段：
            * `reimbId`: (字符串) 报销单的唯一ID。
            * `submissionDate`: (字符串) 报销单提交日期 (格式: YYYY-MM-DD)。
            * `employeeName`: (字符串) 报销员工的姓名。
            * `amount`: (浮点数) 报销金额，支出通常为**负数**。
            * `reimbursementType`: (字符串) 报销类型，例如 "通讯费"。
            '''
        )
        # 2. 创建核心的 agno Agent 实例
        self.coreagent = Agent(
            model=DeepSeek(temperature=0),
            tools=[
                FinancialTools()
            ],
            # 将memory实例注入到Agent中
            memory=self.memory,
            debug_mode=True
        )
        print("A new FinancialAgent instance has been created with its own short-term memory.")

    async def _initialize_knowledge(self):
        """
        一次性获取并缓存API列表。
        """
        if self.is_knowledge_initialized:
            return

        print("DEBUG: 正在进行首次知识初始化，获取API列表...")
        try:
            # 直接通过 coreagent 实例访问并调用工具
            tools_instance = self.coreagent.tools[0]
            api_list_str = await tools_instance.list_financial_apis()

            # 对结果进行精简，只保留关键信息，减少Token占用
            api_list_json = json.loads(api_list_str)
            simplified_list = [{"name": api.get("name"), "description": api.get("description")} for api in
                               api_list_json]

            self.api_list_cache = json.dumps(simplified_list, ensure_ascii=False, indent=2)
            self.is_knowledge_initialized = True
            print("DEBUG: API列表知识缓存成功！")
        except Exception as e:
            print(f"ERROR: 知识初始化失败: {e}")
            self.api_list_cache = "错误：无法加载API列表。"

    async def get_response(self, user_input: str) -> dict:
        # --- Part 1: 准备并调用 Agent (循环执行) ---
        if not self.is_knowledge_initialized:
            await self._initialize_knowledge()

        current_date_str = datetime.now().strftime('%Y-%m-%d')
        formatted_description = self.base_description.format(current_date=current_date_str)

        knowledge_prompt = (
            f"{formatted_description}\n\n"  # <-- 使用格式化后的指令
            "--- [预加载的背景知识：可用API列表] ---\n"
            f"{self.api_list_cache}\n"
            "--- [背景知识结束] ---\n"
        )
        self.coreagent.description = knowledge_prompt

        history_messages = self.memory.get_messages_from_last_n_runs(last_n=4)
        current_user_message = Message(role="user", content=user_input)
        messages_for_loop = history_messages + [current_user_message]

        # 用于记录本次用户请求的所有“思考->行动->结果”轨迹
        full_trace_of_this_turn = []
        final_answer = "Agent 未能得出最终结论。"
        max_turns = 10

        for i in range(max_turns):
            print(f"\n--- Agent Execution Loop: Turn {i + 1}/{max_turns} ---")

            response_object: RunResponse = await self.coreagent.arun(messages=messages_for_loop)
            # arun 返回的结果包含了完整的对话历史，我们需要从中提取出“新”产生的部分，
            # 即本次 LLM 返回的“思考”或“行动”或“最终答案”。
            newly_generated_messages = response_object.messages[len(messages_for_loop):]

            if not newly_generated_messages:
                print("WARN: Agent did not produce any new messages. Breaking loop.")
                final_answer = "Agent 停止响应，任务中断。"
                break

            # 将新产生的消息，同时添加到两个列表中：
            # 1. full_trace_of_this_turn: 用于最终展示给用户的执行步骤。
            full_trace_of_this_turn.extend(newly_generated_messages)
            # 2. messages_for_loop: 用于下一次循环的输入，这样 LLM 就能看到自己上一步的思考和行动。
            messages_for_loop.extend(newly_generated_messages)

            last_message = newly_generated_messages[-1]
            if last_message.role == 'assistant':
                content = last_message.content

                # 检查是否进入 FINAL 阶段
                if "<FINAL_ANSWER_START>" in content and "<FINAL_ANSWER_END>" in content:
                    print("INFO: Agent has produced a final answer. Exiting loop.")

                    # 截取 <FINAL_ANSWER_START> 和 <FINAL_ANSWER_END> 之间的部分
                    match = re.search(r"<FINAL_ANSWER_START>(.*)<FINAL_ANSWER_END>", content, re.S)
                    if match:
                        final_answer = match.group(1).strip()
                    else:
                        final_answer = content  # fallback
                    break

        final_answer_raw = final_answer

        natural_language_summary = final_answer_raw
        visualization_type = None
        title = None
        table_data = None
        chart_data = None

        # 尝试从原始答案中用正则表达式提取 <json_report> 标签中的内容
        # re.DOTALL 标志确保了 . 可以匹配包括换行符在内的任意字符
        match = re.search(r'<json_report>(.*?)</json_report>', final_answer_raw, re.DOTALL)
        if match:
            json_string = match.group(1).strip()
            if json_string.startswith("```json"):
                json_string = json_string[7:]  # 移除开头的 '```json'
            if json_string.endswith("```"):
                json_string = json_string[:-3]  # 移除结尾的 '```'
            # 将自然语言部分和JSON标签部分分离开
            natural_language_summary = re.sub(r'<json_report>.*?</json_report>', '', final_answer_raw,
                                              flags=re.DOTALL).strip()
            try:
                # 先将整个JSON字符串解析为一个父对象
                report_json = json.loads(json_string)
                print("DEBUG: 成功从AI回复中解析出 JSON Report 对象。")

                # 然后从这个父对象中，安全地获取每一个字段
                visualization_type = report_json.get("visualization_type")
                title = report_json.get("title")
                table_data = report_json.get("table_data")
                chart_data = report_json.get("chart_data")

            except json.JSONDecodeError:
                print(f"ERROR: AI生成的JSON格式错误，无法解析: {json_string}")
                natural_language_summary = "AI在生成报告时遇到格式问题，无法展示数据。"

        # 我们将使用处理过的 natural_language_summary 作为最终的 final_answer
        final_answer = natural_language_summary

        # --- Part 2: 解析用于前端展示的步骤 ---
        execution_steps = []
        if full_trace_of_this_turn:
            last_tool_name = None
            for message in full_trace_of_this_turn:
                if message.role == "assistant" and message.tool_calls:
                    if message.content:
                        execution_steps.append({"type": "thought", "content": message.content})
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.get("function", {}).get("name")
                        last_tool_name = tool_name
                        execution_steps.append({
                            "type": "tool_call", "tool_name": tool_name,
                            "tool_args": tool_call.get("function", {}).get("arguments")
                        })
                elif message.role == "tool":
                    output_content = str(message.content)
                    preview = (output_content[:500] + '...') if len(output_content) > 500 else output_content
                    execution_steps.append({
                        "type": "tool_output", "tool_name": last_tool_name or "未知工具",
                        "output_preview": preview, "output_full": output_content
                    })

        # --- Part 3: 清理存入记忆的数据 ---
        if self.memory.runs:
            last_run = self.memory.runs[-1]
            if last_run.response and last_run.response.messages:
                messages_for_cleanup = last_run.response.messages
                for i, message in enumerate(messages_for_cleanup):
                    if message.role == "tool" and len(str(message.content)) > 1000:
                        summary = f"[{message.name or '工具'} 返回了大量数据，内容已总结]"
                        if i + 1 < len(messages_for_cleanup) and messages_for_cleanup[i + 1].role == 'assistant':
                            assistant_summary = messages_for_cleanup[i + 1].content
                            if assistant_summary:
                                summary = f"[原始工具输出过长，已被总结替代]:\n{assistant_summary}"
                        print(f"DEBUG: Cleaning up large tool output for '{message.name}' in memory.")
                        message.content = summary

        # --- Part 4: 返回结果 ---
        return {
            "final_answer": final_answer.replace('**', ''),
            "execution_steps": execution_steps,
            "visualization_type": visualization_type,
            "title": title,
            "table_data": table_data,
            "chart_data": chart_data,
        }