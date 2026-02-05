"""
Input validation for AllyIn Licensing Library

This module provides validation functions for all input parameters
to ensure data integrity and prevent invalid operations.
"""

import os
import re
from typing import Union, Optional
from .exceptions import (
    InvalidProductError, 
    InvalidTrialPeriodError, 
    InvalidCustomerError,
    LicenseFileError,
    ConfigurationError
)

def validate_product_id(product_id: str) -> str:
    """
    Validate product ID format and content.
    
    Args:
        product_id: The product ID to validate
        
    Returns:
        Cleaned product ID string
        
    Raises:
        InvalidProductError: If product ID is invalid
    """
    if not product_id:
        raise InvalidProductError("Product ID cannot be empty or None")
    
    if not isinstance(product_id, str):
        raise InvalidProductError(f"Product ID must be a string, got {type(product_id)}")
    
    # Remove leading/trailing whitespace
    product_id = product_id.strip()
    
    if len(product_id) == 0:
        raise InvalidProductError("Product ID cannot be empty or whitespace only")
    
    if len(product_id) > 255:
        raise InvalidProductError("Product ID cannot exceed 255 characters")
    
    # Check for invalid characters (filesystem unsafe)
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/', '\0']
    for char in invalid_chars:
        if char in product_id:
            raise InvalidProductError(f"Product ID cannot contain '{char}'")
    
    # Check for reserved names (Windows)
    reserved_names = ['CON', 'PRN', 'AUX', 'NUL'] + [f'COM{i}' for i in range(1, 10)] + [f'LPT{i}' for i in range(1, 10)]
    if product_id.upper() in reserved_names:
        raise InvalidProductError(f"Product ID cannot be reserved name: {product_id}")
    
    # More permissive format check - allow more characters but still safe
    if not re.match(r'^[a-zA-Z0-9._\-@#$%^&()\[\]{}]+$', product_id):
        raise InvalidProductError("Product ID contains invalid characters")
    
    return product_id

def validate_trial_period(trial_days: Union[int, float]) -> float:
    """
    Validate trial period value.
    
    Args:
        trial_days: Trial period in days
        
    Returns:
        Validated trial period as float
        
    Raises:
        InvalidTrialPeriodError: If trial period is invalid
    """
    if not isinstance(trial_days, (int, float)):
        raise InvalidTrialPeriodError(f"Trial days must be a number, got {type(trial_days)}")
    
    if trial_days <= 0:
        raise InvalidTrialPeriodError("Trial days must be greater than 0")
    
    if trial_days > 36500:  # 100 years
        raise InvalidTrialPeriodError("Trial days cannot exceed 100 years (36,500 days)")
    
    return float(trial_days)

def validate_customer_id(customer_id: str) -> str:
    """
    Validate customer ID format and content.
    
    Args:
        customer_id: The customer ID to validate
        
    Returns:
        Cleaned customer ID string
        
    Raises:
        InvalidCustomerError: If customer ID is invalid
    """
    if not customer_id:
        raise InvalidCustomerError("Customer ID cannot be empty or None")
    
    if not isinstance(customer_id, str):
        raise InvalidCustomerError(f"Customer ID must be a string, got {type(customer_id)}")
    
    # Remove leading/trailing whitespace
    customer_id = customer_id.strip()
    
    if len(customer_id) == 0:
        raise InvalidCustomerError("Customer ID cannot be empty or whitespace only")
    
    if len(customer_id) > 255:
        raise InvalidCustomerError("Customer ID cannot exceed 255 characters")
    
    # Check for invalid characters
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/', '\0']
    for char in invalid_chars:
        if char in customer_id:
            raise InvalidCustomerError(f"Customer ID cannot contain '{char}'")
    
    return customer_id

