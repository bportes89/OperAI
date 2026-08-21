import asyncio,hashlib,hmac,ipaddress,json,socket,time
from dataclasses import dataclass
from urllib.parse import urlparse
import httpx

@dataclass(frozen=True)
class DeliveryResult:
    delivered:bool;status_code:int|None;error:str|None;retryable:bool

def signed_payload(delivery_id:str,event_type:str,payload:dict,secret:str)->tuple[bytes,str,str]:
    timestamp=str(int(time.time()));body=json.dumps({"id":delivery_id,"type":event_type,"created_at":timestamp,"data":payload},ensure_ascii=False,separators=(",",":"),sort_keys=True).encode();digest=hmac.new(secret.encode(),timestamp.encode()+b"."+body,hashlib.sha256).hexdigest();return body,timestamp,f"t={timestamp},v1={digest}"

def _resolve_public(hostname:str)->None:
    if hostname.lower() in {"localhost","localhost.localdomain"}:raise ValueError("Local webhook destinations are not allowed")
    try:addresses={item[4][0] for item in socket.getaddrinfo(hostname,443,type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:raise ValueError("Webhook hostname could not be resolved") from exc
    if not addresses:raise ValueError("Webhook hostname has no address")
    for value in addresses:
        ip=ipaddress.ip_address(value)
        if not ip.is_global:raise ValueError("Private or reserved webhook destinations are not allowed")

async def validate_destination(url:str)->None:
    parsed=urlparse(url)
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password:raise ValueError("Webhook URL must be a public HTTPS address")
    if parsed.port not in {None,443}:raise ValueError("Webhook URL must use HTTPS port 443")
    await asyncio.to_thread(_resolve_public,parsed.hostname)

async def deliver_webhook(*,delivery_id:str,event_type:str,payload:dict,url:str,secret:str)->DeliveryResult:
    try:await validate_destination(url)
    except ValueError as exc:return DeliveryResult(False,None,str(exc),False)
    body,timestamp,signature=signed_payload(delivery_id,event_type,payload,secret)
    headers={"Content-Type":"application/json","User-Agent":"OperAI-Webhooks/1.0","X-OperAI-Event":event_type,"X-OperAI-Delivery":delivery_id,"X-OperAI-Timestamp":timestamp,"X-OperAI-Signature":signature}
    try:
        async with httpx.AsyncClient(timeout=10,follow_redirects=False) as client:response=await client.post(url,content=body,headers=headers)
        if 200<=response.status_code<300:return DeliveryResult(True,response.status_code,None,False)
        retryable=response.status_code==429 or response.status_code>=500;return DeliveryResult(False,response.status_code,f"HTTP {response.status_code}",retryable)
    except (httpx.TimeoutException,httpx.NetworkError) as exc:return DeliveryResult(False,None,type(exc).__name__,True)
