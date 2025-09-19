from DataAccessLayer.library_storage.gdrive_storage_library import GoogleDriveLibraryStorage
from DataAccessLayer.library_storage.s3_library_storage import S3LibraryStorage
from DataAccessLayer.storage.gdrive_storage import GoogleDriveStorage
from DataAccessLayer.storage.s3_storage import S3Storage
from config import config


def get_storage_library_strategy(storage_type: str):
    if storage_type == "s3":
        return S3LibraryStorage(bucket_name=config.S3_BUCKET)
    elif storage_type == "gdrive":
        return GoogleDriveLibraryStorage()  # add creds config
    # elif storage_type == "local":
    #     return LocalStorage(upload_dir="./uploads")
    # elif storage_type == "db":
    #     return DBStorage()
    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")
