"""Minimal agent interfaces used by the experiment harness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RepoState:
    root: str
    failing_test: str


@dataclass(frozen=True)
class Patch:
    diff: str


class Agent(Protocol):
    def propose_patch(self, repo_state: RepoState, failing_test: str) -> Patch:
        """Return a candidate patch for the current failing test."""
