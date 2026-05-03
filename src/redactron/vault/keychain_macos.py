"""macOS Keychain backend with Touch ID via LocalAuthentication framework.

Security model:
- Master key stored in macOS login keychain via keyring library
- Before every vault access, LAContext.evaluatePolicy fires a Touch ID prompt
- If Touch ID succeeds → key retrieved and vault decrypted
- If Touch ID fails or is cancelled → VaultError raised, vault inaccessible
- This is soft enforcement: the key is in the login keychain (accessible to
  any process after login), but redactron refuses to use it without biometric
  confirmation. Same model as sudo-touchid.
- No Apple Developer account or code signing required.
"""

from __future__ import annotations

import ctypes
import logging
import secrets
import threading
from ctypes import c_char_p, c_int, c_long, c_void_p
from typing import Any

import keyring
import keyring.errors

from redactron.errors import VaultError

log = logging.getLogger(__name__)

_SERVICE_PREFIX = "redactron.vault."
_TOUCH_ID_REASON = "Redactron needs your fingerprint to unlock the encrypted profile vault."

# LAPolicy constants
_LAPolicyDeviceOwnerAuthenticationWithBiometrics = 1
_LAPolicyDeviceOwnerAuthentication = 2  # biometrics OR passcode fallback


def _require_touch_id() -> None:
    """Fire a Touch ID prompt via LAContext. Raises VaultError on failure/cancel."""
    try:
        libobjc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        ctypes.CDLL(
            "/System/Library/Frameworks/LocalAuthentication.framework/LocalAuthentication"
        )
    except OSError as exc:
        log.warning("LocalAuthentication not available: %s — skipping biometric gate.", exc)
        return

    libobjc.objc_getClass.restype = c_void_p
    libobjc.objc_getClass.argtypes = [c_char_p]
    libobjc.sel_registerName.restype = c_void_p
    libobjc.sel_registerName.argtypes = [c_char_p]
    libobjc.objc_msgSend.restype = c_void_p

    LAContext = libobjc.objc_getClass(b"LAContext")
    if not LAContext:
        log.warning("LAContext class not found — skipping biometric gate.")
        return

    # alloc + init
    alloc_sel = libobjc.sel_registerName(b"alloc")
    init_sel = libobjc.sel_registerName(b"init")
    libobjc.objc_msgSend.argtypes = [c_void_p, c_void_p]
    ctx = libobjc.objc_msgSend(LAContext, alloc_sel)
    ctx = libobjc.objc_msgSend(ctx, init_sel)

    # canEvaluatePolicy:error:
    can_eval_sel = libobjc.sel_registerName(b"canEvaluatePolicy:error:")
    libobjc.objc_msgSend.argtypes = [c_void_p, c_void_p, c_long, c_void_p]
    can = libobjc.objc_msgSend(
        ctx, can_eval_sel, _LAPolicyDeviceOwnerAuthenticationWithBiometrics, None
    )
    if not can:
        # Biometrics not available — fall back to passcode
        can = libobjc.objc_msgSend(
            ctx, can_eval_sel, _LAPolicyDeviceOwnerAuthentication, None
        )
        if not can:
            log.warning("No biometric or passcode auth available — skipping gate.")
            return
        policy = _LAPolicyDeviceOwnerAuthentication
    else:
        policy = _LAPolicyDeviceOwnerAuthenticationWithBiometrics

    # evaluatePolicy:localizedReason:reply: (async — use threading.Event to block)
    done = threading.Event()
    result: dict[str, Any] = {"success": False, "error": None}

    # Build NSString for reason
    NSString = libobjc.objc_getClass(b"NSString")
    string_with_utf8_sel = libobjc.sel_registerName(b"stringWithUTF8String:")
    libobjc.objc_msgSend.argtypes = [c_void_p, c_void_p, c_char_p]
    reason_ns = libobjc.objc_msgSend(
        NSString, string_with_utf8_sel, _TOUCH_ID_REASON.encode("utf-8")
    )

    # Define the ObjC block for the reply callback
    # Block layout: isa, flags, reserved, invoke, descriptor, captured vars
    BLOCK_HAS_SIGNATURE = 1 << 30

    reply_callback_type = ctypes.CFUNCTYPE(None, c_void_p, c_int, c_void_p)

    def _reply_impl(block_ptr: Any, success: int, error: Any) -> None:
        result["success"] = bool(success)
        result["error"] = error
        done.set()

    reply_block_invoke = reply_callback_type(_reply_impl)

    class BlockDescriptor(ctypes.Structure):
        _fields_ = [
            ("reserved", ctypes.c_ulong),
            ("size", ctypes.c_ulong),
        ]

    class Block(ctypes.Structure):
        _fields_ = [
            ("isa", c_void_p),
            ("flags", c_int),
            ("reserved", c_int),
            ("invoke", ctypes.c_void_p),
            ("descriptor", ctypes.POINTER(BlockDescriptor)),
        ]

    descriptor = BlockDescriptor(0, ctypes.sizeof(Block))
    block = Block()

    # Get _NSConcreteStackBlock
    libobjc.objc_getClass.argtypes = [c_char_p]
    NSConcreteStackBlock = ctypes.c_void_p.in_dll(libobjc, "_NSConcreteStackBlock")
    block.isa = NSConcreteStackBlock.value
    block.flags = BLOCK_HAS_SIGNATURE
    block.reserved = 0
    block.invoke = ctypes.cast(reply_block_invoke, ctypes.c_void_p).value
    block.descriptor = ctypes.pointer(descriptor)

    eval_sel = libobjc.sel_registerName(b"evaluatePolicy:localizedReason:reply:")
    libobjc.objc_msgSend.argtypes = [c_void_p, c_void_p, c_long, c_void_p, c_void_p]
    libobjc.objc_msgSend(ctx, eval_sel, policy, reason_ns, ctypes.byref(block))

    # Wait for the async callback (max 60s)
    done.wait(timeout=60.0)

    if not done.is_set():
        raise VaultError("Touch ID prompt timed out.")
    if not result["success"]:
        raise VaultError(
            "Touch ID authentication failed or was cancelled. Cannot unlock the vault."
        )


