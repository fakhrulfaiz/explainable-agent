# 🧪 Repository Pattern Testing Examples

## Quick Test Commands

### Install Test Dependencies
```bash
cd backend
pip install -r requirements-test.txt
```

### Run All Tests
```bash
python run_tests.py
```

### Run Specific Test Categories
```bash
# Repository tests only
python -m pytest tests/test_repositories.py -v

# Service tests only  
python -m pytest tests/test_services.py -v

# Integration tests only
python -m pytest tests/test_integration.py -v
```

### Run with Coverage
```bash
pytest tests/ --cov=src --cov-report=term-missing --cov-report=html
```

## 📊 Test Examples

### 1. Repository Unit Test
```python
# tests/test_repositories.py
async def test_create_thread_success(chat_thread_repo, sample_chat_thread):
    # Mock database response
    mock_result = Mock()
    mock_result.inserted_id = "mock_id"
    chat_thread_repo.collection.insert_one.return_value = mock_result
    
    # Test repository method
    result = await chat_thread_repo.create_thread(sample_chat_thread)
    
    # Verify behavior
    assert result is True
    chat_thread_repo.collection.insert_one.assert_called_once()
```

### 2. Service Unit Test
```python
# tests/test_services.py
async def test_create_thread_success(chat_history_service, mock_chat_thread_repo):
    # Mock repository dependency
    mock_chat_thread_repo.create_thread.return_value = True
    
    # Test service method  
    result = await chat_history_service.create_thread(request)
    
    # Verify business logic
    assert result.title == "Test Chat"
    mock_chat_thread_repo.create_thread.assert_called_once()
```

### 3. Integration Test
```python
# tests/test_integration.py
async def test_full_chat_thread_lifecycle():
    # Test complete workflow with real repositories + mocked database
    thread = await service.create_thread(create_request)
    message_added = await service.add_message(add_request)
    retrieved = await service.get_thread(thread.thread_id)
    deleted = await service.delete_thread(thread.thread_id)
    
    # Verify full lifecycle works
    assert all([thread, message_added, retrieved, deleted])
```

## 🎯 Testing Benefits Demonstrated

### ✅ **Fast Unit Tests**
- No database required
- Tests run in milliseconds
- Predictable, isolated behavior

### ✅ **Easy Error Testing**
```python
# Test database failures
chat_thread_repo.collection.insert_one.side_effect = PyMongoError("DB Error")
with pytest.raises(Exception):
    await service.create_thread(request)
```

### ✅ **Dependency Verification**
```python
# Verify repository calls
mock_repo.create_thread.assert_called_once_with(expected_thread)
mock_repo.delete_thread.assert_called_with("thread-id")
```

### ✅ **Business Logic Focus**
```python
# Test service logic without database concerns
assert result.title == expected_title
assert len(result.messages) == expected_count
```

## 📈 Coverage Report

After running tests, view coverage:
```bash
# Terminal report
pytest --cov=src --cov-report=term-missing

# HTML report (open in browser)
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

## 🔧 Test Configuration

### Project Structure
```
backend/
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Test fixtures
│   ├── test_repositories.py # Repository unit tests
│   ├── test_services.py     # Service unit tests
│   ├── test_integration.py  # Integration tests
│   └── README.md           # Test documentation
├── pytest.ini             # Pytest configuration
├── requirements-test.txt   # Test dependencies
└── run_tests.py           # Test runner script
```

### Fixtures Available
```python
# From conftest.py
@pytest.fixture
def mock_chat_thread_repo():        # Mocked repository
def sample_chat_thread():          # Sample data
def chat_history_service():        # Service with mocks
def sample_create_request():       # Request objects
```

## 🚀 Running Your First Test

1. **Install dependencies:**
   ```bash
   cd backend
   pip install -r requirements-test.txt
   ```

2. **Run a simple test:**
   ```bash
   pytest tests/test_repositories.py::TestChatThreadRepository::test_create_thread_success -v
   ```

3. **View output:**
   ```
   tests/test_repositories.py::TestChatThreadRepository::test_create_thread_success PASSED [100%]
   ```

4. **Run all tests with coverage:**
   ```bash
   python run_tests.py
   ```

This demonstrates how the repository pattern makes your code **highly testable** with **fast, reliable unit tests**!
