import importlib
import sys

import pytest


@pytest.fixture(scope="module")
def llm_selector_module():
    sys.modules.pop("llm_service.llm_selector", None)
    return importlib.import_module("llm_service.llm_selector")


def test_get_llm_model_returns_default_model(llm_selector_module):
    model = llm_selector_module.LLMSelector.get_llm_model(None)

    assert model is llm_selector_module.LLMSelector.llm_clients["default"]


def test_get_llm_model_returns_supported_model(llm_selector_module):
    model = llm_selector_module.LLMSelector.get_llm_model("qwen3:8b")

    assert model is llm_selector_module.LLMSelector.llm_clients["qwen3:8b"]


def test_get_llm_model_rejects_unknown_model(llm_selector_module):
    with pytest.raises(ValueError, match="LLM model 'not-a-model' is not supported."):
        llm_selector_module.LLMSelector.get_llm_model("not-a-model")