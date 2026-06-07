"""Registry de prompts — apps injetam implementações por produto."""
from collections.abc import Callable

PromptFn = Callable[[str], str]

_builders: dict[str, PromptFn] = {}


def _register(name: str, fn: PromptFn) -> None:
    _builders[name] = fn


def register_salon_prompts() -> None:
    from apps.salon import prompts as salon

    _register("guardrails", salon.build_guardrails)
    _register("receptionist", salon.build_receptionist_prompt)
    _register("support", salon.build_support_prompt)
    _register("scheduling", salon.build_scheduling_prompt)
    _register("lakehouse", salon.build_lakehouse_prompt)


def build_guardrails(salon_name: str) -> str:
    return _builders["guardrails"](salon_name)


def build_receptionist_prompt(salon_name: str) -> str:
    return _builders["receptionist"](salon_name)


def build_support_prompt(salon_name: str) -> str:
    return _builders["support"](salon_name)


def build_scheduling_prompt(salon_name: str) -> str:
    return _builders["scheduling"](salon_name)


def build_lakehouse_prompt(salon_name: str) -> str:
    return _builders["lakehouse"](salon_name)
