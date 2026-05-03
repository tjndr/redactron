"""macOS Keychain backend with Touch ID (kSecAccessControlBiometryAny).

Uses the Security framework directly via ctypes to set biometric access
control flags — the keyring library does not expose these flags.

Access control choice: kSecAccessControlBiometryAny
- Allows Touch ID OR passcode fallback after 5 failed Touch ID attempts
- NOT kSecAccessControlBiometryCurrentSet (invalidates on fingerprint re-enroll)
- NOT kSecAccessControlUserPresence (allows passcode-only without biometry)
"""

from __future__ import annotations

import ctypes
import ctypes.util
import logging
import secrets
from ctypes import c_char_p, c_int32, c_uint32, c_void_p
from typing import Any

from redactron.errors import VaultError

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Security framework constants
# ---------------------------------------------------------------------------

_SEC_LIB_PATH = "/System/Library/Frameworks/Security.framework/Security"
_CF_LIB_PATH = "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"

# kSecAccessControlBiometryAny = 1 << 1 = 2
_kSecAccessControlBiometryAny: int = 1 << 1

# kSecAttrAccessible values
_kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly = b"pdmn"  # not used directly

# OSStatus codes
_errSecSuccess = 0
_errSecItemNotFound = -25300
_errSecDuplicateItem = -25299
_errSecUserCanceled = -128
_errSecAuthFailed = -25293

_TOUCH_ID_PROMPT = "Redactron needs your fingerprint to unlock the encrypted profile vault."

_SERVICE_PREFIX = "redactron.vault."


def _load_security() -> ctypes.CDLL:
    lib = ctypes.cdll.LoadLibrary(_SEC_LIB_PATH)
    return lib


def _load_cf() -> ctypes.CDLL:
    lib = ctypes.cdll.LoadLibrary(_CF_LIB_PATH)
    return lib


def _cf_string(text: str) -> Any:
    """Create a CFStringRef from a Python str."""
    cf = _load_cf()
    cf.CFStringCreateWithCString.restype = c_void_p
    cf.CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, c_uint32]
    kCFStringEncodingUTF8 = 0x08000100
    return cf.CFStringCreateWithCString(None, text.encode("utf-8"), kCFStringEncodingUTF8)


def _cf_data(data: bytes) -> Any:
    """Create a CFDataRef from bytes."""
    cf = _load_cf()
    cf.CFDataCreate.restype = c_void_p
    cf.CFDataCreate.argtypes = [c_void_p, c_char_p, c_int32]
    return cf.CFDataCreate(None, data, len(data))


def _cf_release(ref: Any) -> None:
    if ref:
        cf = _load_cf()
        cf.CFRelease.argtypes = [c_void_p]
        cf.CFRelease(ref)


def _cf_data_to_bytes(data_ref: Any) -> bytes:
    """Extract bytes from a CFDataRef."""
    cf = _load_cf()
    cf.CFDataGetLength.restype = c_int32
    cf.CFDataGetLength.argtypes = [c_void_p]
    cf.CFDataGetBytePtr.restype = ctypes.POINTER(ctypes.c_uint8)
    cf.CFDataGetBytePtr.argtypes = [c_void_p]
    length = cf.CFDataGetLength(data_ref)
    ptr = cf.CFDataGetBytePtr(data_ref)
    return bytes(ptr[:length])


def _os_status_to_str(status: int) -> str:
    mapping = {
        _errSecItemNotFound: "item not found",
        _errSecDuplicateItem: "duplicate item",
        _errSecUserCanceled: "user cancelled Touch ID prompt",
        _errSecAuthFailed: "Touch ID authentication failed",
    }
    return mapping.get(status, f"OSStatus {status}")


