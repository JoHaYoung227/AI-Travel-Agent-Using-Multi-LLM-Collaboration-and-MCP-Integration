"""
TravelPlanner 데이터를 LLM 프롬프트에 직접 포함하는 시스템
- 45개 train 데이터를 템플릿으로 활용
- 난이도별, 일수별 예시 제공
- 플래너 LLM용 프롬프트 생성
"""

from datasets import load_dataset
import json
import random

# =====================================================
# 1. TravelPlanner 데이터 로드 및 정리
# =====================================================

def load_travelplanner_templates():
    """TravelPlanner train 데이터를 템플릿으로 로드"""
    print("TravelPlanner 데이터 로드 중...")
    dataset = load_dataset("osunlp/TravelPlanner", "train")
    train_data = dataset['train']
    
    print(f"총 {len(train_data)}개 템플릿 로드됨")
    
    # 난이도별, 일수별로 분류
    templates = {
        'easy': {'3': [], '5': [], '7': []},
        'medium': {'3': [], '5': [], '7': []},
        'hard': {'3': [], '5': [], '7': []}
    }
    
    for sample in train_data:
        level = sample['level']
        days = str(sample['days'])
        templates[level][days].append(sample)
    
    # 분류 결과 출력
    print("\n=== 템플릿 분류 결과 ===")
    for level in templates:
        for days in templates[level]:
            count = len(templates[level][days])
            print(f"{level.upper()} {days}일: {count}개")
    
    return templates

# =====================================================
# 2. 프롬프트 생성 함수들
# =====================================================

def format_travel_plan(sample):
    """여행 계획을 읽기 쉬운 형태로 포맷팅"""
    
    # 기본 정보는 항상 출력
    formatted_plan = f"""
출발지: {sample['org']}
목적지: {sample['dest']}
기간: {sample['days']}일
인원: {sample['people_number']}명
예산: ${sample['budget']}
날짜: {sample['date']}
요청: {sample['query']}

여행 계획:
"""
    
    # annotated_plan이 있으면 파싱 시도
    if 'annotated_plan' in sample and sample['annotated_plan']:
        try:
            # 문자열인 경우 JSON 파싱 시도
            if isinstance(sample['annotated_plan'], str):
                # 먼저 eval 시도 (Python 형식일 수 있음)
                try:
                    plan_data = eval(sample['annotated_plan'])
                except:
                    # JSON 파싱 시도
                    plan_data = json.loads(sample['annotated_plan'])
            else:
                plan_data = sample['annotated_plan']
            
            # 리스트 형태인지 확인
            if isinstance(plan_data, list) and len(plan_data) > 1:
                daily_plans = plan_data[1] if isinstance(plan_data[1], list) else []
                
                for i, day_plan in enumerate(daily_plans, 1):
                    if isinstance(day_plan, dict) and day_plan:  # 빈 dict가 아닌 경우만
                        formatted_plan += f"""
Day {i}:
- 현재 위치: {day_plan.get('current_city', 'N/A')}
- 교통: {day_plan.get('transportation', 'N/A')}
- 아침: {day_plan.get('breakfast', 'N/A')}
- 관광지: {day_plan.get('attraction', 'N/A')}
- 점심: {day_plan.get('lunch', 'N/A')}
- 저녁: {day_plan.get('dinner', 'N/A')}
- 숙소: {day_plan.get('accommodation', 'N/A')}
"""
        except Exception as e:
            print(f"계획 파싱 시도 실패: {e}")
            # 원시 데이터 일부만 출력
            plan_str = str(sample['annotated_plan'])[:200] + "..." if len(str(sample['annotated_plan'])) > 200 else str(sample['annotated_plan'])
            formatted_plan += f"\n원시 계획 데이터:\n{plan_str}"
    
    return formatted_plan.strip()

def create_planner_prompt(user_query, templates, num_examples=3):
    """플래너 LLM용 프롬프트 생성"""
    
    # 사용자 쿼리에서 패턴 추출 (간단한 키워드 매칭)
    query_lower = user_query.lower()
    
    # 일수 추출
    target_days = '3'  # 기본값
    if '5 day' in query_lower or '5일' in query_lower:
        target_days = '5'
    elif '7 day' in query_lower or '7일' in query_lower:
        target_days = '7'
    
    # 난이도 추출 (예산이나 제약사항으로 판단)
    target_level = 'easy'  # 기본값
    if 'budget' in query_lower and '$' in query_lower:
        # 예산이 명시된 경우 medium으로
        target_level = 'medium'
    
    # 해당하는 템플릿에서 예시 선택
    available_templates = templates[target_level][target_days]
    if not available_templates:
        # 해당 조건의 템플릿이 없으면 다른 조건에서 가져오기
        available_templates = []
        for level in templates:
            for days in templates[level]:
                available_templates.extend(templates[level][days])
    
    # 랜덤하게 예시 선택
    selected_examples = random.sample(
        available_templates, 
        min(num_examples, len(available_templates))
    )
    
    # 프롬프트 구성
    prompt = """당신은 전문 여행 계획 전문가입니다. 사용자의 요청에 따라 상세한 여행 계획을 작성해주세요.

다음 예시들을 참고해서 비슷한 형식으로 여행 계획을 작성해주세요:

"""
    
    # 예시 추가
    for i, example in enumerate(selected_examples, 1):
        formatted_example = format_travel_plan(example)
        prompt += f"""
=== 예시 {i} ===
사용자 요청: {example['query']}

{formatted_example}

"""
    
    # 실제 사용자 요청 추가
    prompt += f"""
=== 이제 다음 요청에 대한 여행 계획을 작성해주세요 ===
사용자 요청: {user_query}

여행 계획:
"""
    
    return prompt

