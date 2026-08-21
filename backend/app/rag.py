import hashlib
import math
import re

DIMENSIONS=192

def embed_text(value:str)->list[float]:
    vector=[0.0]*DIMENSIONS
    tokens=re.findall(r"[a-zA-ZÀ-ÿ0-9]+",value.lower())
    for token in tokens:
        digest=hashlib.blake2b(token.encode(),digest_size=8).digest()
        index=int.from_bytes(digest[:4],"big")%DIMENSIONS
        vector[index]+=1.0 if digest[4]%2==0 else -1.0
    norm=math.sqrt(sum(x*x for x in vector)) or 1.0
    return [round(x/norm,6) for x in vector]

def cosine(left:list[float],right:list[float])->float:
    return sum(a*b for a,b in zip(left,right,strict=False))

def retrieve(query:str,rows:list[tuple],limit:int=5)->list[dict]:
    query_vector=embed_text(query);ranked=[]
    for chunk,title in rows:
        score=cosine(query_vector,chunk.embedding or embed_text(chunk.content))
        ranked.append({"chunk_id":str(chunk.id),"document":title,"content":chunk.content,"position":chunk.position,"score":round(score,4)})
    return sorted(ranked,key=lambda item:item["score"],reverse=True)[:limit]
