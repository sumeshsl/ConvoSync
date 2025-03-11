from fastapi import FastAPI, Request, HTTPException, Security, Depends
import httpx
import jwt
import uuid
import os
from pydantic import BaseModel
from datetime import datetime, timedelta
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi.middleware.cors import CORSMiddleware
import logging
from rediscache import cache_exists, store_session
from typing import Tuple, Dict, Any, Optional


# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "mysecretkey")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "60"))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:\t %(asctime)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Define backend microservices URLs
MICROSERVICES = {
    "queries": os.getenv("PREPROCESSING_URL")
}

# Security Token Bearer
security = HTTPBearer()
limiter = Limiter(key_func=get_remote_address)

class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: Dict[str, Any]
    token_type: str

# Initialize FastAPI app
app = FastAPI(
    title="AdaptAI API Gateway",
    description="API Gateway for routing requests to microservices",
    version="1.0.0"
)
app.state.limiter = limiter

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS, #TODO: restrict to clients of the API
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Generate JWT token
def create_jwt_token(username: str) -> Dict[str, Any]:
    """
    Create a JWT token for user authentication.
    Args:
        username: The username for which to create a token
    Returns:
        Dict containing token and expiration info
    """
    ttl = timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    logger.info(f"ttl:{ttl}")
    session_id = str(uuid.uuid4())  # Generate a unique session ID
    expiration = datetime.utcnow() + ttl  # Token expiration time
    logger.info(f"exp:{expiration}")
    payload = {
        "user_id": username,
        "session_id": session_id,
        "exp": expiration
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    store_session(username,session_id,token,ttl)
    response = {
        'token': token,
        'expires_in': TOKEN_EXPIRE_MINUTES * 60
    }
    return response

def verify_jwt(token: str) -> Tuple[str, str]:
    """
    Verify JWT Token and extract user info.
    Args:
        token: JWT token to verify
    Returns:
        Tuple of (user_id, session_id)
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload["user_id"]
        session_id = payload["session_id"]

        # ✅ Check if session exists in Redis
        session_key = f"session:{user_id}:{session_id}"

        if not cache_exists(session_key):
            return None  # Session does not exist or expired

        return user_id, session_id
    except jwt.ExpiredSignatureError:
        logger.error(f"JWT Expired: {token}")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        logger.error(f"JWT Invalid: {token}")
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_user_from_token(
        credentials: HTTPAuthorizationCredentials = Security(security)
) -> Tuple[str, str]:
    """
    Dependency to extract and verify user from JWT token.
    Args:
        credentials: HTTP Bearer token credentials
    Returns:
        Tuple of (user_id, session_id)
    """
    return verify_jwt(credentials.credentials)

# User login
@app.post("/login", response_model=TokenResponse)
def login(user: UserLogin) -> TokenResponse:
    """
    Authenticate user and generate JWT token.
    Args:
        user: Login credentials
    Returns:
        Token information on successful login
    Raises:
        HTTPException: If credentials are invalid
    """
    # Validate the username and password.
    if user.username == "admin" and user.password == "password":
        token = create_jwt_token(user.username)
        return {"access_token": token, "token_type": "bearer"}

    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/")
def health_check() -> Dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "healthy", "message": "API Gateway is running"}


async def forward_request(
        service_name: str,
        request: Request,
        headers: dict) -> Dict[str, Any]:
    """
    Forward request from API Gateway to the target microservice.
    Args:
        service_name: Name of the service to forward to
        request: Original FastAPI request
        headers: Headers to include in the forwarded request
    Returns:
        JSON response from the microservice
    """
    if service_name not in MICROSERVICES:
        logger.error(f"Service {service_name} not found.")
        return {"error": "Service not found"}

    service_url = f"{MICROSERVICES[service_name]}{request.url.path}"
    method = request.method
    body = await request.body()

    logger.info(f"Forwarding request: {method} {service_url}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(
                method,
                service_url,
                content=body,
                headers=headers,
                params=request.query_params
            )

            # Log Response Status First
            logger.info(f"Response Status: {response.status_code}")

            if response.status_code >= 400:
                logger.error(f"Error Response: {response.text}")

            return response.json()
        except httpx.RequestError as e:
            logger.error(f"HTTP request failed: {str(e)}")
            raise HTTPException(status_code=503, detail="Service unavailable")

@app.api_route("/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
@limiter.limit("5/minute")
async def gateway(
        service_name: str,
        request: Request,
        user_info: Tuple[str, str] = Depends(get_user_from_token)) -> Any:
    """
    Generic API Gateway endpoint for forwarding to all microservices.
    Args:
        service_name: Name of the service to forward to
        request: Original request
        user_info: User ID and session ID from token
    Returns:
        Response from the microservice
    """
    user_id, session_id = user_info
    modified_headers = dict(request.headers)
    modified_headers["user-id"] = user_id
    modified_headers["session-id"] = session_id
    return await forward_request(service_name, request, modified_headers)
