"""
Google Places API (New) 도구
평점, 리뷰, 가격대 정보 포함
"""
import requests
from typing import Dict, List, Optional

class GooglePlacesToolNew:
    """Google Places API (New)를 사용한 장소 검색 도구"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://places.googleapis.com/v1"

    def search_places(
        self, 
        query: str,
        max_results: int = 10
    ) -> Dict:
        """
        장소 텍스트 검색 (평점, 리뷰 포함)
        
        Args:
            query: 검색어 (예: "restaurants in Tokyo", "hotels near Shibuya")
            max_results: 최대 결과 수 (1-20)
            
        Returns:
            검색 결과 딕셔너리
        """
        try:
            url = f"{self.base_url}/places:searchText"
            
            headers = {
                'Content-Type': 'application/json',
                'X-Goog-Api-Key': self.api_key,
                'X-Goog-FieldMask': (
                    'places.id,'
                    'places.displayName,'
                    'places.formattedAddress,'
                    'places.rating,'
                    'places.userRatingCount,'
                    'places.priceLevel,'
                    'places.types,'
                    'places.location,'
                    'places.businessStatus,'
                    'places.currentOpeningHours,'
                    'places.photos'
                )
            }
            
            data = {
                'textQuery': query,
                'pageSize': min(max_results, 20)
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=15)
            response.raise_for_status()
            
            result = response.json()
            
            places = []
            for place in result.get('places', []):
                place_info = {
                    'place_id': place.get('id', ''),
                    'name': place.get('displayName', {}).get('text', 'N/A'),
                    'address': place.get('formattedAddress', 'N/A'),
                    'rating': place.get('rating', 0),
                    'user_ratings_total': place.get('userRatingCount', 0),
                    'price_level': self._get_price_level(place.get('priceLevel', '')),
                    'types': place.get('types', []),
                    'business_status': place.get('businessStatus', 'UNKNOWN'),
                    'location': place.get('location', {})
                }
                
                opening_hours = place.get('currentOpeningHours', {})
                if opening_hours:
                    place_info['open_now'] = opening_hours.get('openNow', False)
                else:
                    place_info['open_now'] = None
                
                # 사진 URL 추가
                photos = place.get('photos', [])
                if photos and len(photos) > 0:
                    photo_name = photos[0].get('name', '')
                    place_info['photo_url'] = f"https://places.googleapis.com/v1/{photo_name}/media?maxHeightPx=400&maxWidthPx=400&key={self.api_key}"
                else:
                    place_info['photo_url'] = None
                
                places.append(place_info)
            
            return {
                'success': True,
                'count': len(places),
                'places': places
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f"API 요청 실패: {str(e)}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"예상치 못한 오류: {str(e)}"
            }
    
    def get_place_details(self, place_id: str) -> Dict:
        """
        장소 상세 정보 조회 (리뷰 포함)
        """
        try:
            # ✅ 수정: 올바른 Places API (New) 상세 정보 조회 URL 형식 사용
            url = f"{self.base_url}/places/{place_id}"  # <-- 'places/' 프리픽스 추가

            headers = {
                'Content-Type': 'application/json',
                'X-Goog-Api-Key': self.api_key,
                'X-Goog-FieldMask': 'id,displayName,formattedAddress,rating,userRatingCount,reviews,photos'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status() # 404 오류 발생 시 예외 발생

            place = response.json()
            
            details = {
                'place_id': place.get('id', ''),
                'name': place.get('displayName', {}).get('text', 'N/A'),
                'address': place.get('formattedAddress', 'N/A'),
                'phone': place.get('internationalPhoneNumber', 'N/A'),
                'website': place.get('websiteUri', 'N/A'),
                'rating': place.get('rating', 0),
                'user_ratings_total': place.get('userRatingCount', 0),
                'price_level': self._get_price_level(place.get('priceLevel', ''))
            }
            
            # 영업시간
            opening_hours = place.get('regularOpeningHours', {})
            if opening_hours:
                details['opening_hours'] = opening_hours.get('weekdayDescriptions', [])
            
            current_hours = place.get('currentOpeningHours', {})
            if current_hours:
                details['open_now'] = current_hours.get('openNow', False)
            
            # 리뷰 (최대 5개)
            reviews = place.get('reviews', [])
            if reviews:
                details['reviews'] = [
                    {
                        'author': review.get('authorAttribution', {}).get('displayName', 'Anonymous'),
                        'rating': review.get('rating', 0),
                        'text': self._extract_review_text(review),  
                        'time': review.get('relativePublishTimeDescription', 'N/A'),
                        'original_text': self._extract_review_text(review)
                    }
                    for review in reviews[:5]
                ]
            
            # photos는 별도 처리
            photos = place.get('photos', [])
            if photos:
                details['photos'] = [
                    {
                        'photo_reference': photo.get('name', '').split('/')[-1],
                        'height': photo.get('heightPx', 0),
                        'width': photo.get('widthPx', 0)
                    }
                    for photo in photos[:5]
                ]
            
            return {
                'success': True,
                'details': details
            }
            
        except Exception as e:
            print(f"❌ Details API Error: {str(e)}")  # 에러 내용 출력 추가
            return {
                'success': False,
                'error': f"상세 정보 조회 실패: {str(e)}"
            }
    
    def search_nearby(
        self,
        latitude: float,
        longitude: float,
        radius: int = 1000,
        included_types: List[str] = None,
        max_results: int = 10
    ) -> Dict:
        """
        주변 장소 검색 (Nearby Search)
        
        Args:
            latitude: 위도
            longitude: 경도
            radius: 검색 반경 (미터, 최대 50000)
            included_types: 장소 유형 리스트 (예: ["restaurant", "cafe"])
            max_results: 최대 결과 수
            
        Returns:
            검색 결과 딕셔너리
        """
        try:
            url = f"{self.base_url}/places:searchNearby"
            
            headers = {
                'Content-Type': 'application/json',
                'X-Goog-Api-Key': self.api_key,
                'X-Goog-FieldMask': (
                    'places.id,'
                    'places.displayName,'
                    'places.formattedAddress,'
                    'places.rating,'
                    'places.userRatingCount,'
                    'places.priceLevel,'
                    'places.types',
                )
            }
            
            data = {
                'locationRestriction': {
                    'circle': {
                        'center': {
                            'latitude': latitude,
                            'longitude': longitude
                        },
                        'radius': min(radius, 50000)
                    }
                },
                'maxResultCount': min(max_results, 20)
            }
            
            if included_types:
                data['includedTypes'] = included_types
            
            response = requests.post(url, headers=headers, json=data, timeout=15)
            response.raise_for_status()
            
            result = response.json()
            
            # 결과 파싱
            places = []
            for place in result.get('places', []):
                place_info = {
                    'place_id': place.get('id', ''),
                    'name': place.get('displayName', {}).get('text', 'N/A'),
                    'address': place.get('formattedAddress', 'N/A'),
                    'rating': place.get('rating', 0),
                    'user_ratings_total': place.get('userRatingCount', 0),
                    'price_level': self._get_price_level(place.get('priceLevel', '')),
                    'types': place.get('types', [])
                }
                places.append(place_info)
            
            return {
                'success': True,
                'count': len(places),
                'places': places
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"주변 검색 실패: {str(e)}"
            }
    
    def _get_price_level(self, price_level_str: str) -> int:
        """가격 레벨 문자열을 숫자로 변환"""
        price_map = {
            'PRICE_LEVEL_FREE': 0,
            'PRICE_LEVEL_INEXPENSIVE': 1,
            'PRICE_LEVEL_MODERATE': 2,
            'PRICE_LEVEL_EXPENSIVE': 3,
            'PRICE_LEVEL_VERY_EXPENSIVE': 4
        }
        return price_map.get(price_level_str, 0)
    
    def format_places_for_travel(self, places_data: Dict, top_n: int = 5) -> str:
        """
        여행 계획을 위한 장소 정보 포맷팅
        
        Args:
            places_data: search_places() 또는 search_nearby() 결과
            top_n: 표시할 장소 수
            
        Returns:
            포맷된 장소 정보 문자열
        """
        if not places_data.get('success'):
            return f"❌ 장소 정보를 가져올 수 없습니다: {places_data.get('error', 'Unknown error')}"
        
        places = places_data.get('places', [])[:top_n]
        
        if not places:
            return "❌ 검색 결과가 없습니다."
        
        result = f"📍 추천 장소 ({len(places)}개)\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, place in enumerate(places, 1):
            result += f"{i}. **{place['name']}**\n"
            result += f"   📍 {place['address']}\n"
            
            # 평점 표시 (중요!)
            if place['rating'] > 0:
                stars = "⭐" * int(place['rating'])
                result += f"   {stars} {place['rating']}/5.0"
                if place.get('user_ratings_total', 0) > 0:
                    result += f" ({place['user_ratings_total']:,} 리뷰)"
                result += "\n"
            
            # 가격대 표시 (중요!)
            if place.get('price_level', 0) > 0:
                price_symbols = "💰" * place['price_level']
                result += f"   가격대: {price_symbols}\n"
            
            # 영업 상태
            if place.get('open_now') is not None:
                status = "🟢 영업 중" if place['open_now'] else "🔴 영업 종료"
                result += f"   {status}\n"
            
            # 장소 유형
            if place.get('types'):
                main_types = [t.replace('_', ' ').title() for t in place['types'][:3]]
                result += f"   🏷️ {', '.join(main_types)}\n"
            
            result += "\n"
        
        return result

    def _extract_review_text(self, review: Dict) -> str:
            """리뷰 객체에서 텍스트를 안전하게 추출 (get_place_details 바로 아래에 위치)"""
            text_content = review.get('text', '')
            if isinstance(text_content, dict):
                # 딕셔너리로 중첩되어 있을 경우
                return text_content.get('text', '')[:300]
            elif isinstance(text_content, str):
                # 문자열일 경우
                return text_content[:300]
            return ''
    # google_places_tool.py에 함수 추가

    def search_restaurants_near_place(self, place_id: str, radius: int = 500) -> dict:
        """
        특정 장소 근처의 식당 검색
        
        Args:
            place_id: Google Places ID
            radius: 검색 반경 (미터, 기본 500m)
        
        Returns:
            식당 리스트
        """
        try:
            # 먼저 장소의 좌표 가져오기
            place_details = self.get_place_details(place_id)
            if not place_details.get('success'):
                return {'success': False, 'error': 'Failed to get place location'}
            
            location = place_details['details'].get('geometry', {}).get('location', {})
            if not location:
                return {'success': False, 'error': 'No location found'}
            
            lat = location.get('lat')
            lng = location.get('lng')
            
            # 근처 식당 검색
            url = f"{self.base_url}/nearbysearch/json"
            params = {
                'location': f"{lat},{lng}",
                'radius': radius,
                'type': 'restaurant',
                'key': self.api_key,
                'language': 'ko'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] != 'OK':
                return {'success': False, 'error': f"API Error: {data['status']}"}
            
            restaurants = []
            for place in data.get('results', [])[:5]:  # 상위 5개만
                restaurants.append({
                    'name': place.get('name'),
                    'address': place.get('vicinity'),
                    'rating': place.get('rating', 'N/A'),
                    'user_ratings_total': place.get('user_ratings_total', 0),
                    'price_level': place.get('price_level', 'N/A'),
                    'place_id': place.get('place_id'),
                    'types': place.get('types', [])
                })
            
            return {
                'success': True,
                'restaurants': restaurants,
                'count': len(restaurants)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

# 테스트 코드
if __name__ == "__main__":
    # 테스트용 (실제 사용시 환경변수에서 API 키 로드)
    API_KEY = "your_api_key_here"
    
    places = GooglePlacesToolNew(API_KEY)
    
    # 장소 검색 테스트
    print("=== 장소 검색 테스트 (평점 & 리뷰) ===")
    result = places.search_places("famous restaurants in Tokyo")
    print(places.format_places_for_travel(result, top_n=5))
    
    # 주변 검색 테스트
    print("\n=== 주변 검색 테스트 ===")
    nearby = places.search_nearby(
        latitude=35.6762,
        longitude=139.6503,
        radius=2000,
        included_types=["tourist_attraction"]
    )
    print(places.format_places_for_travel(nearby, top_n=5))