from dataclasses import dataclass
from typing import Annotated
import uuid
from fastapi import Depends,HTTPException
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from jwt import InvalidTokenError
from app.core.security import decode_access_token
from app.models import Role

bearer=HTTPBearer(auto_error=False)
@dataclass(frozen=True)
class Principal:user_id:uuid.UUID;organization_id:uuid.UUID;role:Role
async def current_principal(credentials:Annotated[HTTPAuthorizationCredentials|None,Depends(bearer)])->Principal:
    if not credentials:raise HTTPException(401,"Authentication required")
    try:
        p=decode_access_token(credentials.credentials)
        if p.get("type")!="access":raise ValueError
        return Principal(uuid.UUID(p["sub"]),uuid.UUID(p["org"]),Role(p["role"]))
    except (InvalidTokenError,KeyError,ValueError):raise HTTPException(401,"Invalid token")
def require_roles(*roles:Role):
    async def check(p:Annotated[Principal,Depends(current_principal)])->Principal:
        if p.role not in roles:raise HTTPException(403,"Insufficient permission")
        return p
    return check
