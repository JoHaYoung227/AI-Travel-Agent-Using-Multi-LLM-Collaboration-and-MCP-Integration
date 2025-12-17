"""
MCP 기반 AI Travel Agent 메인 실행 파일
"""
from config import Config
from agents.planner import PlannerAgent
from agents.reviewer import ReviewerAgent
from tools.pinecone_tool import PineconeTool
from mcp_server.server import MCPServer
import json
from typing import List, Dict
from tools.weather_tool import WeatherTool 
from tools.google_places_tool import GooglePlacesToolNew
from agents.stylist import StylistAgent

def print_mcp_commands(commands: List[Dict]):
    """MCP 명령 히스토리를 테이블 형태로 출력"""
    print("\n" + "="*70)
    print("📊 MCP Command History")
    print("="*70 + "\n")
    
    # 테이블 헤더
    print(f"{'ID':<4} {'From':<10} {'To':<10} {'Command':<25} {'Status':<12}")
    print("-" * 70)
    
    # 각 명령 출력
    for cmd in commands:
        cmd_id = str(cmd['id'])
        from_agent = cmd['from'][:9]
        to_agent = cmd['to'][:9]
        command = cmd['command'][:24]
        status = cmd['status'][:11]
        
        # 상태에 따라 이모지 추가
        if status == 'completed':
            status = f"✅ {status}"
        elif status == 'failed':
            status = f"❌ {status}"
        else:
            status = f"⏳ {status}"
        
        print(f"{cmd_id:<4} {from_agent:<10} {to_agent:<10} {command:<25} {status:<12}")
    
    print("\n" + "="*70 + "\n")

def print_result(result: dict):
    """결과를 보기 좋게 출력"""
    print("\n" + "="*70)
    print("📋 최종 결과")
    print("="*70 + "\n")
    
    # 초기 일정
    if "initial_itinerary" in result:
        print("1️⃣  초기 여행 일정:")
        itinerary = result["initial_itinerary"]
        print(f"   예상 비용: ${itinerary.get('estimated_cost', 'N/A')}")
        print(f"   호텔 후보: {', '.join(itinerary.get('hotels_needed', []))}")
        print()

    # 날씨 정보 출력
    if "weather_info" in result and result["weather_info"]:
        weather = result["weather_info"]
        current = weather.get('current', {}).get('data', {})
        forecast = weather.get('forecast', {}).get('forecast', [])
        
        print("☀️ 날씨 정보:")
        if current.get('success'):
            print(f"  현재 날씨: {current.get('temperature')}°C, {current.get('description')}")
        if forecast:
            print("  예상 일기 (첫 2일):")
            for day in forecast[:2]:
                print(f"    - Day {day.get('date')}: {day.get('temp_min')}~{day.get('temp_max')}°C, {day.get('description')}")
        print()
    
    # 장소 정보 출력
    if "places_info" in result and result["places_info"].get('success'):
        places = result["places_info"].get('places', [])
        print("📍 Google Places 추천:")
        for i, place in enumerate(places[:3], 1): # 3개만 출력
            print(f"   {i}. {place.get('name', 'N/A')} (평점: {place.get('rating', 'N/A')}/5.0)")
            
    # 호텔 분석 (기존 코드 수정)
    if "hotel_analysis" in result and result["hotel_analysis"]:
        analysis = result["hotel_analysis"]
        print("\n🏨 호텔 리뷰 분석:")
        recommendations = analysis.get("recommendations", [])
        
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                # ❌ 기존 코드: print(f"   {i}. {rec.get('hotel', 'Unknown')} (점수: {rec.get('overall_score', 0)}/5)")
                # ✅ 수정: 점수를 analysis 배열에서 찾거나, recommendations에 top_pick을 포함시키는 방식으로 개선 필요
                hotel_name = rec.get('hotel', 'Unknown')
                analysis_data = next((a for a in analysis.get('analysis', []) if a.get('hotel') == hotel_name), {})
                score = analysis_data.get('overall_score', rec.get('overall_score', 'N/A'))
                
                print(f" {i}. {hotel_name} (종합 점수: {score}/5)")
                print(f" 장점: {', '.join(analysis_data.get('strengths', []))}")
                print(f" 약점: {', '.join(analysis_data.get('weaknesses', []))}")
                print(f" 추천 사유: {rec.get('reason', 'N/A')}") # Reviewer가 제공한 추천 사유
        print()

    # 최종 일정
    if "final_itinerary" in result:
        print("3️⃣  최종 여행 일정:")
        final = result["final_itinerary"]
        days_count = final.get("days", 0) # JSON에 days 필드가 있다면 사용
        itinerary_list = final.get("itinerary", [])
        print(f"   총 {len(itinerary_list) or days_count}일 일정")
        # ----------------------------------------------------
        days = final.get("itinerary", []) # days 변수를 실제 일정을 담는 리스트로 사용
        for day in days[:2]:
            print(f"   Day {day.get('day', '?')}:")
            print(f"      - 교통: {day.get('transportation', 'N/A')}")
            print(f"      - 숙소: {day.get('accommodation', 'N/A')}")
            attractions = day.get('attractions', [])
            if attractions:
                print(f"      - 관광: {', '.join(attractions[:2])}")
        if len(days) > 2:
            print(f"   ... 외 {len(days) - 2}일")
        print()
    
    print("="*70 + "\n")

