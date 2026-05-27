"""sqlpulse — N+1 SQL detector. Drop-in, zero config, any SQL library."""
from .detector import sqlpulse, SQLPulseMiddleware
__version__ = "0.1.0"
__all__ = ["sqlpulse", "SQLPulseMiddleware"]
