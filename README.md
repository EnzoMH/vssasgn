# 🏢 스마트 물류 창고 관리 시스템 (Smart Warehouse Management System)

## 🚀 프로젝트 개요

VSS 입사테스트 과제를 위한 **AI 기반 스마트 물류 창고 관리 대시보드**입니다.
실제 rawdata를 기반으로 **LLM/RAG 시스템**, **AI 차트 생성**, **머신러닝 분석**을 통합하여
차세대 창고 관리 솔루션을 제공합니다.

## ✨ 핵심 기능 (구현 완료)

### 🎯 **Step 1: LLM/RAG 서비스 환경**

- **ChromaDB RAG 시스템**: rawdata 자동 벡터화 및 의미 검색
- **AI 챗봇**: 실제 데이터 기반 즉시 답변 (총재고량, 입출고량, 랙현황 등)
- **Gemini API 통합**: 한국어 최적화 프롬프트 및 안정적인 응답

### 📊 **Step 2: LLM 활용 차트 드로잉**

- **자연어 → 차트 생성**: "랙별 재고를 파이차트로" → 실제 데이터 차트
- **실시간 대시보드**: KPI, 랙별 재고, 일별 트렌드, 제품 카테고리 분포
- **Chart.js 최적화**: 높이 제한, 반응형 디자인, 사용자 친화적 시각화

### 🤖 **AI 분석 시스템**

- **수요 예측**: XGBoost 기반 제품 수요 예측
- **제품 클러스터링**: K-Means를 통한 제품 그룹화
- **이상 탐지**: Isolation Forest로 비정상 패턴 감지
- **원클릭 분석**: 버튼 클릭으로 즉시 ML 분석 결과 확인

## 🛠️ 기술 스택

### **Backend (Python)**

- **FastAPI**: 고성능 웹 API 프레임워크
- **ChromaDB**: 벡터 데이터베이스 (RAG 구현)
- **SentenceTransformers**: 한국어 임베딩 (`jhgan/ko-sroberta-multitask`)
- **Google Gemini API**: LLM 챗봇 및 차트 생성
- **Scikit-learn**: ML 모델 (XGBoost, K-Means, Isolation Forest)
- **Pandas**: 데이터 처리 및 분석
- **PyMuPDF**: PDF 텍스트 추출

### **Frontend (HTML/CSS/JavaScript)**

- **Vanilla JavaScript**: 경량화된 프론트엔드
- **Chart.js**: 인터랙티브 차트 라이브러리
- **Bootstrap CSS**: 반응형 UI 프레임워크
- **Font Awesome**: 아이콘 시스템

### **Data & AI**

- **rawdata 기반**: 실제 Excel/CSV 파일 자동 처리
- **벡터 검색**: 의미 기반 데이터 검색
- **멀티모달 AI**: 텍스트, 차트, 데이터 통합 분석

## 📁 프로젝트 구조

```
vss_asgnM/
├── backend/                          # FastAPI 백엔드
│   ├── app/
│   │   ├── models/                   # ML 모델 (ml_models.py)
│   │   ├── services/                 # 핵심 서비스
│   │   │   ├── ai_service.py         # Gemini API 통합
│   │   │   ├── data_service.py       # rawdata 로딩
│   │   │   ├── vector_db_service.py  # ChromaDB RAG
│   │   │   ├── data_analysis_service.py
│   │   │   └── pdf_analysis_service.py
│   │   ├── utils/
│   │   │   └── ai_chat.py            # 챗봇 로직
│   │   └── main.py                   # FastAPI 앱
│   ├── static/                       # 프론트엔드 파일
│   │   ├── index.html                # 메인 대시보드
│   │   ├── css/style.css             # 스타일시트
│   │   └── js/                       # JavaScript 모듈
│   │       ├── dashboard.js          # 대시보드 관리
│   │       ├── charts.js             # 차트 생성
│   │       └── utils.js              # 유틸리티
│   ├── analyze_data.py               # 독립 실행 분석
│   └── requirements.txt              # Python 패키지
├── .gitignore                        # Git 제외 파일 설정
├── .env.example                      # 환경 변수 예시
└── README.md                         # 프로젝트 문서

# 📂 .gitignore로 제외된 파일들 (로컬에만 존재)
├── rawdata/                          # 원본 데이터 (Excel/CSV)
│   ├── 입고데이터_YYYYMMDD.xlsx
│   ├── 출고데이터_YYYYMMDD.xlsx
│   ├── 상품데이터.xlsx
│   ├── InboundData_YYYYMMDD.csv
│   ├── OutboundData_YYYYMMDD.csv
│   └── product_data.csv
├── chromadb_storage/                 # 벡터 DB 저장소 (자동 생성)
├── VSS_입사테스트과제_AI.pdf        # 과제 명세서
├── .env                              # 환경 변수 (API 키 포함)
└── *.json                            # 분석 결과 파일들
```

## 🚀 빠른 시작

### 📋 사전 준비

```bash
# 필수 요구사항
Python 3.8+
Google Gemini API 키
```

### ⚙️ 설치 및 실행

**1. 프로젝트 설정:**

```bash
git clone [repository-url]
cd vss_asgnM
```

**2. 백엔드 설정:**

```bash
cd backend
pip install -r requirements.txt

# .env 파일 생성 및 API 키 설정
cp .env.example .env
# GEMINI_API_KEY_1=your_api_key_here
```

**3. 서버 실행:**

```bash
python -m uvicorn app.main:app --reload --port 8000
```

**4. 브라우저 접속:**

```
http://localhost:8000
```

### 🎯 **데이터 분석 스크립트 (선택사항)**