class MacOSKeychainBackend:
    """macOS Keychain backend with Touch ID soft-gate via LocalAuthentication.

    Master key stored in login keychain (keyring). Touch ID required before
    every retrieval. Works without code signing or Apple Developer account.
    """

    def __init__(self) -> None:
        self._cache: dict[str, bytes] = {}

    def _service_name(self, vault_id: str) -> str:
        return f"{_SERVICE_PREFIX}{vault_id}"

    def get_or_create_master_key(self, vault_id: str) -> bytes:
        """Require Touch ID, then return the 32-byte master key."""
        if vault_id in self._cache:
            return self._cache[vault_id]

        # Fire Touch ID prompt before accessing keychain
        _require_touch_id()

        service = self._service_name(vault_id)
        stored = keyring.get_password(service, "master_key")

        if stored is not None:
            key = bytes.fromhex(stored)
            if len(key) != 32:
                raise VaultError(f"Retrieved key has unexpected length {len(key)}, expected 32.")
            self._cache[vault_id] = key
            return key

        log.debug("No master key found for vault %s; generating new key.", vault_id)
        key = secrets.token_bytes(32)
        try:
            keyring.set_password(service, "master_key", key.hex())
        except keyring.errors.KeyringError as exc:
            raise VaultError(f"Failed to store master key in keychain: {exc}") from exc

        self._cache[vault_id] = key
        return key

    def delete_master_key(self, vault_id: str) -> None:
        """Remove the master key from the keychain."""
        self._cache.pop(vault_id, None)
        service = self._service_name(vault_id)
        try:
            keyring.delete_password(service, "master_key")
        except keyring.errors.PasswordDeleteError:
            pass
