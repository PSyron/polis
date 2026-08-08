from __future__ import annotations

from pathlib import Path

from polis.evaluation.holdout_json import fail, object_value, string_value
from polis.evaluation.holdout_models import (
    AuthorizationSignatureRequirements,
    JsonValue,
)
from polis.evaluation.holdout_preregistration import (
    AUTHORIZATION_FINGERPRINT,
    AUTHORIZATION_HOST_MACHINE,
    AUTHORIZATION_HOST_SYSTEM,
    AUTHORIZATION_IDENTITY,
    AUTHORIZATION_METHOD,
    AUTHORIZATION_NAMESPACE,
    AUTHORIZATION_PUBLIC_KEY,
    AUTHORIZATION_SIGNED_PAYLOAD,
    SSH_KEYGEN_PATH,
)

_FIELDS = {
    "method",
    "signer_identity",
    "namespace",
    "trusted_public_key",
    "trusted_key_fingerprint",
    "signed_payload",
    "host_system",
    "host_machine",
    "ssh_keygen_path",
}


def parse_authorization_signature(
    value: JsonValue,
) -> AuthorizationSignatureRequirements:
    raw = object_value(value, _FIELDS, "authorization signature")
    names = (
        "method",
        "signer_identity",
        "namespace",
        "trusted_public_key",
        "trusted_key_fingerprint",
        "signed_payload",
    )
    host_system = string_value(raw["host_system"], "authorization host system")
    host_machine = string_value(raw["host_machine"], "authorization host machine")
    executable = Path(
        string_value(raw["ssh_keygen_path"], "authorization ssh-keygen path")
    )
    if not executable.is_absolute():
        fail("ssh-keygen paths must be absolute")
    requirements = AuthorizationSignatureRequirements(
        *(string_value(raw[name], f"authorization signature {name}") for name in names),
        host_system,
        host_machine,
        executable,
    )
    expected = AuthorizationSignatureRequirements(
        AUTHORIZATION_METHOD,
        AUTHORIZATION_IDENTITY,
        AUTHORIZATION_NAMESPACE,
        AUTHORIZATION_PUBLIC_KEY,
        AUTHORIZATION_FINGERPRINT,
        AUTHORIZATION_SIGNED_PAYLOAD,
        AUTHORIZATION_HOST_SYSTEM,
        AUTHORIZATION_HOST_MACHINE,
        Path(SSH_KEYGEN_PATH),
    )
    if requirements != expected:
        fail("authorization signature requirements do not match the approval")
    return requirements
