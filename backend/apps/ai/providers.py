"""Adaptadores recebem somente snapshots já autorizados e não possuem ferramentas de escrita."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Insight:
    provider: str
    paragraphs: list[str]
    uses_language_model: bool = False


class Provider(Protocol):
    def generate(self, *, paragraphs: list[str]) -> Insight: ...


class LocalRulesProvider:
    def generate(self, *, paragraphs: list[str]) -> Insight:
        return Insight(provider="local-rules", paragraphs=paragraphs)


def approved_provider() -> Provider:
    return LocalRulesProvider()
