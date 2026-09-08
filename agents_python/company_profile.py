COMPANY_IDENTITY = {
    "name": "NovaTech Solutions GmbH",
    "founded_year": 2014,
    "annual_turnover_eur": 3_200_000,
    "employee_count": 28,
    "certifications": ["ISO 9001", "ISO 27001"],
    "pq_registered": True,
    "sectors": ["IT", "Digitalization", "Consulting"],
}

UNIVERSAL_ELIGIBILITY_FIELDS = {
    "years_relevant_experience": 6,
    "trade_register_registered": True,
    "commercial_register_registered": True,
    "professional_association_member": True,
    "comparable_project_references_last_5_years": 4,
    "tax_and_social_security_compliant": True,
    "no_insolvency_proceedings": True,
    "no_serious_professional_misconduct": True,
    "no_criminal_convictions": True,
    "liability_insurance": True,
    "minimum_wage_compliant": True,
    "average_annual_staff_last_3_years": 25,
}

DIGITALISIERUNG_FIELDS = {
    "gdpr_compliant": True,
    "data_processing_agreement_available": True,
    "data_hosted_in_eu": True,
    "bsi_c5_attestation": False,
}

SCANDIENSTLEISTUNGEN_FIELDS = {
    "tr_resiscan_compliant": True,
    "din_66399_certified": True,
    "external_data_protection_officer": True,
    "secure_document_logistics": True,
}

WAHLUNTERLAGEN_FIELDS = {
    "confidentiality_declaration_available": True,
    "secure_print_and_mail_logistics": True,
}

_CATEGORY_FIELD_GROUPS = {
    "digitalisierung": DIGITALISIERUNG_FIELDS,
    "scandienstleistungen": SCANDIENSTLEISTUNGEN_FIELDS,
    "wahlunterlagen": WAHLUNTERLAGEN_FIELDS,
}


def get_relevant_profile(category: str | None) -> dict:
    profile = {**COMPANY_IDENTITY, **UNIVERSAL_ELIGIBILITY_FIELDS}

    if category in _CATEGORY_FIELD_GROUPS:
        profile.update(_CATEGORY_FIELD_GROUPS[category])
    else:
        for group in _CATEGORY_FIELD_GROUPS.values():
            profile.update(group)

    return profile


COMPANY_PROFILE = get_relevant_profile(None)