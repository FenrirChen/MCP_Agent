import os
from dotenv import load_dotenv # 用于加载.env文件
import json
from datetime import datetime


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
        #  这个对象将存储本次对话的所有历史记录。
        self.memory = AgentMemory()

        # 2.创建一个cache来缓存api列表
        self.api_list_cache = None
        self.is_knowledge_initialized = False
        self.base_description=(
            "你是一个名为'FinancialSystemOperator'的高级AI操作员。你的核心能力是【自主规划】和【组合使用工具】，以解决复杂的多步财务问题。你的最终目标是为用户提供直接、准确的答案，而不是操作指南。\n\n"

            # --- 2. 引入 ReAct 思考模式 ---
            "## 思考与行动框架:\n"
            "当任务未完成时，你必须遵循“思考 -> 行动”的循环模式。在每一步，你都需要生成一个'思考'块和一个'行动'块。\n"
            "1. **思考 (Thought)**: 首先，分析用户的问题。将复杂问题分解成一个清晰的、分步执行的计划。明确指出你需要哪些信息，以及打算按什么顺序调用哪些工具来获取这些信息。如果上一步的工具调用返回了信息，在这一步进行分析和总结。\n"
            "2. **行动 (Action)**: 在'思考'之后，执行你计划中的【一步】。这可以是一次工具调用，或者是对用户的最终回答。\n\n"
            "当任务已完成，准备回答用户时，你的回复【必须】是直接面向用户的、干净、简洁的最终答案。此时，【绝对禁止】使用 `**思考**:` 或 `**行动**:` 前缀。\n"

            # --- 3. 提供一个多步任务的范例 (Few-shot Example) ---
            "## 复杂任务范例:\n"
            "用户提问: '查询借款单 JKD20250804014 和 JKD20250805008 的金额，并告诉我它们的差额。'\n\n"
            "你的执行流程应该是这样的：\n"
            "--- 范例开始 ---\n"
            "**思考**: 用户需要两个借款单的金额差。我目前没有任何一个单据的信息。我的计划是：\n"
            "1. 调用 `call_financial_api` 获取 JKD20250804014 的信息。\n"
            "2. 调用 `call_financial_api` 获取 JKD20250805008 的信息。\n"
            "3. 在获得两个金额后，进行计算并给出最终答案。\n"
            "现在，我将执行计划的第1步。\n"
            "**行动**: `call_financial_api(service='queryLoanRepayment', request={{'body': {{'documentNumber': 'JKD20250804014'}}}})`\n"
            "--- (系统会返回JKD20250804014的查询结果) ---\n"
            "**思考**: 我已经成功获取了 JKD20250804014 的金额是 120.0。现在我需要执行计划的第2步，获取 JKD20250805008 的信息。\n"
            "**行动**: `call_financial_api(service='queryLoanRepayment', request={{'body': {{'documentNumber': 'JKD20250805008'}}}})`\n"
            "--- (系统会返回JKD20250805008的查询结果) ---\n"
            "**思考**: 我已经获取了 JKD20250805008 的金额是 11.0。现在我拥有了计算差额所需的全部信息。120.0 - 11.0 = 109.0。我可以给出最终答案了。\n"
            "**行动**: 借款单 JKD20250804014 的金额为 120.0 元，JKD20250805008 的金额为 11.0 元，它们的差额是 109.0 元。\n"
            "--- 范例结束 ---\n\n"

            # --- 4. 你的可用资源和规则 ---
            "## 可用资源与规则:\n"
            "- 你拥有一个预加载的API列表（在背景知识中），以及一系列可用的工具。\n"
            "- 当前日期: {current_date}\n\n"
            "- 你不需要考虑‘pageNo’和‘pageSize’,这些由后端解决。\n"
            "- 当你希望用操作型api来查询数据时，可以设置‘isQuery=true’\n"
            "- 当你调用操作型api时，你必须设置‘isQuery=true’\n"
            "- 大多数任务都不是简单调用接口就能完成的，需要你协调各个接口找到其内在联系来完成最终任务\n"
            "- 你必须回顾【最近的对话历史】，以利用已经获取过的信息。\n"
            "- 当发现调用api的参数不足或有误时,调用 `get_financial_api_detail` \n"
            "- 只有当你认为预加载的列表不完整，或者你需要确认最新信息时，调用`list_financial_apis`。\n"


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

        full_trace_of_this_turn = []
        final_answer = "Agent 未能得出最终结论。"
        max_turns = 10

        for i in range(max_turns):
            print(f"\n--- Agent Execution Loop: Turn {i + 1}/{max_turns} ---")

            response_object: RunResponse = await self.coreagent.arun(messages=messages_for_loop)
            newly_generated_messages = response_object.messages[len(messages_for_loop):]

            if not newly_generated_messages:
                print("WARN: Agent did not produce any new messages. Breaking loop.")
                final_answer = "Agent 停止响应，任务中断。"
                break

            full_trace_of_this_turn.extend(newly_generated_messages)
            messages_for_loop.extend(newly_generated_messages)

            last_message = newly_generated_messages[-1]
            if last_message.role == 'assistant' and (not last_message.tool_calls and "**行动**:" not in last_message.content):
                print("INFO: Agent has produced a final answer. Exiting loop.")
                final_answer = last_message.content
                break

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
            "execution_steps": execution_steps
        }
