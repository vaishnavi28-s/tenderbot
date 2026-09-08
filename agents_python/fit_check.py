import json
import re

from litellm import completion

from company_profile import get_relevant_profile

FIT_CHECK_PROMPT = """You are checking whether a company meets a tender's
eligibility requirements. You will be given the company's profile and a
list of eligibility criteria extracted from the tender.

For EACH criterion, judge it independently:
- "met": the company profile clearly satisfies this requirement
- "not_met": the company profile clearly does NOT satisfy this requirement
- "unclear": the criterion doesn't map to anything in the company profile
  (not enough information to judge either way - this is NOT the same as
  "not_met")

Never guess. If the profile doesn't mention something the criterion asks
about, that is "unclear", not "not_met".

Company profile:
{profile}

Eligibility criteria:
{criteria}

Return ONLY a JSON array, one object per criterion, in this exact shape,
nothing else:
[
  {{"criterion": "...", "status": "met", "reason": "one short sentence"}},
  {{"criterion": "...", "status": "not_met", "reason": "one short sentence"}},
  {{"criterion": "...", "status": "unclear", "reason": "one short sentence"}}
]
"""


def compute_fit_tier(verdicts: list[dict]) -> str:
    """
    Plain rule, no AI. Takes the AI's per-criterion verdicts and produces
    one overall tier. Deliberately simple and inspectable.
    """
    if not verdicts:
        return "Unclear"

    statuses = [v.get("status") for v in verdicts]
    met = statuses.count("met")
    not_met = statuses.count("not_met")
    total = len(statuses)

    unclear = statuses.count("unclear")

    if not_met == 0 and met == total:
        return "Great fit"
    if not_met == 0 and met >= total / 2:
        return "Good fit"
    if not_met > 0 and met > 0:
        return "Partial fit"
    if not_met == 0 and unclear > 0:
        return "Unclear"  # nothing failed, just not enough info yet
    return "Low fit"




def extract_json_array(raw_text: str) -> list:
    """
    Finds a valid JSON array in the AI's raw output. Tries every
    bracket-delimited candidate substring, from LAST to FIRST (the AI's
    real final answer tends to come after any preamble/examples), keeping
    the first one that actually parses as valid JSON.

    Fixes a real gap in a simpler greedy-regex approach: if the AI's raw
    text happens to mention an unrelated bracket example, or produces two
    separate array-looking blocks (e.g. a draft then a correction), a
    single greedy match spanning first-'[' to last-']' fails to parse at
    all. Verified against both cases with a real test - this version
    resolves both correctly. Same "take the last match" pattern already
    used in my_mastra_app/src/server.ts for the same underlying problem.
    """
    candidates = re.findall(r"\[.*?\]", raw_text, re.DOTALL)
    for candidate in reversed(candidates):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return []



def check_tender_fit(eligibility_criteria: list[str], category: str | None = None) -> dict:
    """
    Returns {"fitTier": str, "fitReasons": [ {criterion, status, reason} ]}.
    Called once per tender, at fetch/validation time.

    `category` narrows which company-profile fields the AI is shown -
    e.g. a digitalisierung tender is compared against IT/cloud-specific
    fields, not scanning- or election-specific ones that have nothing to
    do with it. Falls back to the full profile if category is unknown.
    """
    if not eligibility_criteria:
        return {"fitTier": "Unclear", "fitReasons": []}

    company_profile = get_relevant_profile(category)
    prompt = FIT_CHECK_PROMPT.format(
        profile=json.dumps(company_profile, indent=2),
        criteria=json.dumps(eligibility_criteria, indent=2),
    )

    try:
        response = completion(
            model="openai/tender-crew-model",
            messages=[{"role": "user", "content": prompt}],
            base_url="http://localhost:4000/v1",
            api_key="sk-1234",
            temperature=0,
        )
        raw_text = response.choices[0].message.content
        verdicts = extract_json_array(raw_text) if raw_text else []

    except Exception as e:
        print(f"Fit check failed: {e}")
        verdicts = []

    return {
        "fitTier": compute_fit_tier(verdicts),
        "fitReasons": verdicts,
    }
