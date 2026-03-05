"""smolagents factory for the helloworld character builder.

This module is loaded by the smolagents_runner.py bridge when the
Python FlatMachine executes a state that references a "smolagents-bridge"
adapter.

The factory receives config kwargs from the machine YAML and must return
a smolagents agent instance that supports .run(task, **kwargs).
"""

from smolagents import LiteLLMModel, CodeAgent


def build_agent(model: str = "cerebras/zai-glm-4.7", **kwargs):
    """Build a smolagents CodeAgent for the hello-world character builder.

    Parameters
    ----------
    model:
        Model identifier passed to LiteLLMModel (e.g. "cerebras/zai-glm-4.7").
    **kwargs:
        Additional keyword arguments forwarded to CodeAgent.
    """
    llm = LiteLLMModel(model_id=model)
    agent = CodeAgent(
        tools=[],
        model=llm,
        system_prompt=(
            "You are an agent in a test-time sequential scaling. "
            "Reply with exactly one output character in text format. "
            "No explanation. No wrapper."
        ),
        max_steps=1,
        **kwargs,
    )
    return agent
