"""The `records` layer's one anticipated failure.

The rule: `RecordError` is the one anticipated failure of reading a repository record — a record
that is absent or cannot be read as the harness writes it — and its message is one line naming
the file and the cause. An `OSError` other than a missing file is not wrapped: it propagates
unchanged. Which exit status a `RecordError` becomes is the caller's.
"""


class RecordError(Exception):
    """A repository record is absent or cannot be read as the harness writes it."""
