"""
Two-Factor Authentication (2FA) utilities using TOTP.
Provides setup, verification, and recovery code management.
"""
import os
import base64
import secrets
import pyotp
import qrcode
from io import BytesIO
from typing import Optional, List, Tuple


def generate_totp_secret() -> str:
    """Generate a new TOTP secret key."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str, issuer: str = "MedInvest") -> str:
    """Generate the provisioning URI for authenticator apps."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def generate_qr_code(secret: str, email: str) -> str:
    """Generate a QR code image as base64 string."""
    uri = get_totp_uri(secret, email)
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return base64.b64encode(buffer.getvalue()).decode()


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code against the secret."""
    if not secret or not code:
        return False
    
    code = code.replace(' ', '').replace('-', '')
    
    if not code.isdigit() or len(code) != 6:
        return False
    
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def generate_recovery_codes(count: int = 10) -> List[str]:
    """Generate a list of recovery codes."""
    codes = []
    for _ in range(count):
        code = secrets.token_hex(4).upper()
        formatted = f"{code[:4]}-{code[4:]}"
        codes.append(formatted)
    return codes


def hash_recovery_code(code: str) -> str:
    """Hash a recovery code for storage."""
    import hashlib
    normalized = code.upper().replace('-', '')
    return hashlib.sha256(normalized.encode()).hexdigest()


def verify_recovery_code(provided_code: str, stored_hashes: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Verify a recovery code against stored hashes.
    Returns (is_valid, matched_hash) so the used code can be invalidated.
    """
    provided_hash = hash_recovery_code(provided_code)
    
    for stored_hash in stored_hashes:
        if secrets.compare_digest(provided_hash, stored_hash):
            return True, stored_hash
    
    return False, None


class TwoFactorManager:
    """Manager class for 2FA operations on a user."""
    
    def __init__(self, user):
        self.user = user
    
    def is_enabled(self) -> bool:
        """Check if 2FA is enabled for the user."""
        return bool(getattr(self.user, 'totp_secret', None))
    
    def setup(self) -> Tuple[str, str, List[str]]:
        """
        Initialize 2FA setup for the user.
        Returns (secret, qr_code_base64, recovery_codes)
        """
        secret = generate_totp_secret()
        qr_code = generate_qr_code(secret, self.user.email)
        recovery_codes = generate_recovery_codes()
        
        return secret, qr_code, recovery_codes
    
    def enable(self, secret: str, verification_code: str, recovery_codes: List[str]) -> bool:
        """
        Enable 2FA after verifying the user can generate valid codes.
        """
        if not verify_totp(secret, verification_code):
            return False
        
        self.user.totp_secret = secret
        self.user.recovery_codes = [hash_recovery_code(code) for code in recovery_codes]
        self.user.twofa_enabled = True
        
        return True
    
    def disable(self) -> None:
        """Disable 2FA for the user."""
        self.user.totp_secret = None
        self.user.recovery_codes = []
        self.user.twofa_enabled = False
    
    def verify(self, code: str) -> bool:
        """Verify a TOTP code."""
        if not self.is_enabled():
            return True
        
        return verify_totp(self.user.totp_secret, code)
    
    def use_recovery_code(self, code: str) -> bool:
        """
        Use a recovery code to bypass 2FA.
        The code is invalidated after use.
        """
        stored_hashes = getattr(self.user, 'recovery_codes', []) or []
        
        is_valid, matched_hash = verify_recovery_code(code, stored_hashes)
        
        if is_valid and matched_hash:
            self.user.recovery_codes = [h for h in stored_hashes if h != matched_hash]
            return True
        
        return False
    
    def regenerate_recovery_codes(self) -> List[str]:
        """Generate new recovery codes, invalidating old ones."""
        new_codes = generate_recovery_codes()
        self.user.recovery_codes = [hash_recovery_code(code) for code in new_codes]
        return new_codes
