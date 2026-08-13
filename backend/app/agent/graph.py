"""
法律智能助手 - 主路由图
根据用户意图分发到不同功能子图：
  - 法律问答（Q&A）：Router → Agent → Generator 三段式
  - 合同审查（Contract Review）：解析 → 风险扫描 → 合规检查 → 报告生成
  - 文书生成（Document Gen）：需求分析 → 文书起草 → 格式审核
  - 案例分析（Case Analysis）：事实梳理 → 法条检索 → 策略分析
"""

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from app.agent.state import AgentState
from app.agent.nodes import router_node, agent_node, generator_node
from app.agent.contract_review.graph import build_contract_review_graph
from app.agent.document_gen.graph import build_document_gen_graph
from app.agent.case_analysis.graph import build_case_analysis_graph
from app.agent.legal_calculator.graph import build_legal_calculator_graph
import json
import re

# LLM 用于意图分类（从模型服务层获取，支持 Fallback）
from app.services.model_service import get_llm
llm = get_llm()

# 构建子图
contract_review_graph = None
document_gen_graph = None
case_analysis_graph = None
legal_calculator_graph = None


def _is_legal_topic(query: str) -> bool:
    """用关键词规则快速判断是否与法律相关
    
    返回 True 表示可能是法律问题，需要继续用 LLM 细分
    返回 False 表示明显与法律无关，直接拦截
    """
    # 法律相关关键词（只要包含就认为是法律问题）
    legal_keywords = [
        # 通用法律概念
        "法律", "法", "法规", "条例", "司法解释", "合法", "违法", "合规",
        "权益", "权利", "义务", "责任", "法律责任",
        # 诉讼与司法程序
        "起诉", "诉讼", "仲裁", "调解", "上诉", "申诉", "再审", "立案",
        "判决", "裁定", "量刑", "刑期", "缓刑", "假释", "减刑",
        "保释", "取保候审", "审判", "公诉", "自诉", "一审", "二审", "终审",
        "死刑", "无期徒刑", "有期徒刑", "拘役", "管制", "罚金", "没收财产",
        "律师", "辩护", "代理", "公证",
        # 刑事类
        "刑法", "犯罪", "刑事", "故意", "过失",
        "故意伤害", "故意杀人", "盗窃", "抢劫", "诈骗", "敲诈勒索",
        "强奸", "猥亵", "绑架", "非法拘禁", "拐卖",
        "贩毒", "吸毒", "聚众斗殴", "寻衅滋事",
        "行贿", "受贿", "贪污", "挪用", "走私",
        "拘留", "逮捕", "通缉", "逃犯",
        # 劳动类
        "劳动", "辞退", "开除", "工资", "加班", "社保", "工伤",
        "劳动合同", "试用期", "竞业限制", "年终奖", "遣散费",
        "经济补偿", "赔偿金", "双倍工资",
        # 合同与债务
        "合同", "协议", "违约", "违约金", "定金", "押金", "保证金",
        "债务", "欠款", "借款", "利息", "逾期", "催收", "民间借贷",
        "担保", "抵押", "质押",
        # 婚姻家庭
        "婚姻", "离婚", "抚养", "赡养", "继承", "遗嘱", "财产分割",
        "婚前", "婚后", "彩礼", "嫁妆", "家暴", "家庭暴力",
        # 侵权与损害
        "侵权", "损害赔偿", "精神损害", "人身损害", "名誉权", "肖像权",
        "隐私权", "人格权", "高空抛物", "噪音扰民",
        # 消费与房产
        "消费者", "维权", "投诉", "退货", "退款", "三包",
        "房产", "租房", "购房", "物业", "拆迁", "拆迁补偿",
        "交房", "烂尾", "产权证",
        # 交通事故
        "交通事故", "责任认定", "保险理赔", "酒驾", "醉驾", "逃逸",
        # 行政与处罚
        "行政", "处罚", "罚款", "违规", "行政复议", "行政处罚",
        # 知识产权
        "知识产权", "专利", "商标", "版权", "著作权",
        # 赔偿相关
        "赔偿", "补偿", "损害赔偿",
    ]
    query_lower = query.lower()
    for keyword in legal_keywords:
        if keyword in query_lower:
            return True
    return False



