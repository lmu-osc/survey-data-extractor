
TRANSLATABLE_COLUMNS = [
    "Q6_oa_comment", "Q6_rdm_comment", "Q6_fair_comment", "Q6_code_comment", "Q6_material_comment", "Q6_prereg_comment", "Q6_rr_comment",
    "Q7_oa_comment", "Q7_rdm_comment", "Q7_fair_comment", "Q7_code_comment", "Q7_material_comment", "Q7_prereg_comment", "Q7_rr_comment",
    "Q8_other_1", "Q8_other_2", "Q8_other_3",
    "Q9_other_1", "Q9_other_2", "Q9_other_3",
    "Q10_other_1", "Q10_other_2", "Q10_other_3",
    "Q11_other_1", "Q11_other_2", "Q11_other_3", "Q12_1", "Q12_2", "Q12_3", "Q12_4", "Q12_5"
]


DEFAULT_INPUT_PATH = "data/LMU_wide_survey_DE_selected_preprocessed.tab"
DEFAULT_OUTPUT_PATH = "data/LMU_wide_survey_DE_selected_translated.tab"
DEFAULT_NOTABLE_QUOTES_PATH = "data/LMU_wide_survey_DE_selected_notable_quotes.tab"
DEFAULT_MAP_OUTPUT_PATH = "data/LMU_wide_survey_DE_selected_translation_map.tab"
DEFAULT_CACHE_PATH = "data/translation_cache.json"
DEFAULT_MODEL = "google:gemini-3.1-flash-lite-preview"