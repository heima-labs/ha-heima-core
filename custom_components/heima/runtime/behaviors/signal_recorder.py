"""Backward-compatible alias for the canonical event behavior."""

from .event_canonicalizer import EventCanonicalizer as SignalRecorderBehavior

__all__ = ["SignalRecorderBehavior"]
