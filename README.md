# Multi-Agent AI Travel Planner (MCP 기반)

LLM + 외부 API + RAG(호텔 리뷰) + 멀티 에이전트 협업(MCP)을 결합한 **AI 여행 일정 생성 서비스**입니다.

---
## 실행 방법

### 1) Flask 웹앱 실행(추천)

```bash
python app.py
```

- 기본적으로 Flask 서버가 실행되며, 브라우저에서 결과 페이지를 확인할 수 있습니다.

---

## 실행 환경

- **Python 3.10+ 권장** (타입힌트 `X | None` 등 문법 호환)
- Windows 

---

## 설치 방법

```bash
# 1) 가상환경 생성(예: conda)
conda create -n capstone python=3.10 -y
conda activate capstone

# 2) 의존성 설치
pip install -r requirements.txt
```

---

## 환경변수(.env) 설정

프로젝트 루트에 `.env` 파일을 만들고 아래 값을 채워주세요.

```env
OPENAI_API_KEY=YOUR_OPENAI_KEY
PINECONE_API_KEY=YOUR_PINECONE_KEY
PINECONE_INDEX_NAME=tripadvisor-reviews

OPENWEATHER_API_KEY=YOUR_OPENWEATHER_KEY
GOOGLE_PLACES_API_KEY=YOUR_GOOGLE_PLACES_KEY

AMADEUS_API_KEY=YOUR_AMADEUS_KEY
AMADEUS_API_SECRET=YOUR_AMADEUS_SECRET
```

> `config.py`에서 `dotenv`로 환경변수를 읽어옵니다.

---

## 프로젝트 구성

- `app.py` : Flask 웹 서버 (입력 폼 → 계획 생성 → 결과 렌더링)
- `mcp_server/server.py` : MCP Server (명령 흐름/툴 호출/에이전트 협업)
- `agents/`
  - `planner.py` : Planner Agent (TravelPlanner 템플릿 기반 일정 생성)
  - `stylist.py` : Stylist Agent (여행 스타일 분류/추천)
  - `reviewer.py` : Reviewer Agent (Pinecone RAG 기반 호텔 리뷰 분석)
- `tools/`
  - `flight_tool.py` : Amadeus 항공 검색
  - `hotel_tool.py` : Amadeus 숙소 검색
  - `weather_tool.py` : OpenWeather
  - `google_places_tool.py` : Google Places/Restaurants
  - `pinecone_tool.py` : Pinecone + 임베딩 모델을 통한 리뷰 검색

---


