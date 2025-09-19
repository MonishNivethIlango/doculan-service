import boto3
from botocore.config import Config
from dotenv import load_dotenv
from config import config

load_dotenv()

s3_client = boto3.client(
    "s3",
    aws_access_key_id=config.AWS_ACCESS_KEY,
    aws_secret_access_key=config.AWS_SECRET_KEY,
    region_name=config.AWS_REGION,
    config=Config(signature_version='s3v4')
)


kms_client = boto3.client(
    "kms",
    aws_access_key_id=config.AWS_ACCESS_KEY,
    aws_secret_access_key=config.AWS_SECRET_KEY,
    region_name=config.AWS_REGION
)

import boto3
from botocore.exceptions import ClientError
import json

class S3Client:
    def __init__(self, bucket_name: str):
        self.bucket = bucket_name
        self.client = s3_client

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def read_json(self, key: str) -> dict:
        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))

    def write_json(self, key: str, data: dict) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(data).encode("utf-8"),
            ContentType="application/json"
        )

    def delete_object(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def list(self, prefix: str) -> list[str]:
        keys = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys

S3_user = S3Client(config.S3_BUCKET)