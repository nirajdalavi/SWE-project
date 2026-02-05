"""
AllyIn Licensing Library
A comprehensive licensing system for AI-based products

This library provides easy-to-use licensing functionality with configurable
trial periods, license tiers, and cryptographic security.
"""

from .license_manager import LicenseManager
from .rsa_keygen import generate_rsa_keypair
from .exceptions import (
    LicenseError,
    InvalidProductError,
    InvalidTrialPeriodError,
    InvalidCustomerError,
    LicenseFileError,
    LicenseValidationError,
    LicenseExpiredError,
    MachineBindingError,
    CryptographicError,
    ConfigurationError
)
from .validation import (
    validate_product_id,
    validate_trial_period,
    validate_customer_id,
    validate_license_duration,
    validate_license_type,
    validate_signature_type,
    validate_file_path
)
from .machine_binding import (
    get_machine_fingerprint,
    validate_machine_binding,
    create_machine_bound_license_data,
    calculate_fingerprint_similarity
)
from .decorators import require_license

# Main classes for easy import
__all__ = [
    "LicenseManager",
    "generate_rsa_keypair",
    "create_simple_license",
    "require_license",
]

# Version info
__version__ = "1.0.0"
__author__ = "AllyIn"
__email__ = "support@allyin.com"

def create_simple_license(product_id, trial_days=30, user_id=None, license_file=None, **kwargs):
    """
    Create a simple license manager for a single product.
    
    Args:
        product_id (str): Unique identifier for your product
        trial_days (float): Trial period in days (can be fractional for minutes/hours)
        user_id (str, optional): Unique user identifier (for per-user trials)
        license_file (str, optional): Custom path for license file
        **kwargs: Additional LicenseManager parameters
        
    Returns:
        LicenseManager: Configured license manager instance
        
    Raises:
        InvalidProductError: If product_id is invalid
        InvalidTrialPeriodError: If trial_days is invalid
        LicenseFileError: If license_file path is invalid
        
    Example:
        >>> from allyin_licensing import create_simple_license
        >>> license_mgr = create_simple_license("MyApp", trial_days=0.002, user_id="user@example.com")
        >>> is_valid, result = license_mgr.is_license_valid()
    """
    # Validate inputs
    validated_product_id = validate_product_id(product_id)
    validated_trial_days = validate_trial_period(trial_days)  # Allow float
    validated_license_file = validate_file_path(license_file)
    
    return LicenseManager(
        product_id=validated_product_id, 
        trial_days=validated_trial_days,
        user_id=user_id,
        license_file=validated_license_file,
        **kwargs
    )

# Convenience functions for common operations
def generate_license_key(product_id, customer_id, days, license_type="trial", sigtype="rsa", **kwargs):
    """
    Generate a license key for a product.
    
    Args:
        product_id (str): Product identifier
        customer_id (str): Customer identifier
        days (int): License duration in days
        license_type (str): "trial" or "paid"
        sigtype (str): "hmac" or "rsa"
        **kwargs: Additional LicenseManager parameters
        
    Returns:
        tuple: (license_key, license_data)
        
    Raises:
        InvalidProductError: If product_id is invalid
        InvalidCustomerError: If customer_id is invalid
        InvalidTrialPeriodError: If days is invalid
        ValueError: If license_type or sigtype is invalid
        
    Example:
        >>> from allyin_licensing import generate_license_key
        >>> key, data = generate_license_key("MyApp", "CUSTOMER123", 30)
        >>> print(f"Generated key: {key}")
    """
    # Validate inputs
    validated_product_id = validate_product_id(product_id)
    validated_customer_id = validate_customer_id(customer_id)
    validated_days = validate_license_duration(days)
    validated_license_type = validate_license_type(license_type)
    validated_sigtype = validate_signature_type(sigtype)
    
    lm = LicenseManager(product_id=validated_product_id, **kwargs)
    return lm.generate_license_key(
        customer_id=validated_customer_id,
        days=validated_days,
        license_type=validated_license_type,
        sigtype=validated_sigtype
    )

def validate_license_key(product_id, license_key, **kwargs):
    """
    Validate a license key for a product.
    
    Args:
        product_id (str): Product identifier
        license_key (str): License key to validate
        **kwargs: Additional LicenseManager parameters
        
    Returns:
        tuple: (is_valid, result)
        
    Raises:
        InvalidProductError: If product_id is invalid
        ValueError: If license_key is empty or None
        
    Example:
        >>> from allyin_licensing import validate_license_key
        >>> is_valid, result = validate_license_key("MyApp", "license-key-here")
        >>> if is_valid:
        ...     print("License is valid!")
    """
    # Validate inputs
    validated_product_id = validate_product_id(product_id)
    
    if not license_key:
        raise ValueError("License key cannot be empty or None")
    
    if not isinstance(license_key, str):
        raise ValueError(f"License key must be a string, got {type(license_key)}")
    
    lm = LicenseManager(product_id=validated_product_id, **kwargs)
    return lm.validate_license_key(license_key)

def check_product_license(product_id, trial_days=30, user_id=None, **kwargs):
    """
    Check if a product has a valid license or trial.
    
    Args:
        product_id (str): Product identifier
        trial_days (float): Trial period in days (can be fractional for minutes/hours)
        user_id (str, optional): Unique user identifier (for per-user trials)
        **kwargs: Additional LicenseManager parameters
        
    Returns:
        dict: License status information
        
    Raises:
        InvalidProductError: If product_id is invalid
        InvalidTrialPeriodError: If trial_days is invalid
        
    Example:
        >>> from allyin_licensing import check_product_license
        >>> status = check_product_license("MyApp", trial_days=0.002, user_id="user@example.com")
        >>> if status["has_access"]:
        ...     print("Access granted!")
    """
    # Validate inputs
    validated_product_id = validate_product_id(product_id)
    validated_trial_days = validate_trial_period(trial_days)  # Allow float
    
    lm = LicenseManager(product_id=validated_product_id, trial_days=validated_trial_days, user_id=user_id, **kwargs)
    
    # Check license validity
    is_valid, result = lm.is_license_valid()
    
    # Check trial status
    trial_info = lm.get_trial_status(user_id=user_id)
    trial_expired = None
    if isinstance(trial_info, dict):
        trial_expired = trial_info.get('is_trial_expired', None)
    
    return {
        "has_access": is_valid or (isinstance(trial_info, dict) and not trial_expired),
        "license_valid": is_valid,
        "license_result": result,
        "trial_info": trial_info if isinstance(trial_info, dict) else None,
        "days_remaining": lm.get_days_remaining() if is_valid else None
    } 