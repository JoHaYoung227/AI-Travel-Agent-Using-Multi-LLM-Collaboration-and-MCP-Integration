"""여행 일정을 생성하는 Planner Agent (호텔 및 항공권 정보 통합)"""
from .base_agent import BaseAgent
from typing import Dict, Any
from datasets import load_dataset
import json
import random
from typing import Dict, Any, Optional

class PlannerAgent(BaseAgent):
    """여행 계획 생성 에이전트"""

    def __init__(self):
        super().__init__(
            name="Planner",
            role="travel planning expert who creates detailed itineraries based on user requirements.",
        )
        self.templates = []
        self.loaded = False

    # --------------------------------------------------------------
    # 템플릿 로딩
    # --------------------------------------------------------------
    def load_templates(self) -> bool:
        """TravelPlanner 데이터셋에서 템플릿 로드 (실패 시 기본 템플릿 사용)"""
        if self.loaded:
            print("✅ Templates already loaded")
            return True

        try:
            print("📂 Loading TravelPlanner dataset...")
            dataset = load_dataset("osunlp/TravelPlanner", "validation")

            self.templates = []
            split_name = "train" if "train" in dataset else list(dataset.keys())[0]
            for item in dataset[split_name]:
                template = {
                    "org": item.get("org", ""),
                    "dest": item.get("dest", ""),
                    "days": item.get("days", 3),
                    "people": item.get("people_number", 2),
                    "query": item.get("query", ""),
                    "reference": item.get("reference_information", {}),
                    "level": item.get("level", "easy"),
                }
                self.templates.append(template)

            self.loaded = True
            print(f"✅ Loaded {len(self.templates)} templates from TravelPlanner")
            return True

        except Exception as e:
            print(f"⚠️  Failed to load TravelPlanner dataset: {e}")
            print("   Using fallback templates instead...")
            self._load_fallback_templates()
            return False

    def _load_fallback_templates(self) -> None:
        """데이터셋 로드 실패 시 기본 템플릿 사용"""
        self.templates = [
            {
                "org": "Seoul",
                "dest": "Tokyo",
                "days": 3,
                "people": 2,
                "query": "Plan a 3-day trip to Tokyo from Seoul for 2 people",
                "reference": {},
                "level": "easy",
            },
            {
                "org": "Seoul",
                "dest": "Osaka",
                "days": 5,
                "people": 2,
                "query": "Plan a 5-day trip to Osaka from Seoul for 2 people",
                "reference": {},
                "level": "medium",
            },
        ]
        self.loaded = True

    # --------------------------------------------------------------
    # 템플릿 선택
    # --------------------------------------------------------------
    def _find_similar_template(self, query: Dict) -> Dict:
        """사용자 쿼리와 가장 유사한 템플릿 찾기"""
        dest = query.get("destination", "").lower()
        days = query.get("days", 3)

        similar = []
        for t in self.templates:
            template_dest = t.get("dest", "").lower()
            template_days = t.get("days", 3)

            if dest and (dest in template_dest or template_dest in dest):
                similar.append(t)
            elif abs(template_days - days) <= 1:
                similar.append(t)

        if not similar:
            similar = self.templates

        return random.choice(similar) if similar else {}

    # --------------------------------------------------------------
    # 프롬프트 생성
    # --------------------------------------------------------------
    def _create_prompt(
        self,
        query: Dict[str, Any],
        template: Dict[str, Any],
        hotel_info: Optional[Dict[str, Any]] = None,
        flight_info: Optional[Dict[str, Any]] = None,
        places_info: Optional[Dict[str, Any]] = None,
        style_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """여행 계획 생성을 위한 프롬프트 작성 (호텔/항공/장소 정보 포함)"""

        departure_date = query.get("departure_date", "YYYY-MM-DD")
        return_date = query.get("return_date", "YYYY-MM-DD")
        origin = query.get("origin", "")
        destination = query.get("destination", "")

        try:
            trip_days = int(query.get("days", 3))
        except Exception:
            trip_days = 3

        if trip_days < 1:
            trip_days = 1
        if trip_days > 5:
            trip_days = 5

        prompt = (
            "당신은 전문 여행 계획 전문가입니다. 사용자의 요청에 따라 상세한 여행 계획을 작성해주세요.\n\n"
            "**여행 요청:**\n"
            f"- 출발지: {origin}\n"
            f"- 도착지: {destination}\n"
            f"- 출발일: {departure_date}\n"
            f"- 도착일: {return_date}\n"
            f"- 기간: {trip_days}일 (시스템은 최대 5일까지 상세 일정을 제공합니다)\n"
            f"- 인원: {query.get('people', 2)}명\n"
            f"- 예산: ₩{query.get('budget', 2000000)}\n"
            f"- 선호사항: {json.dumps(query.get('preferences', {}), ensure_ascii=False)}\n\n"
            "**참고 템플릿 (유사 여행):**\n"
            f"{json.dumps(template, indent=2, ensure_ascii=False)}\n"
        )

        # 여행 스타일 정보 추가
        if style_info and style_info.get('style_name'):
            prompt += f"- 여행 스타일: {style_info.get('style_name')}\n"
            if style_info.get('characteristics'):
                prompt += f"- 스타일 특성: {', '.join(style_info.get('characteristics', []))}\n"
        prompt += "\n"

        # ---------- 호텔 정보 ----------
        if hotel_info and hotel_info.get("success"):
            prompt += "\n\n**추천 호텔 정보:**\n"
            hotels = hotel_info.get("hotels", [])[:3]
            for i, hotel in enumerate(hotels, 1):
                price = hotel.get("price", {}) or {}
                currency = price.get("currency", "KRW")
                per_night = price.get("per_night", 0)
                total = price.get("total", 0)

                prompt += f"{i}. {hotel.get('name', '이름 없음')}\n"
                prompt += f"   - 주소: {hotel.get('address', '주소 정보 없음')}\n"
                prompt += f"   - 1박 평균 가격: {currency} {per_night:,.0f}\n"
                prompt += f"   - 총액: {currency} {total:,.0f}\n"

                rating = hotel.get("rating")
                if rating and rating != "N/A":
                    prompt += f"   - 등급: {rating}성급\n"
                board_type = hotel.get("board_type")
                if board_type:
                    prompt += f"   - 식사: {board_type}\n"

        # ---------- 장소/식당 정보 ----------
        if places_info and places_info.get("success"):
            prompt += "\n\n**추천 관광지 및 주변 식당:**\n"
            for place in places_info.get("places", [])[:5]:
                prompt += f"\n📍 {place.get('name', '이름 없음')}\n"
                prompt += f"   주소: {place.get('address', 'N/A')}\n"
                prompt += f"   평점: {place.get('rating', 'N/A')}\n"

                restaurants = place.get("nearby_restaurants", []) or []
                if restaurants:
                    prompt += "   주변 식당:\n"
                    for rest in restaurants[:3]:
                        price_level = rest.get("price_level", 2) or 2
                        prompt += (
                            f"   - {rest.get('name', '식당')} (평점: {rest.get('rating', 'N/A')}, "
                            f"가격: {'₩' * int(price_level)})\n"
                        )

        # ---------- 항공 정보 ----------
        if flight_info and flight_info.get("success"):
            prompt += "\n\n**추천 항공편 정보:**\n"
            flights = flight_info.get("flights", [])[:3]
            for i, flight in enumerate(flights, 1):
                airlines = ", ".join(
                    flight.get("validating_airline_codes", ["항공사 정보 없음"])
                )
                price = flight.get("price", {}) or {}
                currency = price.get("currency", "KRW")
                total = price.get("total", 0)

                prompt += f"{i}. {airlines}\n"
                prompt += f"   - 가격: {currency} {total:,.0f}\n"

                outbound = flight.get("outbound")
                if outbound:
                    stops_text = (
                        "직항" if outbound.get("stops", 0) == 0 else f"경유 {outbound.get('stops', 0)}회"
                    )
                    prompt += (
                        f"   - 가는 편: {outbound['departure']['airport']} → {outbound['arrival']['airport']} "
                        f"({outbound.get('duration', 'N/A')}, {stops_text})\n"
                    )

                inbound = flight.get("inbound")
                if inbound:
                    stops_text = (
                        "직항" if inbound.get("stops", 0) == 0 else f"경유 {inbound.get('stops', 0)}회"
                    )
                    prompt += (
                        f"   - 오는 편: {inbound['departure']['airport']} → {inbound['arrival']['airport']} "
                        f"({inbound.get('duration', 'N/A')}, {stops_text})\n"
                    )

        # ---------- 필수 지침 ----------
        prompt += (
            "\n**CRITICAL Instructions - 반드시 따라야 합니다:**\n"
            "0. 여행 도시는 반드시 위에 명시된 **도착지(destination)** 기준으로 계획해야 합니다.\n"
            "   - 예시 JSON이나 템플릿에 등장하는 도쿄, 오사카 등 다른 도시는 사용하지 마세요.\n"
            "   - 실제 관광지/식당/활동은 모두 도착지 도시와 그 인근 지역에서만 선택하세요.\n"
            "6. **일정 일수 규칙 (CRITICAL):**\n"
            f"   - 이번 여행은 총 **{trip_days}일**입니다.\n"
            f"   - 아래 JSON에서 `days` 값은 반드시 {trip_days}와 같아야 합니다.\n"
            f"   - `itinerary` 배열에는 day 1부터 day {trip_days}까지, "
            f"각 날짜(day)마다 하나의 객체를 포함해야 합니다.\n"
            "   - 하루도 빠뜨리거나 추가하지 마세요. (예: 3일 여행이면 day 1, day 2, day 3만 있어야 함)\n"
            "   - 시스템은 최대 5일까지 상세 일정을 지원하므로, 5일을 초과하는 요청이 와도 5일까지만 생성하세요.\n\n"
            "1. 모든 출력(여행 계획, 교통, 숙소, 관광지 이름 등)은 **한국어**로 작성되어야 합니다.\n\n"
            "2. **항공편 선택 (필수):**\n"
            "   - 위에 제공된 항공편 리스트에서 **반드시 하나를 선택**하세요\n"
            "   - **CRITICAL:** 선택된 항공편 및 호텔 비용의 총합이 전체 예산의 80%를 초과해서는 안됩니다.\n"
            "   - Day 1 교통편에 선택한 항공사명, 출발시간, 도착시간, 가격을 명시하세요\n\n"
            "3. **호텔 선택 (필수):**\n"
            "   - 위에 제공된 호텔 리스트에서 **반드시 하나를 선택**하세요\n"
            "   - 각 Day의 숙소에 선택한 호텔명, 1박 가격을 명시하세요\n\n"
            "4. **관광지 선택:**\n"
            "   - 각 Day마다 3개의 관광지를 포함하세요\n"
            "   - 관광지 이름과 간단한 설명(1-2문장)\n\n"
            "5. **식사 추천 (CRITICAL - 매우 중요):**\n"
            "   - 제공된 관광지별 nearby_restaurants 정보를 **반드시 활용**하세요\n"
            "   - 각 식사마다 해당 일정의 관광지 근처 실제 식당을 추천하세요\n"
            '   - 형식: "식당명 - 추천메뉴 (관광지명 근처)"\n'
            "   - nearby_restaurants에서 rating이 높은 순으로 선택하세요\n\n"
            "6. **예산 계산:**\n"
            "   - 항공편 + 호텔 + 식사 + 관광 비용을 합산하여 총 예산 내로 조정하세요\n"
            "   - 각 Day마다 일일 예산(daily_cost)을 계산하세요\n\n"
            "※ 제공된 JSON 예시는 \"형태\"만 참고용입니다. 예시 안에 들어 있는 호텔/관광지/식당 이름과 설명은 절대로 그대로 사용하지 말고, 이번 여행 목적지와 도착지에 맞게 모두 새로 작성해야 합니다.\n"
            "# Output Format (JSON):\n"
            "관광지 이름은 반드시 한글로 작성하세요."
            "Example: Senso-ji (X) → 센소지 또는 아사쿠사 사원 (O)"
        )

        # ---------- JSON 포맷 예시 ----------
        json_format = """{
    "destination": "도시, 국가 (예: 일본 도쿄)",
    "days": 이번 여행 총 일수 (예: 3 또는 5),
    "people": 여행 인원 수 (예: 2),
    "estimated_cost": 전체 예상 비용 (정수),
    "selected_flight": {
        "airline": "선택한 항공사 이름",
        "price": 1000000,
        "outbound": "출국편 요약 (예: ICN 15:40 → NRT 18:05)",
        "inbound": "귀국편 요약 (예: NRT 20:00 → ICN 22:30)",
        "booking_url": "항공권 예약 링크 (있으면)"
    },
    "itinerary": [
        {
            "day": 1,
            "date": "YYYY-MM-DD",
            "transportation": {
                "type": "교통수단 (예: 비행기/지하철/버스/도보)",
                "details": "간단한 이동 설명",
                "cost": 0
            },
            "accommodation": {
                "name": "이날 숙소 이름",
                "address": "숙소 주소",
                "type": "숙소 유형",
                "estimated_cost": 0
            },
            "attractions": [
                {
                    "name": "관광지 이름",
                    "description": "관광지에 대한 짧은 설명",
                    "estimated_cost": 0
                }
            ],
            "meals": [
                {
                    "type": "점심/저녁",
                    "suggestion": "식당 이름 + 메뉴 추천",
                    "estimated_cost": 0
                }
            ],
            "daily_cost": 0
        }
    ],
    "budget_breakdown": {
        "flight_total": 0,
        "hotel_total": 0,
        "food_total": 0,
        "attractions_total": 0,
        "transportation_total": 0,
        "total": 0
    }
}"""
        prompt += json_format
        prompt += "\nGenerate the complete itinerary now:"

        return prompt

    # --------------------------------------------------------------
    # 메인 엔트리
    # --------------------------------------------------------------
    def process(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """여행 일정 생성 요청 처리"""

        query = request.get("query", {})
        hotel_info = request.get("hotel_info")
        flight_info = request.get("flight_info")
        places_info = request.get("places_info")
        style_info = request.get("style_info", {})

        # 1. 템플릿 로드
        if not self.loaded:
            self.load_templates()

        # 2. 유사 템플릿 선택
        template = self._find_similar_template(query)

        # 3. 프롬프트 생성
        prompt = self._create_prompt(query, template, hotel_info, flight_info, places_info, style_info)

        # 4. GPT 호출
        try:
            response = self.generate_response(
                user_message=prompt,
                system_context="You are an expert travel planner who strictly outputs only JSON.",
                json_mode=True,
            )

            if isinstance(response, str) and response.startswith("Error:"):
                raise Exception(response)

            result = json.loads(response)

            return {
                "status": "success",
                "itinerary": result,
                "template_used": template.get("query", "unknown"),
            }

        except json.JSONDecodeError as e:
            print(f"⚠️  JSON parsing failed: {e}")
            print(
                f"Raw response: {response[:200]}..."
                if isinstance(response, str)
                else "Raw response not string"
            )
            return {
                "status": "error",
                "message": "Failed to parse GPT response",
                "raw_response": response[:500] if isinstance(response, str) else str(response),
                "itinerary": {
                    "destination": query.get("destination", "Unknown"),
                    "days": query.get("days", 3),
                    "people": query.get("people", 2),
                    "estimated_cost": query.get("budget", 2000000),
                    "itinerary": [],
                    "budget_breakdown": {},
                },
            }

        except Exception as e:
            print(f"❌ Error in PlannerAgent: {e}")
            return {
                "status": "error",
                "message": str(e),
            }

    def inject_photos_into_itinerary(itinerary, places_info):
        """모든 관광지에 사진 주입"""
        
        # places_info에서 장소명 -> photo_url 매핑 생성
        photo_map = {}
        for place in places_info.get('places', []):
            name = place.get('name', '').lower()
            photo_url = place.get('photo_url')
            if photo_url:
                photo_map[name] = photo_url
        
        # 일정의 각 날짜, 각 활동에 사진 매칭
        for day in itinerary:
            for activity in day.get('activities', []):
                activity_name = activity.get('activity', '').lower()
                
                # 정확히 매칭되는 사진 찾기
                matched = False
                for place_name, photo_url in photo_map.items():
                    if place_name in activity_name or activity_name in place_name:
                        activity['photo_url'] = photo_url
                        print(f"✅ 관광지 이미지 매칭: {activity.get('activity')} -> {photo_url[:50]}...")
                        matched = True
                        break
                
                if not matched:
                    activity['photo_url'] = None
        
        return itinerary