```bash
# 독립적인 데이터 분석 및 AI 인사이트 실행
python analyze_data.py
```

## 🔥 실제 사용 예시

### **AI 챗봇 질문**

```
"오늘 총 재고량은 얼마인가요?"
→ 🏢 총 재고량은 1,234개입니다.

"A랙의 현재 상태는?"
→ 🏢 A랙: 300개 (15개 품목)

"재고가 부족한 제품은?"
→ 📦 제품A(5개), 제품B(3개) 부족
```

### **AI 차트 생성**

```
"최근 일주일 입고량을 막대차트로"
→ 실제 데이터 기반 Chart.js 차트 생성

"랙별 재고를 파이차트로"
→ ChromaDB 검색 + 실시간 차트 렌더링
```

### **원클릭 ML 분석**

- **수요 예측 버튼** → 다음 기간 예상 수요량
- **클러스터링 버튼** → 제품 그룹화 결과
- **이상 탐지 버튼** → 비정상 패턴 감지

## 🎯 다음 단계 계획

### **🎨 UX/UI 고도화 (진행 예정)**

- **데이터 분포 기반 차트 자동 선택**: AI Agent가 데이터 특성을 분석하여 최적의 차트 타입 자동 추천
- **스마트 시각화**: 데이터 분포 (정규분포, 편향분포, 범주형 등)에 따른 적합한 차트 스타일 자동 적용
- **개인화된 대시보드**: 사용자 역할별 맞춤형 UI 레이아웃
- **반응형 차트 인터랙션**: 드릴다운, 필터링, 실시간 업데이트

### **🤖 AI Agent 시스템**

- **차트 추천 엔진**: 데이터 타입, 분포, 사용자 의도를 종합 분석
- **UX 최적화 AI**: 사용자 행동 패턴 학습을 통한 인터페이스 개선
- **자동 인사이트 생성**: 데이터 변화 감지 시 자동 알림 및 분석 보고서

### **📊 고급 분석 기능**

- **Step 3: DWG CAD 시각화** (Canvas/WebGL 기반 창고 도면)
- **Step 4: 멀티모달 AI** (이미지 해석, 블루프린트 생성)
- **실시간 스트리밍 데이터 처리**
- **예측 모델 앙상블**

## 💡 특장점()

### **🎯 실제 데이터 기반**

- **Fake 데이터 X**: rawdata 파일을 직접 활용
- **실시간 연동**: 파일 업데이트 시 즉시 반영
- **정확한 분석**: 벡터 검색으로 관련 정보만 추출

### **🚀 VSS 과제 최적화**

- **LLM/RAG 완벽 구현**: ChromaDB + Gemini API
- **차트 드로잉 자동화**: 자연어 → 실제 차트
- **ML 모델 통합**: 수요예측, 클러스터링, 이상탐지
- **스케일러블 아키텍처**: 확장 가능한 설계

### **⚡ 사용자 경험**

- **즉시 답변**: 복잡한 분석 없이 바로 결과 제공
- **직관적 UI**: 원클릭으로 모든 기능 접근
- **반응형 디자인**: 모든 디바이스에서 최적화

## 🏆 VSS 과제 진행 현황

| Step         | 기능                   | 상태    | 완성도 |
| ------------ | ---------------------- | ------- | ------ |
| **Step 1**   | LLM/RAG 서비스 환경    | ✅ 완료 | 100%   |
| **Step 2-1** | LLM 활용 차트 드로잉   | ✅ 완료 | 100%   |
| **Step 2-2** | 라이브러리 차트 시각화 | ✅ 완료 | 100%   |
| **Step 2-3** | KPI/LOI 지표 산출      | ✅ 완료 | 95%    |
| **Step 3**   | DWG CAD 시각화         | 🔄 대기 | 0%     |
| **Step 4**   | 멀티모달 AI 평가       | 🔄 대기 | 0%     |
| **UX/UI**    | 데이터 기반 차트 선택  | 📋 계획 | 0%     |

## 🔧 개발 환경 설정

### **환경 변수 (.env)**

```bash
# Gemini API 키 (최대 4개까지 설정 가능)
GEMINI_API_KEY_1=your_primary_api_key
GEMINI_API_KEY_2=your_secondary_api_key
GEMINI_API_KEY_3=your_tertiary_api_key
GEMINI_API_KEY_4=your_quaternary_api_key

# 선택사항: OpenAI API (미래 확장용)
OPENAI_API_KEY=your_openai_key
```

### **데이터 파일 준비**

```bash
# rawdata/ 디렉토리를 생성하고 다음 형식으로 파일 배치
# (주의: .gitignore로 제외되어 있어 수동으로 준비해야 함)
mkdir rawdata

# 필요한 데이터 파일들:
rawdata/
├── 입고데이터_20250101.xlsx  # 또는 InboundData_20250101.csv
├── 출고데이터_20250101.xlsx  # 또는 OutboundData_20250101.csv
└── 상품데이터.xlsx          # 또는 product_data.csv

# VSS 과제 명세서 (선택사항)
VSS_입사테스트과제_AI.pdf
```

## 🐛 문제 해결

### **자주 발생하는 문제**

**1. ChromaDB 관련 오류**

```bash
pip install chromadb sentence-transformers --upgrade
```

**2. Gemini API 응답 없음**

```bash
# .env 파일에서 API 키 확인
# 여러 API 키 설정으로 rate limit 회피
```

**3. 차트 높이 무한 증가**

```bash
# 이미 수정됨: Chart.js aspectRatio 및 CSS max-height 적용
```

---

**🏆 VSS 입사테스트 과제를 위한 차세대 스마트 창고 관리 시스템**  
_Real Data + AI Intelligence + Smart Visualization_
