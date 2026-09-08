import re
from datetime import datetime
from typing import Optional, Tuple


def normalize_gstin(raw_value: str) -> Tuple[Optional[str], float]:
    """
    Normalize Indian GSTIN (15 characters: 2 state + 10 PAN + 1 entity + Z + 1 checksum).
    Returns (normalized_value, confidence_boost).
    """
    if not raw_value:
        return None, 0.0
    
    # Strip spaces and punctuation
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw_value).upper()
    
    # Standard 15-char GSTIN pattern
    gst_pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
    if re.match(gst_pattern, cleaned):
        return cleaned, 0.98
    
    # If 15 chars but minor variation
    if len(cleaned) == 15 and cleaned[0:2].isdigit() and cleaned[2:7].isalpha() and cleaned[7:11].isdigit():
        return cleaned, 0.85
        
    return cleaned if len(cleaned) >= 10 else None, 0.60


def normalize_pan(raw_value: str) -> Tuple[Optional[str], float]:
    """
    Normalize Indian PAN (10 characters: 5 letters + 4 digits + 1 letter).
    Returns (normalized_value, confidence_boost).
    """
    if not raw_value:
        return None, 0.0
        
    cleaned = re.sub(r"[^A-Za-z0-9]", "", raw_value).upper()
    
    pan_pattern = r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$"
    if re.match(pan_pattern, cleaned):
        return cleaned, 0.98
        
    # Check if 10 chars
    if len(cleaned) == 10:
        return cleaned, 0.80
        
    return cleaned if len(cleaned) >= 8 else None, 0.50


def normalize_date(raw_value: str) -> Tuple[Optional[str], float]:
    """
    Normalize various date formats into ISO 8601 YYYY-MM-DD.
    """
    if not raw_value:
        return None, 0.0
        
    cleaned = raw_value.strip()
    
    # Common date formats
    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%m/%d/%Y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y/%m/%d",
    ]
    
    for fmt in date_formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d"), 0.95
        except ValueError:
            continue
            
    # Try regex search for DD/MM/YYYY or YYYY-MM-DD within string
    d_match = re.search(r"(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})", cleaned)
    if d_match:
        day, month, year = d_match.groups()
        try:
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime("%Y-%m-%d"), 0.90
        except ValueError:
            pass

    return cleaned, 0.50


def normalize_financial_amount(raw_value: str) -> Tuple[Optional[str], float]:
    """
    Normalize Indian financial currency string into a standard float string in INR.
    Handles 'Crore', 'Lakh', 'Cr', 'L', and standard comma notation.
    Example: 'INR 15,40,00,000' -> '154000000.0'
             '15.4 Crore' -> '154000000.0'
             '50 Lakhs' -> '5000000.0'
    """
    if not raw_value:
        return None, 0.0
        
    cleaned = raw_value.replace(",", "").replace("₹", "").replace("INR", "").replace("Rs.", "").replace("Rs", "").strip()
    
    # Check for Crore / Cr
    cr_match = re.search(r"([\d\.]+)\s*(?:crores?|cr)", cleaned, re.IGNORECASE)
    if cr_match:
        try:
            val = float(cr_match.group(1)) * 10000000.0
            return str(val), 0.96
        except ValueError:
            pass
            
    # Check for Lakh / L
    lakh_match = re.search(r"([\d\.]+)\s*(?:lakhs?|lac|l)", cleaned, re.IGNORECASE)
    if lakh_match:
        try:
            val = float(lakh_match.group(1)) * 100000.0
            return str(val), 0.96
        except ValueError:
            pass
            
    # Check for raw number
    num_match = re.search(r"([\d]+(?:\.[\d]+)?)", cleaned)
    if num_match:
        try:
            val = float(num_match.group(1))
            return str(val), 0.92
        except ValueError:
            pass
            
    return cleaned, 0.50


def normalize_experience_years(raw_value: str) -> Tuple[Optional[str], float]:
    """
    Normalize experience string into years as a float string.
    Example: '3 Years' -> '3.0'
             '5+ years' -> '5.0'
    """
    if not raw_value:
        return None, 0.0
        
    num_match = re.search(r"(\d+(?:\.\d+)?)", raw_value)
    if num_match:
        try:
            val = float(num_match.group(1))
            return str(val), 0.95
        except ValueError:
            pass
            
    return raw_value.strip(), 0.50


def normalize_company_name(raw_value: str) -> Tuple[Optional[str], float]:
    """
    Normalize organization / company name by cleaning whitespace and standardizing legal forms.
    """
    if not raw_value:
        return None, 0.0
        
    cleaned = re.sub(r"\s+", " ", raw_value).strip().upper()
    
    # Standardize common suffixes
    cleaned = re.sub(r"\bPVT\.?\s*LTD\.?\b", "PRIVATE LIMITED", cleaned)
    cleaned = re.sub(r"\bLTD\.?\b", "LIMITED", cleaned)
    cleaned = re.sub(r"\bINC\.?\b", "INCORPORATED", cleaned)
    cleaned = re.sub(r"\bCORP\.?\b", "CORPORATION", cleaned)
    
    return cleaned, 0.92


def normalize_msme_number(raw_value: str) -> Tuple[Optional[str], float]:
    """
    Normalize Indian Udyam / MSME Registration Number.
    Format: UDYAM-XX-00-0000000
    """
    if not raw_value:
        return None, 0.0
        
    cleaned = re.sub(r"\s+", "", raw_value).upper()
    udyam_pattern = r"^UDYAM-[A-Z]{2}-\d{2}-\d{7}$"
    if re.match(udyam_pattern, cleaned):
        return cleaned, 0.98
        
    if "UDYAM" in cleaned:
        return cleaned, 0.85
        
    return cleaned, 0.60
