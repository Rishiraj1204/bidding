import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.app.ai.normalizers import (
    normalize_company_name,
    normalize_date,
    normalize_experience_years,
    normalize_financial_amount,
    normalize_gstin,
    normalize_msme_number,
    normalize_pan,
)


class RawExtractedEntity(BaseModel):
    entity_type: str
    raw_value: str
    normalized_value: Optional[str] = None
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    source_snippet: Optional[str] = None
    page_number: Optional[int] = 1


class AIExtractionResult(BaseModel):
    status: str = "COMPLETED"  # "COMPLETED" or "FAILED"
    entities: List[RawExtractedEntity] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class AIExtractionProvider(ABC):
    """Abstract AI Provider interface for extracting structured entities from document text."""

    @abstractmethod
    def extract_entities(
        self,
        raw_text: Optional[str],
        document_type: str,
        filename: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AIExtractionResult:
        """
        Extract verified entities from document OCR text.
        Must not invent unsupported or absent fields (Hallucination Defense).
        """
        pass


class LocalDeterministicAIExtractionProvider(AIExtractionProvider):
    """
    Deterministic Local/Mock AI entity extraction engine.
    - Grounded 100% in verbatim OCR text snippets.
    - Zero hallucination (does not create entities for absent data).
    - Normalizes all field values safely.
    - Returns exact source snippet boundaries.
    """

    def _find_snippet(self, text: str, match_span: tuple, context_chars: int = 50) -> str:
        """Extract a verbatim surrounding context snippet."""
        start = max(0, match_span[0] - context_chars)
        end = min(len(text), match_span[1] + context_chars)
        return text[start:end].replace("\n", " ").strip()

    def extract_entities(
        self,
        raw_text: Optional[str],
        document_type: str,
        filename: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AIExtractionResult:
        if not raw_text or not raw_text.strip():
            return AIExtractionResult(
                status="COMPLETED",
                entities=[],
                summary={"entity_count": 0, "status": "NO_TEXT_TO_EXTRACT"},
            )

        text = raw_text.strip()
        entities: List[RawExtractedEntity] = []
        doc_type_upper = (document_type or "OTHER").upper()

        # -------------------------------------------------------------
        # 1. GSTIN Extraction
        # -------------------------------------------------------------
        gst_regex = re.compile(
            r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}[Z|z][0-9A-Z]{1})\b",
            re.IGNORECASE,
        )
        gst_matches = list(gst_regex.finditer(text))
        if not gst_matches:
            # Check context labels e.g. "GSTIN: 27AABCV1234F1Z5" or "Registration Number: 27AABCV1234F1Z5"
            context_gst = re.finditer(
                r"(?:GSTIN|GST\s*Number|Registration\s*Number)[\s\:\-]+([A-Z0-9]{15})",
                text,
                re.IGNORECASE,
            )
            gst_matches = list(context_gst)

        for m in gst_matches:
            raw_val = m.group(1) if m.groups() else m.group(0)
            norm_val, conf_boost = normalize_gstin(raw_val)
            if norm_val:
                snippet = self._find_snippet(text, m.span())
                entities.append(
                    RawExtractedEntity(
                        entity_type="gstin",
                        raw_value=raw_val,
                        normalized_value=norm_val,
                        confidence=min(1.0, conf_boost),
                        source_snippet=snippet,
                        page_number=1,
                    )
                )

        # -------------------------------------------------------------
        # 2. PAN Number Extraction
        # -------------------------------------------------------------
        pan_regex = re.compile(
            r"\b([A-Z]{5}[0-9]{4}[A-Z]{1})\b",
            re.IGNORECASE,
        )
        pan_matches = list(pan_regex.finditer(text))
        for m in pan_matches:
            raw_val = m.group(1)
            # Avoid matching substring of GSTIN (chars 2 to 12)
            is_sub_of_gst = any(raw_val.upper() in e.raw_value.upper() for e in entities if e.entity_type == "gstin")
            if is_sub_of_gst and "pan" not in text.lower()[max(0, m.start() - 20):m.end() + 20]:
                continue
                
            norm_val, conf_boost = normalize_pan(raw_val)
            if norm_val:
                snippet = self._find_snippet(text, m.span())
                entities.append(
                    RawExtractedEntity(
                        entity_type="pan_number",
                        raw_value=raw_val,
                        normalized_value=norm_val,
                        confidence=min(1.0, conf_boost),
                        source_snippet=snippet,
                        page_number=1,
                    )
                )

        # -------------------------------------------------------------
        # 3. Company / Legal Entity Name Extraction
        # -------------------------------------------------------------
        company_regex = re.compile(
            r"(?:Legal\s*Name|Company\s*Name|Name\s*of\s*the\s*Firm|Bidder\s*Name|Enterprise\s*Name|Client)[\s\:\-]+([A-Za-z0-9\s\.\,\&]+?)(?:\n|\r|\;|$)",
            re.IGNORECASE,
        )
        for m in company_regex.finditer(text):
            raw_val = m.group(1).strip()
            if len(raw_val) >= 3 and not raw_val.isdigit():
                norm_val, conf_boost = normalize_company_name(raw_val)
                snippet = self._find_snippet(text, m.span())
                entities.append(
                    RawExtractedEntity(
                        entity_type="company_name",
                        raw_value=raw_val,
                        normalized_value=norm_val,
                        confidence=conf_boost,
                        source_snippet=snippet,
                        page_number=1,
                    )
                )

        # -------------------------------------------------------------
        # 4. Financial Values & Annual Turnover Extraction
        # -------------------------------------------------------------
        turnover_regex = re.compile(
            r"(?:Turnover|Revenue|Annual\s*Turnover|Total\s*Turnover|Contract\s*Value)[\s\:\-]+(?:INR|Rs\.?|₹)?\s*([\d\,\.]+\s*(?:crores?|lakhs?|lac|cr|l)?)",
            re.IGNORECASE,
        )
        for m in turnover_regex.finditer(text):
            raw_val = m.group(0).strip()
            amount_str = m.group(1).strip()
            norm_val, conf_boost = normalize_financial_amount(amount_str)
            if norm_val:
                snippet = self._find_snippet(text, m.span())
                entities.append(
                    RawExtractedEntity(
                        entity_type="annual_turnover",
                        raw_value=raw_val,
                        normalized_value=norm_val,
                        confidence=conf_boost,
                        source_snippet=snippet,
                        page_number=1,
                    )
                )

        # Net Worth
        net_worth_regex = re.compile(
            r"(?:Net\s*Worth|Capital)[\s\:\-]+(?:INR|Rs\.?|₹)?\s*([\d\,\.]+\s*(?:crores?|lakhs?|lac|cr|l)?)",
            re.IGNORECASE,
        )
        for m in net_worth_regex.finditer(text):
            raw_val = m.group(0).strip()
            amount_str = m.group(1).strip()
            norm_val, conf_boost = normalize_financial_amount(amount_str)
            if norm_val:
                snippet = self._find_snippet(text, m.span())
                entities.append(
                    RawExtractedEntity(
                        entity_type="net_worth",
                        raw_value=raw_val,
                        normalized_value=norm_val,
                        confidence=conf_boost,
                        source_snippet=snippet,
                        page_number=1,
                    )
                )

        # -------------------------------------------------------------
        # 5. Experience Years & Execution Timeline
        # -------------------------------------------------------------
        exp_regex = re.compile(
            r"(?:Experience|Execution\s*Period|Period\s*of\s*Execution|Track\s*Record)[\s\:\-]+([0-9]+(?:\.[0-9]+)?\s*(?:years?|yrs?))",
            re.IGNORECASE,
        )
        for m in exp_regex.finditer(text):
            raw_val = m.group(1).strip()
            norm_val, conf_boost = normalize_experience_years(raw_val)
            if norm_val:
                snippet = self._find_snippet(text, m.span())
                entities.append(
                    RawExtractedEntity(
                        entity_type="experience_years",
                        raw_value=raw_val,
                        normalized_value=norm_val,
                        confidence=conf_boost,
                        source_snippet=snippet,
                        page_number=1,
                    )
                )

        # -------------------------------------------------------------
        # 6. MSME / Udyam Registration
        # -------------------------------------------------------------
        udyam_regex = re.compile(
            r"\b(UDYAM-[A-Z]{2}-\d{2}-\d{7})\b",
            re.IGNORECASE,
        )
        for m in udyam_regex.finditer(text):
            raw_val = m.group(1).strip()
            norm_val, conf_boost = normalize_msme_number(raw_val)
            if norm_val:
                snippet = self._find_snippet(text, m.span())
                entities.append(
                    RawExtractedEntity(
                        entity_type="msme_number",
                        raw_value=raw_val,
                        normalized_value=norm_val,
                        confidence=conf_boost,
                        source_snippet=snippet,
                        page_number=1,
                    )
                )

        # -------------------------------------------------------------
        # 7. Dates (Issue Date, Incorporation Date, Expiry Date)
        # -------------------------------------------------------------
        date_regex = re.compile(
            r"(?:Date\s*of\s*Issue|Issue\s*Date|Incorporation\s*Date|Date\s*of\s*Incorporation|Valid\s*Upto)[\s\:\-]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})",
            re.IGNORECASE,
        )
        for m in date_regex.finditer(text):
            raw_val = m.group(1).strip()
            norm_val, conf_boost = normalize_date(raw_val)
            if norm_val:
                snippet = self._find_snippet(text, m.span())
                entities.append(
                    RawExtractedEntity(
                        entity_type="issue_date",
                        raw_value=raw_val,
                        normalized_value=norm_val,
                        confidence=conf_boost,
                        source_snippet=snippet,
                        page_number=1,
                    )
                )

        # Deduplicate identical entity_type + normalized_value
        unique_entities: List[RawExtractedEntity] = []
        seen_keys = set()
        for e in entities:
            key = (e.entity_type, e.normalized_value or e.raw_value)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_entities.append(e)

        return AIExtractionResult(
            status="COMPLETED",
            entities=unique_entities,
            summary={
                "total_entities": len(unique_entities),
                "document_type": doc_type_upper,
                "engine": "LocalDeterministicAIExtraction-1.0",
            },
        )


# Global AI Provider singleton
_default_ai_provider: Optional[AIExtractionProvider] = None


def get_ai_provider() -> AIExtractionProvider:
    """Accessor / dependency for the active AI Extraction Provider."""
    global _default_ai_provider
    if _default_ai_provider is None:
        _default_ai_provider = LocalDeterministicAIExtractionProvider()
    return _default_ai_provider
