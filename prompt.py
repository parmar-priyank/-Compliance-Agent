"""
prompt.py — Centralized AI prompts, OCR instructions, and check rules.

HOW TO ADD A NEW RULE
─────────────────────
1. If your new QC item just needs presence confirmation (file uploaded = pass),
   add its key to NO_OCR_KEYS below.

2. If it needs OCR + regex/logic (no AI), add its key to OCR_RULE_KEYS and
   add a new `if check_key == "your_key":` block inside run_item_rule().

3. If it needs the Groq LLM to decide, leave it out of both sets — the system
   will use check_document_against_agreement() with the GENERIC_QC_PROMPT
   automatically.

4. To accept natural-language filenames, add keyword aliases to KEYWORD_MAP.
   Format: (["alias one", "alias two"], "qc_key")
   The first match wins, so put more specific aliases earlier in the list.
"""

import re


# ── File extension whitelist ─────────────────────────────────────────────────

VALID_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


# ── Check type routing ───────────────────────────────────────────────────────
# Items in NO_OCR_KEYS: presence alone → "Yes". No file reading needed.
# Items in OCR_RULE_KEYS: OCR the file, then apply run_item_rule() logic.
# Everything else → OCR the file, then call the Groq LLM.

NO_OCR_KEYS   = {"signed_agreement", "meter_photo", "roof_pic"}
OCR_RULE_KEYS = {"deposit", "phase_upgrade", "storey_roof", "electricity_bill", "rate_notice", "scissor_lift"}


# ── AI / Vision prompts ──────────────────────────────────────────────────────

# Sent to the vision model when checking the storey_roof item.
STOREY_PROMPT = (
    "Look at this house image carefully. Answer two things:\n"
    "1. STOREYS: How many storeys/floors does the house have? "
    "Reply 'single storey' if 1 floor, 'double storey' if 2 or more floors.\n"
    "2. ROOF TYPE: What type of roof does the house have? "
    "Common types: Tin/Metal, Tile, Colorbond, Flat, Gable, Hip, Skillion. "
    "Pick the closest match.\n\n"
    "Reply in exactly this format:\n"
    "STOREYS: <single storey or double storey>\n"
    "ROOF TYPE: <roof type detected>"
)

# Default OCR extraction prompt (used when no specific prompt is specified).
DEFAULT_OCR_PROMPT = "Extract all text from this document image. Return plain text only."

# Generic QC compliance check prompt.
# {label} and the document/agreement text are injected by check_document_against_agreement().
GENERIC_QC_PROMPT = """\
You are a solar installation QC compliance checker for ADS Solar.

SIGNED AGREEMENT TEXT:
{agreement_text}

UPLOADED DOCUMENT TEXT:
{doc_text}

QC CHECK: "{label}"

Based on these two documents, does the uploaded document satisfy the QC check "{label}"?

Reply ONLY with a JSON object (no markdown):
{{
  "result": "Yes" or "No" or "N/A",
  "remark": "one short sentence explaining your finding"
}}"""

# Agreement field extraction schema (used by extract_quote_with_groq).
QUOTE_EXTRACTION_SYSTEM = (
    "You are a precise data-extraction engine for solar installation agreements. "
    "Extract values VERBATIM — copy text exactly as it appears, never combine or invent. "
    "CRITICAL ADDRESS RULES: "
    "1. 'billing_address' = copy the full address block under the 'Billing address:' label verbatim. "
    "2. 'delivery_address' = copy the full address block under the 'Delivery address:' label verbatim. "
    "3. 'installation_address' = the customer's property where solar will be installed. "
    "   In ADS Solar agreements this is the Billing address (the customer's address, NOT the retailer's). "
    "   NEVER mix parts from different address blocks. NEVER use the retailer's Postal or Street address. "
    "4. 'retailer_postal_address' = address under 'Postal address:' label. "
    "5. 'retailer_street_address' = address under 'Street address:' label. "
    "Each address field must come from its own clearly labelled section only."
)

