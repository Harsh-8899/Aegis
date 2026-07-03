import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.server import app
from src.data.database import Base, get_db, UserFeedback

# Setup independent sqlite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_feedback.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(autouse=True)
def override_db_dependency():
    # Setup tables in test_feedback.db
    Base.metadata.create_all(bind=engine)
    
    # Store original override
    original_override = app.dependency_overrides.get(get_db)
    
    def local_override():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = local_override
    
    yield
    
    # Restore original override or clear
    if original_override:
        app.dependency_overrides[get_db] = original_override
    else:
        app.dependency_overrides.pop(get_db, None)
        
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

def test_feedback_flow():
    # 1. Test POST with missing fields (should trigger 422 ValidationError)
    response = client.post("/api/v1/system/feedback", json={
        "username": "Test User"
    })
    assert response.status_code == 422

    # 2. Test POST with short comment (should trigger 422 validation)
    response = client.post("/api/v1/system/feedback", json={
        "username": "Test User",
        "email": "test@domain.com",
        "category": "BUG",
        "rating": 5,
        "comment": "bad"
    })
    assert response.status_code == 422

    # 3. Test POST with valid values
    response = client.post("/api/v1/system/feedback", json={
        "username": "Test User",
        "email": "test@domain.com",
        "category": "BUG",
        "rating": 4,
        "comment": "The latency check on the dashboard is very responsive!"
    })
    assert response.status_code == 201
    assert response.json()["status"] == "success"

    # 4. Verify database insertion
    db = TestingSessionLocal()
    fb = db.query(UserFeedback).first()
    assert fb is not None
    assert fb.username == "Test User"
    assert fb.rating == 4
    assert fb.comment == "The latency check on the dashboard is very responsive!"
    db.close()
