"""
Template Fallback Advisories — Section 20 of the build spec.

Every rule has a hand-written template advisory in every supported language.
When the model is unavailable or fails validation, the farmer still gets
a correct warning.

7 rules × 3 severities × 2 Tier-1 languages = 42 short strings.
Only {rain}, {temp}, {days}, {crop} may be substituted — all taken from evidence.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Template table: (rule_id, language) -> template dict
# ---------------------------------------------------------------------------
TEMPLATES: dict[tuple[str, str], dict] = {
    # ==== HEAVY_RAIN_PRE_SPRAY ====
    ("HEAVY_RAIN_PRE_SPRAY", "hi"): {
        "headline": "अगले 2 दिन भारी बारिश की संभावना",
        "body": "अगले 48 घंटों में {rain_mm_next_48h} मिमी बारिश की संभावना है। आपकी {crop} फसल {stage_window} चरण में है। छिड़काव या यूरिया न डालें — बारिश में बह जाएगा।",
        "actions": [
            "छिड़काव बारिश के बाद तक टालें",
            "खेत की नालियाँ साफ करें",
            "यूरिया बारिश के बाद डालें",
        ],
        "spoken_script": "किसान भाई, अगले दो दिन भारी बारिश आने वाली है। अभी छिड़काव या यूरिया मत डालिए, बारिश में बह जाएगा। पहले खेत की नालियाँ साफ कर लीजिए।",
    },
    ("HEAVY_RAIN_PRE_SPRAY", "en"): {
        "headline": "Heavy rain expected in next 2 days",
        "body": "{rain_mm_next_48h} mm rain expected in the next 48 hours. Your {crop} is at {stage_window}. Do not spray or apply urea — it will wash off.",
        "actions": [
            "Postpone spraying until after the rain",
            "Clear the field drains today",
            "Reschedule urea for after the rain",
        ],
        "spoken_script": "Heavy rain is coming in the next two days. Do not spray or apply urea now, it will wash off. Clear your field drains today.",
    },
    # ==== WATERLOG_RISK ====
    ("WATERLOG_RISK", "hi"): {
        "headline": "जलभराव का खतरा — नालियाँ खोलें",
        "body": "अगले 3 दिनों में {rain_mm_3day} मिमी बारिश की संभावना है। आपके खेत में पानी जमा हो सकता है। तुरंत नालियाँ खोलें।",
        "actions": [
            "खेत की नालियाँ तुरंत खोलें",
            "मेड़ साफ करें",
            "बिचड़े की जाँच करें",
        ],
        "spoken_script": "किसान भाई, अगले तीन दिन बहुत बारिश होगी। खेत में पानी जमा हो सकता है। अभी नालियाँ खोल दीजिए और मेड़ साफ कीजिए।",
    },
    ("WATERLOG_RISK", "en"): {
        "headline": "Waterlogging risk — open drainage now",
        "body": "{rain_mm_3day} mm rain expected over the next 3 days. Your field may waterlog. Open drainage channels immediately.",
        "actions": [
            "Open field drainage channels now",
            "Clear the bunds",
            "Check the nursery area",
        ],
        "spoken_script": "Heavy rain is expected for three days. Your field may get waterlogged. Open the drainage channels now and clear the bunds.",
    },
    # ==== HEAT_STRESS_FLOWERING ====
    ("HEAT_STRESS_FLOWERING", "hi"): {
        "headline": "गर्मी का तनाव — शाम को सिंचाई करें",
        "body": "अगले दिनों में तापमान {t_max_peak_c}°C तक पहुँच सकता है। आपकी {crop} फसल {stage_window} में है। शाम को सिंचाई करें, दोपहर में काम न करें।",
        "actions": [
            "शाम को हल्की सिंचाई करें",
            "पलवार (मल्चिंग) करें",
            "दोपहर में खेत का काम न करें",
        ],
        "spoken_script": "किसान भाई, आने वाले दिनों में बहुत गर्मी होगी। आपकी फसल को नुकसान हो सकता है। शाम को सिंचाई करें और दोपहर में खेत में काम न करें।",
    },
    ("HEAT_STRESS_FLOWERING", "en"): {
        "headline": "Heat stress alert — irrigate in the evening",
        "body": "Temperature may reach {t_max_peak_c}°C in the coming days. Your {crop} is at {stage_window}. Irrigate in the evening and avoid midday operations.",
        "actions": [
            "Irrigate in the evening",
            "Apply mulch to conserve moisture",
            "Avoid field operations during midday heat",
        ],
        "spoken_script": "Very hot days are coming. Your crop may be stressed. Water your field in the evening and do not work in the field during the hot midday hours.",
    },
    # ==== DRY_SPELL ====
    ("DRY_SPELL", "hi"): {
        "headline": "सूखे का खतरा — सिंचाई की योजना बनाएं",
        "body": "अगले {dry_days_forecast} दिन बारिश की संभावना बहुत कम है। आपकी {crop} वर्षा आधारित है। सिंचाई को प्राथमिकता दें।",
        "actions": [
            "सबसे जरूरी सिंचाई पहले करें",
            "पलवार (मल्चिंग) करें",
            "मिट्टी की नमी बचाएं",
        ],
        "spoken_script": "किसान भाई, आने वाले दिनों में बारिश नहीं होगी। आपकी फसल को पानी की जरूरत है। जो सबसे जरूरी सिंचाई है वो पहले करें।",
    },
    ("DRY_SPELL", "en"): {
        "headline": "Dry spell ahead — plan irrigation",
        "body": "No significant rain expected for the next {dry_days_forecast} days. Your {crop} is rainfed. Prioritise critical irrigation.",
        "actions": [
            "Prioritise the most critical irrigation",
            "Apply mulch to reduce evaporation",
            "Conserve soil moisture",
        ],
        "spoken_script": "No rain is expected for the coming days. Your crop needs water. Do the most important irrigation first and use mulch to keep the soil moist.",
    },
    # ==== PEST_WEATHER_WINDOW ====
    ("PEST_WEATHER_WINDOW", "hi"): {
        "headline": "कीट का मौसम — खेत की जाँच करें",
        "body": "आने वाले दिनों में नमी {humidity_pct_avg}% से ऊपर रहेगी। यह कीटों के लिए अनुकूल है। अपने {crop} के खेत की जाँच करें।",
        "actions": [
            "खेत में कीटों की जाँच करें",
            "तने और पत्तियों को ध्यान से देखें",
            "जरूरत हो तो नजदीकी KVK से सलाह लें",
        ],
        "spoken_script": "किसान भाई, आने वाले दिनों में मौसम कीटों के लिए अच्छा रहेगा। अपने खेत में कीटों की जाँच करें। कोई दिक्कत हो तो KVK से बात करें।",
    },
    ("PEST_WEATHER_WINDOW", "en"): {
        "headline": "Pest-favourable weather — scout your field",
        "body": "Humidity will stay above {humidity_pct_avg}% in the coming days. This favours pest buildup in {crop}. Scout your field now.",
        "actions": [
            "Scout the field for pests today",
            "Check stems and leaves carefully",
            "Consult your local KVK if needed",
        ],
        "spoken_script": "The weather in the coming days favours pests. Check your field carefully for any signs of pest damage. If you see something, ask your local KVK for advice.",
    },
    # ==== HARVEST_RAIN_CLASH ====
    ("HARVEST_RAIN_CLASH", "hi"): {
        "headline": "कटाई के समय बारिश — जल्दी काटें",
        "body": "आपकी {crop} कटाई के करीब है और {rain_mm_in_window} मिमी बारिश आने वाली है। जल्दी कटाई करें और ढकी हुई जगह में रखें।",
        "actions": [
            "जितना हो सके जल्दी कटाई करें",
            "ढकी हुई भंडारण व्यवस्था करें",
            "फसल को अभी सुखाएं",
        ],
        "spoken_script": "किसान भाई, आपकी फसल कटाई के लिए तैयार है और बारिश आने वाली है। जितना जल्दी हो सके काट लीजिए और ढकी जगह में रखिए।",
    },
    ("HARVEST_RAIN_CLASH", "en"): {
        "headline": "Rain at harvest — consider early harvest",
        "body": "Your {crop} is near harvest and {rain_mm_in_window} mm rain is forecast. Consider harvesting early and arrange covered storage.",
        "actions": [
            "Harvest as soon as possible",
            "Arrange covered storage",
            "Dry produce now before the rain",
        ],
        "spoken_script": "Your crop is ready for harvest and rain is coming. Harvest as soon as you can and keep the produce in a covered place to prevent damage.",
    },
    # ==== FROST_RISK ====
    ("FROST_RISK", "hi"): {
        "headline": "पाला पड़ने का खतरा — फसल ढकें",
        "body": "तापमान {t_min_lowest_c}°C तक गिर सकता है। आपकी {crop} फसल को नुकसान हो सकता है। शाम को हल्की सिंचाई करें और फसल ढकें।",
        "actions": [
            "शाम को हल्की सिंचाई करें",
            "नर्सरी/फसल को ढकें",
            "धुआं कर सकते हैं",
        ],
        "spoken_script": "किसान भाई, आने वाली रात बहुत ठंड होगी, पाला पड़ सकता है। शाम को हल्का पानी दीजिए और फसल को ढक दीजिए।",
    },
    ("FROST_RISK", "en"): {
        "headline": "Frost risk — protect your crop tonight",
        "body": "Temperature may drop to {t_min_lowest_c}°C. Your {crop} could be damaged by frost. Irrigate lightly in the evening and cover the crop.",
        "actions": [
            "Light irrigation in the evening",
            "Cover the nursery or crop",
            "Use smoke protection if possible",
        ],
        "spoken_script": "Very cold night ahead, frost is possible. Water your field lightly this evening and cover your crop or nursery to protect it.",
    },
}


def get_template(
    rule_id: str, language: str, evidence: dict, crop: str = "", stage_window: str = ""
) -> dict | None:
    """
    Return a filled template advisory for the given rule and language.
    Falls back to Hindi if the requested language is unavailable.
    Returns None only if no template exists at all.
    """
    key = (rule_id, language)
    template = TEMPLATES.get(key)

    if template is None and language != "hi":
        # Fallback: try Hindi
        template = TEMPLATES.get((rule_id, "hi"))

    if template is None:
        return None

    # Build substitution context from evidence + crop + stage
    subs = {**evidence, "crop": crop, "stage_window": stage_window}

    def fill(s: str) -> str:
        try:
            return s.format(**subs)
        except (KeyError, IndexError):
            return s  # partial fill is better than crash

    return {
        "headline": fill(template["headline"]),
        "body": fill(template["body"]),
        "actions": [fill(a) for a in template["actions"]],
        "spoken_script": fill(template["spoken_script"]),
    }