QUOTE_SCHEMA = """
Return ONLY a JSON object with this exact shape (use null when a value is
missing, numbers for all money/quantity fields, ISO dates YYYY-MM-DD):
{
  "quote_number": string,
  "valid_until": string,
  "customer_name": string,
  "contact_person": string,
  "customer_email": string,
  "customer_phone": string,
  "billing_address": string,
  "delivery_address": string,
  "installation_address": string,
  "retailer_name": string,
  "retailer_abn": string,
  "retailer_contact_person": string,
  "retailer_email": string,
  "retailer_phone": string,
  "retailer_postal_address": string,
  "retailer_street_address": string,
  "system_price": number,
  "stc_count": number,
  "stc_price_per_unit": number,
  "stc_incentive": number,
  "total_price": number,
  "deposit": number,
  "deposit_due_date": string,
  "balance": number,
  "balance_due_date": string,
  "eft_bsb": string,
  "eft_account_number": string,
  "bpay_biller_code": string,
  "bpay_ref": string,
  "proposed_install_date": string,
  "payment_terms": string,
  "notes": string,
  "roof_type": string,
  "inverter_phase": string,
  "stories": string,
  "extended_warranty": string,
  "backup_type": string,
  "signed_by": string,
  "signed_date": string,
  "rebates": [{"name": string, "amount": number}],
  "line_items": [{"item_type": string, "quantity": number, "specification": string}]
}
""".strip()


# ── Filename → QC key keyword map ────────────────────────────────────────────
# Add new aliases as ("keyword list", "qc_key") tuples.
# The first tuple whose keywords match the filename stem wins.
# Put more specific aliases earlier to avoid false matches.

KEYWORD_MAP = [
    (["signed agreement", "agreement"],                              "signed_agreement"),
    (["deposit", "receipt", "payment"],                              "deposit"),
    (["meter box", "meter photo", "switchboard", "meter board",
      "meter pic", "meterbox"],                                      "meter_photo"),
    (["phase", "upgrade", "3 phase", "single phase"],               "phase_upgrade"),
    (["roof pic", "house pic", "house photo", "roof photo",
      "front of house", "property"],                                 "roof_pic"),
    (["storey", "story", "stories", "roof type"],                   "storey_roof"),
    (["electricity bill", "power bill", "nmi", "energy bill", "ebill", "e-bill", "e bill"], "electricity_bill"),
    (["rate notice", "council rate", "rates notice", "rates"],       "rate_notice"),
    (["meter approval", "meter cert"],                               "meter_approval"),
    (["roof layout", "panel layout"],                                "roof_layout"),
    (["inverter location", "inverter placement"],                    "inverter_location"),
    (["tilt frame", "clip lock", "tiltframe"],                      "tilt_frame"),
    (["scissor lift"],                                               "scissor_lift"),
    (["welcome email", "invoice", "fact sheet", "rl "],             "welcome_email"),
    (["solar vic", "solar victoria", "vic loan", "vic rebate"],     "solar_vic"),
    (["finance", "brighte", "plenti"],                               "finance"),
    (["export control", "export limit"],                             "export_control"),
    (["optimizer", "optimiser", "solaredge"],                       "optimizer"),
    (["first time", "first install", "new install"],                "first_install"),
    (["accounts", "job checked"],                                   "accounts"),
    (["customer informed", "install date", "informed"],             "customer_informed"),
    (["wifi", "wi-fi", "wi fi", "internet"],                        "wifi"),
    (["packing slip", "pack slip"],                                  "packing_slip"),
    (["delivery", "organise delivery", "organize delivery"],        "delivery"),
    (["raise wo", "work order", "wo "],                             "raise_wo"),
    (["inform installer", "installer date"],                        "inform_installer"),
    (["stc", "green deal", "create stc"],                           "stc"),
    (["customer name", "name address", "name & address"],           "cust_name_address"),
    (["solar vic eligible", "eligible rebate", "vic eligible"],     "solar_vic_eligible"),
    (["panel model", "panel spec", "solar panel"],                  "panel_model"),
    (["inverter model", "inverter spec"],                           "inverter_model"),
    (["battery model", "battery spec"],                             "battery_model"),
    # ── Add new keyword aliases above this line ──
]


# ── Per-item rule functions ──────────────────────────────────────────────────

