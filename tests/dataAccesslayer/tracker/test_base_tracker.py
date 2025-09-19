import pytest
from DataAccessLayer.tracker.base import BaseTrackerStrategy

# Test that BaseTrackerStrategy cannot be instantiated directly
def test_base_tracker_strategy_cannot_instantiate():
    with pytest.raises(TypeError):
        BaseTrackerStrategy()

# Test that a subclass missing an abstract method cannot be instantiated
class IncompleteTracker(BaseTrackerStrategy):
    async def add_status(self, file_key, user_email, status): pass
    async def update_status(self, file_key, user_email, status): pass
    async def get_status(self, file_key, user_email): pass
    async def get_all_statuses(self): pass
    # save_metadata is missing

def test_incomplete_tracker_strategy():
    with pytest.raises(TypeError):
        IncompleteTracker()

# Test that a complete subclass can be instantiated and its methods called
class CompleteTracker(BaseTrackerStrategy):
    async def add_status(self, file_key, user_email, status): return 'add'
    async def update_status(self, file_key, user_email, status): return 'update'
    async def get_status(self, file_key, user_email): return 'get'
    async def get_all_statuses(self): return 'all'
    async def save_metadata(self, file_key, user_email, metadata): return 'save'

import asyncio
def test_complete_tracker_strategy():
    tracker = CompleteTracker()
    loop = asyncio.get_event_loop()
    assert loop.run_until_complete(tracker.add_status('f', 'u', 's')) == 'add'
    assert loop.run_until_complete(tracker.update_status('f', 'u', 's')) == 'update'
    assert loop.run_until_complete(tracker.get_status('f', 'u')) == 'get'
    assert loop.run_until_complete(tracker.get_all_statuses()) == 'all'
    assert loop.run_until_complete(tracker.save_metadata('f', 'u', {})) == 'save'
