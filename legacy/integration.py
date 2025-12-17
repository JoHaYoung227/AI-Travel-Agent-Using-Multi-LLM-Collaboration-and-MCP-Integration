"""
GPT API 기반 통합 여행 시스템
- OpenAI GPT-3.5-turbo 사용
- TravelPlanner 실제 데이터 활용
- TripAdvisor RAG 검색 연동
- Before/After 비교 테스트
"""

import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import pinecone
from pinecone import Pinecone
from datasets import load_dataset
import json
import random
import time
import ast
import openai
from openai import OpenAI

# =====================================================
# 1. 시스템 설정
# =====================================================

class Config:
    def __init__(self):
        # API 키들
        self.PINECONE_API_KEY = "your_key"
        self.OPENAI_API_KEY = "your_key"
        self.INDEX_NAME = "tripadvisor-reviews"
        
        # 임베딩 모델
        self.EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# =====================================================
# 2. TravelPlanner 데이터 파서 (개선)
# =====================================================

class TravelPlannerParser:
    """TravelPlanner의 실제 데이터를 파싱하고 활용"""
    
    @staticmethod # <- 추가
    def get_attractions_with_restaurants(destination: str, places_tool) -> dict:
        """관광지와 주변 식당 정보 함께 가져오기"""
        try:
            # 관광지 검색
            places_result = places_tool.search_places(destination, place_type='tourist_attraction')
            
            if not places_result.get('success'):
                return places_result
            
            # 각 관광지마다 주변 식당 검색
            places = places_result.get('places', [])
            for place in places[:5]:  # 상위 5개 관광지만
                place_id = place.get('place_id')
                if place_id:
                    restaurants = places_tool.search_restaurants_near_place(place_id, radius=500)
                    place['nearby_restaurants'] = restaurants.get('restaurants', [])
            
            return {
                'success': True,
                'places': places
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
        
    @staticmethod
    def extract_real_data(sample):
        """샘플에서 실제 사용 가능한 정보 추출 - level 필드 포함"""
        extracted = {
            'basic_info': {
                'org': sample['org'],
                'dest': sample['dest'], 
                'days': sample['days'],
                'people': sample['people_number'],
                'budget': sample['budget'],
                'query': sample['query']
            },
            'level': sample.get('level', 'easy'),  # level 필드 보존
            'hotels': [],
            'restaurants': [],
            'attractions': [],
            'flights': []
        }
        
        # annotated_plan 파싱 시도
        try:
            if isinstance(sample['annotated_plan'], str):
                plan_data = ast.literal_eval(sample['annotated_plan'])
            else:
                plan_data = sample['annotated_plan']
                
            if isinstance(plan_data, list) and len(plan_data) > 1:
                daily_plans = plan_data[1] if isinstance(plan_data[1], list) else []
                
                for day in daily_plans:
                    if isinstance(day, dict):
                        # 교통수단 정보
                        transport = day.get('transportation', '')
                        if 'Flight Number' in str(transport):
                            extracted['flights'].append(transport)
                        
                        # 숙소 정보
                        accommodation = day.get('accommodation', '')
                        if accommodation and accommodation != '-':
                            extracted['hotels'].append(accommodation)
                        
                        # 식당 정보
                        for meal in ['breakfast', 'lunch', 'dinner']:
                            restaurant = day.get(meal, '')
                            if restaurant and restaurant != '-':
                                extracted['restaurants'].append(restaurant)
                        
                        # 관광지 정보
                        attractions = day.get('attraction', '')
                        if attractions and attractions != '-':
                            # 세미콜론으로 분리된 관광지들
                            attraction_list = [a.strip() for a in str(attractions).split(';') if a.strip()]
                            extracted['attractions'].extend(attraction_list)
        
        except Exception as e:
            print(f"데이터 파싱 오류: {e}")
        
        # 중복 제거
        extracted['hotels'] = list(set(extracted['hotels']))
        extracted['restaurants'] = list(set(extracted['restaurants']))
        extracted['attractions'] = list(set(extracted['attractions']))
        extracted['flights'] = list(set(extracted['flights']))
        
        return extracted

# =====================================================
# 3. GPT API 관리자
# =====================================================

class GPTManager:
    """OpenAI GPT API 관리"""
    
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
    
    def get_completion(self, prompt, system_message="", model="gpt-3.5-turbo", max_tokens=1000):
        """GPT 응답 생성"""
        try:
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"GPT API 오류: {e}"

# =====================================================
# 4. TripAdvisor RAG 시스템
# =====================================================

class TripAdvisorRAG:
    """TripAdvisor RAG 시스템"""
    
    def __init__(self, pinecone_api_key, embedding_model):
        self.pinecone_api_key = pinecone_api_key
        self.model = SentenceTransformer(embedding_model)
        self.index = None
        
    def initialize(self):
        """RAG 시스템 초기화"""
        try:
            pc = Pinecone(api_key=self.pinecone_api_key)
            self.index = pc.Index("tripadvisor-reviews")
            print("TripAdvisor RAG 시스템 연결됨")
            return True
        except Exception as e:
            print(f"RAG 시스템 연결 실패: {e}")
            return False
    
    def search_reviews(self, query, top_k=5):
        """호텔 리뷰 검색"""
        if not self.index:
            return []
            
        try:
            query_embedding = self.model.encode([query]).tolist()[0]
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )
            
            reviews = []
            for match in results['matches']:
                reviews.append({
                    'similarity': float(match['score']),
                    'rating': match['metadata']['rating'],
                    'location_mentions': match['metadata']['location_mentions'],
                    'room_mentions': match['metadata']['room_mentions'],
                    'service_mentions': match['metadata']['service_mentions'],
                    'value_mentions': match['metadata']['value_mentions'],
                    'text': match['metadata']['text'][:400]
                })
            
            return reviews
            
        except Exception as e:
            print(f"검색 오류: {e}")
            return []

