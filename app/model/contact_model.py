from typing import Dict
from botocore.exceptions import ClientError
from app.services.security_service import AESCipher
from config import config
from database.db_config import s3_client
from utils.logger import logger
from fastapi import Request, HTTPException
from datetime import datetime, timezone
import requests
from user_agents import parse
import json

class ContactModel:

    @staticmethod
    def _get_contacts_json(email: str) -> dict:
        try:
            response = s3_client.get_object(Bucket=config.S3_BUCKET, Key=f"{email}/contacts/contacts.json")
            data = response["Body"].read().decode("utf-8")
            return json.loads(data)
        except s3_client.exceptions.NoSuchKey:
            return {}
        except Exception as e:
            print(f"Error fetching contacts for {email}: {e}")
            return {}

    @staticmethod
    def _save_contacts_json(email: str, data: dict):
        try:
            s3_client.put_object(
                Bucket=config.S3_BUCKET,
                Key=f"{email}/contacts/contacts.json",
                Body=json.dumps(data),
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=config.KMS_KEY_ID
            )
        except Exception as e:
            print(f"Error saving contacts for {email}: {e}")
            raise

    @staticmethod
    def list_contacts(email: str):
        contacts = ContactModel._get_contacts_json(email)
        return [{"id": contact_id, **contact_data} for contact_id, contact_data in contacts.items()]

    @staticmethod
    def get_contact(contact_id: str, email: str):
        contacts = ContactModel._get_contacts_json(email)
        return contacts.get(contact_id)

    @staticmethod
    def save_contact(contact_id: str, contact_data: dict, email: str):
        contacts = ContactModel._get_contacts_json(email)
        contacts[contact_id] = contact_data
        ContactModel._save_contacts_json(email, contacts)

    @staticmethod
    def update_contact(contact_id: str, updated_data: dict, email: str):
        contacts = ContactModel._get_contacts_json(email)
        if contact_id in contacts:
            contacts[contact_id] = updated_data
            ContactModel._save_contacts_json(email, contacts)
        else:
            raise KeyError(f"Contact ID {contact_id} does not exist for user {email}.")

    @staticmethod
    def delete_contact(contact_id: str, email: str):
        contacts = ContactModel._get_contacts_json(email)
        if contact_id in contacts:
            contacts.pop(contact_id)
            ContactModel._save_contacts_json(email, contacts)
        else:
            raise KeyError(f"Contact ID {contact_id} does not exist for user {email}.")