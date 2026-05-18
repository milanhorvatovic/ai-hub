"""Audit vs format mode toggle. Carries no behavior, just identity."""

from __future__ import annotations

from enum import Enum


class Mode(str, Enum):
    AUDIT = "audit"
    FORMAT = "format"
