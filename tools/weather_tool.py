"""
날씨 API 도구 (OpenWeatherMap API 사용)
"""
import requests
from typing import Dict, Optional
from datetime import datetime

class WeatherTool:
    """OpenWeatherMap API를 사용한 날씨 조회 도구"""

    CITY_NAME_MAP = {
        # 🇰🇷 한국
        '서울': 'Seoul', '인천': 'Incheon', '김포': 'Gimpo',
        '부산': 'Busan', '제주': 'Jeju', '대구': 'Daegu',
        '한국': 'Seoul', 'Korea': 'Seoul',

        # 🇯🇵 일본
        '도쿄': 'Tokyo', '나리타': 'Narita', '하네다': 'Tokyo',
        '오사카': 'Osaka', '간사이': 'Osaka', '교토': 'Kyoto',
        '후쿠오카': 'Fukuoka', '삿포로': 'Sapporo', '나고야': 'Nagoya',
        '오키나와': 'Naha', '나하': 'Naha', '고베': 'Kobe',
        '센다이': 'Sendai', '히로시마': 'Hiroshima', '가고시마': 'Kagoshima',
        '일본': 'Tokyo', 'Japan': 'Tokyo',

        # 🇨🇳 중국
        '베이징': 'Beijing', '북경': 'Beijing',
        '상하이': 'Shanghai', '광저우': 'Guangzhou',
        '선전': 'Shenzhen', '청두': 'Chengdu',
        '시안': 'Xian', '항저우': 'Hangzhou',
        '충칭': 'Chongqing', '쿤밍': 'Kunming',
        '하얼빈': 'Harbin', '우한': 'Wuhan',
        '중국': 'Beijing', 'China': 'Beijing',

        # 🇭🇰🇹🇼🇲🇴
        '홍콩': 'Hong Kong', '마카오': 'Macau',
        '타이베이': 'Taipei', '가오슝': 'Kaohsiung', '타이중': 'Taichung',
        '대만': 'Taipei', 'Taiwan': 'Taipei',

        # 🇹🇭 태국
        '방콕': 'Bangkok', '푸켓': 'Phuket',
        '치앙마이': 'Chiang Mai', '파타야': 'Pattaya',
        '끄라비': 'Krabi',
        '태국': 'Bangkok', 'Thailand': 'Bangkok',

        # 🇻🇳 베트남
        '하노이': 'Hanoi', '호치민': 'Ho Chi Minh City',
        '다낭': 'Da Nang', '나트랑': 'Nha Trang',
        '달랏': 'Dalat', '후에': 'Hue',
        '베트남': 'Hanoi', 'Vietnam': 'Hanoi',

        # 🇸🇬🇲🇾
        '싱가포르': 'Singapore',
        '쿠알라룸푸르': 'Kuala Lumpur', '페낭': 'George Town',
        '코타키나발루': 'Kota Kinabalu', '랑카위': 'Langkawi',
        '말레이시아': 'Kuala Lumpur', 'Malaysia': 'Kuala Lumpur',

        # 🇮🇩 인도네시아
        '발리': 'Denpasar', '자카르타': 'Jakarta',
        '수라바야': 'Surabaya', '족자카르타': 'Yogyakarta',
        '인도네시아': 'Jakarta', 'Indonesia': 'Jakarta',

        # 🇵🇭 필리핀
        '마닐라': 'Manila', '세부': 'Cebu City',
        '보라카이': 'Malay', '팔라완': 'Puerto Princesa',
        '클라크': 'Mabalacat',
        '필리핀': 'Manila', 'Philippines': 'Manila',

        # 🇲🇳🇰🇿🇺🇿
        '울란바토르': 'Ulaanbaatar', '몽골': 'Ulaanbaatar',
        '알마티': 'Almaty', '카자흐스탄': 'Almaty',
        '타슈켄트': 'Tashkent', '우즈베키스탄': 'Tashkent',

        # 🇮🇳🇱🇰🇳🇵
        '뉴델리': 'New Delhi', '뭄바이': 'Mumbai',
        '방갈로르': 'Bengaluru', '첸나이': 'Chennai',
        '콜카타': 'Kolkata', '인도': 'New Delhi',
        '카트만두': 'Kathmandu', '콜롬보': 'Colombo',

        # 🇦🇪🇶🇦🇹🇷
        '두바이': 'Dubai', '아부다비': 'Abu Dhabi',
        '도하': 'Doha', '카타르': 'Doha',
        '이스탄불': 'Istanbul', '앙카라': 'Ankara',

        # 🇫🇷🇬🇧🇮🇹🇪🇸
        '파리': 'Paris', '니스': 'Nice', '마르세유': 'Marseille',
        '런던': 'London', '맨체스터': 'Manchester', '에딘버러': 'Edinburgh',
        '로마': 'Rome', '밀라노': 'Milan', '베네치아': 'Venice', '피렌체': 'Florence',
        '바르셀로나': 'Barcelona', '마드리드': 'Madrid', '세비야': 'Seville',

        # 🇩🇪🇨🇭🇦🇹🇳🇱🇧🇪
        '베를린': 'Berlin', '뮌헨': 'Munich', '프랑크푸르트': 'Frankfurt',
        '취리히': 'Zurich', '제네바': 'Geneva', '빈': 'Vienna',
        '암스테르담': 'Amsterdam', '브뤼셀': 'Brussels',

        # 🇺🇸 미국
        '뉴욕': 'New York', '뉴어크': 'Newark',
        '로스앤젤레스': 'Los Angeles', 'LA': 'Los Angeles',
        '샌프란시스코': 'San Francisco', '라스베이거스': 'Las Vegas',
        '시애틀': 'Seattle', '시카고': 'Chicago',
        '보스턴': 'Boston', '워싱턴': 'Washington',
        '마이애미': 'Miami', '올랜도': 'Orlando',
        '하와이': 'Honolulu', '호놀룰루': 'Honolulu',
        '미국': 'New York', 'United States': 'New York',

        # 🇨🇦🇲🇽
        '밴쿠버': 'Vancouver', '토론토': 'Toronto', '몬트리올': 'Montreal',
        '멕시코시티': 'Mexico City', '칸쿤': 'Cancun',

        # 🇧🇷🇦🇷🇵🇪🇨🇱
        '상파울루': 'Sao Paulo', '리우데자네이루': 'Rio de Janeiro',
        '부에노스아이레스': 'Buenos Aires', '리마': 'Lima', '쿠스코': 'Cusco',
        '산티아고': 'Santiago',

        # 🇦🇺🇳🇿
        '시드니': 'Sydney', '멜버른': 'Melbourne',
        '브리즈번': 'Brisbane', '골드코스트': 'Gold Coast',
        '케언즈': 'Cairns', '오클랜드': 'Auckland',
        '퀸스타운': 'Queenstown',

        # 🇪🇬🇿🇦🇲🇦🇰🇪
        '카이로': 'Cairo', '케이프타운': 'Cape Town',
        '요하네스버그': 'Johannesburg',
        '마라케시': 'Marrakesh', '카사블랑카': 'Casablanca',
        '나이로비': 'Nairobi',
    }
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "http://api.openweathermap.org/data/2.5"
        
    def get_current_weather(self, city: str, country_code: Optional[str] = None) -> Dict:
        """
        현재 날씨 조회
        
        Args:
            city: 도시명 (예: "Seoul", "Tokyo")
            country_code: 국가 코드 (예: "KR", "JP") - 선택사항
            
        Returns:
            날씨 정보 딕셔너리
        """
        try:
            city = self.CITY_NAME_MAP.get(city, city)
            # 쿼리 구성
            location = f"{city},{country_code}" if country_code else city
            
            params = {
                'q': location,
                'appid': self.api_key,
                'units': 'metric',  # 섭씨 온도
                'lang': 'ko'  # 한국어 설명
            }
            
            response = requests.get(f"{self.base_url}/weather", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # 필요한 정보만 추출
            weather_info = {
                'city': data['name'],
                'country': data['sys']['country'],
                'temperature': round(data['main']['temp'], 1),
                'feels_like': round(data['main']['feels_like'], 1),
                'temp_min': round(data['main']['temp_min'], 1),
                'temp_max': round(data['main']['temp_max'], 1),
                'humidity': data['main']['humidity'],
                'description': data['weather'][0]['description'],
                'main': data['weather'][0]['main'],
                'wind_speed': data['wind']['speed'],
                'timestamp': datetime.fromtimestamp(data['dt']).strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return {
                'success': True,
                'data': weather_info
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f"API 요청 실패: {str(e)}"
            }
        except KeyError as e:
            return {
                'success': False,
                'error': f"데이터 파싱 실패: {str(e)}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"예상치 못한 오류: {str(e)}"
            }
    
    def get_forecast(self, city: str, country_code: Optional[str] = None, days: int = 5) -> Dict:
        """
        5일 날씨 예보 조회 (3시간 간격)
        
        Args:
            city: 도시명
            country_code: 국가 코드 - 선택사항
            days: 예보 일수 (최대 5일)
            
        Returns:
            예보 정보 딕셔너리
        """
        try:
            city = self.CITY_NAME_MAP.get(city, city)
            location = f"{city},{country_code}" if country_code else city
            
            params = {
                'q': location,
                'appid': self.api_key,
                'units': 'metric',
                'lang': 'ko',
                'cnt': 40  # ✅ 수정: 요청 일수에 관계없이 최대 5일치(40개) 데이터를 모두 요청
            }
            
            response = requests.get(f"{self.base_url}/forecast", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # 일별로 데이터 그룹화
            daily_forecast = []
            current_date = None
            day_data = []
            
            for item in data['list']:
                date = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')
                
                if current_date != date:
                    if day_data:
                        # 하루의 평균/최저/최고 계산
                        temps = [d['temp'] for d in day_data]
                        daily_forecast.append({
                            'date': current_date,
                            'temp_avg': round(sum(temps) / len(temps), 1),
                            'temp_min': round(min(temps), 1),
                            'temp_max': round(max(temps), 1),
                            'description': day_data[0]['description'],
                            'main': day_data[0]['main']
                        })
                    current_date = date
                    day_data = []
                
                day_data.append({
                    'temp': item['main']['temp'],
                    'description': item['weather'][0]['description'],
                    'main': item['weather'][0]['main']
                })
            
            # 마지막 날 추가
            if day_data:
                temps = [d['temp'] for d in day_data]
                daily_forecast.append({
                    'date': current_date,
                    'temp_avg': round(sum(temps) / len(temps), 1),
                    'temp_min': round(min(temps), 1),
                    'temp_max': round(max(temps), 1),
                    'description': day_data[0]['description'],
                    'main': day_data[0]['main']
                })
            
            return {
                'success': True,
                'city': data['city']['name'],
                'country': data['city']['country'],
                'forecast': daily_forecast
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f"예보 조회 실패: {str(e)}"
            }

    def get_weather_for_dates(self, city: str, departure_date: str, return_date: str, country_code: Optional[str] = None) -> Dict:
        """
        특정 날짜 범위의 날씨 조회
        """
        try:
            from datetime import datetime, timedelta

            dep = datetime.strptime(departure_date, "%Y-%m-%d")
            ret = datetime.strptime(return_date, "%Y-%m-%d")
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            city = self.CITY_NAME_MAP.get(city, city)

            forecast = self.get_forecast(city, country_code, days=5)

            if not forecast.get('success'):
                return forecast

            all_days = forecast.get('forecast', [])
            
            # 여행 날짜가 예보 범위 안에 있는지 확인
            forecast_dates = [datetime.strptime(day['date'], "%Y-%m-%d") for day in all_days]
            max_forecast_date = max(forecast_dates) if forecast_dates else today
            
            filtered_forecast = []
            
            if dep <= max_forecast_date:
                # 여행 날짜가 예보 범위 내
                for day in all_days:
                    day_date = datetime.strptime(day['date'], "%Y-%m-%d")
                    if dep <= day_date <= ret:
                        filtered_forecast.append(day)
                note = f"여행 기간({departure_date} ~ {return_date})의 예상 날씨입니다."
            else:
                # 여행 날짜가 너무 미래 - 가상 날짜 생성
                current_date = dep
                for day in all_days[:min(len(all_days), (ret - dep).days + 1)]:
                    filtered_forecast.append({
                        'date': current_date.strftime("%Y-%m-%d"),
                        'temp_avg': day['temp_avg'],
                        'temp_min': day['temp_min'],
                        'temp_max': day['temp_max'],
                        'description': day['description'],
                        'main': day['main']
                    })
                    current_date += timedelta(days=1)
                note = f"여행 기간({departure_date} ~ {return_date})의 예상 날씨입니다. (최근 예보 데이터 기반)"

            return {
                'success': True,
                'city': forecast['city'],
                'country': forecast['country'],
                'departure_date': departure_date,
                'return_date': return_date,
                'forecast': filtered_forecast,
                'note': note,
            }

        except Exception as e:
            return {
                'success': False,
                'error': f"날짜별 날씨 조회 실패: {str(e)}"
            }
    
    def format_weather_for_travel(self, weather_data: Dict) -> str:
        """
        여행 계획을 위한 날씨 정보 포맷팅
        
        Args:
            weather_data: get_current_weather() 또는 get_forecast() 결과
            
        Returns:
            포맷된 날씨 정보 문자열
        """
        if not weather_data.get('success'):
            return f"❌ 날씨 정보를 가져올 수 없습니다: {weather_data.get('error', 'Unknown error')}"
        
        # 현재 날씨인 경우
        if 'data' in weather_data:
            data = weather_data['data']
            return f"""🌤️ 현재 날씨 - {data['city']}, {data['country']}
━━━━━━━━━━━━━━━━━━━━━━
🌡️ 온도: {data['temperature']}°C (체감: {data['feels_like']}°C)
📊 최저/최고: {data['temp_min']}°C ~ {data['temp_max']}°C
💧 습도: {data['humidity']}%
🌬️ 풍속: {data['wind_speed']} m/s
☁️ 상태: {data['description']}
🕐 조회 시간: {data['timestamp']}
"""
        
        # 예보인 경우
        elif 'forecast' in weather_data:
            result = f"📅 날씨 예보 - {weather_data['city']}, {weather_data['country']}\n"
            result += "━━━━━━━━━━━━━━━━━━━━━━\n"
            
            for day in weather_data['forecast']:
                result += f"\n📆 {day['date']}\n"
                result += f"   🌡️ 평균: {day['temp_avg']}°C (최저: {day['temp_min']}°C, 최고: {day['temp_max']}°C)\n"
                result += f"   ☁️ {day['description']}\n"
            
            return result
        
        return "❌ 알 수 없는 날씨 데이터 형식입니다."


# 테스트 코드
if __name__ == "__main__":
    # 테스트용 (실제 사용시 환경변수에서 API 키 로드)
    API_KEY = "your_api_key_here"
    
    weather = WeatherTool(API_KEY)
    
    # 현재 날씨 테스트
    print("=== 현재 날씨 테스트 ===")
    result = weather.get_current_weather("Seoul", "KR")
    print(weather.format_weather_for_travel(result))
    
    # 예보 테스트
    print("\n=== 날씨 예보 테스트 ===")
    forecast = weather.get_forecast("Tokyo", "JP", days=3)
    print(weather.format_weather_for_travel(forecast))