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
            
            # 2단계: CoT를 통한 VectorDB 검색 필요성 판단
            needs_vector = await self._needs_vector_search(question)
            if needs_vector:
                self.logger.info("CoT 분석 결과: VectorDB 검색 체인으로 처리")
                vector_result = await self._handle_vector_search_query(question)
                if vector_result:
                    return vector_result
            else:
                self.logger.info("CoT 분석 결과: VectorDB 검색 불필요")
            
            # 3단계: 일반 LLM 처리
            self.logger.info("일반 LLM 체인으로 처리")
            return await self._handle_general_query(question)
            
        except Exception as e:
            self.logger.error(f"질의 처리 오류: {e}")
            return f"죄송합니다. 질문을 처리하는 중 오류가 발생했습니다: {str(e)}"
    
    async def _needs_vector_search(self, question: str) -> bool:
        """CoT를 통한 의미론적 분석으로 VectorDB 검색 필요성 판단"""
        try:
            # 1단계: 기본 키워드 필터링 (성능 최적화)
            basic_keywords = [
                "어떤", "어디", "누가", "언제", "얼마", "몇", "얼마나", "무엇", "뭐", "뭔가",
                "리스트", "목록", "현황", "상태", "통계", "조회", "검색", "분석", "주요",
                "supplier", "공급업체", "공급사", "고객사", "업체", "회사", "기업", 
                "product", "상품", "제품", "품목", "랙", "rack", "재고", "수량", "a랙", "b랙"
            ]
            
            question_lower = question.lower()
            has_basic_keywords = any(keyword in question_lower for keyword in basic_keywords)
            
            if not has_basic_keywords:
                return False
            
            # 2단계: 간단한 패턴 기반 사전 필터링
            simple_calc_patterns = ["총 재고량", "총재고", "전체 재고량", "현재 재고량이 얼마"]
            if any(pattern in question_lower for pattern in simple_calc_patterns):
                self.logger.info("사전 필터링: 간단한 계산 질문으로 판단")
                return False
            
            # 벡터 검색 필수 패턴
            vector_required_patterns = ["어떤 상품", "어떤 업체", "주요 공급", "주요 상품", "a랙", "b랙", "랙에"]
            if any(pattern in question_lower for pattern in vector_required_patterns):
                self.logger.info("사전 필터링: 벡터 검색 필수 질문으로 판단")
                return True
            
            # 3단계: CoT 기반 의미론적 분석 (복잡한 케이스만)
            cot_analysis = await self._analyze_question_intent_with_cot(question)
            
            # 4단계: CoT 결과를 바탕으로 최종 판단
            needs_vector = cot_analysis.get("needs_vector_search", False)
            confidence = cot_analysis.get("confidence", 0.5)
            reasoning = cot_analysis.get("reasoning", "")
            
            self.logger.info(f"CoT 분석 결과: needs_vector={needs_vector}, confidence={confidence}, reasoning={reasoning[:100]}...")
            
            return needs_vector
            
        except Exception as e:
            self.logger.warning(f"CoT 분석 실패, 기본 키워드 매칭으로 fallback: {e}")
            # fallback: 기본 키워드 매칭
            basic_vector_keywords = [
                "분석", "트렌드", "패턴", "예측", "supplier", "공급업체", "고객사",
                "상품", "제품", "랙", "재고", "어떤", "어디", "누가", "얼마"
            ]
            return any(keyword in question_lower for keyword in basic_vector_keywords)
    
    async def _analyze_question_intent_with_cot(self, question: str) -> Dict[str, Any]:
        """Chain of Thought를 통한 질문 의도 분석"""
        try:
            if not self.llm_client:
                return {"needs_vector_search": False, "reasoning": "LLM 클라이언트 없음"}
            
            cot_prompt = f"""
당신은 창고 관리 시스템의 질의 분석 전문가입니다. 다음 질문을 단계별로 분석하여 어떤 처리 방식이 필요한지 판단하세요.

**질문:** "{question}"

**분석 단계:**
1. 질문 유형 분류: 이 질문이 요구하는 것은 무엇인가?
2. 데이터 범위 판단: 단순 계산인가, 복합 검색인가?
3. 처리 방식 결정: 직접 계산, 벡터 검색, 일반 LLM 중 무엇이 적합한가?

**판단 기준:**
- 직접 계산: "총 재고량", "전체 입고량" 등 단순 합계 (숫자 하나만 원하는 경우)
- 벡터 검색: "어떤 업체들", "어떤 상품들", "주요 공급사", "A랙 상품", "상위 N개", "목록 조회", "현황 분석"
- 일반 LLM: 개념 설명, 사용법, 일반 상식

**중요:** 다음 질문들은 반드시 벡터 검색이 필요합니다:
- "A랙에 어떤 상품이 있지?" → 벡터 검색 (특정 위치 상품 조회)
- "주요 공급사는?" → 벡터 검색 (공급업체 목록 및 순위)
- "주요 상품은?" → 벡터 검색 (상품 목록 및 분석)
- "현재 재고량이 얼마야?" → 직접 계산 (단순 합계)

**응답 형식 (JSON):**
{{
    "question_type": "data_query|calculation|explanation|other",
    "data_scope": "simple|complex|none",
    "reasoning": "단계별 분석 결과",
    "needs_vector_search": true|false,
    "confidence": 0.0-1.0
}}
"""
            
            # 간단한 LLM 호출로 CoT 분석 수행 (CoT 플래그 전달)
            response = await self.llm_client.answer_simple_query(cot_prompt, {"cot_analysis": True})
            
            # JSON 응답 파싱 시도
            import json
            try:
                # JSON 부분만 추출
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    analysis = json.loads(json_str)
                    
                    self.logger.info(f"CoT 분석 완료: {analysis.get('reasoning', '')}")
                    return analysis
                else:
                    raise ValueError("JSON 형식을 찾을 수 없음")
                    
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"CoT JSON 파싱 실패: {e}")
                # 응답에서 키워드 기반 분석 fallback
                return self._fallback_intent_analysis(question, response)
                
        except Exception as e:
            self.logger.warning(f"CoT 분석 오류: {e}")
            return {"needs_vector_search": False, "reasoning": f"분석 실패: {e}"}
    
    def _fallback_intent_analysis(self, question: str, llm_response: str) -> Dict[str, Any]:
        """LLM 응답 기반 fallback 의도 분석"""
        response_lower = llm_response.lower()
        
        # LLM 응답에서 키워드 감지
        vector_indicators = [
            "벡터 검색", "vector", "복합", "검색", "조회", "분석", 
            "데이터", "목록", "비교", "상위", "하위"
        ]
        
        direct_indicators = [
            "직접", "계산", "단순", "합계", "총", "간단"
        ]
        
        has_vector_indicators = any(indicator in response_lower for indicator in vector_indicators)
        has_direct_indicators = any(indicator in response_lower for indicator in direct_indicators)
        
        if has_vector_indicators and not has_direct_indicators:
            return {
                "needs_vector_search": True,
                "reasoning": "LLM 응답에서 복합 검색 필요성 감지",
                "confidence": 0.7
            }
        elif has_direct_indicators:
            return {
                "needs_vector_search": False,
                "reasoning": "LLM 응답에서 직접 계산 가능성 감지",
                "confidence": 0.8
            }
        else:
            # 질문 자체에서 간단한 패턴 매칭
            question_lower = question.lower()
            complex_patterns = ["어떤", "어느", "누가", "뭐가", "무엇", "리스트", "목록", "상위", "하위"]
            
            if any(pattern in question_lower for pattern in complex_patterns):
                return {
                    "needs_vector_search": True,
                    "reasoning": "질문에서 복합 조회 패턴 감지",
                    "confidence": 0.6
                }
            else:
                return {
                    "needs_vector_search": False,
                    "reasoning": "단순 질문으로 판단",
                    "confidence": 0.5
                }

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
                n_results=15  # 공급업체 등 집계를 위해 더 많은 결과 필요
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
        documents = search_result.get('documents', [])
        chart_data = search_result.get('chart_data', {})
        metadata_summary = search_result.get('metadata_summary', {})
        
        prompt_parts = [
            f"질문: {question}",
            "",
            "== 실제 창고 데이터 검색 결과 ==",
            f"검색된 문서 수: {search_result.get('found_documents', 0)}개",
            ""
        ]
        
        # 메타데이터 요약 정보 추가 (더 구체적)
        if metadata_summary:
            prompt_parts.extend([
                "== 데이터 요약 정보 ==",
                f"• 총 레코드: {metadata_summary.get('total_records', 0)}개",
                f"• 데이터 유형: {metadata_summary.get('data_types', {})}",
                f"• 날짜 범위: {metadata_summary.get('date_range', {})}",
                f"• 수량 통계: {metadata_summary.get('quantity_stats', {})}",
                ""
            ])
        
        # 문서 정보 추가 (상위 3개)
        if documents:
            prompt_parts.append("== 관련 문서 내용 ==")
            for i, doc in enumerate(documents[:3], 1):
                prompt_parts.append(f"{i}. {doc.strip()}")
            prompt_parts.append("")
        
        # 차트 데이터가 있으면 추가
        if chart_data:
            prompt_parts.extend([
                "== 집계된 차트 데이터 ==",
                f"제목: {chart_data.get('title', 'N/A')}",
                f"데이터: {chart_data.get('data', [])}",
                f"라벨: {chart_data.get('labels', [])}",
                ""
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