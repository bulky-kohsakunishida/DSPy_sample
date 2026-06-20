import dspy

from connect_agent_eval.settings import DEFAULT_LM_SETTINGS, LMSettings


def configure_lm(settings: LMSettings = DEFAULT_LM_SETTINGS) -> dspy.LM:
    lm = dspy.LM(
        settings.model,
        api_base=settings.api_base,
        api_key=settings.api_key,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        cache=False,
        extra_body={"think": False},
    )
    dspy.configure(lm=lm)
    return lm

