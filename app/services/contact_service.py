from repositories.contact_repository import ContactRepository

class ContactService:

    @staticmethod
    def create_contact(contact_id: str, contact_data: dict, email: str):
        result = ContactRepository.create_contact(contact_id, contact_data, email)
        return result

    @staticmethod
    def get_contact(contact_id: str, email: str):
        contact = ContactRepository.read_contact(contact_id, email)
        return contact

    @staticmethod
    def get_all_contacts(email: str):
        contacts = ContactRepository.get_all_contacts(email)
        return contacts

    @staticmethod
    def update_contact(contact_id: str, updated_data: dict, email: str):
        result = ContactRepository.update_contact(contact_id, updated_data, email)
        return result

    @staticmethod
    def delete_contact(contact_id: str, email: str):
        result = ContactRepository.delete_contact(contact_id, email)
        return result