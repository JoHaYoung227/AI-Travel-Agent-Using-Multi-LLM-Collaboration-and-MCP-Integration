"""
여행 스타일별 맞춤 추천을 제공하는 Stylist Agent
사용자의 여행 스타일을 분석하고 개인화된 추천을 생성
"""
from .base_agent import BaseAgent
from tools.pinecone_tool import PineconeTool
from typing import Dict, List, Any
import json

class StylistAgent(BaseAgent):
    """여행 스타일 분석 및 맞춤 추천 에이전트"""
    
    def __init__(self, pinecone_tool: PineconeTool):
        super().__init__(
            name="Stylist",
            role="travel style expert who provides personalized recommendations based on traveler types and preferences"
        )
        self.pinecone_tool = pinecone_tool
        self.travel_styles = {
            "family": {
                "name": "가족여행",
                "keywords": ["family", "kids", "children", "가족", "아이", "어린이"],
                "characteristics": ["안전한 환경", "가족친화시설", "교육적 가치", "편의시설 완비"],
                "recommendations": {
                    "accommodations": ["family room", "connecting rooms", "resort with kids club"],
                    "activities": ["theme parks", "museums", "nature centers", "beaches"],
                    "dining": ["family restaurants", "kid-friendly menu", "buffet style"],
                    "transportation": ["comfortable seating", "easy transfers", "short travel times"]
                }
            },
            "business": {
                "name": "비즈니스",
                "keywords": ["business", "corporate", "meeting", "conference", "비즈니스", "업무", "회의"],
                "characteristics": ["효율성", "고품질 서비스", "비즈니스 시설", "접근성"],
                "recommendations": {
                    "accommodations": ["business hotel", "conference facilities", "wifi", "24h service"],
                    "activities": ["city center", "business district", "networking venues"],
                    "dining": ["fine dining", "business lunch", "hotel restaurants"],
                    "transportation": ["airport proximity", "taxi/uber availability", "punctual service"]
                }
            },
            "backpacker": {
                "name": "백패킹",
                "keywords": ["backpacker", "budget", "hostel", "cheap", "백패커", "배낭여행", "저렴"],
                "characteristics": ["경제성", "현지문화 체험", "자유로운 일정", "소셜 활동"],
                "recommendations": {
                    "accommodations": ["hostel", "guesthouse", "shared room", "budget hotel"],
                    "activities": ["free walking tours", "local markets", "hiking", "street food"],
                    "dining": ["street food", "local cuisine", "budget restaurants", "cooking facilities"],
                    "transportation": ["public transport", "walking", "budget airlines", "train"]
                }
            },
            "cultural": {
                "name": "문화탐방",
                "keywords": ["culture", "history", "museum", "heritage", "문화", "역사", "박물관", "유산"],
                "characteristics": ["교육적 가치", "역사적 중요성", "문화적 체험", "깊이 있는 탐방"],
                "recommendations": {
                    "accommodations": ["boutique hotel", "historic area", "cultural district"],
                    "activities": ["museums", "historical sites", "cultural performances", "art galleries"],
                    "dining": ["traditional cuisine", "cultural restaurants", "local specialties"],
                    "transportation": ["guided tours", "cultural tour buses", "walking tours"]
                }
            },
            "luxury": {
                "name": "럭셔리",
                "keywords": ["luxury", "premium", "high-end", "exclusive", "럭셔리", "프리미엄", "고급"],
                "characteristics": ["최상급 서비스", "독점적 경험", "프리미엄 품질", "개인 맞춤 서비스"],
                "recommendations": {
                    "accommodations": ["5-star hotel", "luxury resort", "private villa", "suite"],
                    "activities": ["private tours", "exclusive experiences", "premium attractions"],
                    "dining": ["michelin restaurants", "fine dining", "chef's table", "wine tasting"],
                    "transportation": ["business class", "private transfer", "luxury car", "helicopter"]
                }
            },
            "adventure": {
                "name": "모험여행",
                "keywords": ["adventure", "outdoor", "extreme", "hiking", "모험", "아웃도어", "등산", "익스트림"],
                "characteristics": ["활동적", "도전적", "자연친화", "체험 중심"],
                "recommendations": {
                    "accommodations": ["mountain lodge", "camping", "eco-lodge", "adventure hostel"],
                    "activities": ["hiking", "rock climbing", "water sports", "wildlife watching"],
                    "dining": ["local food", "outdoor dining", "energy food", "local specialties"],
                    "transportation": ["4WD vehicle", "hiking", "adventure tours", "local transport"]
                }
            }
        }
    
    def analyze_travel_style(self, query: Dict) -> Dict[str, Any]:
        """사용자 쿼리에서 여행 스타일 분석"""
        user_text = str(query).lower()
        
        style_scores = {}
        for style_id, style_info in self.travel_styles.items():
            score = 0
            matched_keywords = []
            
            # 키워드 매칭
            for keyword in style_info["keywords"]:
                if keyword in user_text:
                    score += 1
                    matched_keywords.append(keyword)
            
            style_scores[style_id] = {
                "score": score,
                "matched_keywords": matched_keywords,
                "style_info": style_info
            }
        
        # 가장 높은 점수의 스타일 선택
        primary_style = max(style_scores.items(), key=lambda x: x[1]["score"])
        
        # 점수가 0이면 기본 스타일로 설정
        if primary_style[1]["score"] == 0:
            # 인원 수나 예산을 기반으로 추정
            people = query.get("people", 1)
            budget = query.get("budget", 0)
            
            if people >= 3:
                primary_style = ("family", style_scores["family"])
            elif budget >= 3000000:  # 300만원 이상
                primary_style = ("luxury", style_scores["luxury"])
            elif budget <= 1000000:  # 100만원 이하
                primary_style = ("backpacker", style_scores["backpacker"])
            else:
                primary_style = ("cultural", style_scores["cultural"])
        
        return {
            "primary_style": primary_style[0],
            "style_name": primary_style[1]["style_info"]["name"],
            "confidence": primary_style[1]["score"],
            "matched_keywords": primary_style[1]["matched_keywords"],
            "all_scores": style_scores
        }
    
    def generate_style_recommendations(self, style_analysis: Dict, base_itinerary: str = None) -> Dict[str, Any]:
        """스타일 분석 결과를 기반으로 맞춤 추천 생성"""
        primary_style = style_analysis["primary_style"]
        style_info = self.travel_styles[primary_style]
        
        prompt = f"""당신은 여행 스타일 전문가입니다. 분석된 여행 스타일에 맞는 맞춤형 추천을 제공해주세요.

**분석된 여행 스타일:**
- 스타일: {style_analysis['style_name']} ({primary_style})
- 신뢰도: {style_analysis['confidence']}/5
- 매칭 키워드: {', '.join(style_analysis['matched_keywords'])}

**스타일 특성:**
{json.dumps(style_info['characteristics'], ensure_ascii=False)}

**추천 가이드라인:**
{json.dumps(style_info['recommendations'], indent=2, ensure_ascii=False)}
"""

        if base_itinerary:
            prompt += f"""

**기본 여행 일정:**
{base_itinerary}

위 일정을 {style_analysis['style_name']} 스타일에 맞게 개선하고 보완해주세요.
"""
        else:
            prompt += """

**요청사항:**
위 스타일에 맞는 여행 추천사항을 다음 형식으로 제공해주세요:
1. 숙소 추천
2. 활동 및 관광지 추천  
3. 식당 및 음식 추천
4. 교통수단 추천
5. 특별한 팁 및 주의사항
"""

        try:
            response = self.generate_response(
                user_message=prompt,
                system_context="여행 스타일 전문가로서 구체적이고 실용적인 추천을 제공하세요.",
                temperature=0.7
            )
            
            return {
                "success": True,
                "style_analysis": style_analysis,
                "recommendations": response,
                "style_characteristics": style_info['characteristics']
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"추천 생성 실패: {str(e)}",
                "style_analysis": style_analysis
            }
    
    def process(self, query: Dict) -> Dict[str, Any]:
        """메인 처리 함수 - MCP 호환"""
        try:
            # 1. 여행 스타일 분석
            style_analysis = self.analyze_travel_style(query)
            
            # 2. 기본 일정이 있으면 개선, 없으면 새로 생성
            base_itinerary = query.get("base_itinerary", "")
            
            # 3. 스타일 맞춤 추천 생성
            recommendations = self.generate_style_recommendations(style_analysis, base_itinerary)
            
            return {
                "agent": self.name,
                "success": recommendations["success"],
                "data": {
                    "style_analysis": style_analysis,
                    "recommendations": recommendations.get("recommendations", ""),
                    "characteristics": recommendations.get("style_characteristics", []),
                    "style_name": style_analysis["style_name"]
                }
            }
            
        except Exception as e:
            return {
                "agent": self.name,
                "success": False,
                "error": f"Stylist processing error: {str(e)}"
            }
    
    def enhance_itinerary(self, itinerary: str, style: str = None, preferences: Dict = None) -> str:
        """기존 일정을 스타일에 맞게 개선"""
        if style and style in self.travel_styles:
            style_info = self.travel_styles[style]
        else:
            # 선호도를 기반으로 스타일 추정
            dummy_query = preferences or {}
            style_analysis = self.analyze_travel_style(dummy_query)
            style_info = self.travel_styles[style_analysis["primary_style"]]
        
        prompt = f"""다음 여행 일정을 {style_info['name']} 스타일에 맞게 개선해주세요.

**원본 일정:**
{itinerary}

**스타일 특성:**
{json.dumps(style_info['characteristics'], ensure_ascii=False)}

**개선 가이드라인:**
{json.dumps(style_info['recommendations'], indent=2, ensure_ascii=False)}

원본 일정의 구조는 유지하되, 각 항목을 스타일에 맞게 구체적으로 개선해주세요.
예를 들어, 숙소명, 레스토랑명, 구체적인 활동 등을 스타일에 맞게 제안해주세요.
"""
        
        try:
            enhanced = self.generate_response(
                user_message=prompt,
                system_context="여행 일정 개선 전문가로서 실용적이고 구체적인 개선안을 제시하세요.",
                temperature=0.6
            )
            return enhanced
            
        except Exception as e:
            print(f"일정 개선 실패: {e}")
            return itinerary  # 실패 시 원본 반환
    
    def get_style_summary(self, style_id: str) -> Dict[str, Any]:
        """특정 스타일의 요약 정보 반환"""
        if style_id in self.travel_styles:
            style_info = self.travel_styles[style_id]
            return {
                "name": style_info["name"],
                "characteristics": style_info["characteristics"],
                "keywords": style_info["keywords"]
            }
        return {}
    
    def get_all_styles(self) -> Dict[str, Dict]:
        """모든 여행 스타일 정보 반환"""
        return {
            style_id: {
                "name": info["name"],
                "characteristics": info["characteristics"]
            }
            for style_id, info in self.travel_styles.items()
        }

# 사용 예시 및 테스트 함수
def test_stylist_agent():
    """Stylist Agent 테스트"""
    stylist = StylistAgent()
    
    # 테스트 쿼리들
    test_queries = [
        {
            "query": "가족들과 함께 아이들과 가는 여행을 계획하고 있어요",
            "people": 4,
            "budget": 2000000
        },
        {
            "query": "business trip for corporate meeting",
            "people": 2,
            "budget": 3000000
        },
        {
            "query": "저렴하게 배낭여행을 하고 싶어요",
            "people": 1,
            "budget": 800000
        }
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n=== 테스트 {i} ===")
        print(f"쿼리: {query}")
        
        # 스타일 분석
        style_analysis = stylist.analyze_travel_style(query)
        print(f"분석 결과: {style_analysis['style_name']} (신뢰도: {style_analysis['confidence']})")
        
        if style_analysis['matched_keywords']:
            print(f"매칭 키워드: {', '.join(style_analysis['matched_keywords'])}")

if __name__ == "__main__":
    test_stylist_agent()