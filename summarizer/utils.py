import hashlib


""" 
    Generate a SHA256 hash for the given content to maintain the cache freshness of the post summary.
"""

def generate_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
