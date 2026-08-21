import base64,hashlib,json
from cryptography.fernet import Fernet,InvalidToken
from app.core.config import get_settings

def _cipher()->Fernet:
    key=base64.urlsafe_b64encode(hashlib.sha256(get_settings().jwt_secret.encode()).digest())
    return Fernet(key)

def encrypt_credentials(value:str)->str:return _cipher().encrypt(value.encode()).decode()
def decrypt_credentials(value:str)->str:
    try:return _cipher().decrypt(value.encode()).decode()
    except InvalidToken:raise ValueError("Integration credential cannot be decrypted")

def masked_credential(value:str)->str:
    plain=decrypt_credentials(value)
    return f"••••{plain[-4:]}" if len(plain)>=4 else "••••"

def simulate_connection(provider:str,credential:str,base_url:str|None)->dict:
    valid=len(credential.strip())>=4 and (not base_url or base_url.startswith("https://"))
    return {"ok":valid,"provider":provider,"message":"Conexão validada em modo seguro" if valid else "Credencial ou URL inválida"}
