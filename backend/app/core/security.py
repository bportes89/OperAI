import hashlib,secrets
from datetime import UTC,datetime,timedelta
import jwt
from pwdlib import PasswordHash
from app.core.config import get_settings

password_hash=PasswordHash.recommended()
def hash_password(value:str)->str:return password_hash.hash(value)
def verify_password(value:str,hashed:str)->bool:return password_hash.verify(value,hashed)
def create_access_token(*,user_id:str,organization_id:str,role:str)->str:
    s=get_settings();now=datetime.now(UTC)
    return jwt.encode({"sub":user_id,"org":organization_id,"role":role,"type":"access","iat":now,"exp":now+timedelta(minutes=s.access_token_minutes)},s.jwt_secret,algorithm="HS256")
def decode_access_token(token:str)->dict:return jwt.decode(token,get_settings().jwt_secret,algorithms=["HS256"])
def new_refresh_token()->tuple[str,str]:
    raw=secrets.token_urlsafe(48);return raw,hashlib.sha256(raw.encode()).hexdigest()
def hash_refresh_token(raw:str)->str:return hashlib.sha256(raw.encode()).hexdigest()
