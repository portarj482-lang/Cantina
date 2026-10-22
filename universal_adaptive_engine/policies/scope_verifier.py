"""Deterministic scope verification boundary for Cantina workspaces."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ScopeVerification:
    verified: bool
    computed_sha256: str
    expected_sha256: str
    reason: str


def verify_scope_file(
    scope_path: Path,
    trusted_sha256: str,
) -> ScopeVerification:
    """Verify exact scope-file bytes against a trusted SHA-256 digest.

    The expected digest must come from a separately trusted source.
    This function does not independently establish bounty authorization.
    """
    expected = trusted_sha256.strip().lower()

    if len(expected) != 64 or any(
        char not in "0123456789abcdef" for char in expected
    ):
        return ScopeVerification(
            False, "", expected, "Invalid trusted SHA-256 digest."
        )

    try:
        # Resolve once and read bytes; downstream processing must use
        # the verified content, not reopen an untrusted replacement.
        resolved_path = scope_path.resolve(strict=True)
        if not resolved_path.is_file():
            raise OSError("Scope path is not a regular file.")

        content = resolved_path.read_bytes()
    except OSError:
        return ScopeVerification(
            False, "", expected, "Scope file is missing or unreadable."
        )

    computed = hashlib.sha256(content).hexdigest()
    verified = hmac.compare_digest(computed, expected)

    return ScopeVerification(
        verified=verified,
        computed_sha256=computed,
        expected_sha256=expected,
        reason=(
            "Digest matched."
            if verified
            else "Scope digest does not match the trusted snapshot."
        ),
    )