# 非法律关键词列表（出现这些词且无法律上下文时，直接判定为非法律追问）
NON_LEGAL_KEYWORDS = [
    "天气", "气温", "下雨", "吃饭", "吃什么", "电影", "游戏",
    "音乐", "歌曲", "八卦", "新闻", "体育", "篮球", "足球",
    "你好", "早上好", "晚安", "谢谢", "再见",
]


def _is_legal_followup(query: str, chat_history: str) -> bool:
    """判断当前消息是否是法律对话的追问/延续

    接收当前消息和对话历史，让 LLM 结合上下文判断：
    - 是法律讨论的延续（如"那工作3年呢"、"如果是违法的呢"）→ True
    - 不是法律话题（如"今天天气怎样"、"帮我写首诗"）→ False

    参数：
        query: 用户当前输入
        chat_history: 格式化的对话历史字符串

    返回：
        True = 是法律追问，应放行
        False = 不是法律追问，应拦截
    """
    # 预检：如果消息包含明显的非法律关键词，直接拒绝，省一次 LLM 调用
    query_lower = query.lower()
    for kw in NON_LEGAL_KEYWORDS:
        if kw in query_lower:
            print(f"   [追问检测] 命中非法律关键词「{kw}」→ 直接拒绝")
            return False

    prompt = f"""你是一个对话上下文分析器。用户正在和一个法律智能助手对话。

请判断用户的当前消息是否是对前面法律讨论的追问或延续。

对话历史：
{chat_history if chat_history else "（无历史）"}

用户当前消息：{query}

判断标准：
- 如果当前消息是在延续前面的法律话题（如追问细节、补充条件、要求举例、进一步询问等），即使不包含法律关键词，也应判定为追问 → true
- 如果当前消息完全和前面的法律讨论无关（如突然问天气、闲聊、问其他领域问题），应判定为否 → false
- 如果当前消息虽然简短模糊（如"那3年呢"、"违法的呢"、"如果是这样"），但结合历史可以看出是法律讨论的延续 → true

请只返回 JSON：{{"is_followup": true或false}}"""

    try:
        response = llm.invoke(prompt)
        result_text = response.content.strip()
        # 提取 JSON
        match = re.search(r'\{[^}]+\}', result_text)
        if match:
            result = json.loads(match.group())
            is_followup = result.get("is_followup", False)
            print(f"   [追问检测] LLM判断结果：is_followup={is_followup}")
            return is_followup
        return False
    except Exception as e:
        print(f"   [追问检测] LLM调用失败：{e}，默认拒绝")
        return False


def _get_intent(query: str) -> str:
    """判断用户意图属于哪个功能
    
    先用关键词规则快速过滤非法律问题，再用 LLM 细分法律类别
    返回：qa / contract_review / document_gen / case_analysis / legal_calculator / off_topic
    """
    # 第一层：关键词规则快速拦截非法律问题
    if not _is_legal_topic(query):
        return "off_topic"

    prompt = f"""你是一个意图分类器。请根据用户输入判断其意图属于以下6个类别之一：

1. qa：一般的法律问题咨询（如"辞退赔偿多少"、"竞业限制是什么"、"试用期规定"）
2. contract_review：用户提供了一段合同文本，要求审查/分析/检查合同风险
3. document_gen：用户要求生成/起草/撰写一份法律文书（如申请书、起诉状、律师函、协议书）
4. case_analysis：用户描述了一个具体案件/纠纷经过，要求进行案例分析、策略建议、胜诉评估
5. legal_calculator：用户要求计算具体的法律金额（如经济补偿金、违约金、逾期利息、人身损害赔偿、抚养费等），通常包含具体数字或要求精确计算
6. off_topic：与法律完全无关的问题（如"今天天气怎么样"、"帮我写一首诗"、"推荐一部电影"、"1+1等于几"、日常闲聊等）

分类规则（按优先级）：
- 用户贴了一大段合同文本并要求审查 → contract_review
- 用户说"帮我写/起草/生成一份XX文书" → document_gen
- 用户描述了详细的事件经过并要求分析策略/胜诉率 → case_analysis
- 用户要求计算具体金额，附带了具体数字如工资、年限、金额等 → legal_calculator
- 用户的问题与法律有关但不属于上述四类 → qa
- 用户的问题与法律完全无关（闲聊、数学题、编程、生活建议、天气等） → off_topic

用户输入：
{query}

请只返回 JSON：{{"intent": "类别"}}"""

    try:
        response = llm.invoke(prompt)
        result = json.loads(response.content)
        intent = result.get("intent", "qa")
        if intent not in ("qa", "contract_review", "document_gen", "case_analysis", "legal_calculator", "off_topic"):
            intent = "qa"
        return intent
    except Exception:
        return "qa"