def validate_license_duration(days: Union[int, float]) -> float:
    """
    Validate license duration.
    
    Args:
        days: License duration in days
        
    Returns:
        Validated duration as float
        
    Raises:
        InvalidTrialPeriodError: If duration is invalid
    """
    if not isinstance(days, (int, float)):
        raise InvalidTrialPeriodError(f"License duration must be a number, got {type(days)}")
    
    if days < 0:
        raise InvalidTrialPeriodError("License duration cannot be negative")
    
    if days > 36500:  # 100 years
        raise InvalidTrialPeriodError("License duration cannot exceed 100 years (36,500 days)")
    
    return float(days)

def validate_license_type(license_type: str) -> str:
    """
    Validate license type.
    
    Args:
        license_type: The license type to validate
        
    Returns:
        Validated license type
        
    Raises:
        ValueError: If license type is invalid
    """
    if not license_type:
        raise ValueError("License type cannot be empty")
    
    if not isinstance(license_type, str):
        raise ValueError(f"License type must be a string, got {type(license_type)}")
    
    valid_types = ['trial', 'paid', 'basic', 'pro', 'enterprise']
    if license_type.lower() not in valid_types:
        raise ValueError(f"License type must be one of: {', '.join(valid_types)}")
    
    return license_type.lower()

def validate_signature_type(sigtype: str) -> str:
    """
    Validate signature type.
    
    Args:
        sigtype: The signature type to validate
        
    Returns:
        Validated signature type
        
    Raises:
        ValueError: If signature type is invalid
    """
    if not sigtype:
        raise ValueError("Signature type cannot be empty")
    
    if not isinstance(sigtype, str):
        raise ValueError(f"Signature type must be a string, got {type(sigtype)}")
    
    valid_types = ['hmac', 'rsa']
    if sigtype.lower() not in valid_types:
        raise ValueError(f"Signature type must be one of: {', '.join(valid_types)}")
    
    return sigtype.lower()

def validate_file_path(file_path: Optional[str]) -> Optional[str]:
    """
    Validate file path for license files.
    
    Args:
        file_path: The file path to validate
        
    Returns:
        Validated file path or None
        
    Raises:
        LicenseFileError: If file path is invalid
    """
    if file_path is None:
        return None
    
    if not isinstance(file_path, str):
        raise LicenseFileError(f"File path must be a string, got {type(file_path)}")
    
    if len(file_path.strip()) == 0:
        raise LicenseFileError("File path cannot be empty or whitespace only")
    
    # Check for invalid characters in path
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '\0']
    for char in invalid_chars:
        if char in file_path:
            raise LicenseFileError(f"File path cannot contain '{char}'")
    
    # Check if directory exists and is writable
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
        except (OSError, PermissionError) as e:
            raise LicenseFileError(f"Cannot create directory for license file: {e}")
    
    return file_path

def validate_product_config(config: dict) -> dict:
    """
    Validate product configuration dictionary.
    
    Args:
        config: Product configuration dictionary
        
    Returns:
        Validated configuration dictionary
        
    Raises:
        ConfigurationError: If configuration is invalid
    """
    if config is None:
        raise ConfigurationError("Product config cannot be None")
    
    if not isinstance(config, dict):
        raise ConfigurationError(f"Product config must be a dictionary, got {type(config)}")
    
    if not config:
        raise ConfigurationError("Product config cannot be empty")
    
    # Validate required fields
    required_fields = ['trial_days']
    for field in required_fields:
        if field not in config:
            raise ConfigurationError(f"Product config missing required field: {field}")
    
    # Validate trial_days
    try:
        config['trial_days'] = validate_trial_period(config['trial_days'])
    except InvalidTrialPeriodError as e:
        raise ConfigurationError(f"Invalid trial_days in config: {e}")
    
    # Validate optional fields
    if 'description' in config:
        if not isinstance(config['description'], str):
            raise ConfigurationError("Description must be a string")
        if len(config['description']) > 1000:
            raise ConfigurationError("Description cannot exceed 1000 characters")
    
    if 'features' in config:
        if not isinstance(config['features'], list):
            raise ConfigurationError("Features must be a list")
        for feature in config['features']:
            if not isinstance(feature, str):
                raise ConfigurationError("All features must be strings")
    
    return config 