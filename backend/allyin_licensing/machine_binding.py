"""
Enhanced Machine Binding for AllyIn Licensing Library

This module provides improved hardware fingerprinting and machine binding
to prevent license sharing across different machines.
"""

import platform
import hashlib
import uuid
import os
import subprocess
import socket
from typing import Dict, Any, Optional
from .exceptions import MachineBindingError

def get_machine_fingerprint() -> str:
    """
    Get a unique machine fingerprint based on hardware and system characteristics.
    
    Returns:
        str: Unique machine fingerprint (SHA-256 hash)
        
    Raises:
        MachineBindingError: If fingerprinting fails
    """
    try:
        # Collect system information
        system_info = []
        
        # Basic system info
        system_info.extend([
            platform.system(),           # OS name
            platform.machine(),          # Machine type
            platform.processor(),        # CPU info
            platform.node(),             # Hostname
            platform.architecture()[0],  # Architecture
            platform.release(),          # OS release
            platform.version()           # OS version
        ])
        
        # Get MAC addresses
        mac_addresses = get_mac_addresses()
        system_info.extend(mac_addresses)
        
        # Get CPU information
        cpu_info = get_cpu_info()
        system_info.extend(cpu_info)
        
        # Get memory information
        memory_info = get_memory_info()
        system_info.extend(memory_info)
        
        # Get disk information
        disk_info = get_disk_info()
        system_info.extend(disk_info)
        
        # Get network information
        network_info = get_network_info()
        system_info.extend(network_info)
        
        # Create fingerprint
        fingerprint_data = '|'.join(filter(None, system_info))
        fingerprint = hashlib.sha256(fingerprint_data.encode('utf-8')).hexdigest()
        
        return fingerprint
        
    except Exception as e:
        raise MachineBindingError(f"Failed to generate machine fingerprint: {e}")

