"""
Unit tests for Shawarar Lafiya Clinical Guardrail Service.
"""

import pytest
from app.services.guardrail_service import guardrail_service
from app.schemas import TriageTier

def test_convulsion_red_flag_detection_hausa():
    text = "Yaro na yana ta farfadiya da karkarwa a jiki."
    detections = guardrail_service.scan_for_red_flags(text, language="ha")
    assert len(detections) >= 1
    flag_ids = [d.flag_id for d in detections]
    assert "RF_CONVULSION_SEIZURE" in flag_ids
    assert detections[0].severity == "CRITICAL"

def test_unconscious_red_flag_detection_english():
    text = "The patient is completely unconscious and cannot wake up."
    detections = guardrail_service.scan_for_red_flags(text, language="en")
    assert len(detections) >= 1
    flag_ids = [d.flag_id for d in detections]
    assert "RF_UNCONSCIOUS_LETHARGIC" in flag_ids

def test_chest_indrawing_pneumonia_detection():
    text = "Yarinya ta tana da shanyewar kirji kuma numfashi da kyar take yi."
    detections = guardrail_service.scan_for_red_flags(text, language="ha")
    flag_ids = [d.flag_id for d in detections]
    assert "RF_RESPIRATORY_DISTRESS" in flag_ids

def test_cannot_drink_or_breastfeed_danger_sign():
    text = "Jariri ya daina shan nono gaba daya."
    detections = guardrail_service.scan_for_red_flags(text, language="ha")
    flag_ids = [d.flag_id for d in detections]
    assert "RF_CANNOT_DRINK_BREASTFEED" in flag_ids

def test_maternal_hemorrhage_detection():
    text = "Ina da ciki kuma ga zubar jini a lokacin ciki tare da matsanancin ciwon kai."
    detections = guardrail_service.scan_for_red_flags(text, language="ha")
    flag_ids = [d.flag_id for d in detections]
    assert "RF_MATERNAL_HEMORRHAGE" in flag_ids

def test_safe_non_emergency_text_has_no_red_flags():
    text = "Ina da dan mura da atishawa amma ba zazzabi."
    detections = guardrail_service.scan_for_red_flags(text, language="ha")
    assert len(detections) == 0

def test_prohibited_antibiotic_prescription_sanitization():
    unsafe_text = "Ka sha amoxicillin 500mg ko ciprofloxacin sau biyu a rana."
    sanitized, blocked = guardrail_service.sanitize_and_check_prescriptions(unsafe_text)
    assert "amoxicillin" in blocked
    assert "ciprofloxacin" in blocked
    assert "amoxicillin" not in sanitized.lower()
    assert "ciprofloxacin" not in sanitized.lower()
    assert "MAGANI: Ana bukatar gwajin jini" in sanitized

def test_prohibited_antimalarial_prescription_sanitization():
    unsafe_text = "Je kemis ka sayi coartem ko lonart ka sha."
    sanitized, blocked = guardrail_service.sanitize_and_check_prescriptions(unsafe_text)
    assert "coartem" in blocked
    assert "lonart" in blocked

def test_emergency_override_response_structure():
    detections = guardrail_service.scan_for_red_flags("Yaro yana farfadiya", language="ha")
    override = guardrail_service.build_emergency_override_response(detections, language="ha")
    assert override["tier"] == TriageTier.RED
    assert override["is_emergency"] is True
    assert "Gaggawa" in override["tier_label_ha"]
    assert len(override["primary_actions_ha"]) > 0

def test_tts_service_hash_generation():
    from app.services.tts_service import tts_service
    res = tts_service.generate_voice_response("Sannu da zuwa cibiyar lafiya.", language="ha")
    assert res["status"] == "ready"
    assert "text_hash=" in res["audio_url"]
    assert len(res["audio_url"].split("text_hash=")[1].split("&")[0]) == 8

def test_gemini_service_tier_case_normalization():
    from app.services.gemini_service import gemini_service
    sample_data = {
        "tier": " red ",
        "tier_label_ha": "Gaggawa",
        "tier_label_en": "Emergency",
        "is_emergency": True,
        "summary_ha": "Gaggawa ce.",
        "summary_en": "It is an emergency.",
        "primary_actions_ha": ["Tafi asibiti"],
        "primary_actions_en": ["Go to hospital"],
        "clinical_disclaimer_ha": "Shawarar Lafiya taimako ne.",
        "clinical_disclaimer_en": "Triage support only.",
        "nearest_care_guidance_ha": "Tafi PHC.",
        "nearest_care_guidance_en": "Go to PHC."
    }
    gemini_service._validate_triage_json(sample_data)
    assert sample_data["tier"] == "RED"

@pytest.mark.anyio
async def test_triage_service_sanitizes_summaries_and_guidance():
    from app.services.triage_service import triage_service
    from app.services.gemini_service import gemini_service
    from app.schemas import SymptomTriageRequest
    from unittest.mock import AsyncMock, patch

    # Mock gemini to return an unsafe response with prescriptions in summaries and guidance
    unsafe_mock_response = {
        "tier": "YELLOW",
        "tier_label_ha": "Gani Likita",
        "tier_label_en": "Clinical Visit",
        "is_emergency": False,
        "summary_ha": "Mara lafiya ya sha amoxicillin 250mg a gida.",
        "summary_en": "Patient should take augmentin and coartem at home.",
        "primary_actions_ha": ["Sha metronidazole sau biyu a rana"],
        "primary_actions_en": ["Buy ciprofloxacin from pharmacy"],
        "clinical_disclaimer_ha": "Shawarar Lafiya taimako ne kawai.",
        "clinical_disclaimer_en": "Triage support only.",
        "nearest_care_guidance_ha": "Je PHC don karbar cipro.",
        "nearest_care_guidance_en": "Visit clinic to collect ampicillin."
    }

    req = SymptomTriageRequest(
        symptoms_text="Ina da zazzabi da tari",
        language="ha"
    )

    old_avail = gemini_service._available
    old_model = gemini_service._model
    try:
        gemini_service._available = True
        gemini_service._model = "mock_model"
        with patch.object(gemini_service, "run_triage", new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = unsafe_mock_response
            res = await triage_service.triage_symptoms(req)

            # Assert no prohibited drugs remained in summaries or guidance
            assert "amoxicillin" not in res.summary_ha.lower()
            assert "augmentin" not in res.summary_en.lower()
            assert "coartem" not in res.summary_en.lower()
            assert "metronidazole" not in res.primary_actions_ha[0].lower()
            assert "ciprofloxacin" not in res.primary_actions_en[0].lower()
            assert "cipro" not in res.nearest_care_guidance_ha.lower()
            assert "ampicillin" not in res.nearest_care_guidance_en.lower()

            # Assert all detected drugs were recorded in blocked list
            blocked = set(res.blocked_prescriptions_found)
            assert "amoxicillin" in blocked
            assert "augmentin" in blocked
            assert "coartem" in blocked
            assert "metronidazole" in blocked
            assert "ciprofloxacin" in blocked
            assert "ampicillin" in blocked
    finally:
        gemini_service._available = old_avail
        gemini_service._model = old_model


