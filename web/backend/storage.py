from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from diverge.config.paths import resolve_data_dir


class StorageBackend(Protocol):
    def put_bytes(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> None: ...

    def get_bytes(self, key: str) -> bytes: ...

    def list(self, prefix: str = "") -> list[str]: ...

    def delete(self, key: str) -> None: ...

    def presign(self, key: str, *, expires: int = 3600) -> str: ...

    def put_text(self, key: str, text: str, *, content_type: str | None = None) -> None:
        self.put_bytes(key, text.encode("utf-8"), content_type=content_type)

    def get_text(self, key: str) -> str:
        return self.get_bytes(key).decode("utf-8")


def normalize_key(key: str) -> str:
    normalized = str(key).replace("\\", "/").strip("/")
    if not normalized or normalized.startswith("../") or "/../" in f"/{normalized}/":
        raise ValueError("storage key must be a non-empty relative path")
    return normalized


class LocalStorage:
    def __init__(self, root: Path | str):
        self.root = Path(root).expanduser().resolve()

    def _path(self, key: str) -> Path:
        candidate = (self.root / normalize_key(key)).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("storage key escapes local storage root") from exc
        return candidate

    def put_bytes(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def put_text(self, key: str, text: str, *, content_type: str | None = None) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def get_text(self, key: str) -> str:
        return self._path(key).read_text(encoding="utf-8")

    def list(self, prefix: str = "") -> list[str]:
        normalized_prefix = normalize_key(prefix) if prefix.strip("/") else ""
        base = self.root / normalized_prefix
        if not base.exists():
            return []
        if base.is_file():
            return [normalized_prefix]
        results: list[str] = []
        for path in base.rglob("*"):
            if path.is_file():
                results.append(path.relative_to(self.root).as_posix())
        return sorted(results)

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def presign(self, key: str, *, expires: int = 3600) -> str:
        return self._path(key).as_uri()


class TencentCOSStorage:
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        prefix: str = "",
        client=None,
    ):
        self.bucket = bucket
        self.region = region
        self.prefix = prefix.strip("/")
        self.client = client or _build_tencent_cos_client(region)

    def _key(self, key: str) -> str:
        normalized = normalize_key(key)
        if self.prefix:
            return f"{self.prefix}/{normalized}"
        return normalized

    def _strip_prefix(self, key: str) -> str:
        if self.prefix and key.startswith(f"{self.prefix}/"):
            return key[len(self.prefix) + 1 :]
        return key

    def put_bytes(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> None:
        kwargs = {
            "Bucket": self.bucket,
            "Key": self._key(key),
            "Body": data,
        }
        if content_type:
            kwargs["ContentType"] = content_type
        self.client.put_object(**kwargs)

    def put_text(self, key: str, text: str, *, content_type: str | None = None) -> None:
        self.put_bytes(
            key,
            text.encode("utf-8"),
            content_type=content_type or "text/plain; charset=utf-8",
        )

    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        body = response.get("Body") if isinstance(response, dict) else None
        if body is None:
            return b""
        if hasattr(body, "get_raw_stream"):
            return body.get_raw_stream().read()
        if hasattr(body, "read"):
            return body.read()
        if isinstance(body, bytes):
            return body
        return bytes(body)

    def get_text(self, key: str) -> str:
        return self.get_bytes(key).decode("utf-8")

    def list(self, prefix: str = "") -> list[str]:
        cos_prefix = self._key(prefix) if prefix.strip("/") else self.prefix
        response = self.client.list_objects(Bucket=self.bucket, Prefix=cos_prefix)
        contents = response.get("Contents") or [] if isinstance(response, dict) else []
        return sorted(
            self._strip_prefix(item["Key"])
            for item in contents
            if isinstance(item, dict) and item.get("Key")
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))

    def presign(self, key: str, *, expires: int = 3600) -> str:
        return self.client.get_presigned_url(
            Method="GET",
            Bucket=self.bucket,
            Key=self._key(key),
            Expired=expires,
        )


def _build_tencent_cos_client(region: str):
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError as exc:  # pragma: no cover - exercised in deployment.
        raise RuntimeError(
            "Install cos-python-sdk-v5 to use STORAGE_BACKEND=tencent_cos"
        ) from exc

    secret_id = os.environ.get("COS_SECRET_ID", "").strip()
    secret_key = os.environ.get("COS_SECRET_KEY", "").strip()
    if not secret_id or not secret_key:
        raise RuntimeError("COS_SECRET_ID and COS_SECRET_KEY are required")
    config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
    return CosS3Client(config)


_STORAGE: StorageBackend | None = None
_STORAGE_SIGNATURE: tuple[str, ...] | None = None


def reset_storage_cache() -> None:
    global _STORAGE
    global _STORAGE_SIGNATURE
    _STORAGE = None
    _STORAGE_SIGNATURE = None


def get_storage() -> StorageBackend:
    global _STORAGE
    global _STORAGE_SIGNATURE
    signature = (
        os.environ.get("STORAGE_BACKEND", "local").strip().lower(),
        os.environ.get("DATA_DIR", ""),
        os.environ.get("COS_BUCKET", ""),
        os.environ.get("COS_REGION", ""),
        os.environ.get("COS_PREFIX", ""),
    )
    if _STORAGE is not None and _STORAGE_SIGNATURE == signature:
        return _STORAGE

    backend = signature[0]
    if backend == "local":
        _STORAGE = LocalStorage(resolve_data_dir())
        _STORAGE_SIGNATURE = signature
        return _STORAGE
    if backend == "tencent_cos":
        _STORAGE = TencentCOSStorage(
            bucket=_required_env("COS_BUCKET"),
            region=_required_env("COS_REGION"),
            prefix=os.environ.get("COS_PREFIX", ""),
        )
        _STORAGE_SIGNATURE = signature
        return _STORAGE
    if backend == "s3_compatible":
        raise NotImplementedError(
            "s3_compatible storage is reserved for a future overseas adapter"
        )
    raise RuntimeError(f"Unsupported STORAGE_BACKEND '{backend}'")


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def upload_directory(
    local_dir: Path, prefix: str, *, backend: StorageBackend | None = None
) -> list[str]:
    storage_backend = backend or get_storage()
    uploaded: list[str] = []
    for path in sorted(local_dir.rglob("*")):
        if not path.is_file():
            continue
        key = f"{normalize_key(prefix)}/{path.relative_to(local_dir).as_posix()}"
        storage_backend.put_bytes(key, path.read_bytes())
        uploaded.append(key)
    return uploaded


def download_prefix(
    prefix: str, local_dir: Path, *, backend: StorageBackend | None = None
) -> list[Path]:
    storage_backend = backend or get_storage()
    normalized_prefix = normalize_key(prefix)
    downloaded: list[Path] = []
    for key in storage_backend.list(normalized_prefix):
        relative = key[len(normalized_prefix) :].lstrip("/")
        if not relative:
            continue
        target = local_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(storage_backend.get_bytes(key))
        downloaded.append(target)
    return downloaded
