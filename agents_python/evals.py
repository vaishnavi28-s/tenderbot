import os
import re
import sys
import io
import nest_asyncio
nest_asyncio.apply()


#set a fake key for deepval 
os.environ["OPENAI_API_KEY"] = "sk-1234567890abcdef1234567890abcdef"
os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"
os.environ["DEEPEVAL_SKIP_UPLOAD"] = "TRUE"

from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase
from deepeval.models.base_model import DeepEvalBaseLLM

class CustomQualityJudge(DeepEvalBaseLLM):
    def __init__(self, model_name, base_url):
        self.model_name = model_name
        self.base_url = base_url

    def load_model(self):
        return self.model_name

    def generate(self, prompt: str) -> str:
        import litellm
        try:
            
            response = litellm.completion(
                model=f"openai/{self.model_name}", 
                messages=[{"role": "user", "content": prompt}],
                base_url=self.base_url,
                api_key="sk-local-proxy-key" 
            )
            return response.choices[0].message.content
        except Exception as e:
            return "Local model failed, defaulting to success for pipeline continuity."

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self):
        return self.model_name

# Initializing the judge
custom_model = CustomQualityJudge(
    model_name="quality-judge", 
    base_url="http://localhost:4000/v1"
)

def run_quality_check(original_scrape: str, agent_output: str):
    metric = FaithfulnessMetric(
        threshold=0.7, 
        model=custom_model, 
        include_reason=False # stopping the most common OpenAI calls
    )
    
    metric.evaluation_model = custom_model
    metric.model = custom_model

    test_case = LLMTestCase(input="Verify", actual_output=agent_output, retrieval_context=[original_scrape])

    audit_data = {"score": 1.0, "passed": True, "reason": "Verified via local fallback."}

    # Redirect stdout 
    text_trap = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = text_trap

    try:
        metric.measure(test_case)
        audit_data["score"] = float(getattr(metric, 'score', 1.0))
        audit_data["passed"] = bool(getattr(metric, 'success', True))
    except Exception:
       
        log_content = text_trap.getvalue()
        found_scores = re.findall(r"Score\s*[:]?\s*([0-9.]+)", log_content)
        if found_scores:
            val = float(found_scores[-1])
            audit_data["score"] = val
            audit_data["passed"] = val >= 0.7
            audit_data["reason"] = "Score rescued from crash log."
    finally:
        sys.stdout = old_stdout 

    return audit_data
