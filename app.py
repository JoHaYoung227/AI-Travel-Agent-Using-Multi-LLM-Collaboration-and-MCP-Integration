from flask import Flask, render_template, request, jsonify, session
from datetime import datetime
import sys
import os
import json
from urllib.parse import quote

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from config import Config
    from agents.planner import PlannerAgent
    from agents.reviewer import ReviewerAgent
    from agents.stylist import StylistAgent 
    from tools.pinecone_tool import PineconeTool
    from mcp_server.server import MCPServer
    from tools.weather_tool import WeatherTool
    from tools.google_places_tool import GooglePlacesToolNew
    from tools.hotel_tool import AmadeusHotelTool
    from tools.flight_tool import AmadeusFlightTool
    import googlemaps
    SYSTEM_AVAILABLE = True
except ImportError as e:
    SYSTEM_AVAILABLE = False
    print(f"⚠️ Warning: Import failed - {e}")

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.secret_key = 'your-secret-key-here-change-this-to-random-string'  

# Global variables
mcp_server = None
planner = None
reviewer = None
hotel_tool = None
flight_tool = None
gmaps_client = None

def init_system():
    """Initialize system"""
    global mcp_server, planner, reviewer, hotel_tool, flight_tool, gmaps_client
    
    if not SYSTEM_AVAILABLE:
        return False
        
    if mcp_server is not None:
        return True
    
    try:
        Config.validate()

        try:
            gmaps_client = googlemaps.Client(key='AIzaSyCN8bgvjB0DvLgVvpk3GuNhvM_4auVgqH8')
            print("✅ Google Maps client initialized")
        except Exception as e:
            print(f"⚠️ Google Maps initialization failed: {e}")        
        
        pinecone_tool = PineconeTool(
            api_key=Config.PINECONE_API_KEY,
            index_name=Config.PINECONE_INDEX_NAME,
            embedding_model=Config.EMBEDDING_MODEL
        )
        pinecone_tool.initialize()
        
        planner = PlannerAgent()
        planner.initialize(Config.OPENAI_API_KEY)
        planner.load_templates()
        
        reviewer = ReviewerAgent(pinecone_tool)
        reviewer.initialize(Config.OPENAI_API_KEY)

        stylist = StylistAgent(pinecone_tool)
        stylist.initialize(Config.OPENAI_API_KEY)
        
        mcp_server = MCPServer()
        mcp_server.register_agent("planner", planner)
        mcp_server.register_agent("reviewer", reviewer)
        mcp_server.register_agent("stylist", stylist) 
        
        try:
            weather_tool = WeatherTool(api_key=Config.OPENWEATHER_API_KEY)
            mcp_server.register_tool("weather", weather_tool)
        except Exception as e:
            print(f"⚠️ WeatherTool registration failed: {e}")
        
        try:
            places_tool = GooglePlacesToolNew(api_key=Config.GOOGLE_PLACES_API_KEY)
            mcp_server.register_tool("places", places_tool)
        except Exception as e:
            print(f"⚠️ PlacesTool registration failed: {e}")
        
        # 🔥 호텔 툴 등록
        try:
            hotel_tool = AmadeusHotelTool(
                api_key=Config.AMADEUS_API_KEY,
                api_secret=Config.AMADEUS_API_SECRET
            )
            mcp_server.register_tool("hotel", hotel_tool)
            print("✅ HotelTool registered")
        except Exception as e:
            print(f"⚠️ HotelTool registration failed: {e}")
        
        # 🔥 항공권 툴 등록
        try:
            flight_tool = AmadeusFlightTool(
                api_key=Config.AMADEUS_API_KEY,
                api_secret=Config.AMADEUS_API_SECRET
            )
            mcp_server.register_tool("flight", flight_tool)
            print("✅ FlightTool registered")
        except Exception as e:
            print(f"⚠️ FlightTool registration failed: {e}")
        
        print("✅ System initialized")
        return True
        
    except Exception as e:
        print(f"System initialization error: {e}")
        return False
    