def get_mac_addresses() -> list:
    """Get MAC addresses of network interfaces"""
    mac_addresses = []
    
    try:
        # Get all network interfaces
        if platform.system() == "Windows":
            # Windows method
            try:
                result = subprocess.run(['ipconfig', '/all'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if 'Physical Address' in line or 'MAC Address' in line:
                            mac = line.split(':')[-1].strip()
                            if mac and len(mac) == 17:  # Valid MAC format
                                mac_addresses.append(mac)
            except:
                pass
        else:
            # Unix/Linux method
            try:
                result = subprocess.run(['ifconfig'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if 'ether' in line:
                            parts = line.split()
                            for part in parts:
                                if len(part) == 17 and ':' in part:  # MAC format
                                    mac_addresses.append(part)
            except:
                pass
    except:
        pass
    
    # Fallback: get hostname-based MAC
    try:
        hostname = socket.gethostname()
        mac_addresses.append(str(uuid.uuid5(uuid.NAMESPACE_DNS, hostname)))
    except:
        pass
    
    return mac_addresses

def get_cpu_info() -> list:
    """Get CPU information"""
    cpu_info = []
    
    try:
        # CPU count
        cpu_info.append(str(os.cpu_count()))
        
        # Try to get more detailed CPU info
        if platform.system() == "Windows":
            try:
                result = subprocess.run(['wmic', 'cpu', 'get', 'name'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')[1:]  # Skip header
                    for line in lines:
                        if line.strip():
                            cpu_info.append(line.strip())
            except:
                pass
        else:
            try:
                # Try to read /proc/cpuinfo on Linux
                if os.path.exists('/proc/cpuinfo'):
                    with open('/proc/cpuinfo', 'r') as f:
                        for line in f:
                            if line.startswith('model name'):
                                cpu_info.append(line.split(':')[1].strip())
                                break
            except:
                pass
    except:
        pass
    
    return cpu_info

def get_memory_info() -> list:
    """Get memory information"""
    memory_info = []
    
    try:
        # Try to use psutil if available
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_info.extend([
                str(memory.total),
                str(memory.available),
                str(memory.used)
            ])
        except ImportError:
            # Fallback methods
            if platform.system() == "Windows":
                try:
                    result = subprocess.run(['wmic', 'computersystem', 'get', 'TotalPhysicalMemory'], capture_output=True, text=True)
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')[1:]
                        for line in lines:
                            if line.strip().isdigit():
                                memory_info.append(line.strip())
                                break
                except:
                    pass
            else:
                try:
                    # Try to read /proc/meminfo on Linux
                    if os.path.exists('/proc/meminfo'):
                        with open('/proc/meminfo', 'r') as f:
                            for line in f:
                                if line.startswith('MemTotal:'):
                                    memory_info.append(line.split()[1])
                                    break
                except:
                    pass
    except:
        pass
    
    return memory_info

def get_disk_info() -> list:
    """Get disk information"""
    disk_info = []
    
    try:
        # Try to use psutil if available
        try:
            import psutil
            partitions = psutil.disk_partitions()
            for partition in partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_info.extend([
                        partition.device,
                        str(usage.total),
                        str(usage.free)
                    ])
                except:
                    pass
        except ImportError:
            # Fallback: use basic disk info
            if platform.system() == "Windows":
                try:
                    result = subprocess.run(['wmic', 'logicaldisk', 'get', 'size'], capture_output=True, text=True)
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')[1:]
                        for line in lines:
                            if line.strip().isdigit():
                                disk_info.append(line.strip())
                except:
                    pass
    except:
        pass
    
    return disk_info

def get_network_info() -> list:
    """Get network information"""
    network_info = []
    
    try:
        # Hostname
        network_info.append(socket.gethostname())
        
        # IP addresses
        try:
            hostname = socket.gethostname()
            ip_addresses = socket.gethostbyname_ex(hostname)[2]
            network_info.extend(ip_addresses)
        except:
            pass
        
        # Network interfaces
        try:
            interfaces = socket.if_nameindex()
            for interface in interfaces:
                network_info.append(interface[1])
        except:
            pass
    except:
        pass
    
    return network_info

def validate_machine_binding(license_data: Dict[str, Any], current_fingerprint: str) -> bool:
    """
    Validate that license is bound to the current machine.
    
    Args:
        license_data: License data containing machine fingerprint
        current_fingerprint: Current machine fingerprint
        
    Returns:
        bool: True if machine binding is valid
        
    Raises:
        MachineBindingError: If validation fails
    """
    try:
        # Check if license has machine binding
        if 'machine_fingerprint' not in license_data:
            # No machine binding - allow
            return True
        
        license_fingerprint = license_data['machine_fingerprint']
        
        # Compare fingerprints
        if license_fingerprint == current_fingerprint:
            return True
        
        # Allow some tolerance for minor system changes
        # (e.g., memory upgrades, software updates)
        tolerance_score = calculate_fingerprint_similarity(
            license_fingerprint, 
            current_fingerprint
        )
        
        # Allow if similarity is above threshold (80%)
        return tolerance_score >= 0.8
        
    except Exception as e:
        raise MachineBindingError(f"Machine binding validation failed: {e}")

def calculate_fingerprint_similarity(fp1: str, fp2: str) -> float:
    """
    Calculate similarity between two fingerprints.
    
    Args:
        fp1: First fingerprint
        fp2: Second fingerprint
        
    Returns:
        float: Similarity score (0.0 to 1.0)
    """
    try:
        if len(fp1) != len(fp2):
            return 0.0
        
        # Compare character by character
        matches = sum(1 for a, b in zip(fp1, fp2) if a == b)
        similarity = matches / len(fp1)
        
        return similarity
        
    except Exception:
        return 0.0

def create_machine_bound_license_data(license_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add machine binding to license data.
    
    Args:
        license_data: Original license data
        
    Returns:
        Dict: License data with machine binding
    """
    try:
        # Get current machine fingerprint
        fingerprint = get_machine_fingerprint()
        
        # Add to license data
        bound_data = license_data.copy()
        bound_data['machine_fingerprint'] = fingerprint
        bound_data['binding_timestamp'] = str(int(time.time()))
        
        return bound_data
        
    except Exception as e:
        raise MachineBindingError(f"Failed to create machine-bound license: {e}")

# Import time for timestamp
import time 