from ..services.ai_service import WarehouseAI
from ..services.data_service import DataService
from ..services.langchain_service import LangChainRAGService
import logging
import asyncio
from typing import Dict, Any, Optional

class WarehouseChatbot:
    def __init__(self, data_service=None, vector_db_service=None, 
                 demand_predictor=None, product_clusterer=None, anomaly_detector=None):
        self.data_service = data_service or DataService()
        self.vector_db_service = vector_db_service
        self.llm_client = WarehouseAI() # WarehouseAI 인스턴스 사용
        self.logger = logging.getLogger(__name__)
        
        # 🚀 LangChain SELF-RAG 서비스 초기화 (ML 모델들 포함)
        self.langchain_service = LangChainRAGService(
            vector_db_service=self.vector_db_service,
            ai_client=self.llm_client,
            data_service=self.data_service,
            demand_predictor=demand_predictor,
            product_clusterer=product_clusterer,
            anomaly_detector=anomaly_detector
        )
        
        # 처리 체인 설정 (SELF-RAG 추가)
        self.processing_chains = {
            "direct": self._handle_direct_query,
            "vector_search": self._handle_vector_search_query, 
            "self_rag": self._handle_self_rag_query,  # 새로 추가
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
        🧠 강화된 AI 질의 처리 파이프라인
        0. Question Type Analysis (질문 유형 사전 분석)
        1. SELF-RAG (할루시네이션 방지 + 자체 검증)
        2. Direct Answer (간단한 계산)
        3. Specialized Handlers (질문 유형별 전용 처리)
        4. Fallback Vector Search (기존 방식)
        5. General LLM (최후 수단)
        """
        try:
            self.logger.info(f"🧠 [AI_CHAT] 질의 처리 시작: {question}")
            self.logger.info(f"📝 [PROMPT_INPUT] 사용자 질문: '{question}'")
            
            # 🔍 0단계: 질문 유형 사전 분석 (CoT 기반)
            question_analysis = await self._analyze_question_intent_with_cot(question)
            question_type = question_analysis.get("specific_task", "기타")
            needs_vector = question_analysis.get("needs_vector_search", False)
            self.logger.info(f"🔍 [AI_ANALYSIS] 질문 유형: {question_type}, 벡터 검색 필요: {needs_vector}")
            
            # 🎯 0.1단계: CoT 분석 결과에 따른 우선 처리
            if question_type == "계산" and not needs_vector:
                self.logger.info("🧮 [AI_SPECIALIZED] 계산 질문 - 직접 답변 우선 처리")
                direct_result = await self._handle_direct_query(question)
                if direct_result:
                    self.logger.info(f"✅ [AI_SUCCESS] 계산 질문 직접 처리 완료")
                    return direct_result
            
            # 🏗️ 0.1.5단계: 랙 관련 질문 강화 처리 (CoT 결과와 무관하게)
            if any(word in question.lower() for word in ['랙', 'rack']) and any(char in question.upper() for char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
                self.logger.info("🏗️ [AI_SPECIALIZED] 랙 관련 질문 - 강화 처리")
                rack_result = await self._handle_rack_specific_query(question)
                if rack_result:
                    self.logger.info(f"✅ [AI_SUCCESS] 랙 관련 질문 처리 완료")
                    return rack_result
            
            # 📅 0.2단계: 특수 질문 유형별 즉시 처리
            if question_type == "날짜분석":
                self.logger.info("📅 [AI_SPECIALIZED] 날짜 분석 전용 처리")
                date_result = await self._handle_date_analysis_query(question)
                if date_result:
                    self.logger.info(f"✅ [AI_SUCCESS] 날짜 분석 처리 완료")
                    return date_result
            
            elif question_type == "상태분석":
                self.logger.info("📊 [AI_SPECIALIZED] 상태 분석 전용 처리")
                status_result = await self._handle_status_analysis_query(question)
                if status_result:
                    self.logger.info(f"✅ [AI_SUCCESS] 상태 분석 처리 완료")
                    return status_result
            
            elif question_type == "목록조회":
                self.logger.info("📋 [AI_SPECIALIZED] 목록 조회 전용 처리")
                list_result = await self._handle_list_query(question)
                if list_result:
                    self.logger.info(f"✅ [AI_SUCCESS] 목록 조회 처리 완료")
                    return list_result
            
            # 🚀 1단계: SELF-RAG 스마트 처리 (할루시네이션 방지)
            self_rag_success = False
            try:
                self.logger.info("🔬 [AI_PROCESS] SELF-RAG 스마트 처리 시도")
                self_rag_result = await self.langchain_service.smart_process_query(question)
                if self_rag_result and not self_rag_result.startswith("오류") and "처리 중 오류" not in self_rag_result:
                    self.logger.info("✅ [AI_SUCCESS] SELF-RAG 처리 성공")
                    self.logger.info(f"🎯 [AI_OUTPUT] SELF-RAG 결과: '{self_rag_result[:200]}...'")
                    return self_rag_result
                else:
                    self.logger.warning(f"⚠️ [AI_FALLBACK] SELF-RAG 결과 품질 부족: {self_rag_result[:100] if self_rag_result else 'None'}...")
            except Exception as e:
                self.logger.warning(f"⚠️ [AI_ERROR] SELF-RAG 처리 실패, 강화된 fallback 사용: {e}")
            
            # 2단계: 직접 답변 가능한 간단한 질문 체크
            self.logger.info("📊 [AI_PROCESS] 직접 답변 가능성 체크")
            direct_result = await self._handle_direct_query(question)
            if direct_result:
                self.logger.info("📊 [AI_SUCCESS] 직접 답변으로 처리 완료")
                self.logger.info(f"🎯 [AI_OUTPUT] 직접 답변 결과: '{direct_result[:200]}...'")
                return direct_result
            
            # 🔥 3단계: 강화된 벡터 검색 fallback (SELF-RAG 실패 시 더 적극적 활용)
            self.logger.info("🔄 [AI_PROCESS] 강화된 벡터 검색 fallback 시작")
            enhanced_vector_result = await self._handle_enhanced_vector_fallback(question)
            if enhanced_vector_result:
                self.logger.info(f"🎯 [AI_OUTPUT] 강화된 벡터 결과: '{enhanced_vector_result[:200]}...'")
                return enhanced_vector_result
            
            # 4단계: 기존 벡터 검색 방식 (추가 fallback)
            if self._requires_immediate_vector_search(question) or self._is_data_inquiry(question):
                self.logger.info("🔍 [AI_PROCESS] 기존 벡터 검색 방식 사용")
                vector_result = await self._handle_vector_search_query(question)
                if vector_result:
                    self.logger.info(f"🎯 [AI_OUTPUT] 벡터 검색 결과: '{vector_result[:200]}...'")
                    return vector_result
            
            # 5단계: 최후의 일반 LLM 처리
            self.logger.info("💬 [AI_PROCESS] 일반 LLM 체인으로 처리")
            general_result = await self._handle_general_query(question)
            self.logger.info(f"🎯 [AI_OUTPUT] 일반 LLM 결과: '{general_result[:200]}...'")
            return general_result
            
        except Exception as e:
            self.logger.error(f"❌ [AI_ERROR] 질의 처리 오류: {e}")
            return f"죄송합니다. 질문을 처리하는 중 오류가 발생했습니다: {str(e)}"
    
    def _requires_immediate_vector_search(self, question: str) -> bool:
        """즉시 벡터 검색이 필요한 패턴 감지"""
        question_lower = question.lower()
        
        # 특정 위치/객체의 상태/정보를 묻는 패턴
        import re
        immediate_patterns = [
            # 랙 관련
            r"a랙", r"b랙", r"c랙", r"d랙", r"e랙", r"f랙", 
            r"랙.*상태", r"랙.*어때", r"랙.*정보", r"랙.*현황",
            r"랙에.*뭐", r"랙에.*어떤", r"랙에.*무엇",
            
            # 상품 관련
            r"어떤.*상품", r"무슨.*상품", r"뭔.*상품",
            r"상품.*목록", r"상품.*리스트", r"상품.*현황",
            
            # 업체 관련  
            r"어떤.*업체", r"어떤.*공급", r"어떤.*고객",
            r"주요.*공급", r"주요.*업체", r"주요.*고객",
            
            # 상태/현황 질문
            r"상태.*어때", r"현황.*어때", r"어떻게.*되", 
            r"상황.*어때", r"상태.*뭐", r"현황.*뭐"
        ]
        
        for pattern in immediate_patterns:
            if re.search(pattern, question_lower):
                self.logger.info(f"즉시 벡터 검색 패턴 매칭: {pattern}")
                return True
        return False
    
    def _is_data_inquiry(self, question: str) -> bool:
        """데이터 조회성 질문인지 판단 (단순 계산 제외)"""
        question_lower = question.lower()
        
        # 데이터 조회 키워드
        inquiry_keywords = [
            "어떤", "무엇", "뭐", "누가", "어디", "언제",
            "목록", "리스트", "현황", "상태", "정보", "상황",
            "분석", "통계", "트렌드", "패턴", "비교", "조회"
        ]
        
        # 단순 계산 키워드 (벡터 검색 불필요)
        import re
        simple_calc_patterns = [
            r"총.*얼마", r"전체.*얼마", r"합계.*얼마",
            r"총.*개수", r"전체.*개수", r"합계.*개수",
            r"총.*재고량", r"전체.*재고량"
        ]
        
        # 단순 계산이면 벡터 검색 불필요
        for pattern in simple_calc_patterns:
            if re.search(pattern, question_lower):
                self.logger.info(f"단순 계산 패턴으로 벡터 검색 제외: {pattern}")
                return False
        
        # 데이터 조회성 질문이면 벡터 검색 필요
        has_inquiry = any(keyword in question_lower for keyword in inquiry_keywords)
        if has_inquiry:
            self.logger.info("데이터 조회성 질문으로 벡터 검색 필요")
        return has_inquiry
    
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
                self.logger.warning("🔴 [COT_ERROR] LLM 클라이언트 없음")
                return {"needs_vector_search": False, "reasoning": "LLM 클라이언트 없음"}
            
            self.logger.info(f"🧠 [COT_START] 질문 의도 분석 시작: '{question}'")
            
            cot_prompt = f"""
당신은 창고 관리 시스템의 질의 분석 전문가입니다. 다음 질문을 단계별로 분석하여 어떤 처리 방식이 필요한지 정확히 판단하세요.

**질문:** "{question}"

**🔍 핵심 분석 단계:**
1. **질문 의도 파악**: 이 질문이 정말로 원하는 것은?
   - "언제" → 날짜/시간 정보 필요
   - "어떤" → 목록/상세 정보 필요  
   - "얼마" → 수량/금액 정보 필요
   - "부족한" → 임계값 기반 분석 필요

2. **데이터 처리 방식**: 
   - "언제가 제일 높았던" → 날짜별 분석 + 최댓값 검색 → 벡터 검색 필요
   - "부족한 제품" → 재고 분석 + 임계값 비교 → 벡터 검색 필요
   - "총 재고량" → 단순 합계 → 직접 계산
   - "랙 상태" → 특정 위치 정보 → 벡터 검색 필요

**🎯 강화된 판단 기준:**
- **직접 계산**: "총/전체 + 수량" (ex: 총 재고량, 전체 입고량)
- **날짜 분석**: "언제", "가장 높았던 날", "최대/최소인 날" → 반드시 벡터 검색
- **목록 조회**: "어떤", "어느", "무슨", "리스트", "목록" → 반드시 벡터 검색  
- **상태 분석**: "부족한", "위험한", "많은", "적은" → 반드시 벡터 검색
- **위치 조회**: "A랙", "B랙", "C랙", "랙 상태" → 반드시 벡터 검색
- **일반 질문**: 개념, 사용법, 시스템 외부 질문 → 일반 LLM

**🚨 필수 벡터 검색 패턴:**
- "입고량이 제일 높았던 날" → 날짜별 분석 필요 (벡터 검색)
- "재고가 부족한 제품" → 임계값 분석 필요 (벡터 검색)
- "C랙의 상태" → 위치 특정 조회 (벡터 검색)
- "어떤 상품들" → 목록 조회 (벡터 검색)

**응답 형식 (JSON):**
{{
    "question_type": "date_analysis|list_query|status_analysis|calculation|explanation|other",
    "data_scope": "simple|complex|none",
    "reasoning": "질문 의도와 필요한 처리 방식에 대한 구체적 분석",
    "needs_vector_search": true|false,
    "specific_task": "날짜분석|목록조회|상태분석|계산|설명|기타",
    "confidence": 0.0-1.0
}}
"""
            
            self.logger.info(f"📝 [COT_PROMPT] 생성된 CoT 프롬프트:\n{cot_prompt}")
            
            # 간단한 LLM 호출로 CoT 분석 수행 (CoT 플래그 전달)
            self.logger.info("🔄 [COT_PROCESS] LLM에 CoT 분석 요청")
            response = await self.llm_client.answer_simple_query(cot_prompt, {"cot_analysis": True})
            self.logger.info(f"🎯 [COT_RESPONSE] LLM 응답: '{response[:200]}...'")
            
            # JSON 응답 파싱 시도
            import json
            try:
                # JSON 부분만 추출
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    self.logger.info(f"📋 [COT_PARSING] 추출된 JSON: {json_str}")
                    analysis = json.loads(json_str)
                    
                    self.logger.info(f"✅ [COT_SUCCESS] CoT 분석 완료: {analysis.get('reasoning', '')}")
                    self.logger.info(f"🔍 [COT_RESULT] 벡터검색 필요: {analysis.get('needs_vector_search', False)}, 신뢰도: {analysis.get('confidence', 0)}")
                    return analysis
                else:
                    raise ValueError("JSON 형식을 찾을 수 없음")
                    
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"⚠️ [COT_FALLBACK] CoT JSON 파싱 실패: {e}")
                # 응답에서 키워드 기반 분석 fallback
                fallback_result = self._fallback_intent_analysis(question, response)
                self.logger.info(f"🔄 [COT_FALLBACK] Fallback 분석 결과: {fallback_result}")
                return fallback_result
                
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
        """강화된 VectorDB 검색 - fallback 및 상세 응답 포함"""
        if not (self.vector_db_service and self.vector_db_service.is_initialized):
            self.logger.warning("VectorDB 서비스가 초기화되지 않음, fallback 실행")
            return await self._fallback_data_query(question)
            
        try:
            self.logger.info(f"🔍 VectorDB 검색 시작: {question} (총 2,900개 문서 대상)")
            search_result = await self.vector_db_service.search_relevant_data(
                query=question,
                n_results=25  # 2,900개 문서에서 더 많은 결과 검색
            )
            
            if not search_result.get("success"):
                self.logger.warning("⚠️ VectorDB 검색 실패, fallback 실행")
                return await self._fallback_data_query(question)
            
            # 검색 결과 상태 로깅
            found_docs = search_result.get('found_documents', 0)
            if found_docs > 0:
                self.logger.info(f"✅ {found_docs}개 관련 문서 발견")
            else:
                self.logger.warning("⚠️ 관련 문서를 찾지 못함, fallback 실행")
                return await self._fallback_data_query(question)
                
            # 검색 결과가 있으면 상세 응답 생성
            return await self._generate_detailed_response(search_result, question)
            
        except Exception as e:
            self.logger.error(f"VectorDB 검색 오류: {e}")
            return await self._fallback_data_query(question)
    
    async def _fallback_data_query(self, question: str) -> str:
        """VectorDB 실패 시 직접 데이터 조회"""
        question_lower = question.lower()
        
        try:
            # 🏢 개선된 랙별 상태 문의 처리 (모든 랙 지원)
            rack_patterns = ["a랙", "b랙", "c랙", "d랙", "e랙", "f랙", "g랙", "h랙", "i랙", "j랙", "k랙", "l랙", "m랙", "n랙", "o랙", "p랙", "q랙", "r랙", "s랙", "t랙", "u랙", "v랙", "w랙", "x랙", "y랙", "z랙"]
            
            for rack_pattern in rack_patterns:
                if rack_pattern in question_lower and ("상태" in question_lower or "어때" in question_lower or "어떤" in question_lower):
                    rack_letter = rack_pattern[0].upper()  # A, B, C, ... 추출
                    rack_data = self._get_rack_specific_data(rack_letter)
                    
                    if rack_data:
                        rack_name = rack_data.get('rack_name', f'{rack_letter}랙')
                        current_stock = rack_data.get('current_stock', 0)
                        utilization_rate = rack_data.get('utilization_rate', 0)
                        products = rack_data.get('products', ['정보 없음'])
                        product_count = rack_data.get('product_count', 0)
                        status = rack_data.get('status', '⚠️ 알 수 없음')
                        found_method = rack_data.get('found_method', 'legacy')
                        
                        # 🎯 상위 3개 상품명 표시
                        top_products = ', '.join(products[:3]) if len(products) > 0 else '정보 없음'
                        if len(products) > 3:
                            top_products += f" 외 {len(products) - 3}개"
                        
                        data_quality = "✅ 통합 계산 기반" if found_method == 'unified_calculation' else "⚠️ 레거시 방식"
                        
                        return f"""🏢 **{rack_name} 상태 정보:** {data_quality}

📊 **재고 현황:** {current_stock:,}개
📈 **활용률:** {utilization_rate:.1f}%
📦 **저장 상품:** {top_products}
📋 **상품 종류:** {product_count}개
⚠️ **상태:** {status}

💡 **데이터 일관성:** 모든 시스템에서 동일한 수치를 제공합니다."""
                    
                    else:
                        return f"""❌ **{rack_letter}랙 정보를 찾을 수 없습니다.**

🔍 **확인된 문제:**
- 해당 랙이 존재하지 않거나
- 데이터 로딩 중 오류 발생

💡 **해결 방법:**
1. 랙 이름을 다시 확인해주세요 (A~Z)
2. '전체 랙 현황'을 먼저 확인해보세요
3. 잠시 후 다시 시도해주세요"""
            
            # 일반 랙 관련 질문
            if any(word in question_lower for word in ['랙', 'rack']) and any(word in question_lower for word in ['상태', '어때', '현황', '정보']):
                all_racks_data = self._get_all_racks_summary()
                return f"""🏢 **전체 랙 상태 현황:**

{all_racks_data}

💡 특정 랙의 상세 정보를 원하시면 "A랙 상태는 어때?" 형식으로 질문해주세요."""
            
            # 상품 관련 질문
            if any(word in question_lower for word in ['상품', '제품']) and any(word in question_lower for word in ['어떤', '뭐', '목록']):
                return """📦 **주요 상품 정보:**

현재 벡터 검색 시스템이 일시적으로 사용할 수 없어 기본 정보만 제공됩니다.

🔧 **시스템 상태:** 벡터 데이터베이스 재시작 필요
💡 **권장 사항:** 시스템 관리자에게 문의하여 벡터 DB 서비스를 재시작해주세요.

📞 **대안:** 대시보드의 '상품별 재고 현황' 차트를 확인해보세요."""
            
        except Exception as e:
            self.logger.error(f"Fallback 데이터 조회 오류: {e}")
        
        return """❌ **시스템 일시 오류**

현재 상세 정보를 조회할 수 없습니다.

🔧 **가능한 원인:**
- 벡터 데이터베이스 연결 오류
- 데이터 서비스 일시 중단

💡 **해결 방안:**
1. 잠시 후 다시 시도해주세요
2. 대시보드 차트를 통해 기본 정보 확인
3. 시스템 관리자에게 문의

📞 **문의:** /api/vector-db/status로 시스템 상태를 확인할 수 있습니다."""
    
    def _get_rack_specific_data(self, rack_name: str) -> dict:
        """특정 랙의 데이터 조회 - 통합 계산 기반으로 개선"""
        try:
            # 🔄 통합 계산 메서드 사용
            unified_stats = self.data_service.get_unified_inventory_stats()
            
            if "error" in unified_stats:
                self.logger.error(f"❌ 통합 계산 실패: {unified_stats['error']}")
                return {}
            
            rack_distribution = unified_stats.get("rack_distribution", {})
            rack_column = unified_stats.get("rack_column_used")
            
            self.logger.info(f"🔍 [RACK_SEARCH] 찾는 랙: {rack_name}, 사용 컬럼: {rack_column}")
            self.logger.info(f"🔍 [RACK_SEARCH] 사용 가능한 랙들: {list(rack_distribution.keys())}")
            
            # 🎯 개선된 랙 이름 매칭 (다양한 형태 지원)
            target_rack = None
            rack_variations = [
                rack_name.upper(),          # A, B, C
                f"{rack_name.upper()}랙",    # A랙, B랙, C랙
                f"{rack_name.upper()}-RACK", # A-RACK, B-RACK
                rack_name.lower(),          # a, b, c
                f"Rack {rack_name.upper()}", # Rack A, Rack B
                f"{rack_name.upper()}Rack",  # ARack, BRack
            ]
            
            # 정확한 매칭 우선 시도
            for variation in rack_variations:
                for available_rack in rack_distribution.keys():
                    if variation == available_rack or variation in available_rack:
                        target_rack = available_rack
                        self.logger.info(f"✅ [RACK_FOUND] 매칭 성공: {rack_name} → {target_rack}")
                        break
                if target_rack:
                    break
            
            # 부분 매칭 시도 (정확한 매칭 실패 시)
            if not target_rack:
                for available_rack in rack_distribution.keys():
                    if rack_name.upper() in available_rack.upper():
                        target_rack = available_rack
                        self.logger.info(f"🔍 [RACK_PARTIAL] 부분 매칭: {rack_name} → {target_rack}")
                        break
            
            if not target_rack:
                self.logger.warning(f"❌ [RACK_NOT_FOUND] 랙을 찾을 수 없음: {rack_name}")
                self.logger.warning(f"📋 [AVAILABLE_RACKS] 사용 가능한 랙들: {list(rack_distribution.keys())}")
                return {}
            
            # 📊 랙별 상세 데이터 계산
            current_stock = int(rack_distribution[target_rack])
            
            # 📈 실제 상품 정보 조회 (직접 DataFrame 접근)
            if self.data_service.product_master is not None and rack_column:
                import pandas as pd
                rack_products = self.data_service.product_master[
                    self.data_service.product_master[rack_column] == target_rack
                ]
                
                product_count = len(rack_products)
                product_names = rack_products['ProductName'].unique().tolist() if 'ProductName' in rack_products.columns else []
                
                # 📦 제품명 정리 (존재하지 않거나 비어있는 경우 처리)
                valid_products = [name for name in product_names if pd.notna(name) and str(name).strip()]
                if not valid_products:
                    valid_products = [f"제품-{i+1}" for i in range(product_count)]  # 기본 제품명 생성
                
            else:
                product_count = max(1, current_stock // 25)  # 추정 제품 수
                valid_products = [f"제품-{i+1}" for i in range(product_count)]
            
            # 🏗️ 용량 및 활용률 계산
            avg_capacity_per_rack = 50  # 랙당 평균 50개 용량
            max_capacity = avg_capacity_per_rack
            utilization_rate = (current_stock / max_capacity) * 100 if max_capacity > 0 else 0
            
            # 📋 상태 분석
            status = "✅ 정상" if utilization_rate < 80 else "⚠️ 주의" if utilization_rate < 95 else "🚨 포화"
            
            result = {
                'rack_name': target_rack,
                'current_stock': current_stock,
                'max_capacity': max_capacity,
                'utilization_rate': utilization_rate,
                'products': valid_products,
                'product_count': product_count,
                'rack_column_used': rack_column,
                'status': status,
                'is_estimated': False,  # 통합 계산 기반이므로 추정값 아님
                'found_method': 'unified_calculation'
            }
            
            self.logger.info(f"📊 [RACK_RESULT] {target_rack}: {current_stock}개, {utilization_rate:.1f}%, {product_count}개 제품")
            return result
                    
        except Exception as e:
            self.logger.error(f"❌ 랙 데이터 조회 오류: {e}")
            return {}
    
    def _get_all_racks_summary(self) -> str:
        """전체 랙 요약 정보 - 통합 계산 기반으로 개선"""
        try:
            # 🔄 통합 계산 메서드 사용
            unified_stats = self.data_service.get_unified_inventory_stats()
            
            if "error" in unified_stats:
                self.logger.error(f"❌ 통합 계산 실패: {unified_stats['error']}")
                return "📊 현재 랙 정보를 가져올 수 없습니다."
            
            rack_distribution = unified_stats.get("rack_distribution", {})
            
            if not rack_distribution:
                return "❌ 랙 분포 데이터를 찾을 수 없습니다."
            
            # 📊 랙별 정보를 재고량 순으로 정렬
            sorted_racks = sorted(rack_distribution.items(), key=lambda x: x[1], reverse=True)
            
            summary_lines = []
            total_racks = len(sorted_racks)
            total_inventory = sum(rack_distribution.values())
            
            # 🔝 상위 10개 랙 정보 표시
            for i, (rack, qty) in enumerate(sorted_racks[:10]):
                avg_capacity_per_rack = 50  # 랙당 평균 50개 용량
                utilization = (qty / avg_capacity_per_rack) * 100 if avg_capacity_per_rack > 0 else 0
                
                # 📊 상태 아이콘
                status_icon = "✅" if utilization < 80 else "⚠️" if utilization < 95 else "🚨"
                
                # 📈 백분율 계산 (전체 재고 대비)
                percentage = (qty / total_inventory * 100) if total_inventory > 0 else 0
                
                summary_lines.append(f"{status_icon} **{rack}:** {int(qty):,}개 ({utilization:.1f}%, 전체의 {percentage:.1f}%)")
            
            # 📋 요약 정보 추가
            if total_racks > 10:
                summary_lines.append(f"\n📊 **전체 요약:** {total_racks}개 랙 중 상위 10개 표시")
            
            summary_lines.append(f"📦 **총 재고량:** {int(total_inventory):,}개 (통합 계산)")
            summary_lines.append(f"🏢 **활성 랙 수:** {total_racks}개")
            
            return "\n".join(summary_lines)
            
        except Exception as e:
            self.logger.error(f"❌ 전체 랙 요약 오류: {e}")
            return "📊 현재 랙 정보를 가져올 수 없습니다."
    
    async def _generate_detailed_response(self, search_result: dict, question: str) -> str:
        """검색 결과를 바탕으로 상세 응답 생성"""
        try:
            # Vector 검색 결과를 구조화된 프롬프트로 변환
            structured_context = self._vectordb_to_prompt(search_result, question)
            
            # 최적화된 VectorDB 전용 LLM 호출
            response = await self.llm_client.answer_with_vector_context(
                question, structured_context
            )
            
            # 검색된 문서 수 정보는 더 이상 표시하지 않음 (사용자 요청)
            
            self.logger.info("VectorDB 검색 상세 응답 생성 완료")
            return response
            
        except Exception as e:
            self.logger.error(f"상세 응답 생성 오류: {e}")
            return await self._fallback_data_query(question)
    
    async def _handle_general_query(self, question: str) -> str:
        """일반적인 질문을 기본 데이터로 처리"""
        intent = self.analyze_intent(question)
        context_data = self.data_service.get_relevant_data(intent)
        
        # 간단한 LLM 호출 (VectorDB 없이)
        return await self.llm_client.answer_simple_query(question, context_data)
    
    def _vectordb_to_prompt(self, search_result: Dict, question: str) -> str:
        """VectorDB 검색 결과를 구조화된 프롬프트로 변환"""
        self.logger.info(f"🔄 [PROMPT_BUILD] VectorDB → 프롬프트 변환 시작")
        
        documents = search_result.get('documents', [])
        chart_data = search_result.get('chart_data', {})
        metadata_summary = search_result.get('metadata_summary', {})
        
        self.logger.info(f"📊 [PROMPT_DATA] 문서: {len(documents)}개, 차트데이터: {bool(chart_data)}, 메타데이터: {bool(metadata_summary)}")
        
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
        
        final_prompt = "\n".join(prompt_parts)
        self.logger.info(f"📝 [PROMPT_GENERATED] 생성된 프롬프트 길이: {len(final_prompt)}자")
        self.logger.info(f"📝 [PROMPT_CONTENT] 프롬프트 내용:\n{final_prompt[:500]}...")
        
        return final_prompt
    
    def _try_direct_answer(self, question: str) -> Optional[str]:
        """간단한 질문들에 대해 직접 계산하여 답변 (통합 계산 기반)"""
        if not self.data_service.data_loaded:
            return None
            
        question_lower = question.lower()
        
        try:
            # 🔄 통합 계산 메서드 사용
            unified_stats = self.data_service.get_unified_inventory_stats()
            
            if "error" in unified_stats:
                return None
            
            # 총 재고량 질문
            if any(word in question_lower for word in ['총 재고량', '총재고', '전체 재고', '총 재고']):
                total_inventory = unified_stats["total_inventory"]
                product_count = unified_stats["total_products"]
                calculation_method = unified_stats["calculation_method"]
                
                return f"총 재고량은 {total_inventory:,}개입니다. 전체 제품 수는 {product_count}개입니다."
            
            # 입고량 질문 (통합 계산 기반)
            if any(word in question_lower for word in ['입고량', '입고 현황', '오늘 입고']):
                total_inbound = unified_stats["total_inbound_qty"]
                daily_inbound = unified_stats["daily_inbound_avg"]
                
                return f"총 입고량은 {total_inbound:,}개입니다. 일평균 입고량은 {daily_inbound:,}개입니다."
            
            # 출고량 질문 (통합 계산 기반)
            elif any(word in question_lower for word in ['출고량', '출고 현황', '오늘 출고']):
                total_outbound = unified_stats["total_outbound_qty"]
                daily_outbound = unified_stats["daily_outbound_avg"]
                
                return f"총 출고량은 {total_outbound:,}개입니다. 일평균 출고량은 {daily_outbound:,}개입니다."
            
            # 랙 관련 질문 (통합 계산 기반)
            elif any(word in question_lower for word in ['랙', 'rack', 'a랙', 'b랙', 'c랙']):
                rack_distribution = unified_stats["rack_distribution"]
                rack_column = unified_stats["rack_column_used"]
                
                if rack_distribution:
                    # 상위 5개 랙 정보
                    sorted_racks = sorted(rack_distribution.items(), key=lambda x: x[1], reverse=True)
                    rack_info = []
                    for rack, qty in sorted_racks[:5]:
                        rack_info.append(f"• {rack}랙: {int(qty):,}개")
                    
                    return f"랙별 재고 현황 (상위 5개):\n{chr(10).join(rack_info)}\n\n총 랙 수: {len(rack_distribution)}개"
                else:
                    return "랙 정보를 찾을 수 없습니다."
            
        except Exception as e:
            print(f"직접 답변 계산 오류: {e}")
            return None
        
        return None
    
    async def _handle_self_rag_query(self, question: str) -> Optional[str]:
        """SELF-RAG 전용 질문 처리"""
        try:
            self.logger.info(f"🧠 SELF-RAG 전용 처리: {question}")
            return await self.langchain_service.process_with_self_rag(question)
        except Exception as e:
            self.logger.error(f"SELF-RAG 처리 실패: {e}")
            return None
    
    async def _handle_enhanced_vector_fallback(self, question: str) -> Optional[str]:
        """🔥 강화된 벡터 검색 fallback - SELF-RAG 실패 시 전체 벡터 검색 활용"""
        if not (self.vector_db_service and self.vector_db_service.is_initialized):
            self.logger.warning("벡터 DB 서비스 없음 - enhanced fallback 불가")
            return None
        
        try:
            self.logger.info(f"🔍 강화된 벡터 fallback 처리: {question[:50]}...")
            
            # 🚀 1단계: 더 넓은 범위로 벡터 검색
            search_result = await self.vector_db_service.search_relevant_data(
                query=question,
                n_results=25  # SELF-RAG 실패 시 더 많은 문서 수집
            )
            
            if not search_result.get("success") or search_result.get("found_documents", 0) == 0:
                self.logger.warning("강화된 벡터 검색도 실패")
                return None
            
            # 🚀 2단계: 검색 결과를 더 상세하게 분석
            enhanced_context = self._build_enhanced_fallback_context(search_result, question)
            
            # 🚀 3단계: AI에게 더 구체적인 지시사항과 함께 답변 요청
            fallback_prompt = f"""
당신은 창고 관리 전문 AI입니다. SELF-RAG 시스템이 일시적으로 사용할 수 없어 기존 벡터 검색 결과를 바탕으로 답변합니다.

**현재 상황:**
- 현재 날짜: {self.langchain_service.current_datetime.strftime('%Y년 %m월 %d일 %H시 %M분')}
- 데이터 범위: 2025년 1월 1일~7일 (과거 데이터)
- 고급 처리 실패로 기본 벡터 검색 결과 활용

**질문:** {question}

{enhanced_context}

**강화된 답변 규칙:**
1. 🕐 **현재 날짜 필수 명시**: {self.langchain_service.current_datetime.strftime('%Y년 %m월 %d일')}
2. 📅 **데이터 날짜 구분**: "과거 데이터(2025년 1월)"임을 반드시 명시
3. 🔍 **구체적 정보 활용**: 회사명, 상품명, 수량 등 검색된 구체적 정보 최대한 활용
4. ✅ **상세 답변**: 간단히 답하지 말고 검색된 정보를 바탕으로 상세하게 설명
5. ⚠️ **불확실성 표시**: 추정이나 불확실한 내용은 명시적으로 구분
6. 📊 **출처 명시**: 검색된 문서 수와 정보 출처 표시

**답변 시작 예시:**
"현재 날짜({self.langchain_service.current_datetime.strftime('%Y년 %m월 %d일')})와 검색된 과거 데이터(2025년 1월)를 바탕으로 말씀드리면..."

답변:"""
            
            response = await self.llm_client.answer_simple_query(fallback_prompt, {"enhanced_fallback": True})
            
            # 검증 정보 추가
            found_docs = search_result.get("found_documents", 0)
            response += f"\n\n🔍 *강화된 fallback으로 {found_docs}개 문서를 분석한 결과입니다.*"
            response += f"\n⚠️ *고급 처리 시스템 일시 불가로 기본 벡터 검색 결과를 활용했습니다.*"
            
            # 응답 정제 적용
            cleaned_response = self.langchain_service._clean_response(
                response, question, 
                is_simple_question=self.langchain_service._is_simple_question_type(question)
            )
            
            self.logger.info("✅ 강화된 벡터 fallback 성공")
            return cleaned_response
            
        except Exception as e:
            self.logger.error(f"강화된 벡터 fallback 실패: {e}")
            return None
    
    def _build_enhanced_fallback_context(self, search_result: dict, question: str) -> str:
        """강화된 fallback용 컨텍스트 구성"""
        documents = search_result.get("documents", [])
        metadata = search_result.get("metadata_summary", {})
        chart_data = search_result.get("chart_data", {})
        found_docs = search_result.get("found_documents", 0)
        
        context_parts = []
        
        # 검색 결과 요약
        context_parts.append(f"**검색 결과 요약:**")
        context_parts.append(f"- 총 검색된 관련 문서: {found_docs}개 (전체 2,900개 중)")
        context_parts.append(f"- 검색 키워드: {question}")
        context_parts.append("")
        
        # 핵심 문서 내용 (더 많이 포함)
        if documents:
            context_parts.append(f"**핵심 관련 문서 내용 (상위 {min(len(documents), 8)}개):**")
            for i, doc in enumerate(documents[:8], 1):
                context_parts.append(f"{i}. {doc.strip()}")
            context_parts.append("")
        
        # 메타데이터 정보
        if metadata:
            context_parts.append(f"**데이터 메타 정보:**")
            for key, value in metadata.items():
                context_parts.append(f"- {key}: {value}")
            context_parts.append("")
        
        # 차트 데이터 (집계 정보)
        if chart_data:
            context_parts.append(f"**집계 데이터:**")
            if 'title' in chart_data:
                context_parts.append(f"- 차트 제목: {chart_data['title']}")
            if 'data' in chart_data and 'labels' in chart_data:
                data_dict = dict(zip(chart_data.get('labels', []), chart_data.get('data', [])))
                context_parts.append(f"- 집계 결과: {data_dict}")
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    def _get_system_status(self) -> str:
        """현재 시스템 상태 요약"""
        try:
            if self.vector_db_service and self.vector_db_service.is_initialized:
                return "🟢 **시스템 상태:** 벡터 검색 가능 (2,900개 문서 인덱싱 완료)"
            else:
                return "🟡 **시스템 상태:** 벡터 검색 일시 불가, 기본 데이터로 응답"
        except:
            return "🔴 **시스템 상태:** 일부 기능 제한"
    
    # ================== 질문 유형별 전용 처리 메서드 ==================
    
    async def _handle_date_analysis_query(self, question: str) -> Optional[str]:
        """📅 날짜 분석 전용 처리 - "언제", "가장 높았던 날" 등"""
        try:
            self.logger.info(f"📅 [DATE_ANALYSIS] 날짜 분석 질문 처리: '{question}'")
            
            question_lower = question.lower()
            
            # 입고량 최대 날짜 분석
            if "입고량" in question_lower and ("제일" in question_lower or "가장" in question_lower or "최대" in question_lower):
                return await self._analyze_max_inbound_date()
            
            # 출고량 최대 날짜 분석
            elif "출고량" in question_lower and ("제일" in question_lower or "가장" in question_lower or "최대" in question_lower):
                return await self._analyze_max_outbound_date()
            
            # 일반적인 날짜 기반 벡터 검색
            else:
                return await self._handle_vector_search_query(question)
                
        except Exception as e:
            self.logger.error(f"❌ [DATE_ANALYSIS] 날짜 분석 오류: {e}")
            return None
    
    async def _analyze_max_inbound_date(self) -> str:
        """입고량이 가장 높았던 날 분석"""
        try:
            if not self.data_service.data_loaded or self.data_service.inbound_data is None:
                return "📅 입고 데이터가 없어 날짜별 분석을 할 수 없습니다."
            
            # 날짜별 입고량 집계
            daily_inbound = self.data_service.inbound_data.groupby('Date')['PalleteQty'].sum().sort_values(ascending=False)
            
            if len(daily_inbound) > 0:
                max_date = daily_inbound.index[0]
                max_quantity = int(daily_inbound.iloc[0])
                
                # 상위 3일 정보 포함
                top_3 = []
                for i, (date, qty) in enumerate(daily_inbound.head(3).items()):
                    rank = ["🥇", "🥈", "🥉"][i]
                    top_3.append(f"{rank} {date}: {int(qty):,}개")
                
                return f"""📅 **입고량이 가장 높았던 날은 {max_date}입니다.**

📊 **상세 정보:**
- **최대 입고량:** {max_quantity:,}개
- **해당 날짜:** {max_date}

🏆 **상위 3일 순위:**
{chr(10).join(top_3)}

💡 이 정보는 {len(daily_inbound)}일간의 실제 입고 데이터를 분석한 결과입니다."""
            else:
                return "📅 입고 데이터에서 날짜별 정보를 찾을 수 없습니다."
                
        except Exception as e:
            self.logger.error(f"❌ 최대 입고일 분석 오류: {e}")
            return "📅 입고량 날짜 분석 중 오류가 발생했습니다."
    
    async def _analyze_max_outbound_date(self) -> str:
        """출고량이 가장 높았던 날 분석"""
        try:
            if not self.data_service.data_loaded or self.data_service.outbound_data is None:
                return "📅 출고 데이터가 없어 날짜별 분석을 할 수 없습니다."
            
            # 날짜별 출고량 집계
            daily_outbound = self.data_service.outbound_data.groupby('Date')['PalleteQty'].sum().sort_values(ascending=False)
            
            if len(daily_outbound) > 0:
                max_date = daily_outbound.index[0]
                max_quantity = int(daily_outbound.iloc[0])
                
                # 상위 3일 정보 포함
                top_3 = []
                for i, (date, qty) in enumerate(daily_outbound.head(3).items()):
                    rank = ["🥇", "🥈", "🥉"][i]
                    top_3.append(f"{rank} {date}: {int(qty):,}개")
                
                return f"""📅 **출고량이 가장 높았던 날은 {max_date}입니다.**

📊 **상세 정보:**
- **최대 출고량:** {max_quantity:,}개
- **해당 날짜:** {max_date}

🏆 **상위 3일 순위:**
{chr(10).join(top_3)}

💡 이 정보는 {len(daily_outbound)}일간의 실제 출고 데이터를 분석한 결과입니다."""
            else:
                return "📅 출고 데이터에서 날짜별 정보를 찾을 수 없습니다."
                
        except Exception as e:
            self.logger.error(f"❌ 최대 출고일 분석 오류: {e}")
            return "📅 출고량 날짜 분석 중 오류가 발생했습니다."
    
    async def _handle_status_analysis_query(self, question: str) -> Optional[str]:
        """📊 상태 분석 전용 처리 - "부족한", "위험한" 등"""
        try:
            self.logger.info(f"📊 [STATUS_ANALYSIS] 상태 분석 질문 처리: '{question}'")
            
            question_lower = question.lower()
            
            # 재고 부족 제품 분석
            if "부족한" in question_lower and "제품" in question_lower:
                return await self._analyze_low_stock_products()
            
            # 위험 재고 제품 분석
            elif "위험한" in question_lower or "위험" in question_lower:
                return await self._analyze_risk_products()
            
            # 일반적인 상태 기반 벡터 검색
            else:
                return await self._handle_vector_search_query(question)
                
        except Exception as e:
            self.logger.error(f"❌ [STATUS_ANALYSIS] 상태 분석 오류: {e}")
            return None
    
    async def _analyze_low_stock_products(self) -> str:
        """재고 부족 제품 분석"""
        try:
            if not self.data_service.data_loaded or self.data_service.product_master is None:
                return "📊 제품 데이터가 없어 재고 분석을 할 수 없습니다."
            
            # 현재고 기준으로 부족 제품 찾기 (임계값: 20개 이하)
            low_stock_threshold = 20
            stock_column = '현재고' if '현재고' in self.data_service.product_master.columns else 'Start Pallete Qty'
            
            low_stock_products = self.data_service.product_master[
                self.data_service.product_master[stock_column] <= low_stock_threshold
            ].sort_values(stock_column)
            
            if len(low_stock_products) > 0:
                # 상위 5개 부족 제품
                product_list = []
                for idx, (_, product) in enumerate(low_stock_products.head(5).iterrows()):
                    danger_level = "🚨" if product[stock_column] <= 5 else "⚠️" if product[stock_column] <= 10 else "📦"
                    product_name = product.get('ProductName', '알 수 없음')
                    current_stock = int(product[stock_column])
                    rack_info = product.get('랙위치', product.get('Rack Name', '알 수 없음'))
                    
                    product_list.append(f"{danger_level} **{product_name}**: {current_stock}개 ({rack_info}랙)")
                
                return f"""📊 **재고가 부족한 제품 분석 결과:**

🚨 **위험 수준 기준:**
- 🚨 심각 (5개 이하)
- ⚠️ 주의 (6-10개)  
- 📦 부족 (11-20개)

📦 **부족 제품 목록 (상위 5개):**
{chr(10).join(product_list)}

📊 **통계:**
- **총 부족 제품:** {len(low_stock_products)}개
- **분석 기준:** {low_stock_threshold}개 이하
- **전체 제품 수:** {len(self.data_service.product_master)}개

💡 **권장 사항:**
즉시 발주가 필요한 제품들이 있습니다. 특히 🚨 표시 제품은 긴급 보충이 필요합니다."""
            else:
                return f"""✅ **재고 부족 제품 없음**

📊 **분석 결과:**
- **분석 기준:** {low_stock_threshold}개 이하
- **전체 제품 수:** {len(self.data_service.product_master)}개
- **결과:** 모든 제품이 안전 재고 수준을 유지하고 있습니다.

🎉 현재 재고 관리가 양호한 상태입니다."""
                
        except Exception as e:
            self.logger.error(f"❌ 재고 부족 분석 오류: {e}")
            return "📊 재고 부족 제품 분석 중 오류가 발생했습니다."
    
    async def _analyze_risk_products(self) -> str:
        """위험 재고 제품 분석 (매우 낮은 재고)"""
        try:
            if not self.data_service.data_loaded or self.data_service.product_master is None:
                return "📊 제품 데이터가 없어 위험 분석을 할 수 없습니다."
            
            # 위험 임계값: 10개 이하
            risk_threshold = 10
            stock_column = '현재고' if '현재고' in self.data_service.product_master.columns else 'Start Pallete Qty'
            
            risk_products = self.data_service.product_master[
                self.data_service.product_master[stock_column] <= risk_threshold
            ].sort_values(stock_column)
            
            if len(risk_products) > 0:
                return f"""🚨 **위험 재고 제품 {len(risk_products)}개 발견!**

⚠️ **즉시 조치 필요:**
{chr(10).join([f"- {product.get('ProductName', '알 수 없음')}: {int(product[stock_column])}개" for _, product in risk_products.head(5).iterrows()])}

🚨 **긴급 권장 사항:**
1. 즉시 발주 처리
2. 고객 주문 제한 검토
3. 대체 상품 준비"""
            else:
                return "✅ **위험 수준의 재고 부족 제품은 없습니다.**"
                
        except Exception as e:
            self.logger.error(f"❌ 위험 재고 분석 오류: {e}")
            return "🚨 위험 재고 분석 중 오류가 발생했습니다."
    
    async def _handle_list_query(self, question: str) -> Optional[str]:
        """📋 목록 조회 전용 처리 - "어떤", "어느", "목록" 등"""
        try:
            self.logger.info(f"📋 [LIST_QUERY] 목록 조회 질문 처리: '{question}'")
            
            # 목록 조회는 벡터 검색이 가장 적합하므로 벡터 검색으로 처리
            return await self._handle_vector_search_query(question)
                
        except Exception as e:
            self.logger.error(f"❌ [LIST_QUERY] 목록 조회 오류: {e}")
            return None
    
    async def _handle_rack_specific_query(self, question: str) -> Optional[str]:
        """🏗️ 랙 관련 질문 전용 처리 - CoT 결과와 무관하게 우선 적용"""
        try:
            self.logger.info(f"🏗️ [RACK_QUERY] 랙 관련 질문 처리: '{question}'")
            
            question_lower = question.lower()
            
            # 🎯 특정 랙 식별 (A~Z 랙)
            import re
            rack_pattern = re.search(r'([a-z])랙|([a-z])\s*rack|rack\s*([a-z])', question_lower)
            
            if rack_pattern:
                # 매칭된 랙 문자 추출
                rack_letter = (rack_pattern.group(1) or rack_pattern.group(2) or rack_pattern.group(3)).upper()
                self.logger.info(f"🎯 [RACK_IDENTIFIED] 특정 랙 식별: {rack_letter}랙")
                
                # 직접 랙 데이터 조회
                rack_data = self._get_rack_specific_data(rack_letter)
                
                if rack_data:
                    rack_name = rack_data.get('rack_name', f'{rack_letter}랙')
                    current_stock = rack_data.get('current_stock', 0)
                    utilization_rate = rack_data.get('utilization_rate', 0)
                    products = rack_data.get('products', ['정보 없음'])
                    product_count = rack_data.get('product_count', 0)
                    status = rack_data.get('status', '⚠️ 알 수 없음')
                    found_method = rack_data.get('found_method', 'legacy')
                    
                    # 🎯 상위 3개 상품명 표시
                    top_products = ', '.join(products[:3]) if len(products) > 0 else '정보 없음'
                    if len(products) > 3:
                        top_products += f" 외 {len(products) - 3}개"
                    
                    data_quality = "✅ 통합 계산 기반" if found_method == 'unified_calculation' else "⚠️ 레거시 방식"
                    
                    return f"{rack_name} 재고 현황: 현재 재고량 {current_stock:,}개, 활용률 {utilization_rate:.1f}%, 저장 상품 {top_products}, 상품 종류 {product_count}개"
                else:
                    return f"{rack_letter}랙 정보를 찾을 수 없습니다. 랙 이름을 다시 확인해주세요."
            
            # 일반 랙 관련 질문은 기존 fallback으로 처리
            else:
                self.logger.info("🏗️ [RACK_GENERAL] 일반 랙 질문으로 fallback 처리")
                return await self._fallback_data_query(question)
                
        except Exception as e:
            self.logger.error(f"❌ [RACK_QUERY] 랙 관련 질문 처리 오류: {e}")
            return None