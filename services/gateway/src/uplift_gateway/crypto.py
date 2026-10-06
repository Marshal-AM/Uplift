"""Envelope encryption: a fresh KMS data key per token, AES-256-GCM bound to the link identity."""

import os

import boto3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import settings


def _kms():
    return boto3.client("kms", region_name=settings().aws_region)


def _aad(user_id: str, org_id: str, platform: str) -> bytes:
    return f"{user_id}|{org_id}|{platform}".encode()


def encrypt(token: str, user_id: str, org_id: str, platform: str) -> tuple[bytes, bytes]:
    key = _kms().generate_data_key(KeyId=settings().kms_key_id, KeySpec="AES_256")
    nonce = os.urandom(12)
    sealed = AESGCM(key["Plaintext"]).encrypt(nonce, token.encode(), _aad(user_id, org_id, platform))
    return nonce + sealed, key["CiphertextBlob"]


def decrypt(ciphertext: bytes, data_key: bytes, user_id: str, org_id: str, platform: str) -> str:
    plain_key = _kms().decrypt(CiphertextBlob=data_key)["Plaintext"]
    nonce, sealed = ciphertext[:12], ciphertext[12:]
    return AESGCM(plain_key).decrypt(nonce, sealed, _aad(user_id, org_id, platform)).decode()
