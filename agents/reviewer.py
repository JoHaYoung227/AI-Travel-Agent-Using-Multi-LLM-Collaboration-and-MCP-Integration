"""
호텔 리뷰를 분석하고 추천하는 Reviewer Agent
Pinecone에서 검색한 리뷰를 기반으로 평가
"""
from .base_agent import BaseAgent
from tools.pinecone_tool import PineconeTool
from typing import Dict, List, Any
import json

class ReviewerAgent(BaseAgent):
    """호텔 리뷰 분석 에이전트"""
    
    def __init__(self, pinecone_tool: PineconeTool):
        super().__init__(
            name="Reviewer",
            role="travel planning expert who creates detailed itineraries based on user requirements."
        )
        self.pinecone_tool = pinecone_tool
    
    def _create_review_prompt(self, hotels: List[Dict], reviews: List[Dict], preferences: Dict) -> str:
        """리뷰 분석을 위한 프롬프트 생성"""
        
        # 호텔 딕셔너리 리스트에서 이름만 추출 (수정된 부분 1)
        hotel_names = [hotel.get('name', 'Unknown Hotel') for hotel in hotels]
        
        # 리뷰를 호텔별로 그룹화
        hotel_reviews = {}
        for review in reviews:
            hotel_name = review.get('metadata', {}).get('hotel_name', 'Unknown')
            if hotel_name not in hotel_reviews:
                hotel_reviews[hotel_name] = []
            hotel_reviews[hotel_name].append(review)
        
        prompt = f"""You are a hotel review analyst. Analyze the following hotel reviews and provide recommendations.

**User Preferences:**
{json.dumps(preferences, indent=2, ensure_ascii=False)}

**Hotels to Analyze:**
{', '.join(hotel_names)}

**Reviews Data:**
"""
        
        # 각 호텔의 리뷰 추가
        for hotel, hotel_review_list in hotel_reviews.items():
            prompt += f"\n### {hotel}\n"
            for i, review in enumerate(hotel_review_list[:5], 1):  # 최대 5개만
                text = review.get('metadata', {}).get('text', '')[:200]
                rating = review.get('metadata', {}).get('rating', 0)
                prompt += f"{i}. Rating: {rating}/5 - {text}...\n"
        
        prompt += """

**Task:**
Analyze the reviews and provide:
1. Overall sentiment for each hotel
2. Strengths and weaknesses
3. Recommendation score (1-5)
4. Which hotel is best for the user based on their preferences

**Output Format (JSON):**
{
    "analysis": [
        {
            "hotel": "Hotel Name",
            "overall_score": 4.2,
            "sentiment": {
                "location": 4.5,
                "room": 4.0,
                "service": 4.3,
                "value": 3.8
            },
            "strengths": ["Clean rooms", "Great location"],
            "weaknesses": ["Expensive", "Noisy"],
            "suitable_for": "Business travelers, Couples"
        }
    ],
    "recommendations": [
        {
            "rank": 1,
            "hotel": "Hotel Name",
            "reason": "Best match for user preferences..."
        }
    ]
}

Provide the analysis now:"""
        
        return prompt
    
    def process(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        호텔 리뷰 분석 요청 처리
        
        Args:
            request: {
                'hotels': [...],  # 분석할 호텔 리스트
                'preferences': {...},  # 사용자 선호도
                'destination': '...'  # 목적지
            }
        
        Returns:
            분석 결과
        """
        hotels = request.get('hotels', [])
        preferences = request.get('preferences', {})
        destination = request.get('destination', '')
        
        if not hotels:
            return {
                "status": "error",
                "message": "No hotels to analyze"
            }
        
        # 1. Pinecone에서 각 호텔의 리뷰 검색
        all_reviews = []
        for hotel in hotels:
            query_text = f"{hotel} {destination}"
            reviews = self.pinecone_tool.search_reviews(
                        query=query_text,  
                        top_k=5
                    )
            all_reviews.extend(reviews)
        
        if not all_reviews:
            print("⚠️  No reviews found in Pinecone")
            return {
                "status": "error",
                "message": "No reviews found"
            }
        
        # 2. 리뷰 분석 프롬프트 생성
        prompt = self._create_review_prompt(hotels, all_reviews, preferences)
        
        # 3. GPT API 호출
        try:
            response = self.generate_response(
                user_message=prompt, 
                system_context="You are a hotel review analyst who strictly outputs only JSON.",
                json_mode=True
                )
            result = json.loads(response)
            
            return {
                "status": "success",
                "analysis": result.get('analysis', []),
                "recommendations": result.get('recommendations', []),
                "total_reviews_analyzed": len(all_reviews)
            }
            
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON parsing failed: {e}")
            print(f"Raw response: {response[:200]}...")
            
            # JSON 파싱 실패 시 기본 응답
            return {
                "status": "error",
                "message": "Failed to parse GPT response",
                "raw_response": response[:500]
            }
        
        except Exception as e:
            print(f"❌ Error in ReviewerAgent: {e}")
            return {
                "status": "error",
                "message": str(e)
            }