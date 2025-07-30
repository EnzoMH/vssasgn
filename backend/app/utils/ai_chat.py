from ..services.ai_service import WarehouseAI
from ..services.data_service import DataService

class WarehouseChatbot:
    def __init__(self, data_service=None, vector_db_service=None):
        self.data_service = data_service or DataService()
        self.vector_db_service = vector_db_service
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

        # 2. 간단한 질문들에 대해서는 직접 계산
        direct_answer = self._try_direct_answer(question)
        if direct_answer:
            return direct_answer

        # 3. 벡터 DB에서 관련 데이터 검색 (있으면)
        context_data = None
        if self.vector_db_service and self.vector_db_service.is_initialized:
            try:
                search_result = await self.vector_db_service.search_relevant_data(
                    query=question,
                    n_results=10
                )
                if search_result.get("success"):
                    context_data = {
                        "vector_search": search_result,
                        "data_loaded": self.data_service.data_loaded
                    }
            except Exception as e:
                print(f"벡터 DB 검색 오류: {e}")
        
        # 4. 기존 방식으로 데이터 조회 (벡터 DB 없거나 실패시)
        if not context_data:
            context_data = self.data_service.get_relevant_data(intent)

        # 5. LLM으로 응답 생성
        response = await self.llm_client.answer_query(question, context_data)

        return response
    
    def _try_direct_answer(self, question: str) -> str:
        """간단한 질문들에 대해 직접 계산하여 답변"""
        if not self.data_service.data_loaded:
            return None
            
        question_lower = question.lower()
        
        try:
            # 총 재고량 질문
            if any(word in question_lower for word in ['총 재고량', '총재고', '전체 재고', '총 재고']):
                if self.data_service.product_master is not None and '현재고' in self.data_service.product_master.columns:
                    total_inventory = int(self.data_service.product_master['현재고'].sum())
                    product_count = len(self.data_service.product_master)
                    return f"🏢 **총 재고량은 {total_inventory:,}개입니다.**\n\n📊 전체 {product_count}개 품목의 현재 재고를 합계한 결과입니다.\n💡 자세한 랙별 분포는 '랙별 재고 현황' 차트를 확인해보세요."
                else:
                    return "📊 죄송합니다. 현재고 데이터를 찾을 수 없습니다. 데이터가 로드되었는지 확인해주세요."
            
            # 입고량 질문
            if any(word in question_lower for word in ['입고량', '입고 현황', '오늘 입고']):
                if self.data_service.inbound_data is not None and 'PalleteQty' in self.data_service.inbound_data.columns:
                    total_inbound = int(self.data_service.inbound_data['PalleteQty'].sum())
                    inbound_count = len(self.data_service.inbound_data)
                    return f"📦 **총 입고량은 {total_inbound:,}개입니다.**\n\n📈 총 {inbound_count}건의 입고 기록이 있습니다.\n💡 상세한 입고 트렌드는 '일별 입출고 트렌드' 차트를 확인해보세요."
                else:
                    return "📦 죄송합니다. 입고 데이터를 찾을 수 없습니다."
            
            # 출고량 질문
            if any(word in question_lower for word in ['출고량', '출고 현황', '오늘 출고']):
                if self.data_service.outbound_data is not None and 'PalleteQty' in self.data_service.outbound_data.columns:
                    total_outbound = int(self.data_service.outbound_data['PalleteQty'].sum())
                    outbound_count = len(self.data_service.outbound_data)
                    return f"🚚 **총 출고량은 {total_outbound:,}개입니다.**\n\n📉 총 {outbound_count}건의 출고 기록이 있습니다.\n💡 상세한 출고 트렌드는 '일별 입출고 트렌드' 차트를 확인해보세요."
                else:
                    return "🚚 죄송합니다. 출고 데이터를 찾을 수 없습니다."
            
            # 랙 관련 질문
            if any(word in question_lower for word in ['랙', 'rack', 'a랙', 'b랙', 'c랙']):
                if self.data_service.product_master is not None and 'Rack Name' in self.data_service.product_master.columns:
                    rack_summary = self.data_service.product_master.groupby('Rack Name')['현재고'].sum().sort_values(ascending=False)
                    if len(rack_summary) > 0:
                        rack_info = []
                        for rack, qty in rack_summary.head(5).items():
                            rack_info.append(f"• {rack}: {int(qty):,}개")
                        
                        return f"🏢 **랙별 재고 현황:**\n\n" + "\n".join(rack_info) + f"\n\n📊 총 {len(rack_summary)}개 랙에 재고가 분산되어 있습니다."
                    else:
                        return "🏢 랙 정보를 찾을 수 없습니다."
                else:
                    return "🏢 죄송합니다. 랙 데이터를 찾을 수 없습니다."
            
        except Exception as e:
            print(f"직접 답변 계산 오류: {e}")
            return None
        
        return None