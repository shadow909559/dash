"""Singleton metaclass and base class for thread-safe singleton services.

Provides:
  - SingletonMeta: A thread-safe metaclass for creating singleton classes.
  - Singleton: A base class using SingletonMeta for convenience.

Usage:
    class MyService(Singleton):
        def __init__(self):
            # Initialize once
            pass

    # Multiple calls return the same instance
    s1 = MyService()
    s2 = MyService()
    assert s1 is s2
"""

from __future__ import annotations

import threading
from typing import Any


class SingletonMeta(type):
    """Thread-safe metaclass for implementing the Singleton pattern.

    Ensures only one instance of a class exists per process.
    Thread-safe using a reentrant lock for nested singleton creation.
    """

    _instances: dict[type, object] = {}
    _lock: threading.RLock = threading.RLock()

    def __call__(cls, *args: Any, **kwargs: Any) -> object:
        """Return the singleton instance, creating it if necessary."""
        if cls not in cls._instances:
            with cls._lock:
                # Double-checked locking pattern
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]

    @classmethod
    def clear_instance(cls, target_cls: type) -> None:
        """Clear the singleton instance for a specific class (for testing)."""
        with cls._lock:
            cls._instances.pop(target_cls, None)

    @classmethod
    def clear_all(cls) -> None:
        """Clear all singleton instances (for testing/cleanup)."""
        with cls._lock:
            cls._instances.clear()


class Singleton(metaclass=SingletonMeta):
    """Base class for singleton services.

    Inherit from this class to make any service a singleton.
    The __init__ method is called only once, on first instantiation.

    Example:
        class DatabasePool(Singleton):
            def __init__(self):
                self._connections = []

        pool1 = DatabasePool()
        pool2 = DatabasePool()
        assert pool1 is pool2  # True
    """

    pass
