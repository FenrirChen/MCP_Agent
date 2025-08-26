from pydantic import BaseModel, Field
from typing import List, Optional, Union, Any

class Table(BaseModel):
    title: str
    headers: List[str]
    rows: List[List[Any]]

class TableData(BaseModel):
    tables: List[Table]

class ChartDataset(BaseModel):
    label: str
    data: List[Union[int, float]]
    backgroundColor: Optional[List[str]] = None

class ChartData(BaseModel):
    labels: List[str]
    datasets: List[ChartDataset]




#可视化
class RichExecutionStep(BaseModel):
    type: str
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[str] = None
    output_preview: Optional[str] = None
    output_full: Optional[str] = None

class VisualChatResponse(BaseModel):
    final_answer: str
    execution_steps: List[RichExecutionStep]
    visualization_type: Optional[str] = None  # e.g., 'table', 'bar', 'pie'
    title: Optional[str] = None
    table_data: Optional[TableData] = None
    chart_data: Optional[ChartData] = None

class FinalReport(BaseModel):
    visualization_type: str = Field(
        ...,
        description="指明可视化类型。根据用户请求，生成表时为'table', 生成柱形图时为'bar', 生成饼图时为'pie' 。默认为 'table'。"
    )
    title: str = Field(
        ...,
        description="整个报告或图表的总标题，应简洁地概括报告内容。"
    )
    summary: str = Field(
        ...,
        description="一段面向最终用户的、自然语言的总结。直接、清晰地回答用户的问题，禁止包含任何'思考'或'行动'之类的内部过程描述。"
    )
    table_data: Optional[TableData] = Field(
        None,
        description="用于存放表格数据。当且仅当 visualization_type 为 'table' 时，此字段应被填充。"
    )

    chart_data: Optional[ChartData] = Field(
        None,
        description="用于存放图表数据。当且仅当 visualization_type 为 'bar' 或 'pie' 时，此字段应被填充。"
    )