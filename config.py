"""
환경 설정 파일
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    
    # 새로운 API Keys
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")  # 날씨 API
    GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")  # Google Places API
    
    AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY")
    AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET")
    
    # Pinecone 설정
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "tripadvisor-reviews")
    
    # 임베딩 모델
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    
    # GPT 모델
    GPT_MODEL = "gpt-3.5-turbo"
    
    EXCHANGE_RATES = {
        'KRW': 1.0,
        'USD': 1380.0,
        'EUR': 1480.0,
        'GBP': 1760.0,
        'JPY': 9.2,
        'CNY': 190.0,
        'HKD': 177.0,
        'TWD': 42.5,
        'SGD': 1025.0,
        'MYR': 310.0,
        'THB': 38.0,
        'PHP': 24.0,
        'VND': 0.055,
        'IDR': 0.087,
        'INR': 16.3,
        'PKR': 4.9,
        'BDT': 11.5,
        'LKR': 4.2,
        'NPR': 10.2,
        'AUD': 890.0,
        'NZD': 810.0,
        'CAD': 985.0,
        'CHF': 1565.0,
        'SEK': 127.0,
        'NOK': 125.0,
        'DKK': 198.0,
        'PLN': 340.0,
        'CZK': 60.0,
        'HUF': 3.8,
        'RUB': 14.2,
        'TRY': 40.0,
        'ZAR': 75.0,
        'BRL': 270.0,
        'MXN': 68.0,
        'ARS': 1.4,
        'CLP': 1.4,
        'COP': 0.33,
        'PEN': 365.0,
        'AED': 376.0,
        'SAR': 368.0,
        'QAR': 379.0,
        'KWD': 4500.0,
        'BHD': 3660.0,
        'OMR': 3585.0,
        'JOD': 1945.0,
        'ILS': 375.0,
        'EGP': 28.0,
        'MAD': 138.0,
        'TND': 440.0,
        'KES': 10.7,
        'NGN': 0.88,
        'GHS': 88.0,
        'ETB': 11.0,
        'TZS': 0.52,
        'UGX': 0.37,
        'ZMW': 50.0,
        'BWP': 100.0,
        'MUR': 30.0,
        'SCR': 101.0,
    }
    
    @classmethod
    def validate(cls):
        """필수 설정 값 검증"""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        if not cls.PINECONE_API_KEY:
            raise ValueError("PINECONE_API_KEY가 설정되지 않았습니다.")
        print("✅ 설정 검증 완료")
        
        # 선택적 API 키 확인
        if not cls.OPENWEATHER_API_KEY:
            print("⚠️  OPENWEATHER_API_KEY가 설정되지 않았습니다 (선택사항)")
        if not cls.GOOGLE_PLACES_API_KEY:
            print("⚠️  GOOGLE_PLACES_API_KEY가 설정되지 않았습니다 (선택사항)")