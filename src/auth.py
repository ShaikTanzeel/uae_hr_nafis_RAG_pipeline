"""
auth.py — password hashing (PHASE 3, Section D) and demo-account protection
(PHASE 3, Section C4).

Argon2 turns a password into a one-way scrambled string (a "hash") — you can
check a password against a hash, but you can't reverse a hash back into the
original password. This is why a stolen database alone doesn't hand over
anyone's real password.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from src.models.user import User

# Uses argon2-cffi's own tuned default cost parameters (memory/time cost) —
# deliberately expensive to compute, which is what makes brute-forcing a
# stolen hash slow even with specialized hardware.
_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password for storage. Never store plain_password itself."""
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plain-text password against a stored hash. Never raises on a wrong password."""
    try:
        return _hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False


class DemoAccountProtectedError(Exception):
    """Raised when code tries to delete or change the password of a seeded
    demo account. Per §4, this protection applies regardless of DEMO_MODE's
    value — DEMO_MODE only controls whether the login page displays the demo
    credentials, not whether the accounts themselves are protected."""
    pass


def assert_not_demo_account(user: User) -> None:
    """Call this before deleting a user or changing their password. Raising
    (rather than returning a bool) means a caller can't accidentally skip the
    check by forgetting to look at a return value."""
    if user.is_demo_account:
        raise DemoAccountProtectedError(
            f"'{user.email}' is a protected demo account — it cannot be deleted "
            "or have its password changed."
        )