def master_router(state: AgentState) -> dict:
    """主路由节点：判断意图并设置 task_type"""
    query = state["query"]
    intent = _get_intent(query)
    print(f"\n🧭 [主路由] 意图识别：{intent}")
    return {"task_type": intent}


def master_dispatcher(state: AgentState) -> str:
    """主分发条件：根据 task_type 路由到不同处理路径"""
    task_type = state.get("task_type", "qa")
    if task_type == "contract_review":
        return "contract_review"
    elif task_type == "document_gen":
        return "document_gen"
    elif task_type == "case_analysis":
        return "case_analysis"
    elif task_type == "legal_calculator":
        return "legal_calculator"
    elif task_type == "off_topic":
        return "off_topic"
    else:
        return "qa"


def off_topic_node(state: AgentState) -> dict:
    """非法律问题拦截节点：提示用户咨询法律相关内容"""
    print("\n🚫 [非法律问题拦截]")
    return {
        "final_answer": "抱歉，我是法律智能助手，无法回答与法律无关的问题。如果您有法律方面的疑问，欢迎随时向我提问。",
        "query_type": "off_topic"
    }


def contract_review_node(state: AgentState) -> dict:
    """调用合同审查子图"""
    print("\n" + "=" * 50)
    print("📋 启动【合同风险审查】4 Agent 流水线")
    print("=" * 50)
    
    global contract_review_graph
    if contract_review_graph is None:
        contract_review_graph = build_contract_review_graph()
    
    result = contract_review_graph.invoke({
        "contract_text": state["query"],
        "extracted_clauses": "",
        "risk_items": "",
        "compliance_result": "",
        "final_report": ""
    })
    
    answer = result.get("final_report", "合同审查完成，但未能生成报告。")
    print(f"\n✅ 合同审查完成")
    return {"final_answer": answer, "query_type": "contract_review"}


def document_gen_node(state: AgentState) -> dict:
    """调用文书生成子图"""
    print("\n" + "=" * 50)
    print("✍️ 启动【法律文书生成】3 Agent 流水线")
    print("=" * 50)
    
    global document_gen_graph
    if document_gen_graph is None:
        document_gen_graph = build_document_gen_graph()
    
    result = document_gen_graph.invoke({
        "user_requirement": state["query"],
        "requirement_analysis": "",
        "document_draft": "",
        "final_document": "",
        "document_type": ""
    })
    
    answer = result.get("final_document", "文书生成完成，但未能生成文档。")
    doc_type = result.get("document_type", "法律文书")
    print(f"\n✅ {doc_type}生成完成")
    return {"final_answer": answer, "query_type": "document_gen"}


def case_analysis_node(state: AgentState) -> dict:
    """调用案例分析子图"""
    print("\n" + "=" * 50)
    print("📊 启动【案例分析】3 Agent 流水线")
    print("=" * 50)
    
    global case_analysis_graph
    if case_analysis_graph is None:
        case_analysis_graph = build_case_analysis_graph()
    
    result = case_analysis_graph.invoke({
        "case_description": state["query"],
        "facts_summary": "",
        "legal_references": "",
        "analysis_report": ""
    })
    
    answer = result.get("analysis_report", "案例分析完成，但未能生成报告。")
    print(f"\n✅ 案例分析完成")
    return {"final_answer": answer, "query_type": "case_analysis"}


