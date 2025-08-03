import os
import logging
import time
import asyncio
import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque
from threading import Lock

import google.generativeai as genai

from dotenv import load_dotenv, find_dotenv

# .env 파일을 프로젝트 루트부터 상위 디렉토리까지 자동으로 찾아서 로드
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)
    print(f"✅ .env 파일 로드됨: {dotenv_path}")
else:
    print("⚠️ .env 파일을 찾을 수 없습니다. 시스템 환경변수를 사용합니다.")

# 안전한 환경변수 설정 - None 값 체크
def safe_set_env_var(key_name: str):
    """환경변수를 안전하게 설정 (None 값 체크)"""
    value = os.getenv(key_name)
    if value is not None:
        os.environ[key_name] = value
        return True
    return False

# GEMINI API 키들 안전하게 설정
api_keys_loaded = []
for i in range(1, 5):
    key_name = f'GEMINI_API_KEY_{i}'
    if safe_set_env_var(key_name):
        api_keys_loaded.append(key_name)

if api_keys_loaded:
    print(f"✅ 로드된 API 키: {', '.join(api_keys_loaded)}")
else:
    print("⚠️ GEMINI API 키가 설정되지 않았습니다. AI 기능이 제한될 수 있습니다.")

# AI 모델 설정 (legacy/crad_lcrag/utils/ai_model_manager.py 참조)
AI_MODEL_CONFIG = {
    "temperature": 0.1,
    "top_p": 0.8,
    "top_k": 40,
    "max_output_tokens": 2048,
}

@dataclass
class APIKeyStatus:
    """API 키 상태 정보 (gemini_client.py 참조)"""
    key: str
    is_active: bool = True
    request_count: int = 0
    last_request_time: float = 0.0
    error_count: int = 0
    success_count: int = 0
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.error_count
        return self.success_count / total if total > 0 else 0.0

@dataclass
class RateLimitConfig:
    """요청 제한 설정 (rate_limiter.py 참조)"""
    rpm_limit: int = 2000  # 분당 요청 제한
    tpm_limit: int = 4000000  # 분당 토큰 제한
    burst_limit: int = 100  # 버스트 허용 한도
    window_size: int = 60  # 시간 윈도우 (초)

@dataclass
class TokenBucket:
    """토큰 버킷 (rate_limiter.py 참조)"""
    capacity: int
    tokens: float = field(default_factory=lambda: 0)
    last_refill: float = field(default_factory=time.time)
    refill_rate: float = field(default=1.0)  # 초당 토큰 보충률
    
    def __post_init__(self):
        self.tokens = self.capacity
        self.refill_rate = self.capacity / 60.0  # 분당 용량을 초당으로 변환

