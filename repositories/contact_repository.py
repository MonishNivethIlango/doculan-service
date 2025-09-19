from app.model.contact_model import ContactModel

class ContactRepository:
    @staticmethod
    def create_contact(contact_id: str, contact_data: dict, email: str):
        return ContactModel.save_contact(contact_id, contact_data, email)

    @staticmethod
    def get_all_contacts(email: str):
        return ContactModel.list_contacts(email)

    @staticmethod
    def read_contact(contact_id: str, email: str):
        return ContactModel.get_contact(contact_id, email)

    @staticmethod
    def update_contact(contact_id: str, updated_data: dict, email: str):
        return ContactModel.update_contact(contact_id, updated_data, email)

    @staticmethod
    def delete_contact(contact_id: str, email: str):
        return ContactModel.delete_contact(contact_id, email)