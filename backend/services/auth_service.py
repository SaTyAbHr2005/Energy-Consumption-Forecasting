import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("Missing Supabase configuration in environment.")

# Create the admin Supabase client using the Service Role Key for backend verifications/operations
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Validates the Supabase JWT token and returns the user object.
    Raises an HTTP exception if the token is invalid or expired.
    """
    token = credentials.credentials
    try:
        # get_user validates the JWT locally or via Supabase Auth
        # In supabase-py, auth.get_user(token) hits the Supabase auth API to verify
        user_res = supabase_admin.auth.get_user(token)
        user = user_res.user
        if not user:
            raise ValueError("Invalid user")
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
