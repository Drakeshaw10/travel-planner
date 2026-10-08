"""Shared structured-output call used by every node that extracts data from chat.

The profiler (Preferences) and constraints (TripInputs) nodes both ask the LLM
to fill a Pydantic model and both need the same failure handling, so it lives
here once instead of being copied into each node.
"""

import logging

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def extract(extractor, messages, label: str) -> BaseModel | None:
    """Call the model once, and once more if its answer doesn't parse.

    `extractor` is `llm.with_structured_output(Model, include_raw=True)`, which
    returns {"raw", "parsed", "parsing_error"} instead of raising on bad output.
    `label` names the caller in log messages ("profiler", "constraints").

    LLD.md's rule for structured output: retry once with the parse error added,
    then give up and keep the old values. Returns None when both tries fail.

    Only *parse* failures are handled here. If the API call itself fails
    (timeout, 5xx, 429), the exception propagates: the node fails, the
    checkpoint stays as it was, and the user gets the Retry button.
    """
    result = extractor.invoke(messages)
    if result["parsed"] is not None and result["parsing_error"] is None:
        return result["parsed"]

    logger.warning("%s output did not parse, retrying: %s", label, result["parsing_error"])
    retry = [
        *messages,
        HumanMessage(
            "Your previous answer could not be used because of this error:\n"
            f"{result['parsing_error']}\n"
            "Answer again, following the schema exactly."
        ),
    ]
    result = extractor.invoke(retry)
    if result["parsed"] is not None and result["parsing_error"] is None:
        return result["parsed"]

    logger.warning("%s output did not parse twice, keeping old values: %s",
                   label, result["parsing_error"])
    return None
