"""
모든 에이전트의 기본 클래스
GPT API 호출, 대화 이력 관리 등 공통 기능 제공
"""
from openai import OpenAI
from typing import Dict, List, Any, Optional
import json

class BaseAgent:
    """모든 에이전트의 기본 클래스"""
    
    def __init__(self, name: str, role: str, model: str = "gpt-3.5-turbo"):
        self.name = name
        self.role = role
        self.model = model
        self.client = None
        self.conversation_history = []
        
    def initialize(self, api_key: str):
        """OpenAI 클라이언트 초기화"""
        self.client = OpenAI(api_key=api_key)
        print(f"✅ {self.name} Agent 초기화 완료")
    
    def add_message(self, role: str, content: str):
        """대화 이력에 메시지 추가"""
        self.conversation_history.append({
            "role": role,
            "content": content
        })
    
    def generate_response(
            self, 
            user_message: str, 
            system_context: str = "",
            temperature: float = 0.7,
            json_mode: bool = False
        ) -> str:
        """LLM을 사용하여 응답 생성"""
        if not self.client:
            raise RuntimeError(f"{self.name} Agent가 초기화되지 않았습니다.")
        
        # 시스템 프롬프트 구성
        system_prompt = f"You are a {self.role}."
        if system_context:
            system_prompt += f"\n{system_context}"
        
        # ✅ 히스토리 없이, 이번 요청만 보냄
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        try:
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature
            }
            if json_mode:
                params["response_format"] = {"type": "json_object"}
            
            response = self.client.chat.completions.create(**params)
            assistant_message = response.choices[0].message.content
        
            return assistant_message

        except Exception as e:
            print(f"❌ {self.name} Agent 응답 생성 실패: {e}")
            return f"Error: {str(e)}"
    
    def reset(self):
        """대화 이력 초기화"""
        self.conversation_history = []
        print(f"🔄 {self.name} Agent 대화 이력 초기화")
    
    def get_status(self) -> Dict[str, Any]:
        """에이전트 상태 정보"""
        return {
            "name": self.name,
            "role": self.role,
            "model": self.model,
            "history_length": len(self.conversation_history)
        }
