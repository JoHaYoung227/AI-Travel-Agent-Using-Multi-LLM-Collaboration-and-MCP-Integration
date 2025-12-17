"""
AI Travel Planner - User-Friendly Web Interface
실제 사용자를 위한 여행 추천 웹사이트
"""

import gradio as gr
import sys
import os
from datetime import datetime, timedelta

# 현재 디렉토리를 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from config import Config
    from agents.planner import PlannerAgent
    from agents.reviewer import ReviewerAgent
    from tools.pinecone_tool import PineconeTool
    from mcp_server.server import MCPServer
    from tools.weather_tool import WeatherTool
    from tools.google_places_tool import GooglePlacesToolNew
    SYSTEM_AVAILABLE = True
except ImportError as e:
    SYSTEM_AVAILABLE = False
    print(f"⚠️ Warning: Import failed - {e}")

# 전역 변수
mcp_server = None
planner = None
reviewer = None

def init_system():
    """시스템 초기화 (백그라운드)"""
    global mcp_server, planner, reviewer
    
    if not SYSTEM_AVAILABLE:
        return False
        
    if mcp_server is not None:
        return True
    
    try:
        # Config 검증
        Config.validate()
        
        # Pinecone Tool 초기화
        pinecone_tool = PineconeTool(
            api_key=Config.PINECONE_API_KEY,
            index_name=Config.PINECONE_INDEX_NAME,
            embedding_model=Config.EMBEDDING_MODEL
        )
        pinecone_tool.initialize()
        
        # Agent 생성
        planner = PlannerAgent()
        planner.initialize(Config.OPENAI_API_KEY)
        planner.load_templates()
        
        reviewer = ReviewerAgent(pinecone_tool)
        reviewer.initialize(Config.OPENAI_API_KEY)
        
        # MCP Server 생성 및 등록
        mcp_server = MCPServer()
        mcp_server.register_agent("planner", planner)
        mcp_server.register_agent("reviewer", reviewer)
        
        # API Tools 등록
        try:
            weather_tool = WeatherTool(api_key=Config.OPENWEATHER_API_KEY)
            mcp_server.register_tool("weather", weather_tool)
        except Exception as e:
            print(f"⚠️ WeatherTool 등록 실패: {e}")
        
        try:
            places_tool = GooglePlacesToolNew(api_key=Config.GOOGLE_PLACES_API_KEY)
            mcp_server.register_tool("places", places_tool)
        except Exception as e:
            print(f"⚠️ PlacesTool 등록 실패: {e}")
        
        print("✅ 시스템 초기화 완료")
        return True
        
    except Exception as e:
        print(f"System initialization error: {e}")
        return False

def generate_travel_plan(origin, destination, departure_date, return_date, people, budget, interests):
    """여행 계획 생성"""
    if not init_system():
        return "❌ 시스템 초기화 실패. API 키를 확인해주세요.", ""
    
    try:
        # 날짜 검증
        if not departure_date or not return_date:
            return "❌ 출발일과 도착일을 모두 선택해주세요.", ""
        
        # 날짜 문자열을 datetime으로 변환
        dep_date = datetime.strptime(departure_date, "%Y-%m-%d")
        ret_date = datetime.strptime(return_date, "%Y-%m-%d")
        
        # 날짜 유효성 검사
        if ret_date <= dep_date:
            return "❌ 도착일은 출발일보다 이후여야 합니다.", ""
        
        # 여행 일수 계산
        days = (ret_date - dep_date).days
        
        if days > 14:
            return "❌ 최대 14일까지만 계획할 수 있습니다.", ""
        
        # 여행 계획 쿼리 생성
        query = {
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,  # 정확한 날짜 추가
            "return_date": return_date,        # 정확한 날짜 추가
            "days": days,
            "people": int(people),
            "budget": int(budget),
            "preferences": {
                "location": "central location preferred",
                "room_quality": "high",
                "service": "friendly staff"
            }
        }
        
        # 관심사 추가
        if interests:
            query["interests"] = interests
        
        # MCP 프로토콜 실행
        result = mcp_server.process_travel_request(query)
        
        # 결과 포맷팅
        plan_text = format_travel_plan(result, departure_date, return_date, days)
        review_text = format_hotel_reviews(result)
        
        return plan_text, review_text
        
    except ValueError as e:
        return f"❌ 날짜 형식 오류: {str(e)}", ""
    except Exception as e:
        return f"❌ 오류가 발생했습니다: {str(e)}", ""