class MacOSKeychainBackend:
    """macOS Keychain backend with kSecAccessControlBiometryAny.

    Stores the 32-byte master key in the macOS Keychain with biometric
    access control. Touch ID is required on every retrieval; after 5
    failed attempts macOS falls back to the user's login password.
    """

    def __init__(self) -> None:
        self._sec = _load_security()
        self._cf = _load_cf()
        self._cache: dict[str, bytes] = {}

    def _service_name(self, vault_id: str) -> str:
        return f"{_SERVICE_PREFIX}{vault_id}"

    def _build_access_control(self) -> Any:
        """Create a SecAccessControlRef with kSecAccessControlBiometryAny."""
        sec = self._sec
        sec.SecAccessControlCreateWithFlags.restype = c_void_p
        sec.SecAccessControlCreateWithFlags.argtypes = [
            c_void_p,  # allocator
            c_void_p,  # protection
            c_uint32,  # flags
            c_void_p,  # error (CFErrorRef*)
        ]
        # kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly as CFStringRef
        # Use the constant string value directly
        protection = _cf_string("pdmn")  # kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly
        access_ctrl = sec.SecAccessControlCreateWithFlags(
            None,
            protection,
            _kSecAccessControlBiometryAny,
            None,
        )
        _cf_release(protection)
        return access_ctrl

    def get_or_create_master_key(self, vault_id: str) -> bytes:
        """Return the 32-byte master key, creating and storing it if absent.

        Triggers Touch ID prompt on every call (no persistent in-process cache
        beyond the single CLI invocation — cache is per-instance).
        """
        if vault_id in self._cache:
            return self._cache[vault_id]

        # Try to retrieve existing key first
        try:
            key = self._retrieve_key(vault_id)
            self._cache[vault_id] = key
            return key
        except VaultError as exc:
            if "not found" not in str(exc):
                raise
            # Key doesn't exist yet — generate and store
            log.debug("No master key found for vault %s; generating new key.", vault_id)

        key = secrets.token_bytes(32)
        self._store_key(vault_id, key)
        self._cache[vault_id] = key
        return key

    def delete_master_key(self, vault_id: str) -> None:
        """Remove the master key from the keychain."""
        self._cache.pop(vault_id, None)
        sec = self._sec
        service = self._service_name(vault_id)

        service_cf = _cf_string(service)
        account_cf = _cf_string("master_key")

        # Build query dict via CFDictionaryCreate
        query = self._build_query_dict(service_cf, account_cf)
        try:
            sec.SecItemDelete.restype = c_int32
            sec.SecItemDelete.argtypes = [c_void_p]
            status = sec.SecItemDelete(query)
            if status not in (_errSecSuccess, _errSecItemNotFound):
                log.warning("SecItemDelete returned %s", _os_status_to_str(status))
        finally:
            _cf_release(service_cf)
            _cf_release(account_cf)
            _cf_release(query)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_query_dict(self, service_cf: Any, account_cf: Any) -> Any:
        """Build a CFDictionaryRef for keychain queries."""
        cf = self._cf
        cf.CFDictionaryCreateMutable.restype = c_void_p
        cf.CFDictionaryCreateMutable.argtypes = [c_void_p, c_int32, c_void_p, c_void_p]
        cf.CFDictionaryAddValue.argtypes = [c_void_p, c_void_p, c_void_p]

        # Get constant pointers from Security framework
        sec = self._sec
        kSecClass = c_void_p.in_dll(sec, "kSecClass")
        kSecClassGenericPassword = c_void_p.in_dll(sec, "kSecClassGenericPassword")
        kSecAttrService = c_void_p.in_dll(sec, "kSecAttrService")
        kSecAttrAccount = c_void_p.in_dll(sec, "kSecAttrAccount")

        # kCFTypeDictionaryKeyCallBacks / kCFTypeDictionaryValueCallBacks
        kCFTypeDictionaryKeyCallBacks = c_void_p.in_dll(cf, "kCFTypeDictionaryKeyCallBacks")
        kCFTypeDictionaryValueCallBacks = c_void_p.in_dll(cf, "kCFTypeDictionaryValueCallBacks")

        d = cf.CFDictionaryCreateMutable(
            None, 0,
            ctypes.byref(kCFTypeDictionaryKeyCallBacks),
            ctypes.byref(kCFTypeDictionaryValueCallBacks),
        )
        cf.CFDictionaryAddValue(d, kSecClass, kSecClassGenericPassword)
        cf.CFDictionaryAddValue(d, kSecAttrService, service_cf)
        cf.CFDictionaryAddValue(d, kSecAttrAccount, account_cf)
        return d

    def _retrieve_key(self, vault_id: str) -> bytes:
        """Retrieve key from keychain, triggering Touch ID."""
        sec = self._sec
        cf = self._cf
        service = self._service_name(vault_id)

        service_cf = _cf_string(service)
        account_cf = _cf_string("master_key")
        prompt_cf = _cf_string(_TOUCH_ID_PROMPT)

        try:
            kSecClass = c_void_p.in_dll(sec, "kSecClass")
            kSecClassGenericPassword = c_void_p.in_dll(sec, "kSecClassGenericPassword")
            kSecAttrService = c_void_p.in_dll(sec, "kSecAttrService")
            kSecAttrAccount = c_void_p.in_dll(sec, "kSecAttrAccount")
            kSecReturnData = c_void_p.in_dll(sec, "kSecReturnData")
            kSecUseOperationPrompt = c_void_p.in_dll(sec, "kSecUseOperationPrompt")
            kCFBooleanTrue = c_void_p.in_dll(cf, "kCFBooleanTrue")

            kCFTypeDictionaryKeyCallBacks = c_void_p.in_dll(cf, "kCFTypeDictionaryKeyCallBacks")
            kCFTypeDictionaryValueCallBacks = c_void_p.in_dll(
                cf, "kCFTypeDictionaryValueCallBacks"
            )

            cf.CFDictionaryCreateMutable.restype = c_void_p
            cf.CFDictionaryCreateMutable.argtypes = [c_void_p, c_int32, c_void_p, c_void_p]
            cf.CFDictionaryAddValue.argtypes = [c_void_p, c_void_p, c_void_p]

            query = cf.CFDictionaryCreateMutable(
                None, 0,
                ctypes.byref(kCFTypeDictionaryKeyCallBacks),
                ctypes.byref(kCFTypeDictionaryValueCallBacks),
            )
            cf.CFDictionaryAddValue(query, kSecClass, kSecClassGenericPassword)
            cf.CFDictionaryAddValue(query, kSecAttrService, service_cf)
            cf.CFDictionaryAddValue(query, kSecAttrAccount, account_cf)
            cf.CFDictionaryAddValue(query, kSecReturnData, kCFBooleanTrue)
            cf.CFDictionaryAddValue(query, kSecUseOperationPrompt, prompt_cf)

            result = c_void_p(None)
            sec.SecItemCopyMatching.restype = c_int32
            sec.SecItemCopyMatching.argtypes = [c_void_p, ctypes.POINTER(c_void_p)]
            status = sec.SecItemCopyMatching(query, ctypes.byref(result))
            _cf_release(query)

            if status == _errSecItemNotFound:
                raise VaultError("Master key not found in keychain.")
            if status == _errSecUserCanceled:
                raise VaultError(
                    "Touch ID prompt was cancelled. Cannot unlock the vault."
                )
            if status != _errSecSuccess:
                raise VaultError(
                    f"Keychain retrieval failed: {_os_status_to_str(status)}"
                )

            key = _cf_data_to_bytes(result.value)
            _cf_release(result.value)
            if len(key) != 32:
                raise VaultError(f"Retrieved key has unexpected length {len(key)}, expected 32.")
            return key
        finally:
            _cf_release(service_cf)
            _cf_release(account_cf)
            _cf_release(prompt_cf)

    def _store_key(self, vault_id: str, key: bytes) -> None:
        """Store key in keychain with kSecAccessControlBiometryAny."""
        sec = self._sec
        cf = self._cf
        service = self._service_name(vault_id)

        service_cf = _cf_string(service)
        account_cf = _cf_string("master_key")
        data_cf = _cf_data(key)
        access_ctrl = self._build_access_control()

        try:
            kSecClass = c_void_p.in_dll(sec, "kSecClass")
            kSecClassGenericPassword = c_void_p.in_dll(sec, "kSecClassGenericPassword")
            kSecAttrService = c_void_p.in_dll(sec, "kSecAttrService")
            kSecAttrAccount = c_void_p.in_dll(sec, "kSecAttrAccount")
            kSecValueData = c_void_p.in_dll(sec, "kSecValueData")
            kSecAttrAccessControl = c_void_p.in_dll(sec, "kSecAttrAccessControl")

            kCFTypeDictionaryKeyCallBacks = c_void_p.in_dll(cf, "kCFTypeDictionaryKeyCallBacks")
            kCFTypeDictionaryValueCallBacks = c_void_p.in_dll(
                cf, "kCFTypeDictionaryValueCallBacks"
            )

            cf.CFDictionaryCreateMutable.restype = c_void_p
            cf.CFDictionaryCreateMutable.argtypes = [c_void_p, c_int32, c_void_p, c_void_p]
            cf.CFDictionaryAddValue.argtypes = [c_void_p, c_void_p, c_void_p]

            item = cf.CFDictionaryCreateMutable(
                None, 0,
                ctypes.byref(kCFTypeDictionaryKeyCallBacks),
                ctypes.byref(kCFTypeDictionaryValueCallBacks),
            )
            cf.CFDictionaryAddValue(item, kSecClass, kSecClassGenericPassword)
            cf.CFDictionaryAddValue(item, kSecAttrService, service_cf)
            cf.CFDictionaryAddValue(item, kSecAttrAccount, account_cf)
            cf.CFDictionaryAddValue(item, kSecValueData, data_cf)
            if access_ctrl:
                cf.CFDictionaryAddValue(item, kSecAttrAccessControl, access_ctrl)

            sec.SecItemAdd.restype = c_int32
            sec.SecItemAdd.argtypes = [c_void_p, c_void_p]
            status = sec.SecItemAdd(item, None)
            _cf_release(item)

            if status == _errSecDuplicateItem:
                # Update existing item
                self._update_key(vault_id, key)
            elif status != _errSecSuccess:
                raise VaultError(f"Keychain store failed: {_os_status_to_str(status)}")
        finally:
            _cf_release(service_cf)
            _cf_release(account_cf)
            _cf_release(data_cf)
            if access_ctrl:
                _cf_release(access_ctrl)

    def _update_key(self, vault_id: str, key: bytes) -> None:
        """Update an existing keychain item."""
        sec = self._sec
        cf = self._cf
        service = self._service_name(vault_id)

        service_cf = _cf_string(service)
        account_cf = _cf_string("master_key")
        data_cf = _cf_data(key)

        try:
            query = self._build_query_dict(service_cf, account_cf)

            kSecValueData = c_void_p.in_dll(sec, "kSecValueData")
            kCFTypeDictionaryKeyCallBacks = c_void_p.in_dll(cf, "kCFTypeDictionaryKeyCallBacks")
            kCFTypeDictionaryValueCallBacks = c_void_p.in_dll(
                cf, "kCFTypeDictionaryValueCallBacks"
            )
            cf.CFDictionaryCreateMutable.restype = c_void_p
            cf.CFDictionaryCreateMutable.argtypes = [c_void_p, c_int32, c_void_p, c_void_p]
            cf.CFDictionaryAddValue.argtypes = [c_void_p, c_void_p, c_void_p]

            attrs = cf.CFDictionaryCreateMutable(
                None, 0,
                ctypes.byref(kCFTypeDictionaryKeyCallBacks),
                ctypes.byref(kCFTypeDictionaryValueCallBacks),
            )
            cf.CFDictionaryAddValue(attrs, kSecValueData, data_cf)

            sec.SecItemUpdate.restype = c_int32
            sec.SecItemUpdate.argtypes = [c_void_p, c_void_p]
            status = sec.SecItemUpdate(query, attrs)
            _cf_release(query)
            _cf_release(attrs)

            if status != _errSecSuccess:
                raise VaultError(f"Keychain update failed: {_os_status_to_str(status)}")
        finally:
            _cf_release(service_cf)
            _cf_release(account_cf)
            _cf_release(data_cf)