def _extract_deposit_from_agreement(agreement_text: str) -> str | None:
    """Pull the deposit amount out of the signed agreement text."""
    patterns = [
        r'Deposit\s*\(inc\.?\s*GST\)[^\d$]*\$?\s*([\d,]+(?:\.\d{1,2})?)',
        r'Deposit[^\n$]{0,40}\$\s*([\d,]+(?:\.\d{1,2})?)',
        r'\$\s*([\d,]+(?:\.\d{1,2})?)\s*(?:deposit|Deposit)',
    ]
    for pat in patterns:
        m = re.search(pat, agreement_text, re.IGNORECASE)
        if m:
            return m.group(1).replace(",", "").strip()
    return None


def _extract_amount_from_doc(doc_text: str) -> list[str]:
    """Return dollar amounts found in an OCR'd document (currency-context only)."""
    amounts = []
    # Match amounts with explicit $ prefix: $500, $500.00, $ 500.00
    amounts += re.findall(r'\$\s*([\d,]+(?:\.\d{1,2})?)', doc_text)
    # Match amounts followed by AUD/USD currency code: 500.00 AUD
    amounts += re.findall(r'([\d,]+\.\d{2})\s*(?:AUD|USD|aud|usd)', doc_text)
    # Deduplicate while preserving order
    seen = set()
    result = []
    for a in amounts:
        a = a.replace(",", "")
        if a not in seen:
            seen.add(a)
            result.append(a)
    return result


def _amounts_match(expected: str, found_list: list[str]) -> bool:
    try:
        exp = float(expected)
        return any(abs(float(f) - exp) < 0.01 for f in found_list)
    except Exception:
        return False


def _names_match(expected_name: str, doc_lower: str) -> tuple[bool, str]:
    """
    Match individual customer names against OCR'd document text.

    Handles two name styles found in council rate notices:
    - Full names: "Christine Hill" → all words must appear in the doc.
    - Initials style: "Hill, A S & C H" → surname plus a matching first-initial
      for at least one of the parties counts as a match (rate notices commonly
      abbreviate first names to initials).
    """
    if not expected_name:
        return False, ""

    individual_names = [n.strip() for n in re.split(r'\s*&\s*|\s+and\s+', expected_name, flags=re.IGNORECASE) if n.strip()]

    for ind_name in individual_names:
        name_words = [w for w in ind_name.lower().split() if len(w) > 2]
        if name_words and all(w in doc_lower for w in name_words):
            return True, f"Name '{ind_name}' matched on document"

    # Fallback: surname + first-initial match (covers "Hill, A S & C H" style notices)
    for ind_name in individual_names:
        parts = ind_name.split()
        if len(parts) < 2:
            continue
        first, surname = parts[0], parts[-1]
        if len(surname) > 2 and surname.lower() in doc_lower:
            # Look for the surname followed/preceded by the first-name initial somewhere nearby
            initial = first[0].lower()
            surname_lower = surname.lower()
            idx = doc_lower.find(surname_lower)
            window = doc_lower[max(0, idx - 30): idx + len(surname_lower) + 30]
            if re.search(rf'\b{initial}\b', window) or re.search(rf'\b{initial}[a-z]*\s', window):
                return True, f"Name '{ind_name}' matched via surname + initial on document"

    return False, f"Name mismatch — '{expected_name}' not found on document"


def _address_match(expected_address: str, expected_name: str, doc_lower: str) -> tuple[bool, str]:
    """Strip the customer name out of an address block, then token-match the remainder."""
    if not expected_address:
        return False, ""

    clean_address = expected_address
    if expected_name and clean_address.lower().startswith(expected_name.lower()):
        clean_address = clean_address[len(expected_name):].lstrip(", \n")
    for part in expected_name.split("&"):
        part = part.strip()
        if part and clean_address.lower().startswith(part.lower()):
            clean_address = clean_address[len(part):].lstrip(", \n")

    addr_tokens = [t.strip().lower() for t in re.split(r'[,\s]+', clean_address) if len(t.strip()) > 2]
    matched_tokens = sum(1 for t in addr_tokens if t in doc_lower)
    address_ok = len(addr_tokens) > 0 and (matched_tokens / len(addr_tokens)) >= 0.8
    if address_ok:
        return True, f"Address '{clean_address}' matched on document"
    return False, f"Address mismatch — '{clean_address}' not found on document"


