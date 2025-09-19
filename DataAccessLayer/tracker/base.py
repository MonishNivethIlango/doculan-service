from abc import ABC, abstractmethod


class BaseTrackerStrategy(ABC):
    @abstractmethod
    async def add_status(self, file_key: str, user_email: str, status: str):
        pass

    @abstractmethod
    async def update_status(self, file_key: str, user_email: str, status: str):
        pass

    @abstractmethod
    async def get_status(self, file_key: str, user_email: str):
        pass

    @abstractmethod
    async def get_all_statuses(self):
        pass

    @abstractmethod
    async def save_metadata(self, file_key: str, user_email: str, metadata: dict):
        pass