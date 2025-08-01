from ..services.ai_service import WarehouseAI
from ..services.data_service import DataService
import logging
import asyncio
from typing import Dict, Any, Optional

class WarehouseChatbot:
    def __init__(self, data_service=None, vector_db_service=None):
        self.data_service = data_service or DataService()
        self.vector_db_service = vector_db_service
        self.llm_client = WarehouseAI() # WarehouseAI 인스턴스 사용
        self.logger = logging.getLogger(__name__)
        
        # 처리 체인 설정
        self.processing_chains = {
            "direct": self._handle_direct_query,
            "vector_search": self._handle_vector_search_query, 
            "general": self._handle_general_query
        }

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

    async def process_query(self, question: str) -> str:
        """
        개선된 체인 기반 질의 처리
        1. Direct Answer (빠른 계산 결과)
        2. Vector Search (고급 검색)  
        3. General LLM (일반 질의응답)
        """
        try:
            self.logger.info(f"질의 처리 시작: {question[:50]}...")
            
            # 1단계: 직접 답변 가능한 질문인지 확인
            direct_result = await self._handle_direct_query(question)
            if direct_result:
                self.logger.info("직접 답변으로 처리 완료")
                return direct_result
            
            # 2단계: VectorDB 검색이 필요한 복잡한 질문인지 판단
            if self._needs_vector_search(question):
                self.logger.info("VectorDB 검색 체인으로 처리")
                vector_result = await self._handle_vector_search_query(question)
                if vector_result:
                    return vector_result
            
            # 3단계: 일반 LLM 처리
            self.logger.info("일반 LLM 체인으로 처리")
            return await self._handle_general_query(question)
            
        except Exception as e:
            self.logger.error(f"질의 처리 오류: {e}")
            return f"죄송합니다. 질문을 처리하는 중 오류가 발생했습니다: {str(e)}"
    
    def _needs_vector_search(self, question: str) -> bool:
        """VectorDB 검색이 필요한 질문인지 판단"""
        vector_keywords = [
            "분석", "트렌드", "패턴", "예측", "상관관계", 
            "비교", "변화", "증감", "최적화", "추천"
        ]
        return any(keyword in question for keyword in vector_keywords)
    
    async def _handle_direct_query(self, question: str) -> Optional[str]:
        """직접 계산으로 답변 가능한 간단한 질문 처리"""
        return self._try_direct_answer(question)
    
    async def _handle_vector_search_query(self, question: str) -> Optional[str]:
        """VectorDB를 활용한 고급 검색 질문 처리"""
        if not (self.vector_db_service and self.vector_db_service.is_initialized):
            self.logger.info("VectorDB 서비스가 초기화되지 않음, 일반 처리로 넘어감")
            return None
            
        try:
            self.logger.info("VectorDB 검색 시작...")
            search_result = await self.vector_db_service.search_relevant_data(
                query=question,
                n_results=5  # 성능 개선을 위해 5개로 제한
            )
            
            if not search_result.get("success"):
                self.logger.warning("VectorDB 검색 실패")
                return None
                
            # Vector 검색 결과를 구조화된 프롬프트로 변환
            structured_context = self._vectordb_to_prompt(search_result, question)
            
            # 최적화된 VectorDB 전용 LLM 호출
            response = await self.llm_client.answer_with_vector_context(
                question, structured_context
            )
            
            self.logger.info("VectorDB 검색 처리 완료")
            return response
            
        except Exception as e:
            self.logger.error(f"VectorDB 검색 처리 오류: {e}")
            return None
    
    async def _handle_general_query(self, question: str) -> str:
        """일반적인 질문을 기본 데이터로 처리"""
        intent = self.analyze_intent(question)
        context_data = self.data_service.get_relevant_data(intent)
        
        # 간단한 LLM 호출 (VectorDB 없이)
        return await self.llm_client.answer_simple_query(question, context_data)
    
    def _vectordb_to_prompt(self, search_result: Dict, question: str) -> str:
        """VectorDB 검색 결과를 구조화된 프롬프트로 변환"""
        documents = search_result.get('results', {}).get('documents', [[]])[0]
        chart_data = search_result.get('chart_data', {})
        
        prompt_parts = [
            f"질문: {question}",
            "",
            "== 검색된 관련 정보 ==",
        ]
        
        # 문서 정보 추가
        for i, doc in enumerate(documents[:3], 1):  # 상위 3개만
            prompt_parts.append(f"{i}. {doc}")
        
        # 차트 데이터가 있으면 추가
        if chart_data:
            prompt_parts.extend([
                "",
                "== 관련 차트 데이터 ==",
                str(chart_data)
            ])
        
        return "\n".join(prompt_parts)
    
    def _try_direct_answer(self, question: str) -> Optional[str]:
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