def create_simple_examples_prompt(templates, difficulty='easy', days='3', num_examples=2):
    """간단한 예시 프롬프트 생성 (특정 조건)"""
    
    available_templates = templates[difficulty][days]
    if not available_templates:
        print(f"경고: {difficulty} {days}일 템플릿이 없습니다.")
        return ""
    
    selected = random.sample(available_templates, min(num_examples, len(available_templates)))
    
    prompt = f"다음은 {difficulty} 난이도 {days}일 여행 계획 예시입니다:\n\n"
    
    for i, example in enumerate(selected, 1):
        formatted = format_travel_plan(example)
        prompt += f"예시 {i}:\n{formatted}\n\n"
    
    return prompt

# =====================================================
# 3. LLM 연동 시스템
# =====================================================

def get_llm_response(prompt, llm_function):
    """LLM에 프롬프트를 보내고 응답 받기"""
    try:
        response = llm_function(prompt)
        return response
    except Exception as e:
        print(f"LLM 응답 오류: {e}")
        return None

# Mock LLM (테스트용)
def mock_llm(prompt):
    """테스트용 간단한 LLM"""
    return f"""
출발지: 서울
목적지: 부산
기간: 3일
예산: $800

Day 1:
- 교통: KTX 서울역 → 부산역
- 점심: 부산 돼지국밥
- 관광지: 해운대 해수욕장
- 저녁: 자갈치시장 회센터
- 숙소: 해운대 근처 호텔

Day 2:
- 아침: 호텔 조식
- 관광지: 감천문화마을, 태종대
- 점심: 밀면 전문점
- 저녁: 광복로 먹거리
- 숙소: 동일 호텔

Day 3:
- 아침: 호텔 조식
- 관광지: 용두산공원, 부산타워
- 점심: 부산역 근처 식당
- 교통: KTX 부산역 → 서울역
"""

# OpenAI API 연동 (실제 사용시)
def openai_llm(prompt, api_key=None):
    """OpenAI GPT 연동"""
    if not api_key:
        print("OpenAI API 키가 필요합니다.")
        return None
    
    try:
        import openai
        openai.api_key = api_key
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI API 오류: {e}")
        return None

# =====================================================
# 4. 메인 실행 함수
# =====================================================

def main():
    """메인 시스템 실행"""
    
    # 1. 템플릿 로드
    templates = load_travelplanner_templates()
    
    # 2. 테스트 케이스들
    test_queries = [
        "Please help me plan a 3-day trip from Seoul to Busan with a budget of $800 for 2 people.",
        "Plan a 5-day vacation from New York to Los Angeles for a family of 4 with $3000 budget.",
        "Create a 7-day luxury travel plan from London to Paris for 2 people with $5000 budget."
    ]
    
    print("\n=== TravelPlanner 프롬프트 시스템 테스트 ===")
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n--- 테스트 {i} ---")
        print(f"사용자 요청: {query}")
        
        # 프롬프트 생성
        prompt = create_planner_prompt(query, templates, num_examples=2)
        
        print(f"\n생성된 프롬프트 길이: {len(prompt)} 글자")
        print("프롬프트 미리보기:")
        print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        
        # LLM 응답 (Mock 사용)
        print("\n=== LLM 응답 ===")
        response = get_llm_response(prompt, mock_llm)
        print(response)
        
        print("\n" + "="*50)
    
    # 3. 난이도별 예시 생성 테스트
    print("\n=== 난이도별 예시 테스트 ===")
    for difficulty in ['easy', 'medium', 'hard']:
        for days in ['3', '5', '7']:
            example_prompt = create_simple_examples_prompt(templates, difficulty, days, 1)
            if example_prompt:
                print(f"\n{difficulty.upper()} {days}일 예시:")
                print(example_prompt[:300] + "...")

# =====================================================
# 5. 유틸리티 함수들
# =====================================================

def save_templates_to_file(templates, filename="travelplanner_templates.json"):
    """템플릿을 파일로 저장"""
    import json
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)
    print(f"템플릿 저장됨: {filename}")

def get_prompt_stats(templates):
    """프롬프트 통계 정보"""
    total_examples = 0
    for level in templates:
        for days in templates[level]:
            total_examples += len(templates[level][days])
    
    print(f"총 예시 수: {total_examples}")
    
    # 샘플 프롬프트 길이 측정
    sample_query = "Plan a 3-day trip from A to B with $1000 budget."
    sample_prompt = create_planner_prompt(sample_query, templates, 3)
    
    print(f"샘플 프롬프트 길이: {len(sample_prompt)} 글자")
    print(f"예상 토큰 수: {len(sample_prompt.split()) * 1.3:.0f} 토큰")

if __name__ == "__main__":
    main()