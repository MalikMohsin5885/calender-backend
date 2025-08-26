from typing import Optional, Dict

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

# Optional fallback (not recommended for production) if you ever want to read claims without verification.
# import jwt  # pyjwt

def extract_google_user_info(id_token_str: str, audience: Optional[str] = None) -> Optional[Dict]:
    """
    Verify a Google ID token and extract basic user info.

    - id_token_str: the JWT 'id_token' returned by Google.
    - audience: your OAuth client_id. If provided, 'aud' will be checked.
                If None, the token will still be verified (issuer/signature), but 'aud' won’t be enforced.

    Returns a dict containing at least 'email' if valid, else None.
    """
    try:
        request = google_requests.Request()
        claims = google_id_token.verify_oauth2_token(id_token_str, request, audience=audience)
        return {
            "email": claims.get("email"),
            "email_verified": claims.get("email_verified"),
            "name": claims.get("name"),
            "picture": claims.get("picture"),
            "sub": claims.get("sub"),
            "hd": claims.get("hd"),
        }
    except Exception:
        return None

# If you ever need an unverified extractor for debugging only:
# def extract_google_user_info_unverified(id_token_str: str) -> Optional[Dict]:
#     try:
#         claims = jwt.decode(id_token_str, options={"verify_signature": False, "verify_aud": False})
#         return {
#             "email": claims.get("email"),
#             "email_verified": claims.get("email_verified"),
#             "name": claims.get("name"),
#             "picture": claims.get("picture"),
#             "sub": claims.get("sub"),
#             "hd": claims.get("hd"),
#         }
#     except Exception:
#         return None