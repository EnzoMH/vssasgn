from backend.app.services.ai_service import WarehouseAI
from backend.app.services.data_service import DataService

class WarehouseChatbot:
    def __init__(self):
        self.data_service = DataService()
        self.llm_client = WarehouseAI() # WarehouseAI 인스턴스 사용

    def analyze_intent(self, question: str):
        # 질문에서 의도 분석 (예: "재고", "출고량", "예측")
        if "재고" in question:
            return "inventory"
        elif "출고량" in question:
            return "outbound"
        elif "예상" in question or "예측" in question:
            return "prediction"
        else:
            return "general"

    async def process_query(self, question: str):
        # 1. 질문 분석
        intent = self.analyze_intent(question)

        # 2. 관련 데이터 조회
        context_data = self.data_service.get_relevant_data(intent)

        # 3. LLM으로 응답 생성
        response = await self.llm_client.answer_query(question, context_data)

        return response 