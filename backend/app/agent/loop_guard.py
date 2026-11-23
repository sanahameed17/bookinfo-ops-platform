"""
REUSED FROM LAB 3 (lab3-ops-agent/core/helper/loop_guard.py).

Circuit breaker: blocks an IDENTICAL consecutive tool call (same tool, same input) and tells the
agent to use the result it already has. In Lab 3 the agent once called the same status tool 10
times in a row. Change for this project: no exempt tools (all tools here are quick reads).
"""
import functools
import json


class LoopGuard:
    def __init__(self):
        self.last_call = None
        self.blocked = 0

    def reset(self):
        self.last_call = None

    def wrap(self, tool_name, func):
        @functools.wraps(func)
        def guarded(*args, **kwargs):
            key = (tool_name, json.dumps(kwargs, sort_keys=True, default=str), repr(args))
            if key == self.last_call:
                self.blocked += 1
                return (f"LOOP GUARD: you just called {tool_name} with exactly the same input and "
                        "already have its result above. Do not call it again - use that result "
                        "and give the Final Answer (or choose a different action).")
            self.last_call = key
            return func(*args, **kwargs)
        return guarded