def run_item_rule(check_key: str, filename: str, doc_text: str, agreement_text: str, quote: dict | None = None) -> dict | None:
    """
    Custom rule runner called before the generic AI check.

    Returns {"result": "Yes"/"No"/"N/A", "remark": "..."} to short-circuit AI.
    Returns None to fall through to the generic Groq LLM check.

    HOW TO ADD A NEW RULE
    ─────────────────────
    Add an `if check_key == "your_key":` block below.
    • Return a dict to handle the check here (no AI call).
    • Return None to let the AI handle it instead.
    Also add the key to OCR_RULE_KEYS (at the top of this file) if it needs OCR.
    """

    # ── signed_agreement: file present → Yes ────────────────────────────────
    if check_key == "signed_agreement":
        return {"result": "Yes", "remark": f"Refer to {filename}"}

    # ── deposit: match amount in receipt against agreement ───────────────────
    if check_key == "deposit":
        # Prefer the AI-extracted deposit from quote_data (set when agreement was uploaded)
        expected = None
        if quote and quote.get("deposit") is not None:
            expected = str(float(quote["deposit"]))
            # Strip trailing .0 for whole-dollar amounts to simplify matching
            if expected.endswith(".0"):
                expected = expected[:-2]
        if not expected:
            expected = _extract_deposit_from_agreement(agreement_text)
        if not expected:
            return {"result": "N/A", "remark": "Could not find deposit amount in signed agreement"}
        if not doc_text.strip():
            return {"result": "No", "remark": f"Could not extract text from uploaded file. Expected deposit: ${expected}"}
        found = _extract_amount_from_doc(doc_text)
        if _amounts_match(expected, found):
            return {"result": "Yes", "remark": f"Deposit amount ${expected} confirmed in {filename}"}
        found_str = ", ".join(f"${f}" for f in found[:5]) if found else "none"
        return {"result": "No", "remark": f"Expected deposit ${expected} but found: {found_str} in {filename}"}

    # ── electricity_bill: name + address on bill must match agreement ────────
    if check_key == "electricity_bill":
        if not doc_text.strip():
            return {"result": "No", "remark": f"Could not extract text from {filename}"}

        # Get expected name and address from quote_data (AI-extracted at upload time)
        expected_name    = ""
        expected_address = ""
        if quote:
            expected_name    = (quote.get("customer_name") or "").strip()
            expected_address = (
                quote.get("billing_address") or
                quote.get("installation_address") or
                quote.get("delivery_address") or ""
            ).strip()

        if not expected_name and not expected_address:
            return {"result": "N/A", "remark": "Could not find customer name/address in agreement — check manually"}

        doc_lower = doc_text.lower()
        name_ok, name_remark       = _names_match(expected_name, doc_lower)
        address_ok, address_remark = _address_match(expected_address, expected_name, doc_lower)

        remarks = [r for r in (name_remark, address_remark) if r]
        combined = " | ".join(remarks)

        checks = []
        if expected_name:
            checks.append(name_ok)
        if expected_address:
            checks.append(address_ok)

        if all(checks):
            return {"result": "Yes", "remark": combined}
        if not any(checks):
            return {"result": "No",  "remark": combined}
        # One matched, one didn't → N/A
        return {"result": "N/A", "remark": combined}

    # ── rate_notice: council rate notice name + address must match agreement ─
    # Rate notices commonly abbreviate first names to initials, e.g.
    # "Hill, A S & C H" for "Christine Hill & Ashley Hill" — _names_match()
    # accepts a surname + first-initial match for this style.
    if check_key == "rate_notice":
        if not doc_text.strip():
            return {"result": "No", "remark": f"Could not extract text from {filename}"}

        expected_name    = ""
        expected_address = ""
        if quote:
            expected_name    = (quote.get("customer_name") or "").strip()
            expected_address = (
                quote.get("billing_address") or
                quote.get("installation_address") or
                quote.get("delivery_address") or ""
            ).strip()

        if not expected_name and not expected_address:
            return {"result": "N/A", "remark": "Could not find customer name/address in agreement — check manually"}

        doc_lower = doc_text.lower()
        name_ok, name_remark       = _names_match(expected_name, doc_lower)
        address_ok, address_remark = _address_match(expected_address, expected_name, doc_lower)

        remarks = [r for r in (name_remark, address_remark) if r]
        combined = " | ".join(remarks)

        checks = []
        if expected_name:
            checks.append(name_ok)
        if expected_address:
            checks.append(address_ok)

        if all(checks):
            return {"result": "Yes", "remark": combined}
        if not any(checks):
            return {"result": "No",  "remark": combined}
        return {"result": "N/A", "remark": combined}

    # ── meter_photo: file present → Yes ─────────────────────────────────────
    if check_key == "meter_photo":
        return {"result": "Yes", "remark": f"Refer to {filename}"}

    # ── roof_pic: file present → Yes ─────────────────────────────────────────
    if check_key == "roof_pic":
        return {"result": "Yes", "remark": f"Refer to {filename}"}

    # ── phase_upgrade: keyword scan on OCR'd chat screenshot ─────────────────
    if check_key == "phase_upgrade":
        if not doc_text.strip():
            return {"result": "No", "remark": f"Could not extract text from {filename}"}
        # Approval keywords — informal chat language expected
        approval_patterns = [
            r'\bok+\s+for\s+\w+',    # ok/okk for <anything>
            r'\bok\b',               # standalone ok/OK
            r'\bapprove[sd]?\b',
            r'\bapproval\b',
            r'\bconfirm(ed)?\b',
            r'\bcleared?\b',
            r'\ball\s+good\b',
            r'\bgood\s+to\s+go\b',
            r'\bgo\s+ahead\b',
            r'\blooks?\s+good\b',
        ]
        text_lower = doc_text.lower()
        matched = []
        for pat in approval_patterns:
            m = re.search(pat, text_lower)
            if m:
                start = max(0, m.start() - 20)
                end   = min(len(doc_text), m.end() + 40)
                matched.append(doc_text[start:end].strip().replace("\n", " "))
        if matched:
            return {"result": "Yes", "remark": f"Approval found in {filename}: '{matched[0][:80]}'"}
        return {"result": "No", "remark": f"No approval keyword found in {filename}. Check chat manually."}

    # ── storey_roof: check storeys + roof type from house image vs agreement ──
    if check_key == "storey_roof":
        if not doc_text.strip():
            return {"result": "No", "remark": f"Could not extract text/image from {filename}"}

        doc_lower = doc_text.lower()

        # ── Parse vision model response ──────────────────────────────────────
        detected_storeys = ""
        detected_roof    = ""
        for line in doc_text.splitlines():
            line_l = line.strip().lower()
            if line_l.startswith("storeys:"):
                detected_storeys = line.split(":", 1)[-1].strip().lower()
            elif line_l.startswith("roof type:"):
                detected_roof = line.split(":", 1)[-1].strip().lower()

        # Fallback keyword detection if model didn't use the exact format
        if not detected_storeys:
            if any(w in doc_lower for w in ["double storey", "two storey", "2 storey", "2 floor", "second floor", "upper floor"]):
                detected_storeys = "double storey"
            elif any(w in doc_lower for w in ["single storey", "one storey", "1 storey", "1 floor", "ground floor only"]):
                detected_storeys = "single storey"

        # ── Get expected values from quote_data (AI-extracted when agreement uploaded) ──
        expected_storeys = ""
        expected_roof    = ""
        if quote:
            if quote.get("stories"):
                expected_storeys = str(quote["stories"]).strip().lower()
            if quote.get("roof_type"):
                expected_roof = str(quote["roof_type"]).strip().lower()

        # Fallback: parse storeys from raw agreement text
        if not expected_storeys:
            lines = agreement_text.split("\n")
            for i, line in enumerate(lines):
                if re.search(r"Stories:", line.strip(), re.IGNORECASE):
                    for j in range(i + 1, min(i + 8, len(lines))):
                        val = lines[j].strip()
                        if val and not re.match(r'^[\d.]+\s*[Xx]$', val):
                            expected_storeys = val.lower()
                            break
                    break

        if not expected_storeys and not expected_roof:
            return {"result": "N/A", "remark": "Could not find storey/roof info in agreement — check manually"}

        # ── Check storeys ────────────────────────────────────────────────────
        storey_ok = None
        storey_remark = ""
        if expected_storeys:
            exp_is_single = "single" in expected_storeys or "1" in expected_storeys
            exp_is_double = "double" in expected_storeys or "2" in expected_storeys or "two" in expected_storeys
            det_is_single = "single" in detected_storeys
            det_is_double = "double" in detected_storeys

            if not detected_storeys:
                storey_ok     = None
                storey_remark = f"Could not detect storeys from image (expected: {expected_storeys})"
            elif exp_is_single and det_is_single:
                storey_ok     = True
                storey_remark = f"Storeys: single ✓"
            elif exp_is_double and det_is_double:
                storey_ok     = True
                storey_remark = f"Storeys: double ✓"
            else:
                storey_ok     = False
                storey_remark = f"Storey mismatch — agreement: {expected_storeys}, image shows: {detected_storeys}"

        # ── Check roof type ──────────────────────────────────────────────────
        roof_ok = None
        roof_remark = ""
        if expected_roof:
            # Normalise common synonyms before comparing
            def _norm_roof(r: str) -> str:
                r = r.lower()
                for alias, canonical in [
                    ("metal", "tin"), ("colorbond", "tin"), ("colour bond", "tin"),
                    ("colour-bond", "tin"), ("iron", "tin"), ("zincalume", "tin"),
                    ("terracotta", "tile"), ("concrete tile", "tile"), ("clay", "tile"),
                ]:
                    r = r.replace(alias, canonical)
                return r

            exp_norm = _norm_roof(expected_roof)
            det_norm = _norm_roof(detected_roof) if detected_roof else ""

            if not detected_roof:
                roof_ok     = None
                roof_remark = f"Could not detect roof type from image (expected: {expected_roof})"
            elif exp_norm in det_norm or det_norm in exp_norm:
                roof_ok     = True
                roof_remark = f"Roof type: {expected_roof} ✓"
            else:
                roof_ok     = False
                roof_remark = f"Roof mismatch — agreement: {expected_roof}, image shows: {detected_roof}"

        # ── Combine results ──────────────────────────────────────────────────
        remarks = []
        if storey_remark:
            remarks.append(storey_remark)
        if roof_remark:
            remarks.append(roof_remark)
        combined_remark = " | ".join(remarks) if remarks else "Checked storeys and roof type"

        checks = [v for v in [storey_ok, roof_ok] if v is not None]
        if not checks:
            return {"result": "N/A", "remark": combined_remark}
        if all(checks):
            return {"result": "Yes", "remark": combined_remark}
        if not any(checks):
            return {"result": "No",  "remark": combined_remark}
        # One passed, one failed → N/A with remark explaining what's wrong
        return {"result": "N/A", "remark": combined_remark}

    # ── scissor_lift: required if house is 2+ storeys ────────────────────────
    # Triggered by house.png (same image as roof_pic / storey_roof).
    # Primary: parse storeys from the vision model OCR output of the house image.
    # Fallback: use quote_data extracted from the agreement PDF.
    if check_key == "scissor_lift":
        detected_storeys = ""
        doc_lower = doc_text.lower()

        # Parse vision model response (same format as STOREY_PROMPT)
        for line in doc_text.splitlines():
            if line.strip().lower().startswith("storeys:"):
                detected_storeys = line.split(":", 1)[-1].strip().lower()
                break

        # Keyword fallback if model didn't use exact format
        if not detected_storeys:
            if any(w in doc_lower for w in ("double storey", "two storey", "2 storey", "2 floor", "second floor", "upper floor")):
                detected_storeys = "double storey"
            elif any(w in doc_lower for w in ("single storey", "one storey", "1 storey", "1 floor", "ground floor only")):
                detected_storeys = "single storey"

        # Fallback: use stories from quote_data (agreement PDF extraction)
        if not detected_storeys and quote:
            stories_raw = str(quote.get("stories") or "").strip().lower()
            if any(w in stories_raw for w in ("2", "two", "double", "multi", "3", "three", "triple")):
                detected_storeys = "double storey"
            elif any(w in stories_raw for w in ("1", "one", "single")):
                detected_storeys = "single storey"

        if not detected_storeys:
            return {"result": "N/A", "remark": "Could not determine storey count from house image or agreement — check manually"}

        is_multi = "double" in detected_storeys or "2" in detected_storeys
        if is_multi:
            return {"result": "Yes", "remark": f"House is {detected_storeys} — scissor lift required"}
        return {"result": "No", "remark": f"House is {detected_storeys} — scissor lift not required"}

    # ── Add new rules above this line ────────────────────────────────────────
    # Return None to let the generic AI handle everything else.
    return None
