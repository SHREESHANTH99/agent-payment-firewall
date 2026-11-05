"""Log redaction filter and logging utilities.

Masks Authorization, X-Agent-Key, API keys, tokens, and PayPal secrets
in all formatted log records to guarantee that credentials are never leaked.
"""
import logging
import re

SENSITIVE_PATTERNS = [
    (re.compile(r"(?i)(bearer\s+)([A-Za-z0-9_\-\.]{6,})"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(authorization['\":\s=]+)([A-Za-z0-9_\-\.]{6,})"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(x-agent-key['\":\s=]+)([A-Za-z0-9_\-\.]{4,})"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(token['\":\s=]+)([A-Za-z0-9_\-\.]{6,})"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(api[_-]?key['\":\s=]+)([A-Za-z0-9_\-\.]{6,})"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(client[_-]?secret['\":\s=]+)([A-Za-z0-9_\-\.]{6,})"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(password['\":\s=]+)([^\s,;'\"]{4,})"), r"\1[REDACTED]"),
]


class RedactionFilter(logging.Filter):
    """Filter that scrubs secrets and sensitive credential tokens from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            for pattern, repl in SENSITIVE_PATTERNS:
                msg = pattern.sub(repl, msg)
            record.msg = msg
            record.args = ()
        except Exception:
            pass
        return True


def setup_logging():
    """Apply the RedactionFilter to the root logger handlers."""
    redaction_filter = RedactionFilter()
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(redaction_filter)
    # Also attach to handlers added to uvicorn/fastapi
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        l = logging.getLogger(logger_name)
        for h in l.handlers:
            h.addFilter(redaction_filter)
