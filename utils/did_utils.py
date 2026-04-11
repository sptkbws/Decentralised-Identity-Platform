import secrets
import re


DID_PREFIX = "did:decen:"
DID_TOKEN_BYTES = 32     # 64 hex chars → collision-resistant


def generate_did() -> str:
    """
    Generates a W3C-inspired DID string.
    Format:  did:decen:<64-char hex token>
    Example: did:decen:3f8a2b...
    """
    token = secrets.token_hex(DID_TOKEN_BYTES)
    return f"{DID_PREFIX}{token}"


def is_valid_did(did: str) -> bool:
    """
    Validates that a DID string matches our expected format.
    """
    pattern = rf"^{re.escape(DID_PREFIX)}[0-9a-f]{{64}}$"
    return bool(re.match(pattern, did))


def sanitize_did(did: str) -> str:
    """Strip whitespace, lowercase."""
    return did.strip().lower()
