import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from backend.app.models.compliance import VerificationStatusEnum


class VerificationResultData(BaseModel):
    verification_type: str
    status: VerificationStatusEnum
    provider_name: str = "MOCK_GOVERNMENT_GATEWAY"
    is_mock: bool = True
    reference_id: Optional[str] = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None


class VerificationProvider(ABC):
    """Abstract interface for external/government registry verification."""

    @abstractmethod
    def verify(
        self,
        verification_type: str,
        identifier: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VerificationResultData:
        """
        Verify an identifier against registry sources.
        Must clearly identify whether result is simulated/mock.
        """
        pass


class MockGovernmentVerificationProvider(VerificationProvider):
    """
    Deterministic mock provider simulating Indian government portals (GSTN, NSDL PAN, MSME Udyam, MCA).
    Explicitly flags is_mock=True on every response.
    Never claims to be a production government service.
    """

    def verify(
        self,
        verification_type: str,
        identifier: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VerificationResultData:
        clean_id = (identifier or "").strip().upper()
        vtype = (verification_type or "").strip().upper()

        if not clean_id:
            return VerificationResultData(
                verification_type=vtype,
                status=VerificationStatusEnum.FAILED,
                provider_name="MOCK_GOVERNMENT_GATEWAY",
                is_mock=True,
                error_message="Verification failed: Missing or empty identifier.",
            )

        # -------------------------------------------------------------
        # 1. GSTIN Verification
        # -------------------------------------------------------------
        if vtype in ["GST", "GSTIN", "GST_CERTIFICATE"]:
            gst_pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
            if not re.match(gst_pattern, clean_id):
                return VerificationResultData(
                    verification_type="GST",
                    status=VerificationStatusEnum.FAILED,
                    provider_name="MOCK_GOVERNMENT_GATEWAY",
                    is_mock=True,
                    reference_id=clean_id,
                    error_message=f"Invalid GSTIN format: '{clean_id}'. Expected 15-character Indian GSTIN.",
                    summary={"valid_format": False, "status": "INVALID_FORMAT"},
                )

            if "INVALID" in clean_id or "SUSPEND" in clean_id:
                return VerificationResultData(
                    verification_type="GST",
                    status=VerificationStatusEnum.FAILED,
                    provider_name="MOCK_GOVERNMENT_GATEWAY",
                    is_mock=True,
                    reference_id=clean_id,
                    error_message="GSTIN registration is suspended or cancelled in registry records.",
                    summary={"taxpayer_status": "CANCELLED"},
                )

            return VerificationResultData(
                verification_type="GST",
                status=VerificationStatusEnum.VERIFIED,
                provider_name="MOCK_GOVERNMENT_GATEWAY",
                is_mock=True,
                reference_id=clean_id,
                summary={
                    "taxpayer_status": "ACTIVE",
                    "state_code": clean_id[0:2],
                    "entity_pan": clean_id[2:12],
                    "registry": "GSTN_MOCK_GATEWAY",
                },
            )

        # -------------------------------------------------------------
        # 2. PAN Verification
        # -------------------------------------------------------------
        if vtype in ["PAN", "PAN_CARD", "INCOME_TAX"]:
            pan_pattern = r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$"
            if not re.match(pan_pattern, clean_id):
                return VerificationResultData(
                    verification_type="PAN",
                    status=VerificationStatusEnum.FAILED,
                    provider_name="MOCK_GOVERNMENT_GATEWAY",
                    is_mock=True,
                    reference_id=clean_id,
                    error_message=f"Invalid PAN format: '{clean_id}'. Expected 10-character alphanumeric PAN.",
                    summary={"valid_format": False, "status": "INVALID_FORMAT"},
                )

            if "INVALID" in clean_id:
                return VerificationResultData(
                    verification_type="PAN",
                    status=VerificationStatusEnum.FAILED,
                    provider_name="MOCK_GOVERNMENT_GATEWAY",
                    is_mock=True,
                    reference_id=clean_id,
                    error_message="PAN is marked inoperative or invalid in tax records.",
                    summary={"pan_status": "INOPERATIVE"},
                )

            return VerificationResultData(
                verification_type="PAN",
                status=VerificationStatusEnum.VERIFIED,
                provider_name="MOCK_GOVERNMENT_GATEWAY",
                is_mock=True,
                reference_id=clean_id,
                summary={
                    "pan_status": "OPERATIVE_AND_VALID",
                    "pan_category": clean_id[3],
                    "registry": "NSDL_INCOMETAX_MOCK",
                },
            )

        # -------------------------------------------------------------
        # 3. MSME / Udyam Verification
        # -------------------------------------------------------------
        if vtype in ["MSME", "UDYAM", "UDYOG_AADHAAR"]:
            udyam_pattern = r"^UDYAM-[A-Z]{2}-\d{2}-\d{7}$"
            if not re.match(udyam_pattern, clean_id):
                return VerificationResultData(
                    verification_type="MSME",
                    status=VerificationStatusEnum.FAILED,
                    provider_name="MOCK_GOVERNMENT_GATEWAY",
                    is_mock=True,
                    reference_id=clean_id,
                    error_message=f"Invalid Udyam format: '{clean_id}'. Expected format UDYAM-XX-00-0000000.",
                    summary={"valid_format": False},
                )

            return VerificationResultData(
                verification_type="MSME",
                status=VerificationStatusEnum.VERIFIED,
                provider_name="MOCK_GOVERNMENT_GATEWAY",
                is_mock=True,
                reference_id=clean_id,
                summary={
                    "enterprise_type": "SMALL_ENTERPRISE",
                    "udyam_status": "ACTIVE",
                    "registry": "MSME_UDYAM_MOCK",
                },
            )

        # -------------------------------------------------------------
        # 4. Generic / Company Registry Verification
        # -------------------------------------------------------------
        if len(clean_id) >= 4:
            return VerificationResultData(
                verification_type=vtype,
                status=VerificationStatusEnum.VERIFIED,
                provider_name="MOCK_GOVERNMENT_GATEWAY",
                is_mock=True,
                reference_id=clean_id,
                summary={"status": "RECORD_FOUND_MOCK", "identifier": clean_id},
            )

        return VerificationResultData(
            verification_type=vtype,
            status=VerificationStatusEnum.VERIFICATION_UNAVAILABLE,
            provider_name="MOCK_GOVERNMENT_GATEWAY",
            is_mock=True,
            reference_id=clean_id,
            error_message="Verification unavailable for provided identifier format.",
        )


# Global Verification Provider singleton
_default_verification_provider: Optional[VerificationProvider] = None


def get_verification_provider() -> VerificationProvider:
    """Accessor / dependency for the active Verification Provider."""
    global _default_verification_provider
    if _default_verification_provider is None:
        _default_verification_provider = MockGovernmentVerificationProvider()
    return _default_verification_provider
