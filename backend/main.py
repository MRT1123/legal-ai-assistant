"""
法律智能助手 - 主入口
功能：导入法律知识库 → 构建 LangGraph Agent → 测试问答

运行方式：
  cd D:/legal-ai-assistant/backend
  python main.py
"""

import sys
import os

# 把 backend 目录加入 Python 路径（确保 app 模块能被正确导入）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.rag_service import load_sample_legal_data, retrieve_documents
from app.agent.graph import build_graph


def main():
    print("=" * 60)
    print("🏛️  法律智能助手 v0.1 - LangGraph 多智能体架构")
    print("=" * 60)
    
    # ==================== 第1步：初始化知识库 ====================
    print("\n📚 第1步：初始化法律知识库...")
    print("-" * 40)
    
    # 加载示例法律数据（创建向量库）
    # 如果已经存在，下次可以跳过
    load_sample_legal_data()
    
    # ==================== 第2步：构建 LangGraph ====================
    print("\n🏗️  第2步：构建 LangGraph Agent...")
    print("-" * 40)
    
    app = build_graph()
    
    # ==================== 第3步：测试问答 ====================
    print("\n💬 第3步：测试问答")
    print("-" * 40)
    
    # 测试问题列表
    test_questions = [
        "公司辞退我，应该赔偿多少？",
        "竞业限制是什么意思？",
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'='*50}")
        print(f"测试 {i}：{question}")
        print(f"{'='*50}")
        
        # 构建输入状态
        input_state = {
            "query": question,
            "query_type": "",
            "documents": [],
            "tool_results": [],
            "final_answer": "",
            "messages": []
        }
        
        # 运行图
        result = app.invoke(input_state)
        
        # 显示结果
        print(f"\n{'─'*50}")
        print(f"📋 最终回答：")
        print(f"{'─'*50}")
        print(result["final_answer"])
        print()


if __name__ == "__main__":
    main()
