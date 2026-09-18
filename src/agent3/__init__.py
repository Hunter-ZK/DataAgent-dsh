"""Agent3 Data Intelligence Core.

Core is intentionally independent of DeepSeek Harness, MCP, HTTP and UI frameworks.
Adapters depend on Core; Core never depends on adapters.
"""
from agent3.services.core import Agent3Core

__all__ = ["Agent3Core"]
__version__ = "0.1.0"
