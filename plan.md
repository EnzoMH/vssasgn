# VSS AI 팀 입사과제 - 스마트 물류창고 관리 시스템

## 📋 프로젝트 개요

**프로젝트명**: Smart Warehouse Management System  
**목표**: 실제 물류센터에서 사용 가능한 AI 기반 창고관리 대시보드  
**기술스택**: React + TypeScript + FastAPI + gemini + XGBoost + K-means  
**예상 소요시간**: 5-7일

---

## 🎯 데이터 분석 결과

### 보유 데이터

- **상품 마스터**: 101개 제품, A~Z 랙 배치, BOX/EA/PAC 단위
- **입출고 트랜잭션**: 2일간 404건, 완벽 매칭
- **핵심 인사이트**: 대부분 랙에서 순유출, 랙별 물동량 편차 존재

### ML 타겟 변수 (y-label) 후보

1. 다음날 제품별 출고량
2. 랙별 재고 소진 예상일
3. 라인 처리 효율성 점수
4. 재고 부족 위험도

---

## 🚀 단계별 구현 계획

### Phase 1: 핵심 기능 (3-4일) ⭐

> **목표**: 동작하는 대시보드 + 기본 AI 기능

#### 1.1 React 대시보드 구축

```bash
# 프로젝트 초기화
npx create-react-app warehouse-dashboard --template typescript
cd warehouse-dashboard
npm install recharts lucide-react axios tailwindcss
```

**구현할 컴포넌트**:

- `Dashboard.tsx` - 메인 대시보드
- `InventoryChart.tsx` - 랙별 재고 현황
- `TrendChart.tsx` - 일별 입출고 트렌드
- `KPICards.tsx` - 핵심 지표 카드
- `AIChat.tsx` - AI 질의응답 채팅

#### 1.2 FastAPI 백엔드 구축

```bash
# 백엔드 프로젝트 생성
mkdir warehouse-api
cd warehouse-api
pip install fastapi uvicorn pandas scikit-learn xgboost openai python-multipart
```

**API 엔드포인트**:

```python
# main.py
@app.get("/api/dashboard/kpi")      # KPI 데이터
@app.get("/api/inventory/by-rack")  # 랙별 재고
@app.get("/api/trends/daily")       # 일별 트렌드
@app.post("/api/ai/chat")          # AI 질의응답
@app.post("/api/predict/demand")   # 수요 예측
```

#### 1.3 기본 데이터 시각화

- **랙별 입출고 현황** (막대차트)
- **일별 물동량 트렌드** (라인차트)
- **제품 카테고리별 분포** (파이차트)
- **KPI 대시보드** (카드 형태)

### Phase 2: AI 기능 추가 (2-3일) 🤖

> **목표**: LLM 연동 + ML 모델 + 고급 시각화

#### 2.1 LLM 연동 구현

```python
# ai_service.py
class WarehouseAI:
    def __init__(self):
        self.client = OpenAI()  # 또는 Llama

    def answer_query(self, question: str, data_context: dict):
        prompt = f"""
        창고 데이터를 바탕으로 질문에 답하세요:
        데이터: {data_context}
        질문: {question}
        """
        # LLM 호출 및 응답 생성
```

**지원할 질의 예시**:

- "어제 A랙 입고량이 얼마야?"
- "재고가 부족한 제품 알려줘"
- "내일 예상 출고량은?"

#### 2.2 ML 모델 구현

```python
# ml_models.py
class DemandPredictor:
    def __init__(self):
        self.model = XGBRegressor()

    def predict_daily_demand(self, features):
        # 다음날 제품별 출고량 예측

class ProductClusterer:
    def __init__(self):
        self.model = KMeans(n_clusters=4)

    def cluster_products(self, features):
        # 제품을 회전율별로 클러스터링
```

#### 2.3 파일 업로드 및 분석

- CSV/Excel 파일 드래그앤드롭
- 자동 데이터 프로파일링
- AI 기반 인사이트 추출

### Phase 3: 고급 기능 (선택사항) 🔥

> **목표**: CAD 파일 처리 + 멀티모달 AI

#### 3.1 CAD 파일 처리 (Step 3)

```python
# cad_processor.py
import ezdxf  # DWG 파일 처리

class CADAnalyzer:
    def extract_blueprint_info(self, dwg_file):
        # 도면에서 벽, 기둥 정보 추출

    def generate_3d_layout(self, blueprint_data):
        # 3D 시뮬레이션 데이터 생성
```

#### 3.2 멀티모달 AI (Step 4)

- 이미지 + 텍스트 동시 분석
- 도면 이미지 해석
- 블루프린트 생성

---

## 💻 구체적 구현 가이드

### 1. 프로젝트 구조

```
warehouse-system/
├── frontend/                 # React 앱
│   ├── src/
│   │   ├── components/      # 대시보드 컴포넌트
│   │   ├── services/        # API 호출
│   │   ├── types/           # TypeScript 타입
│   │   └── utils/           # 유틸리티
│   └── public/
├── backend/                  # FastAPI 앱
│   ├── app/
│   │   ├── api/            # API 라우터
│   │   ├── models/         # ML 모델
│   │   ├── services/       # 비즈니스 로직
│   │   └── utils/          # 유틸리티
│   ├── data/               # 데이터 파일
│   └── requirements.txt
└── README.md
```

### 2. 핵심 컴포넌트 코드 예시

#### Dashboard.tsx

