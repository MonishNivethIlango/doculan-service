import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from DataAccessLayer.tracker.mongo_tracker import MongoTracker

@pytest.mark.asyncio
@patch('DataAccessLayer.tracker.mongo_tracker.AsyncIOMotorClient')
async def test_mongo_tracker_methods(mock_motor):
    # Arrange
    db_url = 'mongodb://localhost:27017'
    db_name = 'testdb'
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_motor.return_value = mock_client
    mock_client.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_collection
    # Make all collection methods async
    mock_collection.insert_one = AsyncMock()
    mock_collection.update_one = AsyncMock(return_value=MagicMock(matched_count=1, modified_count=1))
    mock_collection.find_one = AsyncMock(return_value={'file_key': 'f', 'user_email': 'u', 'status': 's'})
    mock_collection.find.return_value.to_list = AsyncMock(return_value=[{'file_key': 'f', 'user_email': 'u', 'status': 's'}])
    tracker = MongoTracker(db_url, db_name)
    # Act & Assert
    await tracker.add_status('f', 'u', 's')
    mock_collection.insert_one.assert_awaited_with({'file_key': 'f', 'user_email': 'u', 'status': 's'})
    await tracker.update_status('f', 'u', 's')
    mock_collection.update_one.assert_awaited_with({'file_key': 'f', 'user_email': 'u'}, {'$set': {'status': 's'}})
    res = await tracker.get_status('f', 'u')
    assert res == {'file_key': 'f', 'user_email': 'u', 'status': 's'}
    res_all = await tracker.get_all_statuses()
    assert isinstance(res_all, list)
    await tracker.save_metadata('f', 'u', {'meta': 1})
    mock_collection.update_one.assert_awaited_with({'file_key': 'f', 'user_email': 'u'}, {'$set': {'metadata': {'meta': 1}}}, upsert=True)
