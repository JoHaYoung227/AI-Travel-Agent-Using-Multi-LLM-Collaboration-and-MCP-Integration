import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from urllib.parse import quote

class AmadeusHotelTool:
    """Amadeus API를 사용한 호텔 검색 도구"""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        # 상용 환경(Production)으로 설정
        self.base_url = "https://api.amadeus.com"
        self.access_token = None
        self.token_expires_at = None
        self.city_cache = {}
        
    def _get_access_token(self) -> str:
            """액세스 토큰 발급/갱신 - 상용 환경용"""
            
            if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
                return self.access_token

            try:
                url = f"{self.base_url}/v1/security/oauth2/token" 
                
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
                token = result.get('access_token')
                if not token:
                    raise Exception("토큰 응답에 access_token 필드가 없습니다.")

                self.access_token = token
                expires_in = result.get('expires_in', 1799)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                return self.access_token
                
            except requests.exceptions.HTTPError as e:
                error_details = ""
                try:
                    error_details = e.response.json().get('errors', [{}])[0].get('detail', '')
                except:
                    pass
                raise Exception(f"상용 키 인증 실패 (HTTP {e.response.status_code}): {error_details or str(e)}")
                
            except Exception as e:
                raise Exception(f"액세스 토큰 발급 실패: {str(e)}")

    def resolve_city_code(self, city_input: str) -> Optional[str]:
        """도시명을 IATA 코드로 확인/변환합니다. (하드코딩 맵만 사용)"""
        code = CITY_CODE_MAP.get(city_input)
        if not code:
            code = CITY_CODE_MAP.get(city_input.upper())
        if not code:
            code = CITY_CODE_MAP.get(city_input.capitalize())
        return code

    def _format_address(self, address: Dict) -> str:
        """주소 포맷팅 - lines, cityName, countryCode 필드 활용"""
        parts = []
        if address.get('lines'): 
             # lines는 리스트일 수 있으므로 join 사용
            lines = [line for line in address['lines'] if line.strip()]
            parts.extend(lines)
        if address.get('cityName'): parts.append(address['cityName'])
        if address.get('countryCode'): parts.append(address['countryCode'])
        # 주소가 유효한지 확인: 하나 이상의 유효한 필드가 있어야 함
        return ', '.join(parts) if parts else '주소 정보 불충분 (N/A)'
    
    def _calculate_per_night(self, total: float, check_in: str, check_out: str) -> float:
        """1박당 가격 계산"""
        try:
            check_in_date = datetime.strptime(check_in, '%Y-%m-%d')
            check_out_date = datetime.strptime(check_out, '%Y-%m-%d')
            nights = (check_out_date - check_in_date).days
            # 1박당 평균 가격을 반올림하여 반환
            return round(total / nights, 0) if nights > 0 else total
        except:
            return total
            
    def _format_cancellation(self, cancellations: List[Dict]) -> str:
        """취소 정책 요약 (HotelProduct_CancellationPolicy)"""
        if not cancellations:
            return "취소 정책 정보 없음"
        
        summaries = []
        for policy in cancellations:
            policy_type = policy.get('type', 'FULL_STAY')
            description = policy.get('description', {}).get('text', '')
            deadline = policy.get('deadline')
            
            summary = ""
            
            if deadline:
                try:
                    dt = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
                    summary += f"기한: ~{dt.strftime('%Y-%m-%d %H:%M')}"
                except ValueError:
                    summary += f"기한: {deadline}"
            
            fee_desc = ""
            if policy_type == 'FULL_STAY':
                fee_desc = "총 숙박 요금 몰수"
            else:
                if policy.get('amount'):
                    fee_desc = f"{policy['amount']} 수수료"
                elif policy.get('percentage'):
                    fee_desc = f"{policy['percentage']}% 수수료"
                elif policy.get('numberOfNights'):
                    fee_desc = f"{policy['numberOfNights']}박 수수료"
            
            if fee_desc:
                summary += f" ({fee_desc})" if summary else fee_desc

            if description and len(description) > 50:
                description = description[:47] + "..."
            if description:
                 summary += f" | {description.strip()}"

            summaries.append(summary.strip())
            
        return " | ".join(summaries) if summaries else "정책 상세 정보 없음"


    def search_hotels(
        self,
        city: str,
        check_in_date: str,
        check_out_date: str,
        adults: int = 2,
        radius: int = 20,
        radius_unit: str = "KM",
        currency: str = "KRW",
        max_results: int = 10
    ) -> Dict:
        """
        호텔 검색 (2단계: ID 검색 -> 오퍼 검색)
        """
        try:
            city_code = self.resolve_city_code(city)
            
            if not city_code:
                return {
                    'success': False,
                    'error': f"입력된 '{city}'는 유효한 도시 코드가 아닙니다. (예: PAR, SEL)"
                }
            
            token = self._get_access_token()
            headers = {'Authorization': f'Bearer {token}'}
            
            # 1단계: 도시의 호텔 ID 목록 가져오기 (V1)
            url_step1 = f"{self.base_url}/v1/reference-data/locations/hotels/by-city"
            params_step1 = {
                'cityCode': city_code,
                'radius': radius,
                'radiusUnit': radius_unit
            }
            
            response_step1 = requests.get(url_step1, headers=headers, params=params_step1, timeout=15)
            response_step1.raise_for_status()
            
            hotels_data = response_step1.json()
            
            # 🔥 V1 응답에서 호텔 ID와 주소, 평점 정보를 매핑하여 저장
            hotel_info_v1 = {}
            for hotel in hotels_data.get('data', []):
                hotel_id = hotel.get('hotelId')
                if hotel_id:
                    # _format_address를 사용하여 주소 포맷팅
                    hotel_info_v1[hotel_id] = {
                        'address': self._format_address(hotel.get('address', {})),
                        'rating': hotel.get('rating')
                    }
            
            hotel_ids = list(hotel_info_v1.keys())[:max_results]
            
            if not hotel_ids:
                return {
                    'success': False,
                    'error': '해당 도시에서 호텔을 찾을 수 없습니다.'
                }
            
            # 2단계: 호텔별 가격 오퍼 조회 (V3)
            url_step2 = f"{self.base_url}/v3/shopping/hotel-offers"
            
            params_step2 = {
                'hotelIds': ','.join(hotel_ids[:20]),
                'checkInDate': check_in_date,
                'checkOutDate': check_out_date,
                'adults': adults,
                'currency': currency,
                'roomQuantity': 1,
                'bestRateOnly': True
            }
            
            offers_response = requests.get(url_step2, headers=headers, params=params_step2, timeout=15)
            offers_response.raise_for_status()
            
            offers_data = offers_response.json()
            
            # 결과 파싱
            hotels = []
            for hotel_data in offers_data.get('data', []):
                hotel_info = hotel_data.get('hotel', {})
                offers = hotel_data.get('offers', [])
                
                if not offers: continue
                
                best_offer = min(offers, key=lambda x: float(x['price']['total']))
                
                # --- 상세 정보 추출 ---
                hotel_id = hotel_info.get('hotelId')
                price_info = best_offer['price']
                total_price = float(price_info['total'])
                
                # 세금 총액 계산
                taxes = price_info.get('taxes', [])
                total_tax = sum(float(tax.get('amount', 0)) for tax in taxes)
                
                # 🔥 기본 가격 (Base)을 총액에서 세금을 뺀 값으로 계산
                base_price_calculated = round(total_price - total_tax, 2)
                
                room_details = best_offer.get('room', {})
                room_desc = room_details.get('description', {}).get('text', '상세 설명 없음')
                room_estimated = room_details.get('typeEstimated', {})
                room_category = room_estimated.get('category', 'N/A')
                room_bed_type = room_estimated.get('bedType', 'N/A')
                
                cancellation_summary = self._format_cancellation(
                    best_offer.get('policies', {}).get('cancellations', [])
                )
                board_type = best_offer.get('boardType', 'N/A')
                
                # 🔥 주소 복구 로직: V3 주소가 불완전하면 V1 정보 사용
                address_v3 = self._format_address(hotel_info.get('address', {}))
                address_v1 = hotel_info_v1.get(hotel_id, {}).get('address', '주소 정보 불충분 (N/A)')
                
                if address_v3 == '주소 정보 불충분 (N/A)':
                    address_final = address_v1
                else:
                    address_final = address_v3

                # V3에 평점이 없으면 V1 평점 정보 사용
                rating_final = hotel_info.get('rating') or hotel_info_v1.get(hotel_id, {}).get('rating', 'N/A')
                # --- 추출 끝 ---
                
                hotel = {
                    'hotel_id': hotel_id,
                    'name': hotel_info.get('name', 'N/A'),
                    'rating': rating_final,
                    'address': address_final, 
                    'city_code': hotel_info.get('cityCode', city_code),
                    'price': {
                        'total': total_price,
                        'currency': price_info['currency'],
                        'base': base_price_calculated, # 계산된 기본 가격
                        'tax_total': total_tax,
                        'per_night': self._calculate_per_night(total_price, check_in_date, check_out_date)
                    },
                    'room_type': room_details.get('type', 'N/A'),
                    'room_details_desc': room_desc,
                    'room_category': room_category,
                    'room_bed_type': room_bed_type,
                    'board_type': board_type,
                    'cancellation_summary': cancellation_summary,
                    'offer_id': best_offer.get('id', '')
                }
                hotels.append(hotel)
            
            hotels.sort(key=lambda x: x['price']['total'])
            
            return {
                'success': True,
                'count': len(hotels),
                'hotels': hotels[:max_results],
                'search_params': {
                    'city_code': city_code,
                    'check_in': check_in_date,
                    'check_out': check_out_date,
                    'adults': adults
                }
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = f"API 요청 실패: {str(e)}"
            try:
                response = getattr(e, 'response', None)
                if response is not None:
                    error_details = response.json().get('errors', [{}])
                    error_msg = f"API 오류 (HTTP {response.status_code}): {error_details[0].get('detail', str(e))}"
            except:
                pass
            return {'success': False, 'error': error_msg}
        except Exception as e:
            return {'success': False, 'error': f"호텔 검색 실패: {str(e)}"}
    
    def format_hotels_for_travel(self, hotels_data: Dict, top_n: int = 5) -> str:
            """
            여행 계획을 위한 호텔 정보 포맷팅 (상세 버전)
            """
            if not hotels_data.get('success'):
                return f"❌ 호텔 정보를 가져올 수 없습니다: {hotels_data.get('error', 'Unknown error')}"
            
            hotels = hotels_data.get('hotels', [])[:top_n]
            if not hotels:
                return "❌ 검색 결과가 없습니다."
            
            search_params = hotels_data.get('search_params', {})
            
            result = f"🏨 추천 호텔 ({len(hotels)}개) - 상세 정보\n"
            result += f"📍 **도시 코드:** {search_params.get('city_code')}\n"
            result += f"📅 **기간:** {search_params.get('check_in')} ~ {search_params.get('check_out')}\n"
            result += f"👥 **성인:** {search_params.get('adults')}명\n"
            result += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # 식사 유형 상세 매핑 (BoardType 정의 참고)
            board_map = {
                'ROOM_ONLY': '객실만', 
                'BREAKFAST': '조식 포함', 
                'HALF_BOARD': '조식+석식', 
                'FULL_BOARD': '전체 식사', 
                'ALL_INCLUSIVE': '모두 포함',
                'BUFFET_BREAKFAST': '뷔페 조식',
                'CONTINENTAL_BREAKFAST': '컨티넨탈 조식',
                'N/A': '정보 없음'
            }

            for i, hotel in enumerate(hotels, 1):
                rating_value = hotel.get('rating', 'N/A')
                safe_rating = 0
                if isinstance(rating_value, (int, float)):
                    safe_rating = int(rating_value)
                elif isinstance(rating_value, str) and rating_value.isdigit():
                    safe_rating = int(rating_value)

                result += f"{i}. **{hotel['name']}**\n"
                result += f"   🗺️ 주소: {hotel['address']}\n"
                result += f"   🏛️ 도시 코드: {hotel['city_code']}\n"
                
                if safe_rating > 0:
                    stars = "⭐" * safe_rating
                    result += f"   {stars} ({safe_rating}성급)\n"
                
                # --- 가격 상세 ---
                price = hotel['price']
                currency = price['currency']
                result += f"   💸 **가격 상세 ({currency})**\n"
                result += f"     - **총액 (Total):** {currency} {price['total']:,.0f}\n"
                result += f"     - 기본 가격 (Base): {currency} {price['base']:,.0f}\n"
                result += f"     - 세금/수수료 (Tax): {currency} {price['tax_total']:,.0f}\n"
                result += f"     - 1박당 평균: {currency} {price['per_night']:,.0f}\n"
                
                # --- 객실 및 식사 상세 ---
                board_type_kr = board_map.get(hotel['board_type'], hotel['board_type'])
                result += f"   🛏️ **객실 및 식사 정보**\n"
                result += f"     - 객실 코드: {hotel['room_type']} ({hotel['room_category']} / {hotel['room_bed_type']})\n"
                result += f"     - 객실 설명: {hotel['room_details_desc']}\n"
                result += f"     - 🍽️ 식사 유형: **{board_type_kr}**\n"

                # --- 정책 상세 ---
                cancellation_summary = hotel.get('cancellation_summary', '정보 없음')
                result += f"   📝 **취소/예약 정책:** {cancellation_summary}\n"
                
                hotel_name = hotel['name']
                city_code = search_params.get('city_code')
                search_query = f"{hotel_name} {city_code} hotel booking"
                booking_url = f"https://www.google.com/search?q={quote(search_query)}&hl=ko&ibp=htl"

                result += f"   🔗 [Google Hotels에서 예약 및 상세 정보 확인]({booking_url})\n"
                result += "\n"
            
            return result

# ----------------------------------------------------------------------
# CITY CODE MAP (테스트 환경 변수)
# ----------------------------------------------------------------------

CITY_CODE_MAP = {
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

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    # 환경변수에서 API 키 로드
    # 테스트를 위해 .env 파일이 상위 폴더에 있다고 가정합니다.
    load_dotenv("../.env") 
    API_KEY = os.getenv("AMADEUS_API_KEY")
    API_SECRET = os.getenv("AMADEUS_API_SECRET")
    
    if not API_KEY or not API_SECRET:
        print("❌ .env 파일에 AMADEUS_API_KEY와 AMADEUS_API_SECRET을 설정하세요!")
        exit(1)
    
    hotel_tool = AmadeusHotelTool(API_KEY, API_SECRET)
    
    # 1. 파리 검색 테스트
    print("=== 파리 (PAR) 호텔 검색 테스트 (상세 정보) ===")
    result_par = hotel_tool.search_hotels(
        city="PAR",
        check_in_date="2025-12-01",
        check_out_date="2025-12-05",
        adults=2,
        radius=20
    )
    
    if result_par['success']:
        print(hotel_tool.format_hotels_for_travel(result_par, top_n=3))
    else:
        print(f"에러: {result_par['error']}")
    
    # 2. 서울 검색 테스트
    print("\n=== 서울 (SEL) 호텔 검색 테스트 (상세 정보) ===")
    result_sel = hotel_tool.search_hotels(
        city="SEL",
        check_in_date="2025-12-01",
        check_out_date="2025-12-05",
        adults=2,
        radius=20
    )
    
    if result_sel['success']:
        print(hotel_tool.format_hotels_for_travel(result_sel, top_n=3))
    else:
        print(f"에러: {result_sel['error']}")