def format_travel_plan(result, departure_date, return_date, days):
    """여행 계획을 텍스트로 포맷팅"""
    if not result or "final_plan" not in result:
        return "여행 계획을 생성할 수 없습니다."
    
    plan = result["final_plan"]
    text = "# 🌍 여행 계획\n\n"
    
    # 여행 날짜 정보
    text += f"## 📅 여행 일정\n"
    text += f"- **출발일**: {departure_date} ({format_weekday(departure_date)})\n"
    text += f"- **도착일**: {return_date} ({format_weekday(return_date)})\n"
    text += f"- **총 기간**: {days}일\n\n"
    
    # 날씨 정보
    if "weather_info" in result and result["weather_info"]:
        weather = result["weather_info"]
        if weather.get("success"):
            text += f"## ☀️ 날씨 정보\n"
            
            # 날짜별 예보가 있는 경우
            if "forecast" in weather and weather["forecast"]:
                text += f"**📅 여행 기간 날씨 예보:**\n\n"
                for day in weather["forecast"]:
                    text += f"- **{day['date']}**: {day['temp_min']}~{day['temp_max']}°C, {day['description']}\n"
                text += "\n"
            # 현재 날씨만 있는 경우
            elif "data" in weather:
                data = weather.get("data", {})
                text += f"- 현재 온도: {data.get('temperature')}°C\n"
                text += f"- 날씨: {data.get('description')}\n"
                text += f"- 체감 온도: {data.get('feels_like')}°C\n\n"

    
    # 일정 정보
    if "itinerary" in plan:
        text += "## 🗺️ 일자별 일정\n\n"
        for day in plan["itinerary"]:
            text += f"### Day {day.get('day')}\n"
            if day.get('transportation'):
                trans = day['transportation']
                if isinstance(trans, dict):
                    text += f"- 🚗 교통: {trans.get('type', trans)}\n"
                else:
                    text += f"- 🚗 교통: {trans}\n"
            if day.get('accommodation'):
                acc = day['accommodation']
                if isinstance(acc, dict):
                    text += f"- 🏨 숙소: {acc.get('area', acc)}\n"
                else:
                    text += f"- 🏨 숙소: {acc}\n"
            if day.get('attractions'):
                atts = day['attractions']
                if isinstance(atts, list):
                    text += f"- 🗺️ 관광: {', '.join(atts)}\n"
                else:
                    text += f"- 🗺️ 관광: {atts}\n"
            text += "\n"
    
    # 장소 추천
    if "places_info" in result and result["places_info"].get("success"):
        places = result["places_info"].get("places", [])
        if places:
            text += "## 📍 추천 장소\n\n"
            for place in places[:5]:
                text += f"- **{place.get('name')}** (⭐ {place.get('rating')})\n"
            text += "\n"
    
    return text

def format_weekday(date_str):
    """날짜를 요일로 변환"""
    weekdays = ['월', '화', '수', '목', '금', '토', '일']
    date = datetime.strptime(date_str, "%Y-%m-%d")
    return weekdays[date.weekday()]

def format_hotel_reviews(result):
    """호텔 리뷰를 텍스트로 포맷팅"""
    if not result or "hotel_reviews" not in result:
        return "호텔 리뷰 정보가 없습니다."
    
    reviews = result["hotel_reviews"]
    if not reviews:
        return "호텔 리뷰 정보가 없습니다."
    
    text = "# 🏨 호텔 리뷰 분석\n\n"
    
    for review in reviews[:3]:
        text += f"## {review.get('name', '호텔')}\n"
        text += f"**평점**: {review.get('score', 'N/A')}/5.0\n\n"
        
        if review.get('pros'):
            text += f"**👍 장점**: {review['pros']}\n\n"
        
        if review.get('cons'):
            text += f"**👎 단점**: {review['cons']}\n\n"
        
        if review.get('recommendation'):
            text += f"**추천**: {review['recommendation']}\n\n"
        
        text += "---\n\n"
    
    return text

def update_budget_display(budget):
    """예산을 천 단위 구분 기호로 포맷"""
    return f"₩{budget:,}"

def get_min_date():
    """최소 날짜 (오늘)"""
    return datetime.now().strftime("%Y-%m-%d")

def get_default_departure():
    """기본 출발일 (내일)"""
    return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