def legal_calculator_node(state: AgentState) -> dict:
    """调用法律计算器子图"""
    print("\n" + "=" * 50)
    print("🔢 启动【法律计算器】3 Agent 流水线")
    print("=" * 50)
    
    global legal_calculator_graph
    if legal_calculator_graph is None:
        legal_calculator_graph = build_legal_calculator_graph()
    
    result = legal_calculator_graph.invoke({
        "user_query": state["query"],
        "parsed_params": "",
        "calculation_result": "",
        "final_report": "",
        "calc_type": ""
    })
    
    answer = result.get("final_report", "法律计算完成，但未能生成报告。")
    print(f"\n✅ 法律计算完成")
    return {"final_answer": answer, "query_type": "legal_calculator"}


def qa_router_node(state: AgentState) -> dict:
    """QA 子流程的路由节点（复用原有的 router_node 逻辑）"""
    return router_node(state)


def qa_agent_node(state: AgentState) -> dict:
    """QA 子流程的 Agent 节点"""
    return agent_node(state)


def qa_generator_node(state: AgentState) -> dict:
    """QA 子流程的 Generator 节点"""
    return generator_node(state)


def qa_should_use_agent(state: AgentState) -> str:
    """QA 子流程的条件路由"""
    query_type = state.get("query_type", "simple")
    if query_type == "general":
        return "direct"
    return "search"


def build_graph():
    """搭建主图：包含 Q&A + 合同审查 + 文书生成 + 案例分析
    
    架构：
    START → 主路由（意图识别）
              ├── qa → QA路由 → (Agent检索) → 生成回答 → END
              ├── contract_review → 合同审查流水线 → END
              ├── document_gen → 文书生成流水线 → END
              └── case_analysis → 案例分析流水线 → END
    """
    graph = StateGraph(AgentState)
    
    # === 主路由 ===
    graph.add_node("master_router", master_router)
    
    # === QA 子流程（原有三段式） ===
    graph.add_node("qa_router", qa_router_node)
    graph.add_node("qa_agent", qa_agent_node)
    graph.add_node("qa_generator", qa_generator_node)
    
    # === 非法律问题拦截 ===
    graph.add_node("off_topic", off_topic_node)
    
    # === 新功能子流程 ===
    graph.add_node("contract_review", contract_review_node)
    graph.add_node("document_gen", document_gen_node)
    graph.add_node("case_analysis", case_analysis_node)
    graph.add_node("legal_calculator", legal_calculator_node)
    
    # === 连线 ===
    # 入口 → 主路由
    graph.add_edge(START, "master_router")
    
    # 主路由 → 各子流程
    graph.add_conditional_edges(
        "master_router",
        master_dispatcher,
        {
            "qa": "qa_router",
            "contract_review": "contract_review",
            "document_gen": "document_gen",
            "case_analysis": "case_analysis",
            "legal_calculator": "legal_calculator",
            "off_topic": "off_topic"
        }
    )
    
    # QA 子流程内部连线
    graph.add_conditional_edges(
        "qa_router",
        qa_should_use_agent,
        {
            "search": "qa_agent",
            "direct": "qa_generator"
        }
    )
    graph.add_edge("qa_agent", "qa_generator")
    
    # 各子流程 → END
    graph.add_edge("qa_generator", END)
    graph.add_edge("contract_review", END)
    graph.add_edge("document_gen", END)
    graph.add_edge("case_analysis", END)
    graph.add_edge("legal_calculator", END)
    graph.add_edge("off_topic", END)
    
    # 编译
    app = graph.compile()
    print("\n✅ 主路由图构建完成！")
    print("   支持功能：")
    print("   📖 法律问答（Q&A 三段式）")
    print("   📋 合同风险审查（4 Agent 流水线）")
    print("   ✍️  法律文书生成（3 Agent 流水线）")
    print("   📊 案例分析（3 Agent 流水线）")
    print("   🔢 法律计算器（3 Agent 流水线）")
    print("   🚫 非法律问题拦截")
    print()
    
    return app
