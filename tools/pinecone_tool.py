"""
Pinecone 벡터 DB를 사용한 호텔 리뷰 검색 도구
"""
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
import os

class PineconeTool:
    """호텔 리뷰 검색을 위한 Pinecone 도구"""
    
    def __init__(self, api_key: str, index_name: str, embedding_model: str):
        self.api_key = api_key
        self.index_name = index_name
        self.embedding_model_name = embedding_model
        self.index = None
        self.encoder = None
        
    def initialize(self) -> bool:
        """Pinecone 및 임베딩 모델 초기화"""
        try:
            # Pinecone 초기화
            pc = Pinecone(api_key=self.api_key)
            self.index = pc.Index(self.index_name)
            
            # 임베딩 모델 로드
            self.encoder = SentenceTransformer(self.embedding_model_name)
            
            print(f"✅ Pinecone Tool 초기화 완료 (Index: {self.index_name})")
            return True
            
        except Exception as e:
            print(f"❌ Pinecone Tool 초기화 실패: {e}")
            return False
    
    def search_reviews(
        self, 
        query: str, 
        top_k: int = 5, 
        filters: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """호텔 리뷰 검색"""
        if not self.index or not self.encoder:
            print("❌ Pinecone Tool이 초기화되지 않았습니다.")
            return []
        
        try:
            # 쿼리 임베딩
            query_vector = self.encoder.encode(query).tolist()
            
            # Pinecone 검색
            search_params = {
                "vector": query_vector,
                "top_k": top_k,
                "include_metadata": True
            }
            
            if filters:
                search_params["filter"] = filters
            
            results = self.index.query(**search_params)
            
            # 결과 정리
            reviews = []
            for match in results.get('matches', []):
                metadata = match.get('metadata', {})
                reviews.append({
                    "text": metadata.get('text', ''),
                    "rating": metadata.get('rating', 0),
                    "location_sentiment": metadata.get('location_sentiment', 0),
                    "room_sentiment": metadata.get('room_sentiment', 0),
                    "service_sentiment": metadata.get('service_sentiment', 0),
                    "value_sentiment": metadata.get('value_sentiment', 0),
                    "overall_sentiment": metadata.get('overall_sentiment', 0),
                    "score": float(match.get('score', 0))
                })
            
            print(f"🔍 검색 완료: {len(reviews)}개 리뷰 발견")
            return reviews
            
        except Exception as e:
            print(f"❌ 리뷰 검색 실패: {e}")
            return []
    
    def search_by_hotel_name(
        self, 
        hotel_name: str, 
        min_rating: int = 3,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """호텔 이름으로 특정 등급 이상의 리뷰 검색"""
        filters = {
            "rating": {"$gte": min_rating}
        }
        return self.search_reviews(hotel_name, top_k, filters)