def get_default_return():
    """기본 도착일 (3일 후)"""
    return (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d")

# CSS 스타일
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

.gradio-container {
    font-family: 'Noto Sans KR', 'Segoe UI', sans-serif;
}

.header {
    text-align: center;
    padding: 3rem 2rem;
    background: linear-gradient(135deg, #a8d5e2 0%, #7fc7d9 50%, #89cff0 100%);
    color: white;
    border-radius: 20px;
    margin-bottom: 2rem;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.input-group {
    background: white;
    padding: 2rem;
    border-radius: 15px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    margin-bottom: 1.5rem;
}

.date-box {
    border: 2px solid #7fc7d9;
    border-radius: 10px;
    padding: 1rem;
    background: #f8f9fa;
}
"""

def create_interface():
    """Gradio 인터페이스 생성"""
    
    with gr.Blocks(css=custom_css, title="AI Travel Planner") as app:
        # 헤더
        gr.HTML("""
            <div class="header">
                <h1 style="margin: 0; font-size: 2.5rem;">✈️ AI Travel Planner</h1>
                <p style="margin-top: 0.5rem; font-size: 1.2rem;">Multi-Agent LLM이 만드는 완벽한 여행 계획</p>
            </div>
        """)
        
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("### 📋 여행 정보 입력")
                
                with gr.Row():
                    origin = gr.Textbox(
                        label="🛫 출발지",
                        placeholder="예: 서울, 인천공항",
                        value="Seoul"
                    )
                    destination = gr.Textbox(
                        label="🛬 목적지",
                        placeholder="예: 도쿄, 일본",
                        value="Tokyo, Japan"
                    )
                
                # 날짜 선택 (달력 형태)
                gr.Markdown("### 📅 여행 날짜 선택")
                gr.Markdown("⚠️ **가는 날**과 **오는 날**을 정확히 선택해주세요")
                
                with gr.Row():
                    departure_date = gr.DateTime(
                        label="🛫 가는 날 (출발일)",
                        type="string",
                        value=get_default_departure(),
                        include_time=False
                    )
                    return_date = gr.DateTime(
                        label="🛬 오는 날 (도착일)",
                        type="string",
                        value=get_default_return(),
                        include_time=False
                    )
                
                with gr.Row():
                    people = gr.Slider(
                        label="👥 인원",
                        minimum=1,
                        maximum=10,
                        step=1,
                        value=2
                    )
                
                budget = gr.Slider(
                    label="💰 예산 (원)",
                    minimum=500000,
                    maximum=10000000,
                    step=100000,
                    value=2000000
                )
                budget_display = gr.Textbox(
                    label="",
                    value="₩2,000,000",
                    interactive=False
                )
                
                interests = gr.Textbox(
                    label="🎯 관심사 (쉼표로 구분)",
                    placeholder="예: 문화, 음식, 쇼핑",
                    value=""
                )
                
                generate_btn = gr.Button(
                    "🚀 여행 계획 생성하기",
                    variant="primary",
                    size="lg"
                )
            
            with gr.Column(scale=1):
                gr.Markdown("### 💡 사용 방법")
                gr.Markdown("""
                위의 정보를 입력하고 '여행 계획 생성하기' 버튼을 눌러주세요! ✨
                
                **시스템 특징:**
                - 🤖 Multi-Agent 협업
                - 🌤️ 실시간 날씨 정보
                - 📍 Google Places 추천
                - ⭐ 호텔 리뷰 분석
                
                **NEW! 📅 정확한 날짜 입력**
                - 달력에서 가는 날과 오는 날을 선택하세요
                - 해당 날짜의 실제 날씨를 확인할 수 있습니다
                """)
        
        gr.Markdown("---")
        
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("### 🗺️ 여행 계획")
                plan_output = gr.Markdown(
                    label="",
                    value="여행 계획이 여기에 표시됩니다."
                )
            
            with gr.Column(scale=2):
                gr.Markdown("### 🏨 추천 숙소")
                reviews_output = gr.Markdown(
                    label="",
                    value="호텔 리뷰 분석이 여기에 표시됩니다."
                )
        
        # 예시 섹션
        gr.HTML("""
            <div style="margin-top: 2rem; padding: 1.5rem; background: #f8f9fa; border-radius: 10px;">
                <h3 style="margin-top: 0; color: #5a9fb5;">🌟 인기 여행지 예시</h3>
                <p style="color: #666;">아래 버튼을 클릭하면 자동으로 정보가 입력됩니다!</p>
            </div>
        """)
        
        with gr.Row():
            gr.Examples(
                examples=[
                    ["서울", "도쿄", "2025-11-10", "2025-11-13", 2, 2600000, "문화, 음식, 쇼핑"],
                    ["서울", "오사카", "2025-11-15", "2025-11-19", 2, 3200000, "음식, 역사"],
                    ["서울", "방콕", "2025-12-01", "2025-12-06", 4, 4000000, "음식, 쇼핑, 관광"],
                    ["서울", "다낭", "2025-12-10", "2025-12-14", 2, 2000000, "해변, 휴양, 음식"],
                ],
                inputs=[origin, destination, departure_date, return_date, people, budget, interests],
                label="빠른 선택"
            )
        
        # 푸터
        gr.Markdown("""
            ---
            <div style="text-align: center; color: #666; font-size: 0.9rem;">
                <p>🤖 Multi-Agent LLM Collaboration with MCP Integration</p>
                <p>Powered by GPT • Weather API • Google Places API • TripAdvisor RAG</p>
            </div>
        """)
        
        # 이벤트 연결
        budget.change(
            fn=update_budget_display,
            inputs=budget,
            outputs=budget_display
        )
        
        generate_btn.click(
            fn=generate_travel_plan,
            inputs=[origin, destination, departure_date, return_date, people, budget, interests],
            outputs=[plan_output, reviews_output]
        )
    
    return app

# 실행
if __name__ == "__main__":
    print("="*70)
    print("🚀 AI Travel Planner Starting...")
    print("="*70)
    
    if not SYSTEM_AVAILABLE:
        print("\n⚠️  WARNING: Import failed!")
        print("Make sure all required files are in the same directory.\n")
    else:
        print("\n✅ System files loaded successfully!")
        if init_system():
            print("✅ Travel planning system initialized!\n")
        else:
            print("⚠️  System initialization pending...\n")
    
    print("🌐 Starting web interface...")
    print("📍 Access at: http://localhost:7860")
    print("💡 Press Ctrl+C to stop\n")
    print("="*70)
    
    app = create_interface()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        inbrowser=True
    )