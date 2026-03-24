"""
VERITY — pytest configuration
Global fixtures and test settings.
"""

import asyncio
from typing import Generator

import pytest


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
