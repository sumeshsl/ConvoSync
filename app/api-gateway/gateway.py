from fastapi import FastAPI, Request
import httpx
import jwt
import uuid
from pydantic import BaseModel
from datetime import datetime, timedelta
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import HTTPException, Security
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi.middleware.cors import CORSMiddleware
import logging
from rediscache import cache_exists


limiter = Limiter(key_func=get_remote_address)


app = FastAPI(title="AdaptAI API Gateway")
app.state.limiter = limiter
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:\t %(asctime)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

SECRET_KEY = "mysecretkey"
ALGORITHM = "HS256"

# Security Token Bearer
security = HTTPBearer()

class UserLogin(BaseModel):
    username: str
    password: str

# Define backend microservices URLs
MICROSERVICES = {
    "queries": "http://api-preprocessing:8008",
    "orders": "http://orders-service.default.svc.cluster.local"
}

# Generate JWT token
def create_jwt_token(username: str):
    """Create a JWT token."""
    session_id = str(uuid.uuid4())  # ✅ Generate a unique session ID
    expiration = datetime.utcnow() + timedelta(hours=1)  # Token expiration time
    payload = {
        "user_id": username,
        "session_id": session_id,
        "exp": expiration
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# User login
@app.post("/login")
def login(user: UserLogin):
    """Generate JWT token on successful login."""
    # In a real-world application, validate the username and password.
    if user.username == "admin" and user.password == "password":
        token = create_jwt_token(user.username)
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid credentials")


async def forward_request(service_name: str, request: Request):
    """Forward request from API Gateway to the target microservice."""
    if service_name not in MICROSERVICES:
        logger.error(f"Service {service_name} not found.")
        return {"error": "Service not found"}

    async with httpx.AsyncClient() as client:
        method = request.method
        body = await request.body()
        service_url = f"{MICROSERVICES[service_name]}{request.url.path}"
        logger.info(f"Service URL: {service_url}")
        logger.info(f"Forwarding request: {method} {service_url} with body {body}")

        try:
            response = await client.request(
                method, service_url, content=body, headers=request.headers, params=request.query_params
            )

            # ✅ Log Response Status First
            logger.info(f"Response Status: {response.status_code}")

            # ✅ Log Response Text Safely
            if response.status_code == 200:
                logger.info(f"Response Text: {response.text}")
            else:
                logger.error(f"Error Response: {response.text}")

            return response.json()
        except Exception as e:
            logger.error(f"HTTP request failed: {str(e)}")
            return {"error": "Failed to reach service"}

@app.get("/{service_name}/{path:path}")
@app.post("/{service_name}/{path:path}")
@app.put("/{service_name}/{path:path}")
@app.delete("/{service_name}/{path:path}")
@limiter.limit("5/minute")
async def gateway(service_name: str, request: Request, credentials: HTTPAuthorizationCredentials = Security(security)):
    """Generic API Gateway endpoint for all services."""
    """Authenticated Gateway Request."""
    token = credentials.credentials
    user_id, session_id = verify_jwt(token)
    request.headers = {"user-id": user_id, "session-id": session_id}
    return await forward_request(service_name, request)

@app.get("/")
def root():
    return {"message": "API Gateway is running"}

def verify_jwt(token: str):
    """Verify JWT Token."""
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