# =====================================================
# 5. 통합 여행 시스템
# =====================================================

class TravelPlanningSystem:
    """GPT 기반 통합 여행 계획 시스템"""
    
    def __init__(self, config):
        self.config = config
        self.gpt = None
        self.rag = None
        self.travel_templates = []
        
    def initialize(self):
        """시스템 초기화"""
        print("=== 시스템 초기화 중 ===")
        
        # GPT 초기화 (이제 API 키가 config에 있음)
        self.gpt = GPTManager(self.config.OPENAI_API_KEY)
        print("GPT API 연결됨")
        
        # RAG 초기화
        self.rag = TripAdvisorRAG(self.config.PINECONE_API_KEY, self.config.EMBEDDING_MODEL)
        if not self.rag.initialize():
            print("경고: RAG 시스템 사용 불가")
        
        # TravelPlanner 템플릿 로드
        self.load_travel_templates()
        
        print("시스템 초기화 완료\n")
    
    def load_travel_templates(self):
        """TravelPlanner 템플릿 로드 및 파싱"""
        print("TravelPlanner 템플릿 로드 중...")
        
        try:
            dataset = load_dataset("osunlp/TravelPlanner", "train")
            
            for sample in dataset['train']:
                extracted = TravelPlannerParser.extract_real_data(sample)
                self.travel_templates.append(extracted)
            
            print(f"총 {len(self.travel_templates)}개 템플릿 로드됨")
            
        except Exception as e:
            print(f"템플릿 로드 실패: {e}")
    
    def create_enhanced_prompt(self, user_request, use_templates=True):
        """향상된 프롬프트 생성 - 영어 버전 (디버깅 정보 포함)"""
        
        base_prompt = f"""User Request: {user_request}

Please create a detailed travel plan according to the above request. Follow this format:

Origin: [Origin]
Destination: [Destination]  
Duration: [X days]
Budget: [Budget]

Day 1:
- Transportation: [Specific flight/transport details]
- Breakfast: [Restaurant name]
- Attractions: [Specific attraction names]
- Lunch: [Restaurant name]
- Dinner: [Restaurant name]
- Accommodation: [Hotel name and price]

Day 2:
...

(Include specific venue names and price information for each day)
"""

        if use_templates and self.travel_templates:
            # 관련 템플릿 선택 (간단한 매칭)
            similar_templates = random.sample(self.travel_templates, min(2, len(self.travel_templates)))
            
            # 디버깅: 실제 사용된 템플릿 정보 출력
            print(f"\n[DEBUG] 사용된 템플릿 정보:")
            for i, template in enumerate(similar_templates, 1):
                print(f"템플릿 {i}: {template['basic_info']['org']} → {template['basic_info']['dest']}")
                print(f"  예산: ${template['basic_info']['budget']}, 일수: {template['basic_info']['days']}")
                print(f"  쿼리: {template['basic_info']['query'][:50]}...")
                if template['hotels']:
                    print(f"  호텔: {template['hotels'][:2]}")
                if template['restaurants']:
                    print(f"  식당: {template['restaurants'][:3]}")
                if template['attractions']:
                    print(f"  관광지: {template['attractions'][:3]}")
            print("[DEBUG] 템플릿 정보 끝\n")
            
            examples = "\nReference Examples:\n"
            for i, template in enumerate(similar_templates, 1):
                examples += f"\nExample {i}:\n"
                examples += f"Origin: {template['basic_info']['org']} → Destination: {template['basic_info']['dest']}\n"
                examples += f"Duration: {template['basic_info']['days']} days, Budget: ${template['basic_info']['budget']}\n"
                
                if template['hotels']:
                    examples += f"Hotel Examples: {', '.join(template['hotels'][:2])}\n"
                if template['restaurants']:
                    examples += f"Restaurant Examples: {', '.join(template['restaurants'][:3])}\n"
                if template['attractions']:
                    examples += f"Attraction Examples: {', '.join(template['attractions'][:3])}\n"
            
            return examples + "\n" + base_prompt
        
        return base_prompt
    
    def plan_trip_basic(self, user_request):
        """기본 여행 계획 (템플릿 없음)"""
        prompt = f"""Please create a travel plan for the following request:

{user_request}

Detailed travel plan:"""
        
        system_msg = "You are a travel planning expert. Please create practical and specific travel plans."
        
        return self.gpt.get_completion(prompt, system_msg)
    
    def plan_trip_enhanced(self, user_request):
        """향상된 여행 계획 (템플릿 활용) - 영어 버전"""
        prompt = self.create_enhanced_prompt(user_request, use_templates=True)
        
        system_msg = "You are a travel planning expert. Please create detailed travel plans with specific venue names, prices, and schedules based on the provided examples."
        
        return self.gpt.get_completion(prompt, system_msg)
    
    def review_hotels(self, travel_plan):
        """호텔 검토 (RAG 활용) - 영어 버전"""
        if not self.rag:
            return "RAG system is not available."
        
        # 호텔 관련 리뷰 검색
        reviews = self.rag.search_reviews("hotel accommodation booking room service", top_k=3)
        
        if not reviews:
            return "No relevant reviews found."
        
        review_context = "Reference hotel review data:\n"
        for i, review in enumerate(reviews, 1):
            review_context += f"""
Review {i}: (Rating {review['rating']}/5, Similarity {review['similarity']:.2f})
- Location mentions: {review['location_mentions']}
- Room mentions: {review['room_mentions']} 
- Service mentions: {review['service_mentions']}
- Value mentions: {review['value_mentions']}
Content: {review['text'][:200]}...
"""
        
        prompt = f"""Please review the accommodation choices for the following travel plan:

Travel Plan:
{travel_plan}

{review_context}

Based on the above review data, please analyze:
1. Expected pros and cons of planned accommodations
2. Considerations regarding location, facilities, service, and price aspects
3. Improvement suggestions

Review Results:"""
        
        system_msg = "You are a hotel review specialist. Please provide objective and practical evaluations based on review data."
        
        return self.gpt.get_completion(prompt, system_msg)
    
    def create_level_specific_prompt(self, user_request, target_level='easy', target_days='3'):
        """특정 레벨의 템플릿만 사용하는 프롬프트 생성 - 실제 level 필드 사용"""
        
        base_prompt = f"""User Request: {user_request}

Please create a detailed travel plan according to the above request. Follow this format:

Origin: [Origin]
Destination: [Destination]  
Duration: [X days]
Budget: [Budget]

Day 1:
- Transportation: [Specific details]
- Breakfast: [Restaurant name]
- Attractions: [Attraction names]
- Lunch: [Restaurant name]
- Dinner: [Restaurant name]
- Accommodation: [Hotel name and price]
...
"""

        if self.travel_templates:
            # 실제 level 필드를 사용한 템플릿 필터링
            level_templates = []
            for template in self.travel_templates:
                basic_info = template['basic_info']
                template_days = str(basic_info.get('days', ''))
                template_level = template.get('level', 'unknown')
                
                if template_days == target_days and template_level == target_level:
                    level_templates.append(template)
            
            if level_templates:
                selected_templates = random.sample(level_templates, min(2, len(level_templates)))
                
                print(f"\n[DEBUG] {target_level.upper()} 레벨 {target_days}일 템플릿 (실제 level 필드 사용):")
                for i, template in enumerate(selected_templates, 1):
                    print(f"템플릿 {i}: {template['basic_info']['org']} → {template['basic_info']['dest']}")
                    print(f"  예산: ${template['basic_info']['budget']}")
                    print(f"  실제 레벨: {template.get('level', 'N/A')}")
                    print(f"  쿼리: {template['basic_info']['query'][:50]}...")
                print("[DEBUG] 템플릿 정보 끝\n")
                
                examples = f"\n{target_level.upper()} Level Examples ({target_days} days):\n"
                for i, template in enumerate(selected_templates, 1):
                    examples += f"\nExample {i}:\n"
                    examples += f"Origin: {template['basic_info']['org']} → Destination: {template['basic_info']['dest']}\n"
                    examples += f"Duration: {template['basic_info']['days']} days, Budget: ${template['basic_info']['budget']}\n"
                    examples += f"Level: {template.get('level', 'N/A')}\n"
                    
                    if template['hotels']:
                        examples += f"Hotels: {', '.join(template['hotels'][:2])}\n"
                    if template['restaurants']:
                        examples += f"Restaurants: {', '.join(template['restaurants'][:3])}\n"
                    if template['attractions']:
                        examples += f"Attractions: {', '.join(template['attractions'][:3])}\n"
                
                return examples + "\n" + base_prompt
            else:
                print(f"\n[DEBUG] {target_level.upper()} 레벨 {target_days}일 템플릿을 찾을 수 없습니다.")
                print("[DEBUG] 사용 가능한 템플릿 레벨 확인:")
                level_counts = {}
                for template in self.travel_templates:
                    days = str(template['basic_info'].get('days', ''))
                    level = template.get('level', 'unknown')
                    key = f"{level}_{days}일"
                    level_counts[key] = level_counts.get(key, 0) + 1
                
                for key, count in level_counts.items():
                    print(f"  {key}: {count}개")
                print("[DEBUG] 기본 프롬프트를 사용합니다.\n")
        
        return base_prompt
    
    def get_attractions_with_restaurants(destination: str, places_tool) -> dict:
        """관광지와 주변 식당 정보 함께 가져오기"""
        try:
            # 관광지 검색
            places_result = places_tool.search_places(destination, place_type='tourist_attraction')
            
            if not places_result.get('success'):
                return places_result
            
            # 각 관광지마다 주변 식당 검색
            places = places_result.get('places', [])
            for place in places[:5]:  # 상위 5개 관광지만
                place_id = place.get('place_id')
                if place_id:
                    restaurants = places_tool.search_restaurants_near_place(place_id, radius=500)
                    place['nearby_restaurants'] = restaurants.get('restaurants', [])
            
            return {
                'success': True,
                'places': places
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_level_differences(self, base_query="Plan a 3-day trip to Tokyo with budget"):
        """레벨별 차이 테스트"""
        print("=== 레벨별 템플릿 효과 테스트 ===\n")
        
        # 3가지 레벨별 쿼리 생성
        test_queries = {
            'easy': f"{base_query} of $800 for 1 person",
            'medium': f"{base_query} of $2000 for 2 people with vegetarian food requirements", 
            'hard': f"{base_query} of $5000 for family of 4 with luxury hotels and no flight restrictions"
        }
        
        results = {}
        
        for level in ['easy', 'medium', 'hard']:
            print(f"{'='*20} {level.upper()} 레벨 테스트 {'='*20}")
            print(f"쿼리: {test_queries[level]}\n")
            
            # 해당 레벨 템플릿으로 프롬프트 생성
            prompt = self.create_level_specific_prompt(test_queries[level], target_level=level)
            
            # GPT 응답 생성
            system_msg = f"You are a travel expert specializing in {level}-level travel planning. Create detailed, appropriate plans."
            response = self.gpt.get_completion(prompt, system_msg)
            
            print("결과:")
            print(response)
            print("\n" + "="*70 + "\n")
            
            results[level] = {
                'query': test_queries[level],
                'response': response
            }
        
        return results
    
    def analyze_level_differences(self, results):
        """레벨별 결과 분석"""
        print("=== 레벨별 차이점 분석 ===")
        
        analysis_prompt = f"""다음은 Easy, Medium, Hard 레벨별 여행 계획 결과입니다:

EASY 레벨:
쿼리: {results['easy']['query']}
결과: {results['easy']['response'][:500]}...

MEDIUM 레벨:  
쿼리: {results['medium']['query']}
결과: {results['medium']['response'][:500]}...

HARD 레벨:
쿼리: {results['hard']['query']}
결과: {results['hard']['response'][:500]}...

다음 관점에서 차이점을 분석해주세요:
1. 예산 반영도 (저예산 vs 고예산 특성)
2. 복잡성 (제약사항 처리)
3. 상세도 (정보의 구체성)
4. 추천 수준 (기본 vs 프리미엄)

분석 결과:"""

        analysis = self.gpt.get_completion(analysis_prompt, 
            "You are an expert in travel planning analysis. Provide objective comparison.")
        
        print(analysis)
        return analysis

    def compare_systems(self, user_request):
        """시스템 비교 테스트"""
        print(f"=== 시스템 비교 테스트 ===")
        print(f"요청: {user_request}\n")
        
        # 1. 기본 계획 (템플릿 없음)
        print("1️⃣ 기본 시스템 (템플릿 없음)")
        print("-" * 50)
        basic_plan = self.plan_trip_basic(user_request)
        print(basic_plan)
        
        print("\n" + "="*70 + "\n")
        
        # 2. 향상된 계획 (템플릿 활용)
        print("2️⃣ 향상된 시스템 (TravelPlanner 템플릿 활용)")
        print("-" * 50)
        enhanced_plan = self.plan_trip_enhanced(user_request)
        print(enhanced_plan)
        
        print("\n" + "="*70 + "\n")
        
        # 3. 호텔 검토 (RAG 활용)
        print("3️⃣ 호텔 검토 (TripAdvisor RAG 활용)")
        print("-" * 50)
        hotel_review = self.review_hotels(enhanced_plan)
        print(hotel_review)
        
        return {
            'basic_plan': basic_plan,
            'enhanced_plan': enhanced_plan,
            'hotel_review': hotel_review
        }

# =====================================================
# 6. 메인 실행 함수
# =====================================================

def main():
    """메인 함수"""
    print("=== GPT 기반 통합 여행 시스템 ===\n")
    
    # 시스템 초기화 (API 키는 이제 Config에서 자동으로 설정됨)
    config = Config()
    system = TravelPlanningSystem(config)
    
    # API 키가 설정되어 있는지 확인
    if not config.OPENAI_API_KEY:
        print("OpenAI API 키가 설정되지 않았습니다.")
        return
    
    system.initialize()
    
    # 테스트 모드 선택
    print("테스트 모드를 선택하세요:")
    print("1. 비교 테스트 (Before/After)")
    print("2. 단일 여행 계획")
    print("3. 전체 테스트 세트")
    print("4. 레벨별 차이 테스트")  # 새로 추가
    
    choice = input("선택 (1-4): ").strip()
    
    if choice == "1":
        user_request = input("\n여행 요청을 입력하세요: ").strip()
        system.compare_systems(user_request)
        
    elif choice == "2":
        user_request = input("\n여행 요청을 입력하세요: ").strip()
        print("\n=== 향상된 여행 계획 ===")
        plan = system.plan_trip_enhanced(user_request)
        print(plan)
        
        if input("\n호텔 검토도 진행하시겠습니까? (y/n): ").lower() == 'y':
            print("\n=== 호텔 검토 ===")
            review = system.review_hotels(plan)
            print(review)
            
    elif choice == "3":
        test_requests = [
            "Plan a 3-day trip to Seoul with $1500 budget for 2 people",
            "서울에서 제주도 2박 3일 여행, 예산 100만원",
            "Create a 5-day luxury vacation plan for Tokyo with $3000 budget"
        ]
        
        for i, request in enumerate(test_requests, 1):
            print(f"\n{'='*20} 테스트 {i} {'='*20}")
            system.compare_systems(request)
            if i < len(test_requests):
                input("\n다음 테스트를 진행하려면 Enter를 누르세요...")
    
    elif choice == "4":
        # 레벨별 테스트 실행
        results = system.test_level_differences()
        system.analyze_level_differences(results)

if __name__ == "__main__":
    main()
