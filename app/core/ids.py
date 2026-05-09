from uuid import uuid4


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


def has_prefix(value: str, prefix: str) -> bool:
    return value.startswith(f"{prefix}_")