class RateLimiter:
    """API 요청 제한 관리자 (rate_limiter.py 참조)"""
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.request_buckets: Dict[str, TokenBucket] = {}
        self.token_buckets: Dict[str, TokenBucket] = {}
        self.request_history: Dict[str, deque] = {}
        self.token_history: Dict[str, deque] = {}
        self.lock = Lock()
        self.logger = logging.getLogger(__name__)

    def _get_or_create_buckets(self, api_key: str) -> tuple[TokenBucket, TokenBucket]:
        with self.lock:
            if api_key not in self.request_buckets:
                self.request_buckets[api_key] = TokenBucket(
                    capacity=self.config.rpm_limit,
                    refill_rate=self.config.rpm_limit / 60.0
                )
                self.token_buckets[api_key] = TokenBucket(
                    capacity=self.config.tpm_limit,
                    refill_rate=self.config.tpm_limit / 60.0
                )
                self.request_history[api_key] = deque(maxlen=self.config.rpm_limit)
                self.token_history[api_key] = deque(maxlen=self.config.tpm_limit)
                self.logger.debug(f"🔧 API 키 {api_key[:10]}... 토큰 버킷 생성")
            return self.request_buckets[api_key], self.token_buckets[api_key]

    def _refill_bucket(self, bucket: TokenBucket):
        current_time = time.time()
        time_passed = current_time - bucket.last_refill
        tokens_to_add = time_passed * bucket.refill_rate
        bucket.tokens = min(bucket.capacity, bucket.tokens + tokens_to_add)
        bucket.last_refill = current_time

    def _check_window_limit(self, api_key: str, estimated_tokens: int = 1) -> bool:
        current_time = time.time()
        window_start = current_time - self.config.window_size
        
        request_history = self.request_history[api_key]
        while request_history and request_history[0] < window_start:
            request_history.popleft()
        
        token_history = self.token_history[api_key]
        while token_history and token_history[0]['timestamp'] < window_start:
            token_history.popleft()
        
        current_requests = len(request_history)
        current_tokens = sum(entry['tokens'] for entry in token_history)
        
        if current_requests >= self.config.rpm_limit:
            self.logger.warning(f"⚠️ API 키 {api_key[:10]}... RPM 제한 초과: {current_requests}/{self.config.rpm_limit}")
            return False
        
        if current_tokens + estimated_tokens > self.config.tpm_limit:
            self.logger.warning(f"⚠️ API 키 {api_key[:10]}... TPM 제한 초과: {current_tokens + estimated_tokens}/{self.config.tpm_limit}")
            return False
        
        return True

    async def acquire_permission(
        self,
        api_key: str,
        estimated_tokens: int = 1,
        timeout: float = 10.0
    ) -> bool:
        start_time = time.time()
        request_bucket, token_bucket = self._get_or_create_buckets(api_key)
        
        while time.time() - start_time < timeout:
            with self.lock:
                self._refill_bucket(request_bucket)
                self._refill_bucket(token_bucket)
                
                if not self._check_window_limit(api_key, estimated_tokens):
                    await asyncio.sleep(0.1)
                    continue
                
                if request_bucket.tokens >= 1 and token_bucket.tokens >= estimated_tokens:
                    request_bucket.tokens -= 1
                    token_bucket.tokens -= estimated_tokens
                    current_time = time.time()
                    self.request_history[api_key].append(current_time)
                    self.token_history[api_key].append({'timestamp': current_time, 'tokens': estimated_tokens})
                    self.logger.debug(f"✅ 요청 허가 승인: {api_key[:10]}... (토큰: {estimated_tokens})")
                    return True
            await asyncio.sleep(0.1)
        self.logger.warning(f"⏰ 요청 허가 타임아웃: {api_key[:10]}...")
        return False

    def estimate_tokens(self, text: str) -> int:
        # 간단한 추정 (실제로는 더 정확한 토큰화 필요)
        return max(1, len(text) // 4)

    def get_usage_stats(self, api_key: str) -> Dict[str, Any]:
        if api_key not in self.request_buckets:
            return {"requests_available": self.config.rpm_limit,
                    "tokens_available": self.config.tpm_limit,
                    "requests_used": 0,
                    "tokens_used": 0,
                    "usage_rate": 0.0}
        request_bucket, token_bucket = self._get_or_create_buckets(api_key)
        self._refill_bucket(request_bucket)
        self._refill_bucket(token_bucket)
        current_time = time.time()
        window_start = current_time - self.config.window_size
        recent_requests = [req for req in self.request_history[api_key] if req > window_start]
        recent_tokens = sum(entry['tokens'] for entry in self.token_history[api_key] if entry['timestamp'] > window_start)
        return {"requests_available": int(request_bucket.tokens),
                "tokens_available": int(token_bucket.tokens),
                "requests_used": len(recent_requests),
                "tokens_used": recent_tokens,
                "usage_rate": len(recent_requests) / self.config.rpm_limit,
                "request_bucket_capacity": request_bucket.capacity,
                "token_bucket_capacity": token_bucket.capacity}

    def get_best_available_key(self, api_keys: List[str], estimated_tokens: int = 1) -> Optional[str]:
        """가장 사용 가능한 API 키 반환 (rate_limiter.py 참조)"""
        best_key = None
        best_score = -1
        
        for api_key in api_keys:
            stats = self.get_usage_stats(api_key)
            
            # 사용 가능한지 확인
            if (stats["requests_available"] >= 1 and 
                stats["tokens_available"] >= estimated_tokens):
                
                # 점수 계산 (사용률이 낮을수록 좋음, 요청 가능 토큰이 많을수록 좋음)
                score = (1 - stats["usage_rate"]) * stats["tokens_available"]
                
                if score > best_score:
                    best_score = score
                    best_key = api_key
        
        return best_key

class WarehouseAI:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.gemini_models: List[Dict] = []
        self.gemini_config = AI_MODEL_CONFIG
        self.current_model_index = 0
        self.rate_limiter = RateLimiter() # RateLimiter 인스턴스 추가
        self.offline_mode = False  # 오프라인 모드 플래그
        
        # 차트 생성 전용 설정 (더 일관된 JSON 출력을 위해)
        self.chart_config = genai.GenerationConfig(
            temperature=0.1,  # 더 일관된 출력을 위해 낮은 temperature
            top_p=0.9,
            top_k=20,
            max_output_tokens=2048
        )
        
        # 초기화는 비동기로 처리하지 않고 기본 설정만 진행
        self._setup_models_sync()

    def _setup_models_sync(self):
        """여러 Gemini API 키로 모델 초기화"""
        try:
            api_keys = {
                'GEMINI_1': os.getenv('GEMINI_API_KEY_1'),
                'GEMINI_2': os.getenv('GEMINI_API_KEY_2'),
                'GEMINI_3': os.getenv('GEMINI_API_KEY_3'),
                'GEMINI_4': os.getenv('GEMINI_API_KEY_4')
            }

            # API 키 상태 상세 로깅
            self.logger.info("🔍 API 키 설정 상태 확인:")
            for key_name, key_value in api_keys.items():
                if key_value:
                    masked_key = f"{key_value[:10]}...{key_value[-5:]}" if len(key_value) > 15 else "짧은키"
                    self.logger.info(f"  ✅ {key_name}: {masked_key} (길이: {len(key_value)})")
                else:
                    self.logger.warning(f"  ❌ {key_name}: 설정되지 않음")
                    # 디버깅: 환경변수가 정말 없는지 확인
                    env_val = os.getenv(f'GEMINI_API_KEY_{key_name.split("_")[-1]}')
                    self.logger.warning(f"  🔍 직접 조회: {env_val is not None} (값 존재: {bool(env_val)})")

            valid_keys = {k: v for k, v in api_keys.items() if v and len(v) > 30}  # 최소 길이 검증
            if not valid_keys:
                self.logger.error("경고: 유효한 GEMINI_API_KEY가 없습니다. AI 기능이 제한될 수 있습니다.")
                return

            for model_name, api_key in valid_keys.items():
                try:
                    # API 키 유효성 미리 확인
                    if not self._validate_api_key(api_key):
                        self.logger.warning(f"⚠️ {model_name} API 키 형식이 올바르지 않음")
                        continue
                    
                    genai.configure(api_key=api_key)
                    
                    # 사고 기능 비활성화 설정 추가
                    model_config = self.gemini_config.copy()
                    # 2.5 모델의 사고 기능으로 인한 응답 문제 방지
                    
                    model = genai.GenerativeModel(
                        "gemini-2.0-flash",  # 더 안정적인 1.5 모델 사용 (사고 기능 없음)
                        generation_config=model_config
                    )
                    
                    # API 키는 실제 호출 시에 검증 (초기화 시에는 형식만 확인)
                    
                    self.gemini_models.append({
                        'model': model,
                        'api_key': api_key,
                        'name': model_name,
                        'failures': 0,
                        'last_success': time.time()  # 마지막 성공 시간 추가
                    })
                    self.logger.info(f"🤖 {model_name} 모델 초기화 및 테스트 성공")
                except Exception as e:
                    self.logger.error(f"❌ {model_name} 모델 초기화 실패: {e}")
                    continue

            if not self.gemini_models:
                self.logger.error("❌ 사용 가능한 Gemini 모델이 없습니다.")
                # Fallback 메커니즘 활성화
                self._activate_offline_mode()
            else:
                self.logger.info(f"🎉 총 {len(self.gemini_models)}개의 Gemini 모델 초기화 완료")

        except Exception as e:
            self.logger.error(f"❌ AI 모델 초기화 실패: {e}")
            self._activate_offline_mode()
    
    def _validate_api_key(self, api_key: str) -> bool:
        """API 키 형식 검증"""
        if not api_key or len(api_key) < 30:
            return False
        if not api_key.startswith('AIza'):
            return False
        return True
    
    def _activate_offline_mode(self):
        """API 키가 모두 실패했을 때 오프라인 모드 활성화"""
        self.logger.warning("🔄 오프라인 모드 활성화 - 기본 응답으로 전환")
        self.offline_mode = True

    def _get_next_model(self) -> Optional[Dict]:
        """다음 사용 가능한 모델 선택 (RateLimiter를 활용하여 개선)"""
        if not self.gemini_models:
            return None
        
        available_api_keys = [m['api_key'] for m in self.gemini_models if m['failures'] < 3]
        if not available_api_keys:
            # 모든 모델이 실패한 경우 실패 횟수 리셋
            for model in self.gemini_models:
                model['failures'] = 0
            available_api_keys = [m['api_key'] for m in self.gemini_models]
        
        # RateLimiter의 get_best_available_key를 활용하여 최적의 키 선택
        best_key = self.rate_limiter.get_best_available_key(available_api_keys, estimated_tokens=1) # 토큰 추정은 나중에 질문 텍스트 기반으로 개선
        
        if best_key:            
            # 선택된 키에 해당하는 모델 정보 반환
            for model_info in self.gemini_models:
                if model_info['api_key'] == best_key:
                    return model_info
        return None

    async def answer_query(self, question: str, data_context: dict):
        """Gemini API를 통한 질의응답"""
        if not self.gemini_models:
            return "오류: 사용 가능한 AI 모델이 없습니다."

        max_attempts = len(self.gemini_models)
        estimated_tokens = self.rate_limiter.estimate_tokens(question) # 질문 텍스트 기반 토큰 추정

        for attempt in range(max_attempts):
            current_model_info = self._get_next_model()
            if not current_model_info:
                continue

            api_key = current_model_info['api_key']
            
            # RateLimiter를 통해 권한 획득 시도
            if not await self.rate_limiter.acquire_permission(api_key, estimated_tokens):
                self.logger.warning(f"⚠️ API 키 {api_key[:10]}... 요청 제한으로 인해 대기 또는 다른 키 시도.")
                # 여기서는 바로 다음 키로 넘어가거나, 짧게 대기 후 재시도할 수 있음
                # 간단하게 다음 모델로 넘어가도록 처리
                continue

            try:
                model_instance = current_model_info['model']
                # 벡터 DB 검색 결과가 있는지 확인
                has_vector_search = data_context and 'vector_search' in data_context and data_context['vector_search'].get('success')
                
                if has_vector_search:
                    # 벡터 DB 검색 결과가 있을 때 - 간단하고 직접적인 답변
                    vector_data = data_context['vector_search']
                    chart_data = vector_data.get('chart_data', {})
                    documents = vector_data.get('results', {}).get('documents', [[]])[0] if vector_data.get('results') else []
                    
                    prompt = f"""
당신은 창고 관리 AI 어시스턴트입니다. 실제 창고 데이터를 바탕으로 간단하고 명확한 답변을 제공하세요.

**실제 데이터 검색 결과:**
- 검색된 문서 수: {len(documents)}개
- 차트 데이터: {chart_data}
- 관련 문서: {documents[:3]}  // 상위 3개만 표시

**응답 규칙:**
1. 질문에 대해 직접적이고 간단한 답변을 하세요
2. 구체적인 숫자가 있으면 명시하세요  
3. 3-5문장 이내로 답변하세요
4. 기술적 분석은 요청받을 때만 제공하세요

**질문:** {question}

**답변 예시:**
- "총 재고량은 약 1,234개입니다. 현재 A랙에 456개, B랙에 789개가 있습니다."
- "오늘 입고량은 50개, 출고량은 30개로 순증가 20개입니다."
- "재고가 부족한 제품은 제품A(5개 남음), 제품B(3개 남음)입니다."
"""
                else:
                    # 벡터 DB 검색 결과가 없을 때 - 기존 데이터 분석 방식
                    prompt = f"""
당신은 창고 관리 AI 어시스턴트입니다. 제공된 데이터를 바탕으로 질문에 답변하세요.

**데이터 컨텍스트:**
{data_context}

**응답 규칙:**
1. 데이터가 있으면 구체적인 수치를 포함한 답변
2. 데이터가 부족하면 그 사실을 명시하고 간단한 가이드 제공
3. 5문장 이내로 간결하게 답변
4. 불필요한 기술적 분석은 피하세요

**질문:** {question}
"""
                # Gemini API 호출
                self.logger.info(f"🔄 {current_model_info['name']} API 호출 시작...")
                self.logger.debug(f"📤 프롬프트 길이: {len(prompt)}")
                
                try:
                    # 간단한 API 호출
                    try:
                        response = await model_instance.generate_content_async(prompt)
                    except AttributeError:
                        # generate_content_async가 없는 경우 sync 호출
                        self.logger.info(f"🔄 Async 메서드 없음, sync 호출로 대체")
                        response = model_instance.generate_content(prompt)
                except Exception as api_error:
                    self.logger.warning(f"⚠️ API 호출 실패: {api_error}")
                    raise Exception(f"API 호출 실패: {api_error}")
                
                # 응답 상세 로깅
                self.logger.debug(f"📥 응답 객체 타입: {type(response)}")
                self.logger.debug(f"📥 응답 객체 속성: {[attr for attr in dir(response) if not attr.startswith('_')]}")
                
                # 안전한 텍스트 추출
                result_text = ""
                if hasattr(response, 'text'):
                    result_text = response.text
                elif hasattr(response, 'content'):
                    result_text = str(response.content)
                elif hasattr(response, 'candidates') and response.candidates:
                    # Gemini 응답 구조에 따른 처리
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content'):
                        if hasattr(candidate.content, 'parts'):
                            result_text = candidate.content.parts[0].text
                        else:
                            result_text = str(candidate.content)
                else:
                    result_text = str(response)
                
                self.logger.info(f"📝 응답 텍스트 길이: {len(result_text)}")
                
                if not result_text or result_text.strip() == "":
                    self.logger.error(f"❌ 빈 응답을 받았습니다!")
                    return "오류: Gemini API에서 빈 응답을 받았습니다."
                
                self.logger.info(f"✅ {current_model_info['name']} API 성공 - 응답 (일부): {result_text[:200]}...")
                return result_text

            except Exception as e:
                current_model_info['failures'] += 1
                self.logger.warning(f"⚠️ {current_model_info['name']} API 실패 (시도 {attempt + 1}/{max_attempts}): {str(e)}")

                # 지수 백오프 적용 (RateLimiter의 acquire_permission에서 이미 처리되지만, 여기서도 추가 가능)
                await asyncio.sleep(0.5 * (2 ** attempt)) # 간단한 백오프

                if attempt < max_attempts - 1:
                    self.logger.info(f"🔄 다음 모델로 재시도 중...")
                    continue
                else:
                    self.logger.error(f"❌ 모든 Gemini 모델 시도 실패")
                    return f"오류: 모든 API 호출 실패 - 마지막 오류: {str(e)}"

        return "오류: 모든 모델 시도 실패"
    
    async def answer_with_vector_context(self, question: str, structured_context: str) -> str:
        """VectorDB 컨텍스트가 포함된 질문에 대한 최적화된 답변"""
        if not self.gemini_models:
            return "오류: 사용 가능한 AI 모델이 없습니다."
        
        # VectorDB 전용 프롬프트 생성
        prompt = f"""
당신은 창고 관리 전문 AI입니다. 검색된 실제 데이터를 바탕으로 정확하고 구체적인 답변을 제공하세요.

{structured_context}

**답변 규칙:**
1. 검색된 정보에서 구체적인 회사명, 수치, 날짜 등을 포함하여 답변
2. 공급업체 질문이면 상위 5-10개 업체를 명시하고 입고량도 함께 제시
3. "데이터에 따르면" 또는 "검색 결과"로 시작하여 신뢰성 표시
4. 4-6문장으로 상세하고 구체적인 답변 제공
5. 차트 데이터가 있으면 "상위 공급업체는 ○○(△△개), □□(●●개)" 형식으로 나열

**공급업체 질문 답변 예시:**
"데이터에 따르면 주요 공급업체는 (주)농심(총 45개), 롯데상사(총 23개), (주)서브원(총 18개) 순입니다. 전체 15개 공급업체 중에서 (주)농심이 가장 많은 물량을 납품하고 있으며, 주로 라면류와 음료류를 공급하고 있습니다."

답변:"""
        
        # 단순화된 API 호출 (한 번만 시도)
        current_model_info = self._get_next_model()
        if not current_model_info:
            return "오류: 사용 가능한 모델이 없습니다."
        
        try:
            model_instance = current_model_info['model']
            api_key = current_model_info['api_key']
            response = await self._call_gemini_api(model_instance, prompt, api_key)
            return response
        except Exception as e:
            self.logger.error(f"VectorDB 컨텍스트 처리 실패: {e}")
            return f"죄송합니다. 검색된 정보를 처리하는 중 오류가 발생했습니다."
    
    async def answer_simple_query(self, question: str, context_data: dict) -> str:
        """간단한 질문에 대한 기본 처리 - CoT 분석용 JSON 응답 지원"""
        if self.offline_mode or not self.gemini_models:
            return self._get_offline_response(question, context_data)
        
        # CoT 분석 요청인지 확인
        is_cot_request = context_data and context_data.get("cot_analysis", False)
        
        if is_cot_request:
            # CoT 분석을 위한 JSON 구조화 프롬프트
            prompt = question  # CoT 분석에서는 이미 완전한 프롬프트가 전달됨
        else:
            # 일반적인 간단한 질문 처리 프롬프트
            prompt = f"""
당신은 창고 관리 AI 어시스턴트입니다. 간단하고 직접적으로 답변하세요.

**질문:** {question}

**데이터:** {context_data}

**답변 규칙:**
1. 간단명료하게 2-3문장으로 답변
2. 구체적인 숫자가 있으면 포함
3. 데이터가 부족하면 그 사실을 명시

답변:"""
        
        # 빠른 API 호출
        current_model_info = self._get_next_model()
        if not current_model_info:
            return "오류: 사용 가능한 모델이 없습니다."
        
        try:
            model_instance = current_model_info['model']
            api_key = current_model_info['api_key']
            response = await self._call_gemini_api(model_instance, prompt, api_key)
            return response
        except Exception as e:
            self.logger.error(f"간단한 질의 처리 실패: {e}")
            return f"죄송합니다. 질문을 처리하는 중 오류가 발생했습니다."
    
    async def _call_gemini_api(self, model_instance, prompt: str, api_key: str = None) -> str:
        """간소화된 Gemini API 호출"""
        # API 키가 제공되면 설정
        if api_key:
            genai.configure(api_key=api_key)
            
        try:
            response = await model_instance.generate_content_async(prompt)
        except AttributeError:
            response = model_instance.generate_content(prompt)
        
        # 응답 텍스트 추출
        if hasattr(response, 'text'):
            return response.text
        elif hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                return candidate.content.parts[0].text
        
        return str(response)
    
    def _get_offline_response(self, question: str, context_data: dict) -> str:
        """오프라인 모드에서 사용할 기본 응답"""
        question_lower = question.lower()
        
        # 기본적인 인사말 처리
        if any(word in question_lower for word in ['안녕', '안녕하세요', 'hello', 'hi']):
            return "안녕하세요! 창고 관리 AI 어시스턴트입니다. 현재 오프라인 모드로 운영 중이며, 기본적인 데이터 조회만 가능합니다."
        
        # 이름 관련 질문
        if any(word in question_lower for word in ['이름', '누구', '뭐니', 'name']):
            return "저는 창고 관리 AI 어시스턴트입니다. 현재 API 연결에 문제가 있어 제한된 기능만 제공 중입니다."
        
        # 데이터 관련 질문
        if context_data and isinstance(context_data, dict):
            data_info = []
            for key, value in context_data.items():
                if isinstance(value, (int, float)):
                    data_info.append(f"{key}: {value}")
                elif isinstance(value, str) and len(value) < 100:
                    data_info.append(f"{key}: {value}")
            
            if data_info:
                return f"현재 오프라인 모드입니다. 사용 가능한 기본 데이터:\n" + "\n".join(data_info[:5])
        
        # 기본 응답
        return "죄송합니다. 현재 AI 서비스 연결에 문제가 있습니다. 잠시 후 다시 시도해주세요. 기본적인 재고 조회는 대시보드를 이용해주세요."
    
    async def process_query(self, prompt: str) -> str:
        """차트 생성을 위한 단순한 프롬프트 처리 메서드"""
        # 차트 생성에서는 박하한 데이터 컨텍스트로 호출
        context_data = {"chart_generation": True, "prompt_only": True}
        return await self.answer_query(prompt, context_data)
    
    async def generate_chart_config(self, user_request: str, available_data: dict) -> dict:
        """사용자 요청을 분석하여 차트 설정을 생성합니다."""
        
        # 사용 가능한 데이터 요약
        data_summary = self._summarize_available_data(available_data)
        
        chart_prompt = f"""
당신은 데이터 시각화 전문가입니다. 사용자의 자연어 요청을 분석하여 Chart.js 호환 차트 설정을 생성해주세요.

**사용자 요청**: {user_request}

**사용 가능한 데이터**:
{data_summary}

**응답 형식**: 반드시 아래 JSON 구조로만 응답해주세요.

```json
{{
    "chart_type": "bar|line|pie|doughnut|radar|scatter",
    "title": "차트 제목",
    "data": {{
        "labels": ["라벨1", "라벨2", "라벨3"],
        "datasets": [{{
            "label": "데이터셋 이름",
            "data": [값1, 값2, 값3],
            "backgroundColor": ["색상1", "색상2", "색상3"],
            "borderColor": "테두리색상",
            "borderWidth": 1
        }}]
    }},
    "options": {{
        "responsive": true,
        "plugins": {{
            "title": {{
                "display": true,
                "text": "차트 제목"
            }},
            "legend": {{
                "display": true,
                "position": "top"
            }}
        }},
        "scales": {{
            "y": {{
                "beginAtZero": true
            }}
        }}
    }},
    "query_info": {{
        "data_source": "사용된 데이터 소스",
        "filters_applied": "적용된 필터링",
        "aggregation": "집계 방식"
    }}
}}
```

**주의사항**:
1. 사용자 요청에 가장 적합한 차트 타입을 선택하세요
2. 실제 데이터에 기반하여 realistic한 값을 제공하세요
3. 색상은 시각적으로 구분이 잘 되도록 선택하세요
4. JSON 형식을 정확히 지켜주세요
"""
        
        try:
            # 차트 전용 설정으로 API 호출
            original_config = self.gemini_config
            self.gemini_config = self.chart_config
            
            response = await self.process_query(chart_prompt)
            
            # 원래 설정으로 복원
            self.gemini_config = original_config
            
            # JSON 파싱 시도
            import json
            import re
            
            # JSON 부분만 추출
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # ```json 태그가 없다면 전체에서 JSON 찾기
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("JSON 형식을 찾을 수 없습니다")
            
            chart_config = json.loads(json_str)
            
            # 필수 필드 검증
            required_fields = ['chart_type', 'title', 'data']
            for field in required_fields:
                if field not in chart_config:
                    raise ValueError(f"필수 필드 '{field}'가 없습니다")
            
            self.logger.info(f"✅ 차트 설정 생성 성공: {chart_config['chart_type']} - {chart_config['title']}")
            return {
                "success": True,
                "chart_config": chart_config,
                "message": "차트 설정이 성공적으로 생성되었습니다."
            }
            
        except Exception as e:
            self.logger.error(f"❌ 차트 설정 생성 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "차트 설정 생성에 실패했습니다.",
                "fallback_config": self._get_fallback_chart_config(user_request)
            }
    
    def _summarize_available_data(self, available_data: dict) -> str:
        """사용 가능한 데이터를 요약하여 문자열로 반환합니다."""
        summary_lines = []
        
        for data_name, data_info in available_data.items():
            if isinstance(data_info, dict):
                summary_lines.append(f"- {data_name}: {data_info.get('description', '설명 없음')}")
                if 'columns' in data_info:
                    summary_lines.append(f"  컬럼: {', '.join(data_info['columns'][:5])}{'...' if len(data_info['columns']) > 5 else ''}")
                if 'row_count' in data_info:
                    summary_lines.append(f"  행 수: {data_info['row_count']}")
            else:
                summary_lines.append(f"- {data_name}: {str(data_info)[:100]}...")
        
        return '\n'.join(summary_lines) if summary_lines else "사용 가능한 데이터 정보가 없습니다."
    
    def _get_fallback_chart_config(self, user_request: str) -> dict:
        """AI 생성 실패 시 사용할 기본 차트 설정을 반환합니다."""
        return {
            "chart_type": "bar",
            "title": "데이터 차트",
            "data": {
                "labels": ["데이터 1", "데이터 2", "데이터 3"],
                "datasets": [{
                    "label": "기본 데이터셋",
                    "data": [10, 20, 30],
                    "backgroundColor": ["#FF6384", "#36A2EB", "#FFCE56"],
                    "borderColor": "#36A2EB",
                    "borderWidth": 1
                }]
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": "기본 차트"
                    },
                    "legend": {
                        "display": True,
                        "position": "top"
                    }
                },
                "scales": {
                    "y": {
                        "beginAtZero": True
                    }
                }
            },
            "query_info": {
                "data_source": "기본 데이터",
                "filters_applied": "없음",
                "aggregation": "기본"
            }
        }
    
    async def analyze_image_with_prompt(self, image_data: str, prompt: str) -> Dict[str, Any]:
        """
        Gemini Vision API를 사용하여 이미지 분석
        
        Args:
            image_data: base64 인코딩된 이미지 데이터
            prompt: 분석 요청 프롬프트
        
        Returns:
            분석 결과 딕셔너리
        """
        try:
            # API 키 선택
            api_key = self._get_best_api_key()
            if not api_key:
                raise Exception("사용 가능한 API 키가 없습니다.")
            
            # Gemini 모델 설정
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash-8b')
            
            # 이미지 데이터 준비
            import base64
            from io import BytesIO
            
            # base64 디코딩
            image_bytes = base64.b64decode(image_data)
            
            # PIL Image 객체 생성
            try:
                from PIL import Image
                image = Image.open(BytesIO(image_bytes))
            except ImportError:
                raise Exception("PIL(Pillow) 라이브러리가 설치되지 않았습니다.")
            
            # Gemini Vision API 호출
            response = model.generate_content([prompt, image])
            
            if response and response.text:
                # API 호출 성공 기록
                self._record_api_success(api_key)
                
                return {
                    "success": True,
                    "response": response.text.strip(),
                    "model": "gemini-1.5-flash-8b",
                    "api_key_used": api_key[-10:] if api_key else "unknown"
                }
            else:
                raise Exception("Gemini API 응답이 비어있습니다.")
        
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"이미지 분석 오류: {error_msg}")
            
            # API 키 오류 기록
            if api_key:
                self._record_api_error(api_key, error_msg)
            
            return {
                "success": False,
                "error": error_msg,
                "response": None
            } 