def main():
    """메인 실행 함수"""
    
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║        Multi-Agent AI Travel Agent with MCP                  ║
    ║                                                              ║
    ║        Planner Agent + Reviewer Agent                        ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # 1. 설정 검증
    print("\n🔧 시스템 초기화 중...\n")
    try:
        Config.validate()
    except ValueError as e:
        print(f"❌ 설정 오류: {e}")
        return
    
    # 2. Pinecone Tool 초기화
    pinecone_tool = PineconeTool(
        api_key=Config.PINECONE_API_KEY,
        index_name=Config.PINECONE_INDEX_NAME,
        embedding_model=Config.EMBEDDING_MODEL
    )
    
    if not pinecone_tool.initialize():
        print("⚠️  Pinecone Tool 초기화 실패. Reviewer 기능이 제한됩니다.")
    
    # 3. Agent 생성
    planner = PlannerAgent()
    planner.initialize(Config.OPENAI_API_KEY)
    planner.load_templates()
    
    reviewer = ReviewerAgent(pinecone_tool)
    reviewer.initialize(Config.OPENAI_API_KEY)

    stylist = StylistAgent()
    stylist.initialize(Config.OPENAI_API_KEY)
    
    # 4. MCP Server 생성 및 Agent 등록
    mcp_server = MCPServer()
    mcp_server.register_agent("planner", planner)
    mcp_server.register_agent("reviewer", reviewer)
    mcp_server.register_agent("stylist", stylist)

    try:
        # 1) Weather Tool 등록
        weather_tool = WeatherTool(api_key=Config.OPENWEATHER_API_KEY)
        mcp_server.register_tool("weather", weather_tool)
    except Exception as e:
        print(f"⚠️ WeatherTool 등록 실패: {e}")

    try:
        # 2) Google Places Tool 등록
        places_tool = GooglePlacesToolNew(api_key=Config.GOOGLE_PLACES_API_KEY)
        mcp_server.register_tool("places", places_tool)
    except Exception as e:
        print(f"⚠️ PlacesTool 등록 실패: {e}")

    mcp_server.register_agent("planner", planner)
    mcp_server.register_agent("reviewer", reviewer)
    
    print(f"\n✅ 시스템 초기화 완료\n")    
    
    print(f"\n✅ 시스템 초기화 완료\n")
    print(f"상태: {mcp_server.get_status()}\n")
    
    # 5. 테스트 쿼리 실행
    test_queries = [
        {
            "name": "도쿄 3일 여행",
            "query": {
                "origin": "Seoul, Incheon Airport",
                "destination": "Tokyo, Japan",
                "days": 3,
                "people": 2,
                "budget": 2000000,
                "preferences": {
                    "location": "central location preferred",
                    "room_quality": "high",
                    "service": "friendly staff"
                }
            }
        },
        {
            "name": "오사카 5일 여행",
            "query": {
                "origin": "Seoul",
                "destination": "Osaka, Japan",
                "days": 5,
                "people": 2,
                "budget": 3000000,
                "preferences": {
                    "location": "near attractions",
                    "value": "good value for money"
                }
            }
        }
    ]
    
    # 사용자가 선택하도록
    print("📋 사용 가능한 테스트 시나리오:")
    for i, tq in enumerate(test_queries, 1):
        q = tq["query"]
        print(f"   {i}. {tq['name']}: {q['origin']} → {q['destination']} ({q['days']}일, ${q['budget']})")
    
    print(f"   0. 직접 입력")
    
    try:
        choice = input("\n선택하세요 (0-2): ").strip()
        
        if choice == "0":
            # 직접 입력
            print("\n직접 여행 계획 입력:")
            origin = input("출발지: ").strip() or "Seoul"
            destination = input("목적지: ").strip() or "Tokyo"
            days = int(input("일수 (3/5/7): ").strip() or "3")
            people = int(input("인원: ").strip() or "2")
            budget = int(input("예산 ($): ").strip() or "2000000")
            
            test_query = {
                "origin": origin,
                "destination": destination,
                "days": days,
                "people": people,
                "budget": budget,
                "preferences": {
                    "location": "central",
                    "service": "friendly"
                }
            }
        else:
            idx = int(choice) - 1
            if 0 <= idx < len(test_queries):
                test_query = test_queries[idx]["query"]
            else:
                print("❌ 잘못된 선택, 첫 번째 시나리오 사용")
                test_query = test_queries[0]["query"]
    
    except (ValueError, KeyboardInterrupt):
        print("\n기본 시나리오 사용")
        test_query = test_queries[0]["query"]
    
    # 6. Multi-Agent Collaboration 실행
    print("\n" + "="*70)
    print(f"🎯 선택된 여행: {test_query['origin']} → {test_query['destination']} ({test_query['days']}일)")
    print("="*70)
    
    result = mcp_server.process_travel_request(test_query)
    
    # 7-1. MCP 명령 히스토리 출력 (새로 추가!)
    if "collaboration_log" in result:
        commands = result["collaboration_log"].get("mcp_commands", [])
        print_mcp_commands(commands)
    
    # 7-2. 결과 출력
    print_result(result)
    
    # 8. 결과를 JSON 파일로 저장
    output_file = "travel_plan_result.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"💾 전체 결과가 '{output_file}'에 저장되었습니다.\n")
    
    # 9. 협업 로그 출력
    if "collaboration_log" in result:
        log = result["collaboration_log"]
        print("\n📊 협업 프로세스 요약:")
        print(f"   시작 시간: {log.get('start_time', 'N/A')}")
        print(f"   종료 시간: {log.get('end_time', 'N/A')}")
        
        # 시간 계산
        if log.get('start_time') and log.get('end_time'):
            from datetime import datetime
            start = datetime.fromisoformat(log['start_time'])
            end = datetime.fromisoformat(log['end_time'])
            duration = (end - start).total_seconds()
            print(f"   소요 시간: {duration:.1f}초")
        
        commands = log.get('mcp_commands', [])
        print(f"   총 명령 수: {len(commands)}")
        
        # 명령별 요약
        for cmd in commands:
            print(f"   • Command #{cmd['id']}: {cmd['command']} ({cmd['from']} → {cmd['to']})")
    
    print("\n" + "="*70)
    print("✨ 프로그램 종료")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()