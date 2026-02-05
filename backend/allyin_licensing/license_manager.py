import os
import json
import hashlib
import hmac
import base64
import time
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import bcrypt
import platform
import uuid
import threading
import cryptography.hazmat.primitives.asymmetric.rsa as rsa_mod
import typing

class LicenseManager:
    def __init__(self, product_id="AllyIn", trial_days=30.0, user_id=None, rsa_private_key_path=None, rsa_public_key_path="public_key.pem", license_file=None,secret_key=None):
        """
        Args:
            product_id (str): Product identifier
            trial_days (float): Trial period in days (can be fractional for minutes/hours)
            user_id (str, optional): Unique user identifier (for per-user trials)
            rsa_private_key_path (str, optional): Path to RSA private key
            rsa_public_key_path (str, optional): Path to RSA public key
            license_file (str, optional): Custom path for license file
        """
        self.product_id = product_id
        self.trial_days = float(trial_days)
        self.user_id = user_id
        self.secret_key = secret_key or self._generate_secret_key()
        self.data_dir = self._get_data_directory()
        self.trials_file = os.path.join(self.data_dir, "trials.json")
        self._trials_lock = threading.Lock()
        
        # Use custom license file path if provided, otherwise use default
        if license_file:
            self.license_file = license_file
            # Ensure the directory for the custom license file exists
            license_dir = os.path.dirname(license_file)
            if license_dir:
                os.makedirs(license_dir, exist_ok=True)
        else:
            self.license_file = os.path.join(self.data_dir, "license.dat")
        
        self.installation_file = os.path.join(self.data_dir, "installation.dat")
        self.machine_id = self._get_machine_id()
        self.rsa_private_key = None
        self.rsa_public_key = None
        
        # Load RSA keys if available
        if rsa_private_key_path and os.path.exists(rsa_private_key_path):
            with open(rsa_private_key_path, "rb") as f:
                self.rsa_private_key = serialization.load_pem_private_key(f.read(), password=None)
        if rsa_public_key_path and os.path.exists(rsa_public_key_path):
            with open(rsa_public_key_path, "rb") as f:
                self.rsa_public_key = serialization.load_pem_public_key(f.read())
        
        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
        
    def _generate_secret_key(self):
        """Generate a secret key for HMAC signing"""
        return Fernet.generate_key()
    
    def _get_data_directory(self):
        """Get the appropriate data directory for the current OS"""
        system = platform.system()
        if system == "Windows":
            appdata = os.getenv('APPDATA')
            if not appdata:
                appdata = os.path.expanduser('~')
            return os.path.join(appdata, 'AllyIn', 'Licensing')
        elif system == "Darwin":  # macOS
            return os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'AllyIn', 'Licensing')
        else:  # Linux
            return os.path.join(os.path.expanduser('~'), '.allyin', 'licensing')
    
    def _get_machine_id(self):
        """Generate a unique machine identifier"""
        system_info = [
            platform.machine(),
            platform.processor(),
            platform.node(),
            str(uuid.getnode())  # MAC address
        ]
        return hashlib.sha256(''.join(system_info).encode()).hexdigest()[:16]
    
    def _encrypt_data(self, data):
        """Encrypt data using Fernet"""
        f = Fernet(self.secret_key)
        return f.encrypt(json.dumps(data).encode())
    
    def _decrypt_data(self, encrypted_data):
        """Decrypt data using Fernet"""
        try:
            f = Fernet(self.secret_key)
            decrypted = f.decrypt(encrypted_data)
            return json.loads(decrypted.decode())
        except Exception:
            return None
    
    def _save_encrypted_data(self, data, filename):
        """Save encrypted data to file"""
        encrypted = self._encrypt_data(data)
        with open(filename, 'wb') as f:
            f.write(encrypted)
    
    def _load_encrypted_data(self, filename):
        """Load and decrypt data from file"""
        if not os.path.exists(filename):
            return None
        try:
            with open(filename, 'rb') as f:
                encrypted = f.read()
            return self._decrypt_data(encrypted)
        except Exception:
            return None

    def _load_trials(self):
        if not os.path.exists(self.trials_file):
            return {}
        try:
            with open(self.trials_file, 'rb') as f:
                encrypted = f.read()
            return self._decrypt_data(encrypted) or {}
        except Exception:
            return {}

    def _save_trials(self, trials):
        encrypted = self._encrypt_data(trials)
        with open(self.trials_file, 'wb') as f:
            f.write(encrypted)

    def _get_user_trial_info(self, user_id):
        trials = self._load_trials()
        return trials.get(user_id)

    def _set_user_trial_info(self, user_id, info):
        with self._trials_lock:
            trials = self._load_trials()
            if user_id in trials:
                # Safeguard: never overwrite first_install_date if it exists
                existing = trials[user_id]
                if 'first_install_date' in existing:
                    info['first_install_date'] = existing['first_install_date']
                    print(f"[DEBUG] Not overwriting first_install_date for user_id={user_id}, product_id={self.product_id}: {existing['first_install_date']}")
            trials[user_id] = info
            self._save_trials(trials)
    
    def generate_license_key(self, customer_id, days, license_type="trial", sigtype="hmac"):
        """Generate a secure license key (HMAC or RSA)"""
        date_fmt = "%Y%m%dT%H%M%S"
        start_date = datetime.now().strftime(date_fmt)
        end_date = (datetime.now() + timedelta(days=days)).strftime(date_fmt)
        license_data = {
            "product_id": self.product_id,
            "customer_id": customer_id,
            "machine_id": self.machine_id,
            "license_type": license_type,
            "start_date": start_date,
            "end_date": end_date,
            "days": days,
            "created_at": datetime.now().strftime(date_fmt),
            "sigtype": sigtype
        }
        data_string = f"{self.product_id}|{customer_id}|{self.machine_id}|{start_date}|{end_date}|{days}|{license_type}|{sigtype}"
        if sigtype == "rsa":
            if not self.rsa_private_key:
                raise ValueError("RSA private key not loaded for signing.")
            if not isinstance(self.rsa_private_key, rsa_mod.RSAPrivateKey):
                raise TypeError("Loaded private key is not an RSA private key.")
            signature = base64.urlsafe_b64encode(
                self.rsa_private_key.sign(
                    data_string.encode(),
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
            ).decode()
        else:
            signature = hmac.new(
                self.secret_key,
                data_string.encode(),
                hashlib.sha256
            ).hexdigest()
        combined_data = f"{data_string}|{signature}"
        license_key = base64.urlsafe_b64encode(combined_data.encode()).decode()
        return license_key, license_data

    def validate_license_key(self, license_key):
        """Validate a license key (HMAC or RSA)"""
        try:
            decoded = base64.urlsafe_b64decode(license_key.encode()).decode()
            parts = decoded.split('|')
            if len(parts) != 9:  # 8 data parts + 1 signature
                return False, "Invalid license key format"
            product_id, customer_id, machine_id, start_date, end_date, days, license_type, sigtype, signature = parts
            data_string = f"{product_id}|{customer_id}|{machine_id}|{start_date}|{end_date}|{days}|{license_type}|{sigtype}"
            if product_id != self.product_id:
                return False, "Invalid product ID"
            if machine_id != self.machine_id:
                return False, "License key not valid for this machine"
            if sigtype == "rsa":
                if not self.rsa_public_key:
                    return False, "RSA public key not loaded for verification."
                if not isinstance(self.rsa_public_key, rsa_mod.RSAPublicKey):
                    return False, "Loaded public key is not an RSA public key."
                try:
                    self.rsa_public_key.verify(
                        base64.urlsafe_b64decode(signature.encode()),
                        data_string.encode(),
                        padding.PSS(
                            mgf=padding.MGF1(hashes.SHA256()),
                            salt_length=padding.PSS.MAX_LENGTH
                        ),
                        hashes.SHA256()
                    )
                except Exception as e:
                    return False, f"Invalid RSA signature: {str(e)}"
            else:
                expected_signature = hmac.new(
                    self.secret_key,
                    data_string.encode(),
                    hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(signature, expected_signature):
                    return False, "Invalid HMAC signature"
            date_fmt = "%Y%m%dT%H%M%S"
            end_datetime = datetime.strptime(end_date, date_fmt)
            if datetime.now() > end_datetime:
                return False, "License key has expired"
            license_data = {
                "product_id": product_id,
                "customer_id": customer_id,
                "machine_id": machine_id,
                "license_type": license_type,
                "start_date": start_date,
                "end_date": end_date,
                "days": int(days),
                "sigtype": sigtype,
                "validated_at": datetime.now().strftime(date_fmt)
            }
            return True, license_data
        except Exception as e:
            return False, f"License validation error: {str(e)}"
    
    def install_license(self, license_key):
        """Install a license key"""
        is_valid, result = self.validate_license_key(license_key)
        
        if not is_valid:
            return False, result
        
        # Save the license
        self._save_encrypted_data(result, self.license_file)
        
        # If this is the first installation, save installation date
        if not os.path.exists(self.installation_file):
            installation_data = {
                "first_install_date": datetime.now().isoformat(),
                "machine_id": self.machine_id,
                "product_id": self.product_id
            }
            self._save_encrypted_data(installation_data, self.installation_file)
        
        return True, "License installed successfully"
    
    def get_current_license(self):
        """Get the currently installed license"""
        return self._load_encrypted_data(self.license_file)
    
    def get_installation_info(self, user_id=None):
        if user_id or self.user_id:
            user_id = user_id or self.user_id
            return self._get_user_trial_info(user_id)
        else:
            return self._load_encrypted_data(self.installation_file)
    
    def is_license_valid(self):
        """Check if the current license is valid"""
        license_data = self.get_current_license()

        if not license_data:
            return False, "No license found"
        if not isinstance(license_data, dict):
            print(f"[DEBUG] license_data is not a dict: type={type(license_data)}, value={license_data}")
            return False, "License data is not a valid dictionary"
        license_dict = typing.cast(dict[str, typing.Any], license_data)
        # Check if license has expired
        end_date = datetime.fromisoformat(license_dict['end_date'])
        if datetime.now() > end_date:
            return False, "License has expired"
        return True, license_dict
    
    def get_days_remaining(self):
        """Get the number of days remaining in the license"""
        is_valid, result = self.is_license_valid()
        
        if not is_valid:
            return 0
        
        end_date = datetime.fromisoformat(result['end_date'])
        remaining = (end_date - datetime.now()).days
        return max(0, remaining)
    
    def revoke_license(self):
        """Revoke the current license"""
        if os.path.exists(self.license_file):
            os.remove(self.license_file)
        return True, "License revoked"
    
    def get_trial_status(self, user_id=None):
        user_id = user_id or self.user_id
        if user_id:
            trial_info = self._get_user_trial_info(user_id)
            if not trial_info:
                print(f"[DEBUG] Creating new trial for user_id={user_id}, product_id={self.product_id}")
                trial_info = {
                    "first_install_date": datetime.now().isoformat(),
                    "user_id": user_id,
                    "product_id": self.product_id
                }
                self._set_user_trial_info(user_id, trial_info)
            else:
                print(f"[DEBUG] Loaded existing trial for user_id={user_id}, product_id={self.product_id}: {trial_info}")
            # Always use the original first_install_date
            first_install = datetime.fromisoformat(trial_info['first_install_date'])
            elapsed = datetime.now() - first_install
            elapsed_days = elapsed.total_seconds() / 86400  # 86400 seconds in a day
            days_remaining = max(0, self.trial_days - elapsed_days)
            result = {
                "first_install_date": trial_info['first_install_date'],
                "days_elapsed": elapsed_days,
                "trial_days": self.trial_days,
                "days_remaining": days_remaining,
                "is_trial_expired": elapsed_days >= self.trial_days
            }
            print(f"[DEBUG] get_trial_status result for user_id={user_id}, product_id={self.product_id}: {result}")
            return result
        else:
            # Fallback to machine-based
            installation_info = self.get_installation_info()
            if not installation_info:
                print(f"[DEBUG] No installation found for machine-based trial.")
                return None, "No installation found"
            first_install = datetime.fromisoformat(installation_info['first_install_date'])
            elapsed = datetime.now() - first_install
            elapsed_days = elapsed.total_seconds() / 86400
            days_remaining = max(0, self.trial_days - elapsed_days)
            result = {
                "first_install_date": installation_info['first_install_date'],
                "days_elapsed": elapsed_days,
                "trial_days": self.trial_days,
                "days_remaining": days_remaining,
                "is_trial_expired": elapsed_days >= self.trial_days
            }
            print(f"[DEBUG] get_trial_status result for machine-based trial: {result}")
            return result 