import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from backend.app.models.compliance import ComplianceStatusEnum
from backend.app.models.document_extraction import Evidence
from backend.app.models.tender import TenderRequirement


class RuleEvaluationResult(BaseModel):
    status: ComplianceStatusEnum
    reason: str
    confidence: float = 1.0
    matched_evidence_id: Optional[str] = None
    extracted_value: Optional[str] = None
    normalized_value: Optional[str] = None
    source_document_filename: Optional[str] = None
    source_page: Optional[int] = None
    source_snippet: Optional[str] = None


def _parse_float(val: Any) -> Optional[float]:
    """Safely convert a string/numeric value to float."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        cleaned = re.sub(r"[^0-9\.\-]", "", str(val))
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


def evaluate_requirement_against_evidence(
    requirement: TenderRequirement,
    evidence_list: List[Evidence],
) -> RuleEvaluationResult:
    """
    Deterministically evaluate a single TenderRequirement against all available Bid Evidence.
    
    Safety Rules:
    1. No evidence -> NEVER mark COMPLIANT.
    2. Low confidence (< 0.70) -> NEEDS_REVIEW.
    3. Conflicting evidence -> NEEDS_REVIEW.
    4. Invalid operator or unparseable comparison -> NEEDS_REVIEW.
    """
    param = (requirement.parameter or "").strip().lower()
    op = (requirement.operator or "").strip().lower()
    threshold = (requirement.threshold_value or "").strip()
    req_text = requirement.requirement_text.strip()
    is_mandatory = requirement.mandatory

    # Map requirement parameter / text keywords to candidate evidence records
    candidate_evidence: List[Evidence] = []

    for ev in evidence_list:
        ev_field = (ev.field_name or "").strip().lower()
        
        # Exact parameter match
        if param and (param == ev_field or param in ev_field or ev_field in param):
            candidate_evidence.append(ev)
            continue

        # Parameter aliases
        if param in ["turnover", "annual_turnover", "revenue"] and ev_field in ["annual_turnover", "turnover"]:
            candidate_evidence.append(ev)
            continue
        if param in ["experience", "experience_years", "past_experience"] and ev_field in ["experience_years", "execution_period"]:
            candidate_evidence.append(ev)
            continue
        if param in ["gst", "gstin", "gst_number"] and ev_field in ["gstin", "gst_number"]:
            candidate_evidence.append(ev)
            continue
        if param in ["pan", "pan_number"] and ev_field in ["pan_number", "pan"]:
            candidate_evidence.append(ev)
            continue
        if param in ["msme", "udyam", "msme_number"] and ev_field in ["msme_number", "udyam"]:
            candidate_evidence.append(ev)
            continue
        if param in ["company_name", "bidder_name", "firm_name"] and ev_field in ["company_name", "firm_name"]:
            candidate_evidence.append(ev)
            continue

        # Keyword match against requirement text if parameter is empty
        if not param:
            req_lower = req_text.lower()
            if "gst" in req_lower and ev_field == "gstin":
                candidate_evidence.append(ev)
            elif "pan" in req_lower and ev_field == "pan_number":
                candidate_evidence.append(ev)
            elif ("turnover" in req_lower or "revenue" in req_lower) and ev_field == "annual_turnover":
                candidate_evidence.append(ev)
            elif ("experience" in req_lower or "years" in req_lower) and ev_field == "experience_years":
                candidate_evidence.append(ev)
            elif ("msme" in req_lower or "udyam" in req_lower) and ev_field == "msme_number":
                candidate_evidence.append(ev)

    # -------------------------------------------------------------
    # 1. Check: No evidence found
    # -------------------------------------------------------------
    if not candidate_evidence:
        if is_mandatory:
            return RuleEvaluationResult(
                status=ComplianceStatusEnum.NON_COMPLIANT,
                reason=f"Mandatory requirement not satisfied: No grounded supporting evidence found for '{param or req_text}'.",
                confidence=1.0,
            )
        else:
            return RuleEvaluationResult(
                status=ComplianceStatusEnum.NOT_APPLICABLE,
                reason=f"Optional requirement: No candidate evidence provided for '{param or req_text}'.",
                confidence=1.0,
            )

    # -------------------------------------------------------------
    # 2. Check: Conflicting evidence
    # -------------------------------------------------------------
    unique_norm_values = set(
        (ev.normalized_value or ev.extracted_value).strip().upper()
        for ev in candidate_evidence
        if ev.normalized_value or ev.extracted_value
    )
    if len(unique_norm_values) > 1:
        first_ev = candidate_evidence[0]
        return RuleEvaluationResult(
            status=ComplianceStatusEnum.NEEDS_REVIEW,
            reason=f"Conflicting evidence detected across multiple documents: {', '.join(unique_norm_values)}. Manual inspection required.",
            confidence=0.60,
            matched_evidence_id=first_ev.id,
            extracted_value=first_ev.extracted_value,
            normalized_value=first_ev.normalized_value,
            source_document_filename=first_ev.bid_document.filename if first_ev.bid_document else None,
            source_page=first_ev.page_number or 1,
            source_snippet=first_ev.snippet_text,
        )

    # Pick the highest confidence evidence item
    best_ev = max(candidate_evidence, key=lambda e: e.confidence or 0.0)
    ev_val_str = (best_ev.normalized_value or best_ev.extracted_value or "").strip()
    ev_conf = best_ev.confidence or 0.9

    # -------------------------------------------------------------
    # 3. Check: Low confidence evidence (< 0.70)
    # -------------------------------------------------------------
    if ev_conf < 0.70:
        return RuleEvaluationResult(
            status=ComplianceStatusEnum.NEEDS_REVIEW,
            reason=f"Evidence found but confidence is low ({(ev_conf * 100):.0f}%). Human review required before decision.",
            confidence=ev_conf,
            matched_evidence_id=best_ev.id,
            extracted_value=best_ev.extracted_value,
            normalized_value=best_ev.normalized_value,
            source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
            source_page=best_ev.page_number or 1,
            source_snippet=best_ev.snippet_text,
        )

    # -------------------------------------------------------------
    # 4. Evaluate Operators
    # -------------------------------------------------------------
    # Default operator if none provided: existence / is_present
    if not op or op in ["exists", "required", "is_present", "present"]:
        if ev_val_str:
            return RuleEvaluationResult(
                status=ComplianceStatusEnum.COMPLIANT,
                reason=f"Requirement verified: Valid document evidence present with value '{ev_val_str}'.",
                confidence=ev_conf,
                matched_evidence_id=best_ev.id,
                extracted_value=best_ev.extracted_value,
                normalized_value=best_ev.normalized_value,
                source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                source_page=best_ev.page_number or 1,
                source_snippet=best_ev.snippet_text,
            )
        else:
            return RuleEvaluationResult(
                status=ComplianceStatusEnum.NON_COMPLIANT if is_mandatory else ComplianceStatusEnum.NEEDS_REVIEW,
                reason=f"Required attribute evidence was empty.",
                confidence=ev_conf,
                matched_evidence_id=best_ev.id,
            )

    # Numeric comparisons (>=, >, <=, <)
    if op in [">=", "gte", "greater_equal", ">", "gt", "greater_than", "<=", "lte", "less_equal", "<", "lt", "less_than"]:
        val_num = _parse_float(ev_val_str)
        thresh_num = _parse_float(threshold)

        if val_num is None or thresh_num is None:
            return RuleEvaluationResult(
                status=ComplianceStatusEnum.NEEDS_REVIEW,
                reason=f"Numeric comparison operator '{op}' could not parse values (Extracted: '{ev_val_str}', Threshold: '{threshold}').",
                confidence=0.50,
                matched_evidence_id=best_ev.id,
                extracted_value=best_ev.extracted_value,
                normalized_value=best_ev.normalized_value,
                source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                source_page=best_ev.page_number or 1,
                source_snippet=best_ev.snippet_text,
            )

        unit_str = f" {requirement.unit}" if requirement.unit else ""
        if op in [">=", "gte", "greater_equal"]:
            if val_num >= thresh_num:
                return RuleEvaluationResult(
                    status=ComplianceStatusEnum.COMPLIANT,
                    reason=f"Criteria satisfied: Extracted value ({val_num:g}{unit_str}) >= required threshold ({thresh_num:g}{unit_str}).",
                    confidence=ev_conf,
                    matched_evidence_id=best_ev.id,
                    extracted_value=best_ev.extracted_value,
                    normalized_value=best_ev.normalized_value,
                    source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                    source_page=best_ev.page_number or 1,
                    source_snippet=best_ev.snippet_text,
                )
            else:
                return RuleEvaluationResult(
                    status=ComplianceStatusEnum.NON_COMPLIANT,
                    reason=f"Criteria failed: Extracted value ({val_num:g}{unit_str}) < required threshold ({thresh_num:g}{unit_str}).",
                    confidence=ev_conf,
                    matched_evidence_id=best_ev.id,
                    extracted_value=best_ev.extracted_value,
                    normalized_value=best_ev.normalized_value,
                    source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                    source_page=best_ev.page_number or 1,
                    source_snippet=best_ev.snippet_text,
                )

        if op in [">", "gt", "greater_than"]:
            if val_num > thresh_num:
                return RuleEvaluationResult(
                    status=ComplianceStatusEnum.COMPLIANT,
                    reason=f"Criteria satisfied: Extracted value ({val_num:g}{unit_str}) > required threshold ({thresh_num:g}{unit_str}).",
                    confidence=ev_conf,
                    matched_evidence_id=best_ev.id,
                    extracted_value=best_ev.extracted_value,
                    normalized_value=best_ev.normalized_value,
                    source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                    source_page=best_ev.page_number or 1,
                    source_snippet=best_ev.snippet_text,
                )
            else:
                return RuleEvaluationResult(
                    status=ComplianceStatusEnum.NON_COMPLIANT,
                    reason=f"Criteria failed: Extracted value ({val_num:g}{unit_str}) not greater than required threshold ({thresh_num:g}{unit_str}).",
                    confidence=ev_conf,
                    matched_evidence_id=best_ev.id,
                    extracted_value=best_ev.extracted_value,
                    normalized_value=best_ev.normalized_value,
                    source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                    source_page=best_ev.page_number or 1,
                    source_snippet=best_ev.snippet_text,
                )

        if op in ["<=", "lte", "less_equal"]:
            if val_num <= thresh_num:
                return RuleEvaluationResult(
                    status=ComplianceStatusEnum.COMPLIANT,
                    reason=f"Criteria satisfied: Extracted value ({val_num:g}{unit_str}) <= required ceiling ({thresh_num:g}{unit_str}).",
                    confidence=ev_conf,
                    matched_evidence_id=best_ev.id,
                    extracted_value=best_ev.extracted_value,
                    normalized_value=best_ev.normalized_value,
                    source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                    source_page=best_ev.page_number or 1,
                    source_snippet=best_ev.snippet_text,
                )
            else:
                return RuleEvaluationResult(
                    status=ComplianceStatusEnum.NON_COMPLIANT,
                    reason=f"Criteria failed: Extracted value ({val_num:g}{unit_str}) exceeds required ceiling ({thresh_num:g}{unit_str}).",
                    confidence=ev_conf,
                    matched_evidence_id=best_ev.id,
                    extracted_value=best_ev.extracted_value,
                    normalized_value=best_ev.normalized_value,
                    source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                    source_page=best_ev.page_number or 1,
                    source_snippet=best_ev.snippet_text,
                )

        if op in ["<", "lt", "less_than"]:
            if val_num < thresh_num:
                return RuleEvaluationResult(
                    status=ComplianceStatusEnum.COMPLIANT,
                    reason=f"Criteria satisfied: Extracted value ({val_num:g}{unit_str}) < required ceiling ({thresh_num:g}{unit_str}).",
                    confidence=ev_conf,
                    matched_evidence_id=best_ev.id,
                    extracted_value=best_ev.extracted_value,
                    normalized_value=best_ev.normalized_value,
                    source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                    source_page=best_ev.page_number or 1,
                    source_snippet=best_ev.snippet_text,
                )
            else:
                return RuleEvaluationResult(
                    status=ComplianceStatusEnum.NON_COMPLIANT,
                    reason=f"Criteria failed: Extracted value ({val_num:g}{unit_str}) not less than required ceiling ({thresh_num:g}{unit_str}).",
                    confidence=ev_conf,
                    matched_evidence_id=best_ev.id,
                    extracted_value=best_ev.extracted_value,
                    normalized_value=best_ev.normalized_value,
                    source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                    source_page=best_ev.page_number or 1,
                    source_snippet=best_ev.snippet_text,
                )

    # String equality (equals, ==, eq)
    if op in ["==", "eq", "equals", "equal"]:
        if ev_val_str.upper() == threshold.upper():
            return RuleEvaluationResult(
                status=ComplianceStatusEnum.COMPLIANT,
                reason=f"Exact match verified: '{ev_val_str}' == '{threshold}'.",
                confidence=ev_conf,
                matched_evidence_id=best_ev.id,
                extracted_value=best_ev.extracted_value,
                normalized_value=best_ev.normalized_value,
                source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                source_page=best_ev.page_number or 1,
                source_snippet=best_ev.snippet_text,
            )
        else:
            return RuleEvaluationResult(
                status=ComplianceStatusEnum.NON_COMPLIANT,
                reason=f"Value mismatch: Extracted '{ev_val_str}' does not equal expected '{threshold}'.",
                confidence=ev_conf,
                matched_evidence_id=best_ev.id,
                extracted_value=best_ev.extracted_value,
                normalized_value=best_ev.normalized_value,
                source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                source_page=best_ev.page_number or 1,
                source_snippet=best_ev.snippet_text,
            )

    # String inequality (!=, neq, not_equals)
    if op in ["!=", "neq", "not_equals", "not_equal"]:
        if ev_val_str.upper() != threshold.upper():
            return RuleEvaluationResult(
                status=ComplianceStatusEnum.COMPLIANT,
                reason=f"Inequality verified: Extracted '{ev_val_str}' != '{threshold}'.",
                confidence=ev_conf,
                matched_evidence_id=best_ev.id,
                extracted_value=best_ev.extracted_value,
                normalized_value=best_ev.normalized_value,
                source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                source_page=best_ev.page_number or 1,
                source_snippet=best_ev.snippet_text,
            )
        else:
            return RuleEvaluationResult(
                status=ComplianceStatusEnum.NON_COMPLIANT,
                reason=f"Prohibited value found: Extracted '{ev_val_str}' matches prohibited '{threshold}'.",
                confidence=ev_conf,
                matched_evidence_id=best_ev.id,
                extracted_value=best_ev.extracted_value,
                normalized_value=best_ev.normalized_value,
                source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                source_page=best_ev.page_number or 1,
                source_snippet=best_ev.snippet_text,
            )

    # Contains / Matches substring or regex
    if op in ["contains", "in", "matches", "like"]:
        if threshold.lower() in ev_val_str.lower() or (best_ev.snippet_text and threshold.lower() in best_ev.snippet_text.lower()):
            return RuleEvaluationResult(
                status=ComplianceStatusEnum.COMPLIANT,
                reason=f"Pattern verified: Value contains required keyword '{threshold}'.",
                confidence=ev_conf,
                matched_evidence_id=best_ev.id,
                extracted_value=best_ev.extracted_value,
                normalized_value=best_ev.normalized_value,
                source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                source_page=best_ev.page_number or 1,
                source_snippet=best_ev.snippet_text,
            )
        else:
            return RuleEvaluationResult(
                status=ComplianceStatusEnum.NON_COMPLIANT,
                reason=f"Pattern missing: Value '{ev_val_str}' does not contain required keyword '{threshold}'.",
                confidence=ev_conf,
                matched_evidence_id=best_ev.id,
                extracted_value=best_ev.extracted_value,
                normalized_value=best_ev.normalized_value,
                source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
                source_page=best_ev.page_number or 1,
                source_snippet=best_ev.snippet_text,
            )

    # Unknown operator fallback -> NEEDS_REVIEW
    return RuleEvaluationResult(
        status=ComplianceStatusEnum.NEEDS_REVIEW,
        reason=f"Unsupported rule operator '{op}'. Please specify a standard operator (>=, <=, ==, !=, contains, exists).",
        confidence=0.50,
        matched_evidence_id=best_ev.id,
        extracted_value=best_ev.extracted_value,
        normalized_value=best_ev.normalized_value,
        source_document_filename=best_ev.bid_document.filename if best_ev.bid_document else None,
        source_page=best_ev.page_number or 1,
        source_snippet=best_ev.snippet_text,
    )
