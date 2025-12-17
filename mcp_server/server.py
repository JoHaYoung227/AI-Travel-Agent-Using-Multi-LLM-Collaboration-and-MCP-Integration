"""
Multi-Agent Collaboration MCP Server (API Integration)
Command-based Protocol Implementation
Weather API and Google Places API Integration
"""
from typing import Dict, Any, List, Optional
import json
from datetime import datetime

class MCPServer:
    """Multi-Agent Collaboration Protocol Server with External API Integration"""
    
    def __init__(self):
        self.agents = {}
        self.tools = {}
        self.command_history = []
        self.collaboration_history = []
    
    def register_agent(self, agent_name: str, agent):
        """Register agent"""
        self.agents[agent_name] = agent
        print(f"ðŸ“ Agent '{agent_name}' registered")
    
    def register_tool(self, tool_name: str, tool):
        """Register external API tool"""
        self.tools[tool_name] = tool
        print(f"ðŸ”§ Tool '{tool_name}' registered")
    
    def send_command(
        self, 
        from_agent: str, 
        to_agent: str, 
        command: str, 
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send command between agents"""
        cmd = {
            "id": len(self.command_history) + 1,
            "from": from_agent,
            "to": to_agent,
            "command": command,
            "params": params,
            "timestamp": datetime.now().isoformat(),
            "status": "pending",
            "result": None
        }
        self.command_history.append(cmd)
        
        print(f"\nðŸ“‹ Command #{cmd['id']}: {from_agent} â†’ {to_agent}")
        print(f"   Action: {command}")
        print(f"   Params: {list(params.keys())}")
        
        return cmd
    
    def complete_command(self, command_id: int, status: str, result: Any = None):
        """Complete command processing"""
        for cmd in self.command_history:
            if cmd['id'] == command_id:
                cmd['status'] = status
                cmd['result'] = result
                cmd['completed_at'] = datetime.now().isoformat()
                print(f"   âœ… Command #{command_id} {status}")
                break
    
    def call_api_tool(self, tool_name: str, method: str, **kwargs) -> Dict:
        """
        Call external API tool
        
        Args:
            tool_name: Tool name (weather, places, etc)
            method: Method name (get_current_weather, search_places, etc)
            **kwargs: Arguments to pass to the method
            
        Returns:
            API call result
        """
        tool = self.tools.get(tool_name)
        if not tool:
            return {
                'success': False,
                'error': f"Tool '{tool_name}' not found"
            }
        
        try:
            method_func = getattr(tool, method)
            result = method_func(**kwargs)
            return result
        except AttributeError:
            return {
                'success': False,
                'error': f"Method '{method}' not found in tool '{tool_name}'"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Tool execution error: {str(e)}"
            }
    
    def process_travel_request(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process travel request with MCP protocol (API Integration)
        Command-based Agent Collaboration + External API
        """
        print(f"\n{'='*70}")
        print(f"ðŸŽ¯ MCP Server: Enhanced Agent Collaboration with External APIs")
        print(f"{'='*70}\n")
        
        collaboration_log = {
            "query": query,
            "mcp_commands": [],
            "api_calls": [],
            "start_time": datetime.now().isoformat()
        }
        
        # ============================================================
        # Command 0: System â†’ Weather API (GET_WEATHER_INFO)
        # ============================================================
        destination = query.get("destination", "")
        departure_date = query.get("departure_date")
        return_date = query.get("return_date")
        parts = destination.split(',')
        destination_city_only = parts[0].strip() if len(parts) >= 2 else parts[0].strip() 

        if destination and 'weather' in self.tools:
            print(f"\nðŸŒ¤ï¸ Getting weather info: {destination}")
            
            cmd_weather = self.send_command(
                from_agent="system",
                to_agent="weather_api",
                command="GET_WEATHER_INFO",
                params={"city": destination, "dates": f"{departure_date} ~ {return_date}"}
            )
            weather_tool_instance = self.tools.get('weather')
            
            if departure_date and return_date and weather_tool_instance:
                weather_result = self.call_api_tool(
                    'weather',
                    'get_weather_for_dates', # 기간별 날씨 조회 (최우선)
                    city=destination_city_only,
                    departure_date=departure_date,
                    return_date=return_date
                )
            else:
                weather_result = self.call_api_tool(
                    'weather',
                    'get_current_weather',
                    city=destination_city_only
                )
                
            if weather_result.get('success'):
                            # API가 반환한 예보 리스트
                            forecast_list = weather_result.get('forecast', [])
                            
                            # 여행 기간 계산
                            days_of_trip = query.get('days', 0)
                            
                            # 🔥 수정: 예보가 아예 없거나 (len == 0), 여행 기간보다 짧을 경우 추가 예보 요청
                            if days_of_trip > 0 and len(forecast_list) < days_of_trip:
                                print(f"⚠️  Forecast incomplete ({len(forecast_list)}/{days_of_trip} days). Requesting more data.")
                                
                                if weather_tool_instance:
                                    # 요청 일수를 전체 여행 일수로 설정
                                    days_to_request = days_of_trip 
                                    
                                    weather_forecast_result = self.call_api_tool(
                                        'weather',
                                        'get_forecast',
                                        city=destination_city_only,
                                        days=min(days_to_request, 5) # OpenWeatherMap의 5일 예보 제한 고려
                                    )
                                    
                                    if weather_forecast_result.get('success'):
                                        new_forecast = weather_forecast_result.get('forecast', [])
                                        
                                        # 기존 예보와 새 예보를 합치고 중복 제거 (날짜 기준)
                                        existing_dates = {f['date'] for f in forecast_list}
                                        
                                        for new_f in new_forecast:
                                            if new_f.get('date') not in existing_dates:
                                                forecast_list.append(new_f)
                                                existing_dates.add(new_f.get('date'))
                                        
                                        # 최종적으로 정렬
                                        forecast_list.sort(key=lambda x: x.get('date', ''))
                                    
                            weather_result['forecast'] = forecast_list # 업데이트된 리스트 저장

                            self.complete_command(cmd_weather['id'], 'completed', 'Weather data retrieved')
                            collaboration_log["weather_info"] = weather_result
                            print(f"   ✅ Weather info retrieved (Total days: {len(weather_result.get('forecast', []))})")

        flights_data = {}
        if 'flight' in self.tools:
            print(f"\n✈️ Searching flights: {query.get('origin')} → {destination_city_only}") # 로그 변경
            cmd_flight = self.send_command(
                from_agent="system", to_agent="flight_api", command="SEARCH_FLIGHTS",
                params={"origin": query.get('origin'), "destination": destination_city_only, # 🔥 클렌징된 destination 사용
                        "departure_date": query.get('departure_date'), "return_date": query.get('return_date'),
                        "adults": query.get('people', 2)}
            )
            flight_result = self.call_api_tool('flight', 'search_flights',
                origin=query.get('origin'), destination=destination_city_only, # 🔥 클렌징된 destination 사용
                departure_date=query.get('departure_date'), return_date=query.get('return_date'),
                adults=query.get('people', 2), max_results=3
            )
            if flight_result.get('success'):
                self.complete_command(cmd_flight['id'], 'completed', f"{len(flight_result.get('flights', []))} flights found")
                collaboration_log["flights_data"] = flight_result
                flights_data = flight_result

        hotels_data = {}
        if 'hotel' in self.tools:
            print(f"\n🏨 Searching hotels in {destination_city_only}") # 로그 변경
            cmd_hotel = self.send_command(
                from_agent="system", to_agent="hotel_api", command="SEARCH_HOTELS",
                params={"city": destination_city_only, "check_in_date": query.get('departure_date'), # 🔥 클렌징된 destination 사용
                        "check_out_date": query.get('return_date'), "adults": query.get('people', 2)}
            )
            hotel_result = self.call_api_tool('hotel', 'search_hotels',
                city=destination_city_only, check_in_date=query.get('departure_date'), # 🔥 클렌징된 destination 사용
                check_out_date=query.get('return_date'), adults=query.get('people', 2), max_results=5
            )
            if hotel_result.get('success'):
                self.complete_command(cmd_hotel['id'], 'completed', f"{len(hotel_result.get('hotels', []))} hotels found")
                collaboration_log["hotels_data"] = hotel_result
                hotels_data = hotel_result

        # ============================================================
        # Command 0: System → Stylist (ANALYZE_TRAVEL_STYLE) 🔥 NEW
        # ============================================================
        cmd_style = self.send_command(
            from_agent="system",
            to_agent="stylist", 
            command="ANALYZE_TRAVEL_STYLE",
            params={"query": query}
        )
        
        print(f"\n🎨 Executing Command #0: ANALYZE_TRAVEL_STYLE")
        stylist = self.agents.get("stylist")
        style_analysis = {}
        
        if stylist:
            style_result = stylist.process(query)
            if style_result.get("success"):
                style_analysis = style_result["data"]
                print(f"   ✅ Style: {style_analysis.get('style_name', 'Unknown')}")
                self.complete_command(cmd_style['id'], 'completed', f"Style: {style_analysis.get('style_name')}")
            else:
                self.complete_command(cmd_style['id'], 'failed', 'Style analysis failed')
        else:
            self.complete_command(cmd_style['id'], 'failed', 'Stylist agent not found')
        
        collaboration_log["style_analysis"] = style_analysis

        # ============================================================
        # Command 1: User Planner (CREATE_ITINERARY)
        # ============================================================
        cmd1 = self.send_command(
            from_agent="user",
            to_agent="planner",
            command="CREATE_ITINERARY",
            params={
                "origin": query.get("origin"),
                "destination": query.get("destination"),
                "days": query.get("days"),
                "people": query.get("people"),
                "budget": query.get("budget"),
                "weather_info": collaboration_log.get("weather_info")
            }
        )
        
        print(f"\nðŸ“ Executing Command #1: CREATE_ITINERARY")
        planner = self.agents.get("planner")
        if not planner:
            self.complete_command(cmd1['id'], 'failed', 'Planner agent not found')
            return {"error": "Planner agent not found"}
        
        planner_request = {
            "query": query,
            "style_info":style_analysis,
            "context": collaboration_log.get("weather_info"),
            "hotel_info": hotels_data,
            "flight_info": flights_data,
            "places_info": collaboration_log.get("places_info", {})
        }
        planner_response = planner.process(planner_request)
        initial_itinerary = planner_response.get("itinerary", {})
        
        self.complete_command(cmd1['id'], 'completed', 'Initial itinerary created')
        
        # ============================================================
        # Command 1.5: System → Google Places API (SEARCH_ATTRACTIONS)
        # ============================================================
        places_info = {}
        if 'places' in self.tools:
            print(f"\n📍 Getting place info with restaurants: {destination}")
            
            cmd_places = self.send_command(
                from_agent="system",
                to_agent="places_api",
                command="SEARCH_ATTRACTIONS",
                params={"query": destination, "destination": destination}
            )
            
            # 관광지 검색
            places_result = self.call_api_tool(
                'places',
                'search_places',
                query=f"tourist attractions in {destination}"
            )
            
            if places_result.get('success'):
                # 각 관광지마다 주변 식당 검색
                places = places_result.get('places', [])
                for place in places[:5]:  # 상위 5개만
                    place_id = place.get('place_id')
                    if place_id:
                        restaurants = self.call_api_tool(
                            'places',
                            'search_restaurants_near_place',
                            place_id=place_id,
                            radius=500
                        )
                        if restaurants.get('restaurants'):
                            for restaurant in restaurants['restaurants']:
                                if restaurant.get('photos') and len(restaurant['photos']) > 0:
                                    photo_ref = restaurant['photos'][0].get('photo_reference')
                                    if photo_ref:
                                        restaurant['photo_url'] = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference={photo_ref}&key={self.tools.get('places').api_key}"

                        place['nearby_restaurants'] = restaurants.get('restaurants', [])
                places_info = places_result
                self.complete_command(cmd_places['id'], 'completed', 'Places and restaurants retrieved')
                collaboration_log["places_info"] = places_info
                print(f"   ✅ {len(places)} places with restaurants retrieved")
            else:
                self.complete_command(cmd_places['id'], 'failed', places_result.get('error'))
        
        # ============================================================
        # Command 2: Planner â†’ Reviewer (ANALYZE_HOTELS)
        # ============================================================
        hotels = hotels_data.get('hotels', []) 

        cmd2 = self.send_command(
            from_agent="planner",
            to_agent="reviewer",
            command="ANALYZE_HOTELS",
            params={
                "hotels": hotels, # ⬅️ 이제 정의된 'hotels' 변수를 사용합니다.
                "preferences": query.get("preferences", {}),
                "requester": "planner"
            }
        )

        print(f"\n🗺️  Executing Command #2: ANALYZE_HOTELS ({len(hotels)} hotels)")
        reviewer = self.agents.get("reviewer")
        if not reviewer:
            self.complete_command(cmd2['id'], 'failed', 'Reviewer agent not found')
            return {"error": "Reviewer agent not found"}

        reviewer_request = {
            "hotels": hotels, # ⬅️ 이제 정의된 'hotels' 변수를 사용합니다.
            "preferences": query.get("preferences"),
            "destination": query.get("destination")
        }
        reviewer_response = reviewer.process(reviewer_request)

        hotel_analysis = {
            "analysis": reviewer_response.get("analysis", []),
            "recommendations": reviewer_response.get("recommendations", []),
            "top_pick": reviewer_response.get("recommendations", [{}])[0].get('hotel', 'N/A')
        }
        
        self.complete_command(
            cmd2['id'], 
            'completed', 
            f"{len(hotel_analysis.get('recommendations', []))} hotels analyzed"
        )
        
        # ============================================================
        # Command 3: Reviewer â†’ Planner (REQUEST_REFINEMENT)
        # ============================================================
        top_pick = hotel_analysis.get('top_pick', 'N/A')
        recommendations = hotel_analysis.get('recommendations', [])
        
        cmd3 = self.send_command(
            from_agent="reviewer",
            to_agent="planner",
            command="REQUEST_REFINEMENT",
            params={
                "analysis_summary": {
                    "top_pick": top_pick,
                    "total_analyzed": len(recommendations),
                    "recommendations": [r['hotel'] for r in recommendations]
                },
                "full_analysis": hotel_analysis,
                "weather_info": collaboration_log.get("weather_info"),
                "places_info": collaboration_log.get("places_info")
            }
        )
        
        print(f"\nðŸ“ Executing Command #3: REQUEST_REFINEMENT")
        print(f"   Reviewer's top pick: {top_pick}")
        
        refinement_prompt = self._create_refinement_prompt(
            initial_itinerary,
            hotel_analysis,
            collaboration_log.get("weather_info"),
            collaboration_log.get("places_info"),
            hotels_data,  
            flights_data   
        )
        
        final_response = planner.generate_response(
            refinement_prompt,
            system_context="Update the itinerary with hotel recommendations and API data. Respond in valid JSON format.",
            json_mode=True
        )
        
        try:
            final_itinerary = json.loads(final_response)
            self.complete_command(cmd3['id'], 'completed', 'Itinerary refined')
        except json.JSONDecodeError:
            print("âš ï¸  Final itinerary JSON parsing failed, using initial itinerary")
            final_itinerary = initial_itinerary
            self.complete_command(cmd3['id'], 'completed_with_warning', 'Used initial itinerary')
        
        # ============================================================
        # Collaboration Complete
        # ============================================================
        collaboration_log["end_time"] = datetime.now().isoformat()
        collaboration_log["mcp_commands"] = self.command_history
        self.collaboration_history.append(collaboration_log)
        
        print(f"\n{'='*70}")
        print(f"âœ… MCP Protocol Complete: {len(self.command_history)} commands executed")
        print(f"   - Weather API: {'âœ…' if collaboration_log.get('weather_info') else 'âŒ'}")
        print(f"   - Places API: {'âœ…' if collaboration_log.get('places_info') else 'âŒ'}")
        print(f"{'='*70}\n")
        
        return {
            "query": query,
            "style_analysis": style_analysis, 
            "initial_itinerary": initial_itinerary,
            "hotel_analysis": hotel_analysis,
            "final_itinerary": final_itinerary,
            "weather_info": collaboration_log.get("weather_info"),
            "places_info": collaboration_log.get("places_info"),
            "hotel_info": hotels_data,  
            "flight_info": flights_data,
            "collaboration_log": collaboration_log
        }
    
    def _create_refinement_prompt(
            self,
            initial_itinerary: Dict,
            hotel_analysis: Dict,
            weather_info: Optional[Dict] = None,
            places_info: Optional[Dict] = None,
            hotels_data: Optional[Dict] = None, 
            flights_data: Optional[Dict] = None 
        ) -> str:
            """Create refinement prompt for final itinerary (with API data and scoring)"""
            
            prompt = """당신은 여행 일정 최종 검토 전문가입니다. Planner가 작성한 초안을 검토하고, Reviewer의 호텔 분석과 API 데이터를 반영하여 최적의 여행 일정을 완성하세요.

    **Planner의 초안 일정:**
    """
            prompt += json.dumps(initial_itinerary, indent=2, ensure_ascii=False)
            
            prompt += "\n\n**Reviewer의 호텔 분석:**\n"
            prompt += json.dumps(hotel_analysis, indent=2, ensure_ascii=False)
            
            # 항공편 API 원본 데이터 포맷팅
            if flights_data and flights_data.get('success'):
                prompt += "\n\n**사용 가능한 항공편 리스트:**\n"
                for i, flight in enumerate(flights_data.get('flights', [])[:3], 1):
                    airlines = ', '.join(flight.get('validating_airline_codes', ['N/A']))
                    # API에서 오는 데이터에 더 충실하도록 출력 포맷 변경 (출발/도착 시간 포함)
                    out = flight.get('outbound', {})
                    inb = flight.get('inbound', {})
                    
                    prompt += f"\n{i}. {airlines}\n"
                    prompt += f"   가격: {flight['price']['currency']} {flight['price']['total']:,.0f}\n"
                    if out.get('departure'):
                        prompt += f"   가는편: {out['departure']['airport']} {out['departure']['time'][:16]} → {out['arrival']['airport']} {out['arrival']['time'][:16]}\n"
                    if inb.get('departure'):
                        prompt += f"   오는편: {inb['departure']['airport']} {inb['departure']['time'][:16]} → {inb['arrival']['airport']} {inb['arrival']['time'][:16]}\n"
            
            # 호텔 API 원본 데이터 포맷팅
            if hotels_data and hotels_data.get('success'):
                prompt += "\n\n**사용 가능한 호텔 리스트:**\n"
                for i, hotel in enumerate(hotels_data.get('hotels', [])[:3], 1):
                    prompt += f"\n{i}. {hotel['name']}\n"
                    prompt += f"   주소: {hotel['address']}\n"
                    prompt += f"   1박 평균: {hotel['price']['currency']} {hotel['price']['per_night']:,.0f}\n"
                    prompt += f"   총액: {hotel['price']['currency']} {hotel['price']['total']:,.0f}\n"
                    if hotel.get('rating') and hotel['rating'] != 'N/A':
                        prompt += f"   등급: {hotel['rating']}성급\n"
            
            # Add weather info
            if weather_info:
                prompt += "\n\n**날씨 정보:**\n"
                if 'forecast' in weather_info and weather_info.get('forecast'):
                    prompt += "예보:\n"
                    for day in weather_info.get('forecast', []):
                        prompt += f"  - {day['date']}: {day['temp_min']}~{day['temp_max']}°C, {day['description']}\n"
                elif weather_info.get('data'):
                    current = weather_info['data']
                    prompt += f"현재: {current['temperature']}°C, {current['description']}\n"
            
            # Add place info
            if places_info and places_info.get('success'):
                prompt += "\n\n**추천 관광지 (Google Places API):**\n"
                for i, place in enumerate(places_info.get('places', [])[:5], 1):
                    prompt += f"{i}. {place['name']} (평점: {place['rating']}/5.0)\n"
                    prompt += f"   위치: {place.get('address', place.get('vicinity', 'N/A'))}\n"

            is_round_trip = flights_data and flights_data.get('search_params', {}).get('return')

            prompt += """

    **최종 일정 작성 지침:**

    1. **일정의 무결성 보장 (CRITICAL):**
    - Day 1에는 반드시 **출국편 (가는 편)** 비행기 정보를 포함하세요.
    """
            # 🔥 CRITICAL: 귀국편 일정 누락 방지 지침 추가
            if is_round_trip:
                prompt += f"    - **Day {initial_itinerary.get('days', 3)} (마지막 날)**에는 반드시 **귀국편 (오는 편)** 비행기 정보를 포함하고, 해당 Day의 숙소는 생략하세요.\n"
            
            prompt += """
    - **귀국일 일정 조정 (CRITICAL):** 마지막 날 일정은 선택된 **귀국편의 출발 시간(Departure Time)**에 맞춰 조정해야 합니다. 출발 시간 **3시간 전**에 공항에 도착하는 것을 기준으로 하여, 그 전까지 소화 가능한 관광지를 배치하세요.\n
    
    2. **고정 비용 배분 규칙 (CRITICAL FIX):**
    - **항공권 비용:** 항공권 총액(왕복)은 **Day 1의 교통비** 항목에 **전액**을 반영하세요. (현재 LLM의 동작 방식 유지)
    - **숙박 비용:** 총 숙박 비용은 **각 숙박일**에 **균등하게 분배**하여 `accommodation` 항목의 `estimated_cost`에 반영하세요. (이미 LLM이 잘 하고 있을 가능성이 높지만 명시적으로 지시)
    - **귀국일 교통비 (Day 3):** 마지막 날의 교통비는 항공권 총액이 아니라, **호텔에서 공항까지 이동하는 대중교통 예상 비용**만 배분하세요. (₩5,000 ~ ₩15,000 수준)
    
    3. **예산 검증 및 잔액 활용:**
    - 총 예산(₩{query.get('budget', 2000000)})에서 항공권과 숙박비를 뺀 **잔액**으로 일일 관광, 식비, 기타 교통비를 **합리적으로 배분**하세요.
    -  항공 + 호텔 + 식사 + 관광 비용 합산이 **최종 예산(₩{query.get('budget', 2000000)})을 절대 초과할 수 없습니다.**
    - 항공 + 호텔 + 식사 + 관광 비용 합산
    - 예산 초과 시 조정 (저렴한 항공편/호텔 선택 또는 관광지 축소)
    - budget_breakdown 섹션에 상세 내역 작성

    4. **일일 비용 상세화 (CRITICAL FIX):**
    - **교통 (대중교통):** 각 Day의 `attractions` 간 이동에 필요한 **일일 대중교통 예상 비용**을 ₩5,000 ~ ₩15,000 수준으로 현실적으로 책정하여 `transportation` 항목에 반영하세요. (Day 2의 ₩2000과 같은 비현실적인 값을 피하도록 지시)
    - 각 Day마다 일일 예산(`daily_cost`)을 계산하여 **모든 항목 비용의 합계와 정확히 일치**하도록 하세요.

    5. **항공편 통합:**
        - Planner가 선택한 항공편을 확인하고, 예산/일정에 더 적합한 항공편이 있다면 변경하세요
        - Day 1의 transportation에 구체적인 항공편 정보 포함 (항공사, 출발시간, 도착시간, 가격)
        - **직항 우선 원칙 (CRITICAL):** 예산 초과가 크지 않다면 (전체 예산의 5% 미만), **반드시 직항 항공편을 우선적으로 선택**하세요. 직항이 없거나 예산 초과 폭이 클 때만 경유 항공편을 고려하세요. # ⬅️ 직항 우선 지침 추가

    6. **호텔 통합:**
    - Reviewer의 호텔 분석에서 top_pick 호텔을 우선 고려하세요
    - 호텔 리스트에서 실제 호텔명, 주소, 1박 가격을 정확히 반영하세요
    - 각 Day의 accommodation에 선택한 호텔의 구체적 정보 포함
    
    7. **관광지 최적화:**
    - Google Places API의 추천 관광지를 일정에 통합하세요
    - 각 관광지에 name, description, estimated_cost, reason 포함
    - 날씨를 고려하여 실내/실외 활동 균형 맞추기

    6. **품질 보장:**
    - 모든 정보는 한국어로 작성
    - 각 Day마다 일일 예산(daily_cost) 계산
    - Reviewer의 피드백을 반영한 개선사항 명시

    **JSON 출력 형식:**
    - 반드시 완전한 JSON 형식으로 출력하세요
    - selected_flight, selected_hotel, budget_breakdown 섹션 포함 필수
    - 각 Day의 attractions는 배열 형태로 상세 정보 포함

    이제 최적화된 최종 여행 일정을 JSON 형식으로 출력하세요:
    """
            
            return prompt
    
    def get_status(self) -> Dict[str, Any]:
        """Get server status"""
        return {
            "registered_agents": list(self.agents.keys()),
            "registered_tools": list(self.tools.keys()),
            "total_commands": len(self.command_history),
            "collaboration_count": len(self.collaboration_history)
        }
    
    def print_command_summary(self):
        """Print command history summary"""
        print("\n" + "="*70)
        print("ðŸ“Š MCP Command History Summary")
        print("="*70)
        
        for cmd in self.command_history:
            status_emoji = "âœ…" if cmd['status'] == 'completed' else "âš ï¸"
            print(f"\n{status_emoji} Command #{cmd['id']}")
            print(f"   {cmd['from']} â†’ {cmd['to']}: {cmd['command']}")
            print(f"   Status: {cmd['status']}")
            if cmd.get('result'):
                print(f"   Result: {cmd['result']}")
        
        print("\n" + "="*70 + "\n")
