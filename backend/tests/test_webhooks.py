import hashlib,hmac,json
from app.webhooks import signed_payload
def test_signed_payload_is_verifiable():
    body,timestamp,signature=signed_payload("delivery-1","order.created",{"amount":10},"secret")
    expected=hmac.new(b"secret",timestamp.encode()+b"."+body,hashlib.sha256).hexdigest()
    assert signature==f"t={timestamp},v1={expected}"
    assert json.loads(body)["type"]=="order.created"