```typescript
const Dashboard: React.FC = () => {
  const [kpiData, setKpiData] = useState(null);
  const [inventoryData, setInventoryData] = useState([]);

  useEffect(() => {
    // API 데이터 로드
    fetchDashboardData();
  }, []);

  return (
    <div className="dashboard">
      <KPICards data={kpiData} />
      <div className="charts-grid">
        <InventoryChart data={inventoryData} />
        <TrendChart />
        <AIChat />
      </div>
    </div>
  );
};
```

#### FastAPI 메인 구조

```python
# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Warehouse Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/dashboard/kpi")
async def get_kpi_data():
    # KPI 계산 로직
    return {
        "total_inventory": 2157,
        "daily_throughput": 427,
        "rack_utilization": 0.87,
        "inventory_turnover": 2.3
    }
```

### 3. 데이터 처리 파이프라인

```python
# data_processor.py
class DataProcessor:
    def __init__(self):
        self.inbound_data = []
        self.outbound_data = []
        self.product_master = {}

    def load_excel_files(self):
        # Excel 파일들을 로드하고 전처리

    def calculate_kpis(self):
        # KPI 계산

    def prepare_ml_features(self):
        # ML 모델용 피처 생성
```

### 4. AI 챗봇 구현

```python
# ai_chat.py
class WarehouseChatbot:
    def __init__(self):
        self.data_service = DataService()
        self.llm_client = OpenAI()

    async def process_query(self, question: str):
        # 1. 질문 분석
        intent = self.analyze_intent(question)

        # 2. 관련 데이터 조회
        context_data = self.data_service.get_relevant_data(intent)

        # 3. LLM으로 응답 생성
        response = await self.generate_response(question, context_data)

        return response
```

---

## 🎨 UI/UX 디자인 가이드

### 색상 팔레트

```css
:root {
  --primary: #3b82f6; /* 파란색 */
  --secondary: #10b981; /* 초록색 */
  --warning: #f59e0b; /* 주황색 */
  --danger: #ef4444; /* 빨간색 */
  --dark: #1f2937; /* 다크 그레이 */
  --light: #f9fafb; /* 밝은 그레이 */
}
```

### 컴포넌트 스타일

```css
.kpi-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
}

.chart-container {
  background: white;
  border-radius: 12px;
  padding: 20px;
  height: 400px;
}
```

### 반응형 그리드

```css
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  padding: 20px;
}
```

---

## 📊 차트 구현 예시

### 1. 랙별 재고 현황 (Bar Chart)

```typescript
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const InventoryChart = ({ data }) => (
  <ResponsiveContainer width="100%" height={300}>
    <BarChart data={data}>
      <XAxis dataKey="rackName" />
      <YAxis />
      <Tooltip />
      <Bar dataKey="currentStock" fill="#3B82F6" />
      <Bar dataKey="capacity" fill="#E5E7EB" />
    </BarChart>
  </ResponsiveContainer>
);
```

### 2. 일별 트렌드 (Line Chart)

```typescript
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const TrendChart = ({ data }) => (
  <ResponsiveContainer width="100%" height={300}>
    <LineChart data={data}>
      <XAxis dataKey="date" />
      <YAxis />
      <Tooltip />
      <Line
        type="monotone"
        dataKey="inbound"
        stroke="#10B981"
        strokeWidth={2}
      />
      <Line
        type="monotone"
        dataKey="outbound"
        stroke="#EF4444"
        strokeWidth={2}
      />
    </LineChart>
  </ResponsiveContainer>
);
```

---

## 🚀 배포 및 실행 가이드

### 개발 환경 실행

```bash
# 백엔드 실행
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 프론트엔드 실행
cd frontend
npm install
npm start
```

### 프로덕션 배포

```bash
# Docker 컨테이너로 배포
docker-compose up -d

# 또는 Vercel (프론트엔드) + Railway (백엔드)
vercel --prod
railway deploy
```

---

## ✅ 체크리스트

### Phase 1 체크리스트

- [ ] React 프로젝트 초기화
- [ ] FastAPI 백엔드 구축
- [ ] 데이터 로딩 및 전처리
- [ ] KPI 카드 컴포넌트
- [ ] 기본 차트 3개 (Bar, Line, Pie)
- [ ] API 연동
- [ ] 반응형 레이아웃

### Phase 2 체크리스트

- [ ] OpenAI/Llama API 연동
- [ ] AI 챗봇 UI
- [ ] XGBoost 수요예측 모델
- [ ] K-means 제품 클러스터링
- [ ] 파일 업로드 기능
- [ ] 고급 시각화 (히트맵, 산점도)

### Phase 3 체크리스트 (선택)

- [ ] CAD 파일 처리
- [ ] 멀티모달 AI
- [ ] 3D 시각화
- [ ] 실시간 업데이트

---

## 🎯 면접 어필 포인트

### 1. 실무 적용 가능성

> "실제 물류센터에서 사용할 수 있는 수준으로 구현했습니다"

### 2. AI 기술 활용

> "단순 대시보드가 아닌 예측 분석과 자연어 질의가 가능합니다"

### 3. 확장성

> "모듈식 구조로 새로운 기능 추가가 쉽습니다"

### 4. 사용자 경험

> "직관적인 UI와 실시간 반응성을 고려했습니다"

---

## 💡 추가 개선 아이디어

### 단기 개선

- 알림 시스템 (재고 부족 경고)
- 엑셀 리포트 자동 생성
- 모바일 앱 지원

### 장기 개선

- IoT 센서 연동
- 로봇 제어 시스템
- 블록체인 기반 이력 관리

---

**이 문서를 참고해서 단계별로 구현하시면 VSS 입사과제를 성공적으로 완성할 수 있을 것입니다! 화이팅! 🚀**