def get_place_coordinates(place_name, city):
    """장소 이름으로 좌표 검색"""
    global gmaps_client
    
    if not gmaps_client:
        return None
        
    try:
        query = f"{place_name}, {city}"
        result = gmaps_client.geocode(query)
        
        if result:
            location = result[0]['geometry']['location']
            return {
                'lat': location['lat'],
                'lng': location['lng']
            }
    except Exception as e:
        print(f"좌표 검색 실패: {place_name} - {e}")
    
    return None

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

cached_result = {}

def convert_to_krw(amount, currency):
    rate = Config.EXCHANGE_RATES.get(currency, 1.0)
    return int(amount * rate)

def format_price_with_krw(amount, currency):
    if not currency or currency == 'KRW':
        return f"{int(amount):,}원"
    krw_amount = convert_to_krw(amount, currency)
    return f"{int(amount):,} {currency} (약 {krw_amount:,}원)"

@app.route('/plan', methods=['POST'])
def plan():
    """Generate travel plan"""
    global cached_result

    try:
        origin = request.form.get('origin', 'Seoul')
        destination = request.form.get('destination', 'Tokyo')
        departure_date = request.form.get('departure_date')
        return_date = request.form.get('return_date')
        people = request.form.get('people', '2')
        budget = request.form.get('budget', '2000000')
        travel_style = request.form.get('travel_style', '')
        
        destination_en = destination
        print(f"DEBUG: destination_en = {destination_en}")
        
        if not departure_date or not return_date:
            return render_template('result.html', error="출발일과 도착일을 모두 선택해주세요.")
        
        dep_date = datetime.strptime(departure_date, "%Y-%m-%d")
        ret_date = datetime.strptime(return_date, "%Y-%m-%d")
        days = (ret_date - dep_date).days+1
        
        if days <= 0:
            return render_template('result.html', error="도착일은 출발일보다 이후여야 합니다.")
        
        if days > 14:
            return render_template('result.html', error="최대 14일까지만 계획할 수 있습니다.")
        
        if not init_system():
            return render_template('result.html', error="시스템 초기화 실패.")
        
        query = {
            "origin": origin,
            "destination": destination_en,
            "departure_date": departure_date,
            "return_date": return_date,
            "days": days,
            "people": int(people),
            "budget": int(budget),
            "travel_style": travel_style, 
            "preferences": {
                "location": "central location preferred",
                "room_quality": "high",
                "service": "friendly staff"
            }
        }
        
        result = mcp_server.process_travel_request(query)

        import json
        print("\n=== RAW WEATHER INFO DEBUG ===")
        print(json.dumps(result.get('weather_info', 'WEATHER INFO NOT FOUND'), indent=2, ensure_ascii=False))
        print("==============================")       
        print("\n=== Result Keys ===")
        print(list(result.keys()))
        
        # =======================================================
        # 1. 호텔 리뷰 데이터 파싱 개선
        # =======================================================
        hotel_reviews = []
        if result.get('hotel_analysis') and result['hotel_analysis'].get('recommendations'):
            for rec in result['hotel_analysis']['recommendations'][:3]:
                score = rec.get('overall_score', 0)
                if isinstance(score, str):
                    try:
                        score = float(score)
                    except:
                        score = 0
                
                hotel_reviews.append({
                    'name': rec.get('hotel', 'Hotel'),
                    'score': score,
                    'pros': ', '.join(rec.get('strengths', [])) or 'N/A', 
                    'cons': ', '.join(rec.get('weaknesses', [])) or 'N/A', 
                    'recommendation': rec.get('reason', 'N/A')
                })

        # =======================================================
        # 2. 장소 정보 파싱 개선
        # =======================================================
        places_info = result.get('places_info', {})
        places_tool_instance = None

        try:
            if mcp_server is not None and hasattr(mcp_server, 'tools'):
                places_tool_instance = mcp_server.tools.get("places")
            
            if places_tool_instance:
                # 관광지와 식당 정보 함께 가져오기
                from legacy.integration import TravelPlannerParser
                enhanced_places = TravelPlannerParser.get_attractions_with_restaurants(
                    destination_en, 
                    places_tool_instance
                )
                
                if enhanced_places.get('success'):
                    places_info = enhanced_places
                    print(f"✅ 관광지 {len(places_info['places'])}곳과 주변 식당 정보 조회 완료")
            
        except Exception as e:
            print(f"❌ 관광지/식당 정보 조회 실패: {e}")

        if places_info.get('success') and places_info.get('places'):
            processed_places = []
            
            for place in places_info['places']:
                place_id = place.get('place_id')
                place_name = place.get('name', 'Unknown')
                
                if place_id and places_tool_instance:
                    try:
                        details = places_tool_instance.get_place_details(place_id)
                        if details.get('success'):
                            photos = details.get('details', {}).get('photos', [])
                            if photos and len(photos) > 0:
                                photo_ref = photos[0].get('photo_reference')
                                if photo_ref:
                                    place['photo_url'] = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference={photo_ref}&key={Config.GOOGLE_PLACES_API_KEY}"
                                    print(f"✅ Photo URL 생성: {place_name} -> {place['photo_url'][:80]}")
                                else:
                                    print(f"⚠️ {place_name} - photo_reference 없음")
                            else:
                                print(f"⚠️ {place_name} - photos 배열 비어있음")
                        else:
                            print(f"⚠️ {place_name} - details API 실패")
                    except Exception as e:
                        print(f"❌ {place_name} details 조회 실패: {e}")
                else:
                    print(f"⚠️ {place_name} - place_id 없거나 places_tool_instance 없음")
                
                place['short_reviews'] = []
                processed_places.append(place)

            places_info['places'] = processed_places

        # =======================================================
        # 3. 날씨 정보 파싱 개선 - get_weather_for_dates 사용
        # =======================================================
        weather_info = {'success': False, 'data': {}, 'forecast': []}
        
        try:
            weather_tool_instance = WeatherTool(api_key=Config.OPENWEATHER_API_KEY)
            parts = destination_en.split(',')
            city_name = parts[0].strip() if len(parts) >= 2 else parts[0].strip()  # "파리" 추출 ✅
            country_code = None
        
            print(f"=== 날씨 API 호출 파라미터 ===")
            print(f"city_name: {city_name}")
            print(f"departure_date: {departure_date}")
            print(f"return_date: {return_date}")
            print(f"===========================")

            # 날짜 범위로 날씨 조회 (현재 날씨 + 예보)
            weather_result = weather_tool_instance.get_weather_for_dates(
                city=city_name,
                departure_date=departure_date,
                return_date=return_date,
                country_code=country_code
            )
            
            if weather_result.get('success'):
                weather_info['success'] = True
                weather_info['forecast'] = weather_result.get('forecast', [])
                weather_info['note'] = weather_result.get('note', "")
                
                # 현재 날씨도 별도로 조회
                current_weather_result = weather_tool_instance.get_current_weather(city_name, country_code)
                if current_weather_result.get('success'):
                    weather_info['data'] = current_weather_result.get('data', {})
                
                # 현재 날씨가 없으면 첫 번째 예보 데이터로 대체
                if not weather_info['data'] and weather_info['forecast']:
                    first_forecast = weather_info['forecast'][0]
                    weather_info['data'] = {
                        'temperature': first_forecast.get('temp_avg'),
                        'temp_min': first_forecast.get('temp_min'),
                        'temp_max': first_forecast.get('temp_max'),
                        'description': first_forecast.get('description', '정보 없음'),
                        'humidity': 0,
                        'wind_speed': 0
                    }
                
                print(f"✅ 날씨 정보 조회 성공: {len(weather_info['forecast'])}일 예보")
            else:
                print(f"⚠️ 날씨 조회 실패: {weather_result.get('error')}")
                
        except Exception as e:
            print(f"❌ 날씨 조회 중 오류: {e}")
            import traceback
            traceback.print_exc()
            
        # =======================================================
        # 4. 🔥 호텔 API 호출 및 데이터 보강 (링크 생성)
        # =======================================================
        hotels_data = result.get('hotel_info', {})
        
        if hotels_data.get('success'):
            for hotel in hotels_data.get('hotels', []):
                # Google Hotels 검색 링크 생성
                hotel_name = hotel.get('name', 'Hotel')
                city_code = hotel.get('city_code', destination_en.split(',')[0].strip())
                search_query = f"{hotel_name} {city_code} hotel booking"
                booking_url = f"https://www.google.com/search?q={quote(search_query)}&hl=ko&ibp=htl"
                hotel['booking_url'] = booking_url

                price = hotel.get('price', {})
                currency = price.get('currency', 'KRW')
                per_night = price.get('per_night', 0)
                total = price.get('total', 0)
                
                hotel['per_night_krw'] = convert_to_krw(per_night, currency)
                hotel['total_krw'] = convert_to_krw(total, currency)

        # =======================================================
        # 5. 🔥 항공권 API 호출 및 데이터 보강 (링크 생성)
        # =======================================================
        flights_data = result.get('flight_info', {})
        print("\n=== DEBUG: FLIGHTS DATA ===")
        import json
        if flights_data.get('success'):
            print(f"Flights Success: {len(flights_data.get('flights', []))} found.")
        else:
            print(f"Flights Failed: {flights_data.get('error', 'Unknown Error')}")
        print(json.dumps(flights_data, indent=2, ensure_ascii=False))
        print("==============================")
        
        if flights_data.get('success'):
            params = flights_data.get('search_params', {})
            origin_code = params.get('origin')
            destination_code = params.get('destination')
            departure_date = params.get('departure')
            return_date = params.get('return')
            
            # Google Flights 기본 쿼리 생성
            q = f"flights from {origin_code} to {destination_code} on {departure_date}"
            if return_date:
                q += f" return on {return_date}"
            booking_url = f"https://www.google.com/flights?q={quote(q.strip())}"
            
            for flight in flights_data.get('flights', []):
                # 모든 항공편에 동일한 기본 Google Flights 링크 주입
                flight['booking_url'] = booking_url

        final_plan = result.get('final_itinerary', result.get('initial_itinerary', {}))

        # 🔥 관광지 이미지 직접 검색
        if places_tool_instance and final_plan.get('itinerary'):
            for day in final_plan.get('itinerary', []):
                for attraction in day.get('attractions', []):
                    if not attraction.get('photo_url'):
                        attraction_name = attraction.get('name', '').strip()
                        try:
                            search_result = places_tool_instance.search_places(
                                query=f"{attraction_name} {destination_en}",
                                max_results=1
                            )
                            if search_result.get('success') and search_result.get('places'):
                                photo_url = search_result['places'][0].get('photo_url')
                                if photo_url:
                                    attraction['photo_url'] = photo_url
                                    print(f"✅ 관광지 이미지 검색: {attraction_name} -> {photo_url[:50]}...")
                        except Exception as e:
                            print(f"⚠️ {attraction_name} 이미지 검색 실패: {e}")

        # 🔥 식당 이미지 직접 검색
        if places_tool_instance and final_plan.get('itinerary'):
            for day in final_plan.get('itinerary', []):
                for meal in day.get('meals', []):
                    if not meal.get('photo_url'):
                        meal_name = meal.get('suggestion', '').strip()
                        restaurant_name = meal_name.split('-')[0].strip() if '-' in meal_name else meal_name
                        try:
                            search_result = places_tool_instance.search_places(
                                query=f"{restaurant_name} restaurant {destination_en}",
                                max_results=1
                            )
                            if search_result.get('success') and search_result.get('places'):
                                photo_url = search_result['places'][0].get('photo_url')
                                if photo_url:
                                    meal['photo_url'] = photo_url
                                    print(f"✅ 식당 이미지 검색: {restaurant_name} -> {photo_url[:50]}...")
                        except Exception as e:
                            print(f"⚠️ {restaurant_name} 이미지 검색 실패: {e}")

        try:
            if places_info.get('success') and places_info.get('places') and final_plan.get('itinerary'):
                # 1) places_info 에서 실제 식당 리스트 뽑기
                all_restaurants = []
                for place in places_info['places']:
                    place_name = place.get('name', '')
                    for r in (place.get('nearby_restaurants') or []):
                        all_restaurants.append({
                            "place_name": place_name,
                            "name": r.get("name", "식당"),
                            "rating": r.get("rating", "N/A"),
                            "photo_url": r.get("photo_url", "")
                        })

                # 2) placeholder 패턴 정의
                placeholder_patterns = [
                    "레스토랑 A", "레스토랑 B", "레스토랑 C", "레스토랑 D",
                    "Restaurant A", "Restaurant B", "Restaurant C", "Restaurant D",
                    "레스토랑 ", "Restaurant "
                ]

                # 3) day.meals 를 돌면서 placeholder 를 실제 식당으로 덮어쓰기
                rest_idx = 0
                for day in final_plan.get('itinerary', []):
                    meals = day.get('meals') or []
                    for meal in meals:
                        suggestion = (meal.get('suggestion') or "").strip()
                        # 너무 짧거나, 위 패턴이 포함된 경우 → 가짜 이름으로 판단
                        if any(pat in suggestion for pat in placeholder_patterns):
                            if rest_idx < len(all_restaurants):
                                r = all_restaurants[rest_idx]
                                rest_idx += 1
                                place_name = r.get("place_name", "관광지")
                                meal['suggestion'] = f"{r['name']} - 추천 메뉴 ( {place_name} 근처 )"
                                meal['photo_url'] = r.get('photo_url', '')
        except Exception as e:
            print(f"⚠️ 식당 이름 후처리 중 오류: {e}")
        
        # ----------------------------------------------------
        # 🔥 CRITICAL FIX: selected_flight 누락 시 API 데이터로 보강
        # ----------------------------------------------------
        selected_flight = final_plan.get('selected_flight', {}) 

        if flights_data.get('success') and flights_data.get('flights'):
            api_top_flight = flights_data['flights'][0]
            
            # LLM 응답에 필수 필드가 없으면 강제 주입 (LLM 응답을 덮어쓰기)
            if not selected_flight.get('outbound') or not selected_flight.get('inbound'):
                
                # API 데이터에서 상세 정보 추출
                out_dep_time = api_top_flight['outbound']['departure']['time'][11:16]
                out_arr_time = api_top_flight['outbound']['arrival']['time'][11:16]
                in_dep_time = api_top_flight['inbound']['departure']['time'][11:16]
                in_arr_time = api_top_flight['inbound']['arrival']['time'][11:16]
                
                selected_flight = {
                    "airline": ', '.join(api_top_flight.get('validating_airline_codes', ['N/A'])),
                    "price": api_top_flight['price']['total'],
                    "outbound": f"{api_top_flight['outbound']['departure']['airport']} {out_dep_time} → {api_top_flight['outbound']['arrival']['airport']} {out_arr_time}",
                    "inbound": f"{api_top_flight['inbound']['departure']['airport']} {in_dep_time} → {api_top_flight['inbound']['arrival']['airport']} {in_arr_time}",
                    "booking_url": flights_data.get('flights', [{}])[0].get('booking_url', '#')
                }
                final_plan['selected_flight'] = selected_flight # 최종 계획에 반영
                print("✅ CRITICAL FIX: 항공편 정보가 API 데이터로 강제 보강되었습니다.")

        # 🔥 CRITICAL FIX 2: 호텔 정보 & 일별 숙소 동기화
        # ----------------------------------------------------
        if hotels_data.get('success') and hotels_data.get('hotels'):
            api_top_hotel = hotels_data['hotels'][0]

            # 1) 가격 추출
            price_info = api_top_hotel.get('price', {}) or {}
            hotel_total = 0.0
            hotel_per_night = 0.0
            for key in ['total', 'base']:
                v = price_info.get(key)
                if v:
                    try:
                        hotel_total = float(v)
                        break
                    except (TypeError, ValueError):
                        pass
            
            v = price_info.get('per_night')
            if v:
                try:
                    hotel_per_night = float(v)
                except (TypeError, ValueError):
                    pass

            if hotel_per_night == 0.0 and hotel_total > 0:
                search_params = hotels_data.get('search_params', {}) or {}
                check_in_str = search_params.get('check_in')
                check_out_str = search_params.get('check_out')
                if check_in_str and check_out_str:
                    try:
                        from datetime import datetime as _dt
                        d1 = _dt.fromisoformat(check_in_str)
                        d2 = _dt.fromisoformat(check_out_str)
                        nights = max((d2 - d1).days, 1)
                        hotel_per_night = hotel_total / nights
                    except Exception:
                        hotel_per_night = hotel_total

            # 2) 공통으로 쓸 호텔 정보 정규화
            normalized_hotel = {
                "name": api_top_hotel.get("name", "추천 호텔"),
                "address": api_top_hotel.get("address", "주소 정보 없음"),
                "type": (
                    f"{api_top_hotel.get('rating')}성급 호텔"
                    if api_top_hotel.get('rating') not in [None, 'N/A']
                    else "호텔"
                ),
                "estimated_cost": hotel_total,
                "per_night_cost": hotel_per_night,
                "currency": price_info.get('currency', 'KRW'),
                "estimated_cost_krw": convert_to_krw(hotel_total, price_info.get('currency', 'KRW')),
                "per_night_cost_krw": convert_to_krw(hotel_per_night, price_info.get('currency', 'KRW')),
                "price_display": format_price_with_krw(hotel_total, price_info.get('currency', 'KRW')),
                "per_night_display": format_price_with_krw(hotel_per_night, price_info.get('currency', 'KRW')),
                "booking_url": api_top_hotel.get("booking_url", "#"),
            }
            # 3) selected_hotel 덮어쓰기
            final_plan["selected_hotel"] = normalized_hotel

            # 4) 일별 itinerary 안의 숙소도 이 호텔로 통일 (마지막 날 N/A는 그대로)
            if final_plan.get("itinerary"):
                for day_idx, day in enumerate(final_plan["itinerary"]):
                    acc = day.get("accommodation", {})

                    # 이미 "N/A"로 지운 마지막 날은 건드리지 않기
                    if not acc or acc.get("name") == "N/A":
                        continue

                    day["accommodation"] = {
                        "name": normalized_hotel["name"],
                        "address": normalized_hotel["address"],
                        "type": normalized_hotel["type"],
                        "estimated_cost": hotel_per_night,
                        "booking_url": normalized_hotel["booking_url"],
                    }

            print("✅ CRITICAL FIX 2: 호텔 정보가 API 데이터와 동기화되었습니다.")

        days = final_plan.get('days', 0) # Days 변수가 여기서 다시 정의되어야 함
        
        if days > 1 and final_plan.get('itinerary') and final_plan.get('selected_flight'):
            itinerary = final_plan['itinerary']
            selected_flight = final_plan['selected_flight']

            # 기본 booking_url 보정
            selected_flight['booking_url'] = flights_data.get('flights', [{}])[0].get('booking_url', '#')

            # 1. Day 1 (출국편) 정보 강제 주입
            if len(itinerary) > 0 and selected_flight.get('outbound'):
                day1_transport = itinerary[0]['transportation']

                # 🔧 예쁘게 표시될 수 있도록 outbound dict → 한 줄 텍스트로 변환
                outbound = selected_flight.get('outbound')
                details_text = "출국편 정보가 없습니다."
                booking_url = selected_flight.get('booking_url')

                if isinstance(outbound, dict):
                    airline = outbound.get('airline') or selected_flight.get('airline', '')
                    route = outbound.get('route', '')
                    dep = outbound.get('departure_time')
                    arr = outbound.get('arrival_time')

                    if isinstance(dep, str):
                        dep = dep.replace("T", " ")
                    if isinstance(arr, str):
                        arr = arr.replace("T", " ")

                    parts = []
                    if airline:
                        parts.append(airline)
                    if route:
                        parts.append(route)
                    time_part = " ~ ".join([x for x in [dep, arr] if x])
                    if time_part:
                        parts.append(time_part)

                    details_text = "출국편: " + " / ".join(parts)

                    # outbound 안에 booking_url 이 있으면 그걸 우선 사용
                    booking_url = outbound.get('booking_url', booking_url)
                elif outbound:
                    # 문자열인 경우 그대로 사용
                    details_text = f"출국편: {outbound}"

                # 비행기 타입인 경우에만 Day1 교통 정보 덮어쓰기
                if day1_transport.get('type') == '비행기':
                    itinerary[0]['transportation'] = {
                        "type": "비행기",
                        "cost": day1_transport.get('cost', selected_flight.get('price', 0)),
                        "details": details_text,
                        "airline": selected_flight.get('airline'),
                        "flight_number": selected_flight.get('flight_number', 'N/A'),
                        "booking_url": booking_url,
                    }
                    print("✅ CRITICAL FIX: Day1 교통 정보가 항공편 데이터로 정리되었습니다.")
                    
            # 2. 마지막 날 (귀국편) 정보 강제 주입
            last_day_index = days - 1 
            if len(itinerary) > last_day_index and selected_flight.get('inbound'):
                
                # 마지막 날 교통 정보 강제 주입
                itinerary[last_day_index]['transportation'] = {
                    "type": "비행기",
                    "cost": itinerary[last_day_index].get('transportation', {}).get('cost', 0),
                    "details": f"귀국편: {selected_flight['inbound']}", # 상세 정보 주입
                    "airline": selected_flight['airline'],
                    "flight_number": selected_flight.get('flight_number', 'N/A'),
                    "booking_url": selected_flight['booking_url']
                }
                
                # 마지막 날 숙소 제거 (숙박은 하지 않으므로)
                itinerary[last_day_index]['accommodation'] = {
                    "name": "N/A", 
                    "type": "N/A", 
                    "estimated_cost": 0, 
                    "address": "N/A"
                }
                selected_hotel = final_plan.get('selected_hotel', {})
                if selected_hotel.get('name'):
                    selected_hotel_name = selected_hotel['name']
                    selected_city = final_plan.get('destination', '').split(',')[0].strip()
                    search_query = f"{selected_hotel_name} {selected_city} hotel booking"
                    booking_url = f"https://www.google.com/search?q={quote(search_query)}&hl=ko&ibp=htl"
                    selected_hotel['booking_url'] = booking_url # 🔥 final_plan에 링크 주입 (숙소 상세 일정에서 사용)
                    
                    # Day 별 숙소에도 링크 주입 (선택된 호텔 정보와 일치하는 경우)
                    for day_data in itinerary:
                        if day_data.get('accommodation', {}).get('name') == selected_hotel_name:
                            day_data['accommodation']['booking_url'] = booking_url

                print(f"✅ CRITICAL FIX: Day {days}의 귀국편 비행기 정보가 성공적으로 주입되었습니다.")
            else:
                 print(f"⚠️ CRITICAL FIX 실패: Day {days}에 귀국편 정보를 주입할 수 없습니다. (데이터 부족)")


             # 🔥🔥🔥 8. CRITICAL FIX: Daily Cost 재계산 로직 추가 🔥🔥🔥
            for day in final_plan['itinerary']:
                current_day_cost = 0
                
                # 1. Transportation Cost
                transport_cost = day.get('transportation', {}).get('cost', 0)
                if isinstance(transport_cost, (int, float)):
                    current_day_cost += transport_cost
                
                # 2. Accommodation Cost
                # 마지막 날 숙소는 0이므로 안전하게 확인
                accommodation_cost = day.get('accommodation', {}).get('estimated_cost', 0)
                if isinstance(accommodation_cost, (int, float)):
                    current_day_cost += accommodation_cost
                
                # 3. Attractions Cost
                for activity in day.get('attractions', []):
                    attraction_cost = activity.get('estimated_cost', 0)
                    if isinstance(attraction_cost, (int, float)):
                        current_day_cost += attraction_cost
                
                day_total_from_llm = day.get('daily_cost', current_day_cost)
                
                if day_total_from_llm > current_day_cost:
                    current_day_cost = day_total_from_llm
                else:
                    pass 
                    
                day['daily_cost'] = int(current_day_cost) # 최종 daily_cost 업데이트

        # =======================================================
        # 4. 최종 결과 객체 구성
        # =======================================================

        places_data = []
        
        if final_plan and 'itinerary' in final_plan:
            for day_idx, day in enumerate(final_plan['itinerary'], 1):
                if 'attractions' in day:
                    for place in day['attractions']:
                        place_name = place.get('name', '')
                        if place_name:
                            coords = get_place_coordinates(place_name, destination_en)
                            if coords:
                                places_data.append({
                                    'day': day_idx,
                                    'name': place_name,
                                    'lat': coords['lat'],
                                    'lng': coords['lng']
                                })
        
        style_analysis = result.get('style_analysis', {})

        # ============================
        # 예산 요약 (항공 + 숙소 기준)
        # ============================
        user_budget = int(budget)

        # 1) 항공 총액
        flight_total = 0.0
        if flights_data and flights_data.get('success') and flights_data.get('flights'):
            try:
                flight_total = float(flights_data['flights'][0]['price']['total'])
            except Exception:
                flight_total = 0.0

        # 2) 숙소 총액
        hotel_total = 0.0

        # 🔥 우선순위 1: final_plan.selected_hotel.price.total 사용
        selected_hotel = final_plan.get("selected_hotel") or {}
        price_info = selected_hotel.get("price") or {}
        estimated_cost = selected_hotel.get("estimated_cost")

        # price.total → estimated_cost 순으로 먼저 사용
        for value in [price_info.get("total"), estimated_cost]:
            try:
                if value:
                    hotel_total = float(value)
                    break
            except (TypeError, ValueError):
                continue

        # 🔥 우선순위 2: 그래도 0이면 hotels_data 로 fallback
        if hotel_total == 0.0 and hotels_data and hotels_data.get("success") and hotels_data.get("hotels"):
            try:
                first_hotel = hotels_data["hotels"][0]
                pinfo = first_hotel.get("price", {})
                for key in ["total", "base"]:
                    if key in pinfo and pinfo[key]:
                        hotel_total = float(pinfo[key])
                        break
            except Exception:
                hotel_total = 0.0

        hotel_total_krw = convert_to_krw(hotel_total, selected_hotel.get('currency', 'KRW'))
        budget_base = flight_total + hotel_total_krw
        print(f"=== 숙소 가격 디버그 ===")
        print(f"hotel_total (원본): {hotel_total}")
        print(f"currency: {selected_hotel.get('currency', 'KRW')}")
        print(f"hotel_total_krw (변환): {hotel_total_krw}")
        print(f"flight_total: {flight_total}")
        print(f"budget_base: {budget_base}")
        print(f"====================")

        budget_summary = {
            "user_budget": user_budget,
            "total_cost": int(budget_base),
            "flight_total": int(flight_total),
            "hotel_total": int(hotel_total),
            "hotel_total_krw": hotel_total_krw,
            "hotel_currency": selected_hotel.get('currency', 'KRW'),
            "diff": user_budget - int(budget_base),
            "is_over": budget_base > user_budget,
        }

        if budget_summary["is_over"] and user_budget > 0:
            budget_summary["over_rate"] = round((budget_base - user_budget) / user_budget * 100, 1)
        else:
            budget_summary["over_rate"] = 0.0

        result_obj = {
            'final_plan': final_plan,
            'weather_info': weather_info, 
            'places_info': places_info,   
            'hotel_reviews': hotel_reviews,
            'hotels_data': hotels_data,
            'flights_data': flights_data,
            'style_info': style_analysis,
            'places_json': json.dumps(places_data)
        }

        cached_result = {
            'result': result_obj,
            'origin': origin,
            'destination': destination,
            'days': final_plan.get('days', days)
        }

        final_days = final_plan.get('days', days)
        
        return render_template('result.html',
                            final_plan=final_plan,
                            origin=origin,
                            destination=destination,
                            departure_date=departure_date,
                            return_date=return_date,
                            days=final_days,
                            budget_summary=budget_summary,
                            people=int(people),
                            budget=int(budget),
                            result=result_obj)
        
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print(traceback.format_exc())
        return render_template('result.html', error=f"오류: {str(e)}", result=None)
    
@app.route('/info')
def info():
    """추가 정보 페이지"""
    global cached_result
    
    try:
        if not cached_result:
            return render_template('info.html', error="여행 계획 데이터가 없습니다. 먼저 여행 계획을 생성해주세요.")
        
        return render_template('info.html',
                             origin=cached_result['origin'],
                             destination=cached_result['destination'],
                             result=cached_result['result'])
        
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print(traceback.format_exc())
        return render_template('info.html', error=f"오류: {str(e)}")

if __name__ == '__main__':
    print("="*70)
    print("🚀 AI Travel Planner Starting...")
    print("="*70)
    print("🌐 Access at: http://localhost:5000")
    print("="*70)
    
    app.run(host='0.0.0.0', port=5000, debug=True)