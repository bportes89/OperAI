import uuid
from app.core.security import create_access_token,decode_access_token,new_refresh_token
def test_access_token_is_scoped():
    user,org=str(uuid.uuid4()),str(uuid.uuid4());payload=decode_access_token(create_access_token(user_id=user,organization_id=org,role="owner"));assert payload["sub"]==user and payload["org"]==org and payload["role"]=="owner"
def test_refresh_token_is_stored_as_hash():
    raw,hashed=new_refresh_token();assert raw!=hashed and len(hashed)==64
