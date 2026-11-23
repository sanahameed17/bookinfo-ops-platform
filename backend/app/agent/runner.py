"""
AI OpsAgent - LangChain structured-chat ReAct agent, adapted from Lab 3 (core/agent_builder.py).

REUSED from Lab 3:
  * initialize_agent(... STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION) from langchain_classic
    (the combination that worked with DeepSeek in Lab 3);
  * RobustStructuredChatOutputParser (DeepSeek DSML / bare JSON / plain final answer);
  * LoopGuard circuit breaker; handle_parsing_errors=True; tool errors become Observations;
  * ChatOpenAI with key / base URL / model from environment variables, temperature 0, timeout.

CHANGED for this project:
  * only READ-ONLY tools (see tool_impls.py) - no Docker, kubectl apply, exec or file tools;
  * every tool call is recorded and returned to the frontend as evidence;
  * the conversation history comes from the request (stateless backend, no server memory);
  * LLM/API errors become structured HTTP errors without leaking the API key.
"""
import json
import logging
import re
import time

from app.agent.loop_guard import LoopGuard
from app.agent.tool_impls import TOOL_SPECS
from app.errors import LLMError, LLMNotConfigured

log = logging.getLogger(__name__)

AGENT_RULES = """You are OpsAgent, a READ-ONLY site-reliability assistant for the Istio Bookinfo
application running in Kubernetes namespace "{namespace}".

Facts about the system:
- Logical services: productpage, details, ratings, reviews. "reviews" is ONE Kubernetes Service
  with three Deployments/versions: reviews-v1, reviews-v2, reviews-v3. Do not call them three services.
- Each pod has the application container plus the istio-proxy (Envoy) sidecar.
- CPU is measured in cores (0.1 cores = 100 millicores). Memory is in MiB.
- Anomaly thresholds: CPU > {cpu} cores, memory > {mem} MiB per pod.

Rules:
- ALWAYS call tools to get facts. Never invent numbers, pod names or dependencies.
- If a tool says Prometheus or a metric is unavailable, say so clearly. Missing data is NOT healthy.
- You cannot change anything: you have no tool to delete, restart, scale or edit resources.
  If the user asks for a change, explain that you are read-only and suggest the kubectl command
  they could run themselves.
- For questions about readiness, liveness, probes or "failed checks", call BOTH get_pods (current state)
  AND get_pod_events (probe failures of the last hour, reason "Unhealthy"), and report both.
- "readiness_probe": "none defined" means no probe is configured - it is NOT a failure.
- Write plain text without Markdown (no ** or #).
- For "why" questions, combine evidence (metric trend, restarts, events, probes) and say what is
  proven and what is only a hypothesis.
- Keep the final answer short and concrete; mention pod names and values with units.
"""


def _sanitize(text: str, secret: str) -> str:
    if secret:
        text = text.replace(secret, "***")
    return re.sub(r"sk-[A-Za-z0-9_\-*]{6,}", "sk-***", text)


class AgentRunner:
    def __init__(self, settings, platform):
        self.settings = settings
        self.platform = platform

    # ------------------------------------------------------------------ building blocks
    def _llm(self):
        from langchain_openai import ChatOpenAI
        s = self.settings
        return ChatOpenAI(model=s.effective_llm_model, api_key=s.effective_llm_api_key,
                          base_url=s.effective_llm_base_url or None, temperature=0, max_retries=1,
                          timeout=s.llm_timeout_seconds, max_tokens=1500)

    def build_tools(self, recorder: list, guard: LoopGuard):
        from langchain_core.tools import StructuredTool
        from pydantic import Field, create_model

        tools = []
        for name, (fn, description, args) in TOOL_SPECS.items():
            fields = {a: (t, Field(default=d, description=h)) for a, (t, d, h) in args.items()}
            schema = create_model(f"{name}_input", **fields)

            def run(_fn=fn, _name=name, **kwargs):
                start = time.perf_counter()
                result = _fn(self.platform, **kwargs)
                text = json.dumps(result, default=str)
                if len(text) > 6000:
                    text = text[:6000] + ' ... (truncated)'
                recorder.append({"tool": _name, "input": kwargs, "output_preview": text[:600],
                                 "duration_ms": int((time.perf_counter() - start) * 1000)})
                return text

            tool = StructuredTool.from_function(func=guard.wrap(name, run), name=name,
                                                description=description, args_schema=schema)
            tool.handle_tool_error = True
            tool.handle_validation_error = True
            tools.append(tool)
        return tools

    # ------------------------------------------------------------------ public
    def ask(self, message: str, history: list[dict] | None = None) -> dict:
        s = self.settings
        if not s.llm_configured:
            raise LLMNotConfigured("The AI agent has no API key. Set LLM_API_KEY (and LLM_BASE_URL, "
                                   "LLM_MODEL) in the .env file and restart the backend.")
        from langchain_classic.agents import AgentType, initialize_agent
        from app.agent.output_parser import RobustStructuredChatOutputParser

        recorder: list[dict] = []
        guard = LoopGuard()
        tools = self.build_tools(recorder, guard)
        prefix = AGENT_RULES.format(namespace=s.k8s_namespace, cpu=s.cpu_threshold_cores,
                                    mem=s.memory_threshold_mib) + "\nYou have access to the following tools:"
        started = time.perf_counter()
        try:
            agent = initialize_agent(
                tools=tools, llm=self._llm(),
                agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                agent_kwargs={"prefix": prefix, "output_parser": RobustStructuredChatOutputParser()},
                verbose=False, max_iterations=s.llm_max_iterations, handle_parsing_errors=True,
            )
            question = message
            if history:
                convo = "\n".join(f"{h['role']}: {h['content']}" for h in history[-6:])
                question = f"Conversation so far:\n{convo}\n\nNew question: {message}"
            result = agent.invoke({"input": question})
        except Exception as e:
            log.warning("agent failed: %s", type(e).__name__)
            raise LLMError(self._explain(e), {"type": type(e).__name__,
                                              "tools_used_before_error": [r["tool"] for r in recorder]}) from e

        answer = str(result.get("output", "")).strip()
        try:  # Lab 3 clean_final_answer(): unwrap a JSON final-answer blob
            data = json.loads(re.sub(r"^```(json)?|```$", "", answer).strip())
            if isinstance(data, dict) and data.get("action") == "Final Answer":
                answer = str(data.get("action_input", answer))
        except (ValueError, TypeError):
            pass
        from app.services.platform import now_iso
        return {"answer": answer, "tools_used": recorder, "model": s.effective_llm_model,
                "duration_ms": int((time.perf_counter() - started) * 1000), "generated_at": now_iso()}

    def _explain(self, e: Exception) -> str:
        name = type(e).__name__
        hints = {
            "AuthenticationError": "The LLM provider rejected the API key (check LLM_API_KEY).",
            "PermissionDeniedError": "The LLM provider denied access for this key/model.",
            "NotFoundError": "The model or base URL was not found (check LLM_MODEL and LLM_BASE_URL).",
            "RateLimitError": "The LLM provider rate limit or quota was reached. Try again later.",
            "APITimeoutError": "The LLM provider did not answer in time.",
            "APIConnectionError": "Cannot connect to the LLM provider (network/proxy/base URL).",
            "BadRequestError": "The LLM provider rejected the request.",
        }
        msg = hints.get(name, f"The AI agent failed ({name}).")
        return _sanitize(f"{msg} {str(e)[:200]}", self.settings.effective_llm_api_key)
