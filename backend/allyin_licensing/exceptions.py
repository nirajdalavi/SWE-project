"""
Custom exceptions for AllyIn Licensing Library

This module provides specific exception types for different licensing scenarios
to enable better error handling and debugging.
"""

class LicenseError(Exception):
    """Base exception for all licensing-related errors"""
    pass

class InvalidProductError(LicenseError):
    """Raised when product ID is invalid or malformed"""
    pass

class InvalidTrialPeriodError(LicenseError):
    """Raised when trial period is invalid"""
    pass

class InvalidCustomerError(LicenseError):
    """Raised when customer ID is invalid"""
    pass

class LicenseFileError(LicenseError):
    """Raised when license file operations fail"""
    pass

class LicenseValidationError(LicenseError):
    """Raised when license validation fails"""
    pass

class LicenseExpiredError(LicenseError):
    """Raised when license has expired"""
    pass

class MachineBindingError(LicenseError):
    """Raised when machine binding fails"""
    pass

class CryptographicError(LicenseError):
    """Raised when cryptographic operations fail"""
    pass

class ConfigurationError(LicenseError):
    """Raised when configuration is invalid"""
    pass

class MultiProductError(LicenseError):
    """Raised when multi-product operations fail"""
    pass

class DuplicateProductError(MultiProductError):
    """Raised when trying to add a duplicate product"""
    pass

class ProductNotFoundError(MultiProductError):
    """Raised when product is not found"""
    pass 