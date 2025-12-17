"""
Amadeus Flight Search API 도구 - 최종 안정화 버전
항공권 검색, 가격 비교, Google Flights 예약 링크 제공
- 중복 여정 제거 로직 추가
- Google Flights 링크 안정화 (가장 보편적인 쿼리 포맷 사용)
"""
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from urllib.parse import quote

class AmadeusFlightTool:
    """Amadeus API를 사용한 항공권 검색 도구"""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.amadeus.com/v2"
        self.access_token = None
        self.token_expires_at = None
        self.airport_cache = {}  # 검색한 공항 코드 캐싱
    
    def search_airport_code(self, city_or_airport: str) -> Optional[str]:
        # 1. 🔥 CRITICAL FIX: 풀네임을 그대로 먼저 확인 (새로 추가한 매핑 사용)
        fallback_full = AIRPORT_CODE_MAP.get(city_or_airport)
        if fallback_full:
            self.airport_cache[city_or_airport] = fallback_full
            print(f"✅ '{city_or_airport}' → {fallback_full} (하드코딩 풀네임 매핑 사용)")
            return fallback_full
            
        # 2. 키워드를 클렌징합니다. (예: "서울, 인천공항" -> "서울")
        cleaned_keyword = city_or_airport.split(',')[0].strip()
        
        """
        도시명/공항명으로 IATA 코드 검색 (하드코딩 우선, API는 보조)
        """
        # 1. 캐시 확인 및 IATA 코드 형식 체크
        if city_or_airport in self.airport_cache:
            return self.airport_cache[city_or_airport]
        
        if len(city_or_airport) == 3 and city_or_airport.isupper():
            self.airport_cache[city_or_airport] = city_or_airport
            print(f"✅ '{city_or_airport}'는 IATA 코드로 바로 사용됩니다.")
            return city_or_airport

        # 2. 🔥 하드코딩 매핑을 가장 먼저 확인하여 API 오류 우회!
        fallback_code = AIRPORT_CODE_MAP.get(cleaned_keyword)
        if fallback_code:
            self.airport_cache[cleaned_keyword] = fallback_code
            print(f"✅ '{cleaned_keyword}' → {fallback_code} (하드코딩 매핑 사용)")
            return fallback_code

        # 3. API 동적 검색 시도 (매핑에 없는 새로운 도시일 경우)
        try:
            token = self._get_access_token()
            
            url = "https://api.amadeus.com/v1/reference-data/locations"
            headers = {'Authorization': f'Bearer {token}'}
            params = {
                'keyword': cleaned_keyword,
                'subType': 'AIRPORT,CITY', # AIRPORT와 CITY 모두 검색
                'page[limit]': 5
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                # 🔥 공항 검색 단계 에러 디버그
                print("⚠️  공항 코드 검색 HTTPError:")
                print("  URL:", response.url)
                print("  Status Code:", response.status_code)
                print("  Body:", response.text)
                return None
            
            data = response.json()
            locations = data.get('data', [])
            
            if locations:
                # 개선된 로직: AIRPORT 타입을 우선하여 찾습니다.
                airport_match = next((loc for loc in locations if loc.get('subType') == 'AIRPORT'), None)
                city_match = next((loc for loc in locations if loc.get('subType') == 'CITY'), None)
                
                best_match = airport_match if airport_match else city_match
            
                if best_match and best_match.get('iataCode'):
                    iata_code = best_match.get('iataCode')
                    self.airport_cache[city_or_airport] = iata_code
                    print(f"✅ '{city_or_airport}' → {iata_code} (API 검색 사용)")
                    return iata_code
                
                print(f"⚠️  '{city_or_airport}'에 대한 공항을 API에서 찾을 수 없습니다.")
                return None
            
            print(f"⚠️  '{city_or_airport}'에 대한 공항 데이터를 받지 못했습니다.")
            return None
            
        except Exception as e:
            # API 요청 자체에 문제가 생긴 경우 (400 Bad Request 등)
            print(f"⚠️  공항 코드 검색 실패 (API 요청 오류): {str(e)}")
            return None

    def _get_access_token(self) -> str:
        """
        OAuth 2.0 액세스 토큰 발급
        토큰은 30분간 유효하며, 만료되면 자동 갱신
        """
        # 토큰이 유효하면 재사용
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at:
                return self.access_token
        
        try:
            url = "https://api.amadeus.com/v1/security/oauth2/token"
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.api_key,
                'client_secret': self.api_secret
            }
            
            response = requests.post(url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            self.access_token = result['access_token']
            
            # 토큰 만료 시간 설정 (30분 - 1분 여유)
            expires_in = result.get('expires_in', 1799)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            return self.access_token
            
        except Exception as e:
            raise Exception(f"액세스 토큰 발급 실패: {str(e)}")
    
    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        adults: int = 1,
        travel_class: str = "ECONOMY",
        currency: str = "KRW",
        max_results: int = 10,
        non_stop: bool = False
    ) -> Dict:
        """
        항공권 검색
        """
        try:
            # 1. IATA 코드 변환
            origin_code = self.search_airport_code(origin)
            destination_code = self.search_airport_code(destination)
            
            if not origin_code or not destination_code:
                return {'success': False, 'error': f"출발지/목적지 공항 코드를 찾을 수 없습니다."}
            
            token = self._get_access_token()
            url = f"{self.base_url}/shopping/flight-offers"
            
            headers = {'Authorization': f'Bearer {token}'}
            
            params = {
                'originLocationCode': origin_code,
                'destinationLocationCode': destination_code,
                'departureDate': departure_date,
                'adults': adults,
                'currencyCode': currency,
                'max': min(max_results * 5, 250),  # 중복 제거를 위해 API 최대 250개 요청
                'travelClass': travel_class
            }
            
            if return_date:
                params['returnDate'] = return_date
            
            if non_stop:
                params['nonStop'] = 'true'
            
            # 🔥 디버그용: 실제 요청 URL 출력
            print("🔍 Amadeus FlightOffers 요청:")
            print("  URL:", url)
            print("  Params:", params)

            response = requests.get(url, headers=headers, params=params, timeout=20)

            # 🔥 HTTPError 디버그 (400 에러 내용까지 보기)
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                print("❌ Flight API HTTPError 발생")
                print("  URL:", response.url)
                print("  Status Code:", response.status_code)
                print("  Response Body:", response.text)
                # 사용자에게도 어느 정도 정보 전달
                return {
                    'success': False,
                    'error': f"Amadeus Flight API 오류 {response.status_code}: {response.text}"
                }
            
            data = response.json()
            
            # 🔥 중복 제거를 위한 딕셔너리
            unique_flights = {} 
            
            for offer in data.get('data', []):
                itineraries = offer.get('itineraries', [])
                
                # 1. 여정 정보 파싱
                flight_info = {
                    'offer_id': offer.get('id', ''),
                    'price': {
                        'total': float(offer['price']['total']),
                        'currency': offer['price']['currency'],
                        'per_person': float(offer['price']['total']) / adults
                    },
                    'outbound': self._parse_itinerary(itineraries[0]) if itineraries else None,
                    'inbound': self._parse_itinerary(itineraries[1]) if len(itineraries) > 1 else None,
                    'seats_available': offer.get('numberOfBookableSeats', 'N/A'),
                    'instant_ticketing': offer.get('instantTicketingRequired', False),
                    'validating_airline_codes': offer.get('validatingAirlineCodes', [])
                }
                
                # 2. 🔥 중복 체크 키 생성: 가는 편 출발 시간 + 오는 편 출발 시간 + 총액
                out_dep = flight_info['outbound']['departure']['time'] if flight_info['outbound'] else ""
                in_dep = flight_info['inbound']['departure']['time'] if flight_info['inbound'] else ""
                
                # 가격은 반올림된 가격을 사용하여 그룹화 (API 오퍼가 가격만 미세하게 다를 수 있음)
                price_key = round(flight_info['price']['total'], 0) 
                
                # (가는 편 출발 시간 | 오는 편 출발 시간 | 총액)을 결합
                unique_key = f"{out_dep}|{in_dep}|{price_key}"
                
                if unique_key not in unique_flights:
                    unique_flights[unique_key] = flight_info
            
            flights = list(unique_flights.values())
            
            # 가격순 정렬
            flights.sort(key=lambda x: x['price']['total'])
            
            return {
                'success': True,
                'count': len(flights),
                'flights': flights[:max_results], # 중복 제거 후 최종 결과 수로 슬라이싱
                'search_params': {
                    'origin': origin_code,
                    'destination': destination_code,
                    'departure': departure_date,
                    'return': return_date,
                    'adults': adults,
                    'class': travel_class
                }
            }
            
        except requests.exceptions.RequestException as e:
            # 🔥 네트워크/요청 관련 에러 디테일 출력
            resp = getattr(e, "response", None)
            if resp is not None:
                print("❌ Flight API Request Error DETAIL:")
                print("  URL:", resp.url)
                print("  Status Code:", resp.status_code)
                print("  Body:", resp.text)
            else:
                print(f"❌ Flight API Request Error: {str(e)}")
            return {'success': False, 'error': f"API 요청 실패: {str(e)}"}
        except Exception as e:
            print(f"❌ Flight API Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': f"항공권 검색 실패: {str(e)}"}
        
    def _parse_itinerary(self, itinerary: Dict) -> Dict:
        """여정(itinerary) 파싱"""
        segments = itinerary.get('segments', [])
        if not segments: return {}
        
        first_segment = segments[0]
        last_segment = segments[-1]
        
        duration_formatted = self._format_duration(itinerary.get('duration', 'N/A'))
        stops = len(segments) - 1
        layovers = []
        
        for i in range(len(segments) - 1):
            current_arrival = segments[i]['arrival']['at']
            next_departure = segments[i + 1]['departure']['at']
            layover_duration = self._calculate_layover(current_arrival, next_departure)
            layover_airport = segments[i]['arrival']['iataCode']
            layovers.append({'airport': layover_airport, 'duration': layover_duration})
        
        return {
            'departure': {
                'airport': first_segment['departure']['iataCode'],
                'time': first_segment['departure']['at']
            },
            'arrival': {
                'airport': last_segment['arrival']['iataCode'],
                'time': last_segment['arrival']['at']
            },
            'duration': duration_formatted,
            'stops': stops,
            'layovers': layovers,
            'segments': [
                {'carrier': seg['carrierCode']}
                for seg in segments
            ]
        }
    
    def _format_duration(self, duration: str) -> str:
        """ISO 8601 duration을 읽기 쉬운 형식으로 변환"""
        if not duration or duration == 'N/A':
            return 'N/A'
        try:
            duration = duration.replace('PT', '')
            hours = 0
            minutes = 0
            
            if 'H' in duration:
                hours_str = duration.split('H')[0]
                hours = int(hours_str)
                duration = duration.split('H')[1]
            
            if 'M' in duration:
                minutes_str = duration.split('M')[0]
                minutes = int(minutes_str)
            
            parts = []
            if hours > 0: parts.append(f"{hours}시간")
            if minutes > 0: parts.append(f"{minutes}분")
            
            return " ".join(parts) if parts else 'N/A'
        except:
            return 'N/A'
    
    def _calculate_layover(self, arrival_time: str, departure_time: str) -> str:
        """경유 대기 시간 계산"""
        try:
            arrival = datetime.fromisoformat(arrival_time.replace('Z', '+00:00'))
            departure = datetime.fromisoformat(departure_time.replace('Z', '+00:00'))
            
            diff = departure - arrival
            total_seconds = diff.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            
            parts = []
            if hours > 0: parts.append(f"{hours}시간")
            if minutes > 0: parts.append(f"{minutes}분")
            
            return " ".join(parts) if parts else '1분 미만'
        except:
            return "N/A"
    
    def format_flights_for_travel(self, flights_data: Dict, top_n: int = 5) -> str:
        """
        여행 계획을 위한 항공권 정보 포맷팅
        """
        if not flights_data.get('success'):
            return f"❌ 항공권 정보를 가져올 수 없습니다: {flights_data.get('error', 'Unknown error')}"
        
        flights = flights_data.get('flights', [])[:top_n]
        
        if not flights:
            return "❌ 검색 결과가 없습니다."
        
        search_params = flights_data.get('search_params', {})
        
        result = f"✈️ 추천 항공권 ({len(flights)}개)\n"
        result += f"🛫 {search_params.get('origin')} → {search_params.get('destination')}\n"
        result += f"📅 출발: {search_params.get('departure')}\n"
        if search_params.get('return'):
            result += f"📅 귀국: {search_params.get('return')}\n"
        result += f"👥 성인 {search_params.get('adults')}명 · {search_params.get('class')}\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, flight in enumerate(flights, 1):
            result += f"{i}. "
            
            airlines = flight.get('validating_airline_codes', [])
            if airlines:
                result += f"**{', '.join(airlines)}**\n"
            
            price = flight['price']
            result += f"   💰 {price['currency']} {price['total']:,.0f}"
            if search_params.get('adults', 1) > 1:
                result += f" (1인당 약 {price['per_person']:,.0f}원)"
            result += "\n"
            
            # 가는 편
            if flight.get('outbound'):
                outbound = flight['outbound']
                result += f"\n   🛫 **가는 편**\n"
                result += f"      {outbound['departure']['airport']} {outbound['departure']['time'][:16]}\n"
                
                # 왕복일 경우 총 비행 시간 대신 여정 정보 출력 (중복 방지)
                duration_text = outbound['duration']
                if outbound['stops'] > 0:
                    duration_text += f" (경유 {outbound['stops']}회)"
                else:
                    duration_text += " (직항)"
                    
                result += f"      ↓ {duration_text}\n"

                for layover in outbound['layovers']:
                    result += f"      • {layover['airport']} 대기 {layover['duration']}\n"
                
                result += f"      {outbound['arrival']['airport']} {outbound['arrival']['time'][:16]}\n"
            
            # 오는 편
            if flight.get('inbound'):
                inbound = flight['inbound']
                result += f"\n   🛬 **오는 편**\n"
                result += f"      {inbound['departure']['airport']} {inbound['departure']['time'][:16]}\n"
                
                duration_text = inbound['duration']
                if inbound['stops'] > 0:
                    duration_text += f" (경유 {inbound['stops']}회)"
                else:
                    duration_text += " (직항)"
                    
                result += f"      ↓ {duration_text}\n"

                for layover in inbound['layovers']:
                    result += f"      • {layover['airport']} 대기 {layover['duration']}\n"
                
                result += f"      {inbound['arrival']['airport']} {inbound['arrival']['time'][:16]}\n"
            
            # 좌석 수
            if flight['seats_available'] != 'N/A':
                result += f"\n   💺 잔여석 {flight['seats_available']}석\n"

            # ------------------------------------------------------------------
            # Google Flights 링크 생성 (최종 안정화 버전)
            # ------------------------------------------------------------------
            origin_code = search_params.get('origin')
            destination_code = search_params.get('destination')
            departure_date = search_params.get('departure')
            return_date = search_params.get('return')
            
            # 쿼리: flights from [출발지] to [도착지] on [출발일] [return on [귀국일]]
            q = f"flights from {origin_code} to {destination_code} on {departure_date}"
            if return_date:
                q += f" return on {return_date}"
            
            booking_url = f"https://www.google.com/flights?q={quote(q.strip())}"

            # ------------------------------------------------------------------

            result += f"\n   🔗 [Google Flights에서 예약 및 가격 확인]({booking_url})"
            result += "\n\n"
        
        return result


AIRPORT_CODE_MAP = {
   # 🇰🇷 한국
    '서울': 'ICN', '인천': 'ICN', '김포': 'GMP', '서울, 인천공항': 'ICN',
    'Seoul': 'ICN', 'Incheon': 'ICN', 'Gimpo': 'GMP',
    '부산': 'PUS', 'Busan': 'PUS',
    '제주': 'CJU', 'Jeju': 'CJU',
    '대구': 'TAE', 'Daegu': 'TAE',
    '한국': 'ICN', 'Korea': 'ICN',
    
    # 🇯🇵 일본
    '도쿄': 'NRT', 'Tokyo': 'NRT', '나리타': 'NRT', '하네다': 'HND',
    'Haneda': 'HND', '일본': 'NRT', 'Japan': 'NRT',
    '오사카': 'KIX', 'Osaka': 'KIX', '간사이': 'KIX',
    '교토': 'KIX', 'Kyoto': 'KIX',
    '후쿠오카': 'FUK', 'Fukuoka': 'FUK',
    '삿포로': 'CTS', 'Sapporo': 'CTS',
    '나고야': 'NGO', 'Nagoya': 'NGO',
    '오키나와': 'OKA', 'Okinawa': 'OKA', '나하': 'OKA',
    '고베': 'UKB', 'Kobe': 'UKB',
    '센다이': 'SDJ', 'Sendai': 'SDJ',
    '히로시마': 'HIJ', 'Hiroshima': 'HIJ',
    '가고시마': 'KOJ', 'Kagoshima': 'KOJ',
    
    # 🇨🇳 중국
    '베이징': 'PEK', 'Beijing': 'PEK', '북경': 'PEK',
    '상하이': 'PVG', 'Shanghai': 'PVG',
    '광저우': 'CAN', 'Guangzhou': 'CAN',
    '선전': 'SZX', 'Shenzhen': 'SZX',
    '청두': 'CTU', 'Chengdu': 'CTU',
    '시안': 'XIY', 'Xian': 'XIY',
    '항저우': 'HGH', 'Hangzhou': 'HGH',
    '충칭': 'CKG', 'Chongqing': 'CKG',
    '쿤밍': 'KMG', 'Kunming': 'KMG',
    '하얼빈': 'HRB', 'Harbin': 'HRB',
    '우한': 'WUH', 'Wuhan': 'WUH',
    '중국': 'PEK', 'China': 'PEK',
    
    # 🇭🇰🇲🇴🇹🇼
    '홍콩': 'HKG', 'Hong Kong': 'HKG',
    '마카오': 'MFM', 'Macau': 'MFM',
    '타이베이': 'TPE', 'Taipei': 'TPE',
    '가오슝': 'KHH', 'Kaohsiung': 'KHH',
    '타이중': 'RMQ', 'Taichung': 'RMQ',
    '대만': 'TPE', 'Taiwan': 'TPE',
    
    # 🇹🇭 태국
    '방콕': 'BKK', 'Bangkok': 'BKK',
    '푸켓': 'HKT', 'Phuket': 'HKT',
    '치앙마이': 'CNX', 'Chiang Mai': 'CNX',
    '파타야': 'UTP', 'Pattaya': 'UTP',
    '끄라비': 'KBV', 'Krabi': 'KBV',
    '태국': 'BKK', 'Thailand': 'BKK',
    
    # 🇻🇳 베트남
    '하노이': 'HAN', 'Hanoi': 'HAN',
    '호치민': 'SGN', 'Ho Chi Minh': 'SGN',
    '다낭': 'DAD', 'Da Nang': 'DAD',
    '나트랑': 'CXR', 'Nha Trang': 'CXR',
    '달랏': 'DLI', 'Dalat': 'DLI',
    '후에': 'HUI', 'Hue': 'HUI',
    '베트남': 'SGN', 'Vietnam': 'SGN',
    
    # 🇸🇬🇲🇾
    '싱가포르': 'SIN', 'Singapore': 'SIN',
    '쿠알라룸푸르': 'KUL', 'Kuala Lumpur': 'KUL',
    '페낭': 'PEN', 'Penang': 'PEN',
    '코타키나발루': 'BKI', 'Kota Kinabalu': 'BKI',
    '랑카위': 'LGK', 'Langkawi': 'LGK',
    '말레이시아': 'KUL', 'Malaysia': 'KUL',
    
    # 🇮🇩 인도네시아
    '발리': 'DPS', 'Bali': 'DPS',
    '자카르타': 'CGK', 'Jakarta': 'CGK',
    '수라바야': 'SUB', 'Surabaya': 'SUB',
    '족자카르타': 'JOG', 'Yogyakarta': 'JOG',
    '인도네시아': 'CGK', 'Indonesia': 'CGK',
    
    # 🇵🇭 필리핀
    '마닐라': 'MNL', 'Manila': 'MNL',
    '세부': 'CEB', 'Cebu': 'CEB',
    '보라카이': 'MPH', 'Boracay': 'MPH',
    '팔라완': 'PPS', 'Palawan': 'PPS',
    '클라크': 'CRK', 'Clark': 'CRK',
    '필리핀': 'MNL', 'Philippines': 'MNL',
    
    # 🇲🇳🇰🇿🇺🇿
    '울란바토르': 'ULN', 'Ulaanbaatar': 'ULN',
    '몽골': 'ULN', 'Mongolia': 'ULN',
    '칭기즈칸': 'ULN',
    '알마티': 'ALA', 'Almaty': 'ALA',
    '카자흐스탄': 'ALA', 'Kazakhstan': 'ALA',
    '타슈켄트': 'TAS', 'Tashkent': 'TAS',
    '우즈베키스탄': 'TAS', 'Uzbekistan': 'TAS',
    
    # 🇮🇳🇳🇵🇱🇰
    '뉴델리': 'DEL', 'New Delhi': 'DEL',
    '뭄바이': 'BOM', 'Mumbai': 'BOM',
    '방갈로르': 'BLR', 'Bangalore': 'BLR',
    '첸나이': 'MAA', 'Chennai': 'MAA',
    '콜카타': 'CCU', 'Kolkata': 'CCU',
    '인도': 'DEL', 'India': 'DEL',
    '카트만두': 'KTM', 'Kathmandu': 'KTM',
    '네팔': 'KTM', 'Nepal': 'KTM',
    '콜롬보': 'CMB', 'Colombo': 'CMB',
    '스리랑카': 'CMB', 'Sri Lanka': 'CMB',
    
    # 🇦🇪🇶🇦🇹🇷🇮🇱
    '두바이': 'DXB', 'Dubai': 'DXB',
    '아부다비': 'AUH', 'Abu Dhabi': 'AUH',
    'UAE': 'DXB',
    '도하': 'DOH', 'Doha': 'DOH',
    '카타르': 'DOH', 'Qatar': 'DOH',
    '이스탄불': 'IST', 'Istanbul': 'IST',
    '앙카라': 'ESB', 'Ankara': 'ESB',
    '터키': 'IST', 'Turkey': 'IST',
    '텔아비브': 'TLV', 'Tel Aviv': 'TLV',
    '예루살렘': 'TLV', 'Jerusalem': 'TLV',
    '이스라엘': 'TLV', 'Israel': 'TLV',
    
    # 🇫🇷 프랑스
    '파리': 'CDG', 'Paris': 'CDG',
    '니스': 'NCE', 'Nice': 'NCE',
    '마르세유': 'MRS', 'Marseille': 'MRS',
    '프랑스': 'CDG', 'France': 'CDG',
    
    # 🇬🇧 영국
    '런던': 'LHR', 'London': 'LHR',
    '맨체스터': 'MAN', 'Manchester': 'MAN',
    '에딘버러': 'EDI', 'Edinburgh': 'EDI',
    '영국': 'LHR', 'United Kingdom': 'LHR',
    
    # 🇮🇹 이탈리아
    '로마': 'FCO', 'Rome': 'FCO',
    '밀라노': 'MXP', 'Milan': 'MXP',
    '베네치아': 'VCE', 'Venice': 'VCE',
    '피렌체': 'FLR', 'Florence': 'FLR',
    '이탈리아': 'FCO', 'Italy': 'FCO',
    
    # 🇪🇸 스페인
    '바르셀로나': 'BCN', 'Barcelona': 'BCN',
    '마드리드': 'MAD', 'Madrid': 'MAD',
    '세비야': 'SVQ', 'Seville': 'SVQ',
    '스페인': 'MAD', 'Spain': 'MAD',
    
    # 🇳🇱🇧🇪
    '암스테르담': 'AMS', 'Amsterdam': 'AMS',
    '네덜란드': 'AMS', 'Netherlands': 'AMS',
    '브뤼셀': 'BRU', 'Brussels': 'BRU',
    '벨기에': 'BRU', 'Belgium': 'BRU',
    
    # 🇩🇪 독일
    '베를린': 'BER', 'Berlin': 'BER',
    '뮌헨': 'MUC', 'Munich': 'MUC',
    '프랑크푸르트': 'FRA', 'Frankfurt': 'FRA',
    '독일': 'FRA', 'Germany': 'FRA',
    
    # 🇨🇭🇦🇹
    '취리히': 'ZRH', 'Zurich': 'ZRH',
    '제네바': 'GVA', 'Geneva': 'GVA',
    '스위스': 'ZRH', 'Switzerland': 'ZRH',
    '빈': 'VIE', 'Vienna': 'VIE',
    '잘츠부르크': 'SZG', 'Salzburg': 'SZG',
    '오스트리아': 'VIE', 'Austria': 'VIE',
    
    # 🇨🇿🇭🇺🇵🇱🇷🇺
    '프라하': 'PRG', 'Prague': 'PRG',
    '체코': 'PRG', 'Czech Republic': 'PRG',
    '부다페스트': 'BUD', 'Budapest': 'BUD',
    '헝가리': 'BUD', 'Hungary': 'BUD',
    '바르샤바': 'WAW', 'Warsaw': 'WAW',
    '크라쿠프': 'KRK', 'Krakow': 'KRK',
    '폴란드': 'WAW', 'Poland': 'WAW',
    '모스크바': 'SVO', 'Moscow': 'SVO',
    '상트페테르부르크': 'LED', 'Saint Petersburg': 'LED',
    '러시아': 'SVO', 'Russia': 'SVO',
    
    # 🇸🇪🇩🇰🇳🇴🇫🇮🇮🇸
    '스톡홀름': 'ARN', 'Stockholm': 'ARN',
    '스웨덴': 'ARN', 'Sweden': 'ARN',
    '코펜하겐': 'CPH', 'Copenhagen': 'CPH',
    '덴마크': 'CPH', 'Denmark': 'CPH',
    '오슬로': 'OSL', 'Oslo': 'OSL',
    '노르웨이': 'OSL', 'Norway': 'OSL',
    '헬싱키': 'HEL', 'Helsinki': 'HEL',
    '핀란드': 'HEL', 'Finland': 'HEL',
    '레이캬비크': 'KEF', 'Reykjavik': 'KEF',
    '아이슬란드': 'KEF', 'Iceland': 'KEF',
    
    # 🇬🇷🇵🇹🇭🇷
    '아테네': 'ATH', 'Athens': 'ATH',
    '산토리니': 'JTR', 'Santorini': 'JTR',
    '그리스': 'ATH', 'Greece': 'ATH',
    '리스본': 'LIS', 'Lisbon': 'LIS',
    '포르투': 'OPO', 'Porto': 'OPO',
    '포르투갈': 'LIS', 'Portugal': 'LIS',
    '두브로브니크': 'DBV', 'Dubrovnik': 'DBV',
    '자그레브': 'ZAG', 'Zagreb': 'ZAG',
    '크로아티아': 'ZAG', 'Croatia': 'ZAG',
    
    # 🇺🇸 미국
    '뉴욕': 'JFK', 'New York': 'JFK', '뉴어크': 'EWR',
    'JFK': 'JFK', 'Newark': 'EWR',
    '로스앤젤레스': 'LAX', 'Los Angeles': 'LAX',
    'LA': 'LAX', 'LAX': 'LAX',
    '샌프란시스코': 'SFO', 'San Francisco': 'SFO',
    '라스베이거스': 'LAS', 'Las Vegas': 'LAS',
    '시애틀': 'SEA', 'Seattle': 'SEA',
    '시카고': 'ORD', 'Chicago': 'ORD',
    '보스턴': 'BOS', 'Boston': 'BOS',
    '워싱턴': 'IAD', 'Washington': 'IAD',
    '마이애미': 'MIA', 'Miami': 'MIA',
    '올랜도': 'MCO', 'Orlando': 'MCO',
    '하와이': 'HNL', '호놀룰루': 'HNL', 'Honolulu': 'HNL',
    '미국': 'JFK', 'United States': 'JFK',
    
    # 🇨🇦🇲🇽
    '밴쿠버': 'YVR', 'Vancouver': 'YVR',
    '토론토': 'YYZ', 'Toronto': 'YYZ',
    '몬트리올': 'YUL', 'Montreal': 'YUL',
    '캐나다': 'YYZ', 'Canada': 'YYZ',
    '멕시코시티': 'MEX', 'Mexico City': 'MEX',
    '칸쿤': 'CUN', 'Cancun': 'CUN',
    '멕시코': 'MEX', 'Mexico': 'MEX',
    
    # 🇧🇷🇦🇷🇵🇪🇨🇱
    '상파울루': 'GRU', 'Sao Paulo': 'GRU',
    '리우데자네이루': 'GIG', 'Rio de Janeiro': 'GIG',
    '브라질': 'GRU', 'Brazil': 'GRU',
    '부에노스아이레스': 'EZE', 'Buenos Aires': 'EZE',
    '아르헨티나': 'EZE', 'Argentina': 'EZE',
    '리마': 'LIM', 'Lima': 'LIM',
    '쿠스코': 'CUZ', 'Cusco': 'CUZ',
    '페루': 'LIM', 'Peru': 'LIM',
    '산티아고': 'SCL', 'Santiago': 'SCL',
    '칠레': 'SCL', 'Chile': 'SCL',
    
    # 🇦🇺🇳🇿
    '시드니': 'SYD', 'Sydney': 'SYD',
    '멜버른': 'MEL', 'Melbourne': 'MEL',
    '브리즈번': 'BNE', 'Brisbane': 'BNE',
    '골드코스트': 'OOL', 'Gold Coast': 'OOL',
    '케언즈': 'CNS', 'Cairns': 'CNS',
    '호주': 'SYD', 'Australia': 'SYD',
    '오클랜드': 'AKL', 'Auckland': 'AKL',
    '퀸스타운': 'ZQN', 'Queenstown': 'ZQN',
    '뉴질랜드': 'AKL', 'New Zealand': 'AKL',
    
    # 🇪🇬🇿🇦🇲🇦🇰🇪
    '카이로': 'CAI', 'Cairo': 'CAI',
    '이집트': 'CAI', 'Egypt': 'CAI',
    '케이프타운': 'CPT', 'Cape Town': 'CPT',
    '요하네스버그': 'JNB', 'Johannesburg': 'JNB',
    '남아공': 'JNB', 'South Africa': 'JNB',
    '마라케시': 'RAK', 'Marrakech': 'RAK',
    '카사블랑카': 'CMN', 'Casablanca': 'CMN',
    '모로코': 'CMN', 'Morocco': 'CMN',
    '나이로비': 'NBO', 'Nairobi': 'NBO',
    '케냐': 'NBO', 'Kenya': 'NBO',
}

# ----------------------------------------------------------------------
# 테스트 코드 (실제 실행 시 이 부분이 파일 하단에 위치해야 합니다.)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    # 환경변수에서 API 키 로드
    load_dotenv("../.env")
    API_KEY = os.getenv("AMADEUS_API_KEY")
    API_SECRET = os.getenv("AMADEUS_API_SECRET")
    
    if not API_KEY or not API_SECRET:
        print("❌ _env 파일에 AMADEUS_API_KEY와 AMADEUS_API_SECRET을 설정하세요!")
        exit(1)
    
    flight_tool = AmadeusFlightTool(API_KEY, API_SECRET)
    
    # 1. 서울 → 도쿄 왕복 항공권 검색
    print("=== 서울 → 도쿄 왕복 항공권 검색 (한글 도시명 사용) ===")
    result = flight_tool.search_flights(
        origin="서울",  
        destination="도쿄", 
        departure_date="2026-01-12",
        return_date="2026-01-14",
        adults=2,
        travel_class="ECONOMY"
    )
    
    if result['success']:
        print(flight_tool.format_flights_for_travel(result, top_n=3))
    else:
        print(f"에러: {result['error']}")
    
    # 2. 인천 → Prague 편도 항공권 검색
    print("\n=== 인천 → Prague 편도 항공권 검색 ===")
    result2 = flight_tool.search_flights(
        origin="인천",  
        destination="Prague", 
        departure_date="2026-01-12",
        adults=1
    )
    
    if result2['success']:
        print(flight_tool.format_flights_for_travel(result2, top_n=2))
    else:
        print(f"에러: {result2['error']}")
