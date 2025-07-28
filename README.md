# 스마트 물류 창고 관리 시스템 (Smart Warehouse Management System)

## 🚀 프로젝트 개요

이 프로젝트는 AI 기반의 스마트 물류 창고 관리 대시보드를 구축하여, 재고 관리 및 물류 운영의 효율성을 극대화하는 것을 목표로 합니다. 최신 웹 기술과 머신러닝 모델을 통합하여 데이터 분석, 수요 예측, 제품 클러스터링, 이상 징후 탐지 등 고급 기능을 제공합니다.

## ✨ 주요 기능

*   **실시간 대시보드:** KPI (핵심 성과 지표), 랙별 재고 현황, 일별 물동량 트렌드, 제품 카테고리 분포 등 다양한 시각화를 통해 창고 운영 현황을 한눈에 파악할 수 있습니다.
*   **AI 기반 질의응답 (챗봇):** Google Gemini AI를 활용하여 자연어 질문에 대한 데이터 기반의 심층적인 인사이트를 제공합니다. Chain of Thought (CoT) 추론 방식을 적용하여 AI의 분석 품질을 향상시켰습니다.
*   **수요 예측:** 과거 입출고 데이터를 기반으로 향후 제품 수요를 예측하여 적정 재고 수준 유지 및 재고 비용 절감에 기여합니다.
*   **제품 클러스터링:** 제품 특성(회전율, 재고량 등)에 따라 제품을 그룹화하여 랙 배치 최적화 및 맞춤형 재고 관리 전략 수립을 지원합니다.
*   **이상 징후 탐지:** Isolation Forest 모델을 활용하여 일별 입출고량 등에서 발생하는 비정상적인 패턴을 자동으로 감지하고, 잠재적인 문제에 대한 조기 경고를 제공합니다.
*   **데이터 업로드:** CSV 및 Excel 형식의 데이터를 드래그앤드롭 방식으로 쉽게 업로드하여 시스템에 반영할 수 있습니다.
*   **데이터 분석 스크립트:** 백엔드에서 독립적으로 실행 가능한 Python 스크립트(`backend/analyze_data.py`)를 제공하여, 터미널 환경에서 핵심 데이터 분석 결과와 AI 기반 인사이트를 빠르게 확인할 수 있습니다.

## 🛠️ 기술 스택

*   **프론트엔드 (Frontend):**
    *   React.js
    *   TypeScript
    *   Tailwind CSS (UI/UX)
    *   Recharts (데이터 시각화)
    *   Axios (API 통신)
    *   React Dropzone (파일 업로드)
*   **백엔드 (Backend):**
    *   FastAPI (Python 웹 프레임워크)
    *   Pandas (데이터 처리 및 분석)
    *   Scikit-learn (XGBoost, K-Means, Isolation Forest)
    *   Google Gemini API (AI 챗봇)
    *   `python-dotenv` (환경 변수 관리)
    *   `uvicorn` (ASGI 서버)

## 📁 프로젝트 구조

```
vss_asgnM/
├── backend/                  # FastAPI 백엔드 애플리케이션
│   ├── app/
│   │   ├── models/           # ML 모델 정의 (ml_models.py)
│   │   ├── services/         # 데이터 처리, AI, 분석 서비스 (data_service.py, ai_service.py, data_analysis_service.py)
│   │   ├── utils/            # 유틸리티 함수 (ai_chat.py)
│   │   └── main.py           # FastAPI 애플리케이션 메인 파일
│   ├── analyze_data.py       # 데이터 분석 및 AI 인사이트 스크립트
│   └── requirements.txt      # 백엔드 Python 의존성
├── frontend/                 # React + TypeScript 프론트엔드 애플리케이션
│   ├── public/
│   ├── src/
│   │   ├── components/       # React 컴포넌트
│   │   └── App.tsx, index.tsx, index.css, tailwind.config.js 등
│   └── package.json          # 프론트엔드 Node.js 의존성
├── rawdata/                  # 원본 데이터 파일 (CSV, XLSX)
├── .env.example              # 환경 변수 예시
├── .gitignore                # Git 버전 관리 제외 파일 설정
├── README.md                 # 프로젝트 설명 (현재 파일)
├── todolist.md               # 프로젝트 진행 상황 To-Do 리스트
└── data_and_insight.md       # AI 기반 데이터 분석 결과 및 ML 모델 활용 제안 문서
└── data_after_extend.md      # ML 모델 고도화 및 AI 챗봇 기능 확장 계획 문서
```

## 🚀 시작하기

### 📋 사전 준비 사항

*   Node.js (npm 포함)
*   Python 3.8+ (pip 포함)
*   Google Gemini API 키 (환경 변수 `.env` 파일에 `GEMINI_API_KEY_1` 등으로 설정)

### ⚙️ 설치 및 실행

**1. 프로젝트 클론 및 이동:**

```bash
git clone https://github.com/EnzoMH/vssasgn.git
cd vssasgn
```

**2. 백엔드 설정 및 실행:**

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```
(참고: `requirements.txt`에 포함되지 않은 `xgboost`, `scikit-learn` 등은 수동 설치 필요)
```bash
pip install xgboost scikit-learn
```

**3. 프론트엔드 설정 및 실행:**

```bash
cd ../frontend
npm install
npm start
```

**4. 데이터 분석 스크립트 실행 (선택 사항):**

FastAPI 서버가 실행 중이지 않아도, 데이터 분석 및 AI 인사이트를 터미널에서 직접 확인하고 싶을 때 사용합니다.

```bash
cd ../backend
python analyze_data.py
```

## 💡 향후 개선 아이디어

*   **데이터 품질 관리 시스템:** `ProductCode` 및 `ProductName` 정합성, `현재고` 데이터의 실시간 반영 등 데이터 품질을 자동으로 검증하고 개선하는 시스템 구축.
*   **ML 모델 고도화:** 실제 데이터 기반의 특징 공학, 고급 모델 튜닝 및 재학습 파이프라인 구축.
*   **AI 챗봇 기능 확장:** 사용자 질의 의도에 따른 ML 모델 직접 연동, 실행 가능한(Actionable) 최적화 제안, LangChain/AI Agent Chain 아키텍처 도입.
*   **프론트엔드 확장:** ML 모델 결과(예측 차트, 클러스터 시각화, 이상 징후 알림)를 대시보드에 통합하여 시각화.
*   **ML Ops 파이프라인:** CI/CD를 통한 모델 배포 자동화, 모델 성능 모니터링, 데이터 드리프트 감지 및 자동 재학습.
*   **고급 물류 기능:** 경로 최적화, 스케줄링, 창고 시뮬레이션 등.

---
