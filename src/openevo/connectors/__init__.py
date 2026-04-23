"""Experience adapters: normalize external data into RawExperience."""

from openevo.connectors.base import ExperienceAdapter
from openevo.connectors.chat_adapter import ChatAdapter
from openevo.connectors.code_adapter import CodeAdapter
from openevo.connectors.doc_adapter import DocAdapter
from openevo.connectors.error_adapter import ErrorAdapter
from openevo.connectors.tool_adapter import ToolAdapter

_ADAPTERS: dict[str, ExperienceAdapter] = {
    "code": CodeAdapter(),
    "chat": ChatAdapter(),
    "error": ErrorAdapter(),
    "doc": DocAdapter(),
    "tool": ToolAdapter(),
}


def get_adapter(source_type: str) -> ExperienceAdapter | None:
    return _ADAPTERS.get(source_type)


__all__ = [
    "ChatAdapter",
    "CodeAdapter",
    "DocAdapter",
    "ErrorAdapter",
    "ExperienceAdapter",
    "ToolAdapter",
    "get_adapter",
]
