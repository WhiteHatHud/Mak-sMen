# services/storage/blob_storage.py
from __future__ import annotations
from typing import Optional, Dict, Any, Iterable, Callable
import os
import uuid
import logging
from datetime import datetime, timedelta


from azure.storage.blob.aio import BlobServiceClient, ContainerClient, BlobClient # type: ignore
from azure.storage.blob import generate_blob_sas, BlobSasPermissions # type: ignore


logger = logging.getLogger(__name__)


AZ_BLOB_CONN_STR = os.getenv("AZURE_BLOB_CONNECTION_STRING")
AZ_BLOB_ACCOUNT_URL = os.getenv("AZURE_BLOB_ACCOUNT_URL")
AZ_BLOB_ACCOUNT_NAME = os.getenv("AZURE_BLOB_ACCOUNT_NAME")
AZ_BLOB_ACCOUNT_KEY = os.getenv("AZURE_BLOB_ACCOUNT_KEY")
AZ_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "beth-data")
CDN_BASE_URL = os.getenv("CDN_BASE_URL") # optional, for constructing CDN URLs

class ProgressHook:
    def __init__(self, total_bytes: int, cb: Optional[Callable[[int, int], None]] = None):
        self.total = total_bytes
        self.sent = 0
        self.cb = cb
    
    def __call__(self, bytes_amount: int):
        self.sent += bytes_amount
        if self.cb:
            try:
                self.cb(self.sent, self.total)
            except Exception:
                pass




class BlobStorageClient:
    def __init__(self, container: Optional[str] = None):
        self.container_name = container or AZ_BLOB_CONTAINER
        if AZ_BLOB_CONN_STR:
            self._svc = BlobServiceClient.from_connection_string(AZ_BLOB_CONN_STR)
        elif AZ_BLOB_ACCOUNT_URL and AZ_BLOB_ACCOUNT_KEY:
            from azure.core.credentials import AzureNamedKeyCredential # type: ignore
            cred = AzureNamedKeyCredential(AZ_BLOB_ACCOUNT_NAME, AZ_BLOB_ACCOUNT_KEY)
            from azure.storage.blob import BlobServiceClient as SyncBlobServiceClient # type: ignore
            self._svc = SyncBlobServiceClient(account_url=AZ_BLOB_ACCOUNT_URL, credential=cred) # type: ignore
        else:
            raise RuntimeError("Azure Blob credentials not configured")


    async def _get_container(self) -> ContainerClient:
        cont = self._svc.get_container_client(self.container_name)
        try:
            await cont.create_container()
        except Exception:
            pass
        return cont

    async def upload_stream(self, *, name: Optional[str], data, length: int, content_type: Optional[str] = None, on_progress: Optional[Callable[[int, int], None]] = None) -> Dict[str, Any]:
        blob_name = name or str(uuid.uuid4())
        cont = await self._get_container()
        blob: BlobClient = cont.get_blob_client(blob_name)
        progress = ProgressHook(length, on_progress)
        await blob.upload_blob(data, overwrite=True, length=length, content_settings={"content_type": content_type}, raw_response_hook=lambda resp: progress(resp.context.options.get('data_stream_total', 0))) # type: ignore
        url = blob.url
        cdn_url = f"{CDN_BASE_URL.rstrip('/')}/{blob_name}" if CDN_BASE_URL else None
        return {"name": blob_name, "url": url, "cdn_url": cdn_url}


    async def download_stream(self, name: str):
        cont = await self._get_container()
        blob = cont.get_blob_client(name)
        stream = await blob.download_blob()
        return stream.chunks()


    def generate_sas(self, name: str, *, minutes: int = 60, permissions: str = "r") -> str:
        perms = BlobSasPermissions(read='r' in permissions, write='w' in permissions, create='c' in permissions, delete='d' in permissions)
        sas = generate_blob_sas(
            account_name=AZ_BLOB_ACCOUNT_NAME,
            container_name=self.container_name,
            blob_name=name,
            account_key=AZ_BLOB_ACCOUNT_KEY,
            permission=perms,
            expiry=datetime.utcnow() + timedelta(minutes=minutes),
        )
        base = AZ_BLOB_ACCOUNT_URL or ""
        return f"{base}/{self.container_name}/{name}?{sas}"

    async def set_lifecycle(self, days: int = 30):
        # Placeholder: requires management-plane API; document policy externally
        logger.info("Lifecycle policy would archive/delete blobs after %s days", days)


    async def copy_backup(self, src_name: str, dest_container: str):
        dest = self._svc.get_container_client(dest_container)
        await dest.create_container()
        src_url = f"{AZ_BLOB_ACCOUNT_URL}/{self.container_name}/{src_name}"
        dest_blob = dest.get_blob_client(src_name)
        await dest_blob.start_copy_from_url(src_url)


    async def put_encryption_scope(self, name: str, scope: str):
        # Encryption at rest is default with Azure-managed keys; customer-managed requires scope on container
        logger.info("Set encryption scope '%s' for blob %s (container-level recommended)", scope, name)


# Virus scanning integration points
    async def scan_before_commit(self, name: str) -> None:
        logger.info("Virus scan placeholder for blob %s", name)


# Data retention policy
    async def enforce_retention(self, name: str, days: int):
        logger.info("Retention placeholder: mark %s for deletion after %s days", name, days)