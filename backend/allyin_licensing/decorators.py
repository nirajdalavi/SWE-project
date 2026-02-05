from functools import wraps
import sys
from .exceptions import LicenseValidationError


def require_license(product_id, trial_days=30, user_id=None, message=None):
    """
    Decorator to enforce license check before executing a function.
    If license is invalid or trial expired, prints a message and exits.
    Args:
        product_id (str): Product identifier
        trial_days (int): Trial period in days
        user_id (str, optional): Unique user identifier (for per-user trials)
        message (str, optional): Custom message to show on block
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **fkwargs):
            from . import check_product_license  # Import here to avoid circular import
            status = check_product_license(product_id, trial_days, user_id=user_id)
            if not status.get("has_access", False):
                msg = message or (
                    f"Your trial for '{product_id}' has expired or your license is invalid. "
                    "Please contact support or purchase a license."
                )
                print(msg)
                sys.exit(1)
            return func(*args, **fkwargs)
        return wrapper
    return decorator 