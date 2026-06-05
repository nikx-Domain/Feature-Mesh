import hashlib


def get_rollout_bucket(flag_key: str, context_key: str) -> int:
    """
    Computes a deterministic bucket between 0 and 99999 for percentage rollouts.
    We use SHA-256 and modulo to provide 0.001% granularity.
    
    The hash is seeded by both the flag_key and context_key to ensure that
    a user falls into different buckets for different flags (preventing all 
    features from being rolled out to the exact same cohort of 10% users).
    """
    hash_key = f"{flag_key}.{context_key}".encode()
    hash_hex = hashlib.sha256(hash_key).hexdigest()

    # Take the first 8 characters (32-bits) of the hex digest
    hash_int = int(hash_hex[:8], 16)

    # We want a percentage between 0 and 100,000 (representing 0.000% to 99.999%)
    # This allows up to 3 decimal places of precision.
    return hash_int % 100000
