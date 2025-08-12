"""Shared Pydantic schema models for AI gateway & Flask bridging."""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class AISuggestion(BaseModel):
    type: str
    original_text: Optional[str] = None
    suggestion: str
    explanation: Optional[str] = None
    category: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    metadata: Dict[str, Any] | None = None

class DetectResponse(BaseModel):
    suggestions: List[AISuggestion] = []
    has_suggestions: bool
    source: str
    success: bool = True

class EnhancementResult(BaseModel):
    enhanced_content: str
    reasoning: Optional[str] = None
    source: str = "ai"
    success: bool = True
    predefined: bool = False

class EnhancementRequest(BaseModel):
    enhancement_request: str
    current_content: str = ""
    title: str = ""
    context: Dict[str, Any] | None = None

class DetectRequest(BaseModel):
    content: str
    context: Dict[str, Any] | None = None
    ai_enabled: bool = True
    request_type: str = "semantic"
    action: Optional[str] = None
    enhancement_request: Optional[str] = None
    current_content: Optional[str] = None
    title: Optional[str] = None

__all__ = [
    "AISuggestion",
    "DetectResponse",
    "EnhancementResult",
    "EnhancementRequest",
    "DetectRequest",
]
