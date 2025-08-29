"""
API Management Module

Provides FastAPI application setup, middleware configuration, and common API utilities.
Includes rate limiting, CORS, authentication middleware, and response formatting.
"""

from typing import Optional, Dict, Any, List, Callable
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import time
import uuid
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from .config import get_config
from .logging import get_logger, LoggerMixin
from .auth import AuthManager, TokenData, get_auth_manager


class APIResponse:
    """Standardized API response format."""
    
    @staticmethod
    def success(data: Any = None, message: str = "Success", meta: Optional[Dict] = None):
        """Create a successful response."""
        response = {
            "success": True,
            "message": message,
            "data": data,
            "timestamp": time.time()
        }
        if meta:
            response["meta"] = meta
        return response
    
    @staticmethod
    def error(message: str = "Error", code: int = 400, details: Optional[Dict] = None):
        """Create an error response."""
        response = {
            "success": False,
            "message": message,
            "error": {
                "code": code,
                "details": details or {}
            },
            "timestamp": time.time()
        }
        return response
    
    @staticmethod
    def paginated(data: List[Any], page: int, per_page: int, total: int, message: str = "Success"):
        """Create a paginated response."""
        return APIResponse.success(
            data=data,
            message=message,
            meta={
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page
                }
            }
        )


class RequestTracker:
    """Track API requests for monitoring and debugging."""
    
    def __init__(self):
        self.requests: Dict[str, Dict] = {}
    
    def start_request(self, request_id: str, path: str, method: str, client_ip: str):
        """Start tracking a request."""
        self.requests[request_id] = {
            "path": path,
            "method": method,
            "client_ip": client_ip,
            "start_time": time.time(),
            "status": "in_progress"
        }
    
    def end_request(self, request_id: str, status_code: int):
        """End request tracking."""
        if request_id in self.requests:
            req = self.requests[request_id]
            req["end_time"] = time.time()
            req["duration"] = req["end_time"] - req["start_time"]
            req["status_code"] = status_code
            req["status"] = "completed"


class APIManager(LoggerMixin):
    """Manages FastAPI application configuration and middleware."""
    
    def __init__(self, config=None):
        self.config = config or get_config().api
        self.app: Optional[FastAPI] = None
        self.limiter = Limiter(key_func=get_remote_address)
        self.request_tracker = RequestTracker()
        self.auth_manager = get_auth_manager()
        self.security = HTTPBearer(auto_error=False)
    
    def create_app(
        self, 
        title: Optional[str] = None,
        description: str = "Ghost Backend API",
        version: str = "1.0.0",
        **kwargs
    ) -> FastAPI:
        """Create and configure FastAPI application."""
        app = FastAPI(
            title=title or get_config().project_name,
            description=description,
            version=version,
            debug=self.config.debug,
            **kwargs
        )
        
        self._setup_middleware(app)
        self._setup_exception_handlers(app)
        self._setup_routes(app)
        
        self.app = app
        self.logger.info(f"FastAPI application created: {title}")
        return app
    
    def _setup_middleware(self, app: FastAPI):
        """Set up middleware stack."""
        # Request tracking middleware
        @app.middleware("http")
        async def request_tracking_middleware(request: Request, call_next):
            request_id = str(uuid.uuid4())
            request.state.request_id = request_id
            
            self.request_tracker.start_request(
                request_id,
                request.url.path,
                request.method,
                request.client.host if request.client else "unknown"
            )
            
            response = await call_next(request)
            self.request_tracker.end_request(request_id, response.status_code)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response
        
        # Rate limiting middleware
        app.state.limiter = self.limiter
        
        @app.exception_handler(RateLimitExceeded)
        async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
            response = JSONResponse(
                status_code=429,
                content=APIResponse.error(
                    message="Rate limit exceeded",
                    code=429
                )
            )
            # Apply rate limit handler logic if needed
            enhanced_response = _rate_limit_exceeded_handler(request, exc)
            return enhanced_response
        
        app.add_middleware(SlowAPIMiddleware)
        
        # CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Trusted host middleware for production
        if get_config().environment == "production":
            app.add_middleware(
                TrustedHostMiddleware,
                allowed_hosts=["*"]  # Configure this properly in production
            )
        
        # Request logging middleware
        @app.middleware("http")
        async def logging_middleware(request: Request, call_next):
            start_time = time.time()
            
            response = await call_next(request)
            
            process_time = time.time() - start_time
            self.logger.info(
                f"{request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Time: {process_time:.3f}s - "
                f"Client: {request.client.host if request.client else 'unknown'}"
            )
            
            response.headers["X-Process-Time"] = str(process_time)
            return response
    
    def _setup_exception_handlers(self, app: FastAPI):
        """Set up global exception handlers."""
        
        @app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content=APIResponse.error(
                    message=exc.detail,
                    code=exc.status_code
                )
            )
        
        @app.exception_handler(ValueError)
        async def value_error_handler(request: Request, exc: ValueError):
            return JSONResponse(
                status_code=400,
                content=APIResponse.error(
                    message=str(exc),
                    code=400
                )
            )
        
        @app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            self.logger.error(f"Unhandled exception: {exc}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content=APIResponse.error(
                    message="Internal server error",
                    code=500
                )
            )
    
    def _setup_routes(self, app: FastAPI):
        """Set up default API routes."""
        
        @app.get("/")
        async def root():
            """Root endpoint."""
            return APIResponse.success(
                data={"name": get_config().project_name, "version": "1.0.0"},
                message="Welcome to Ghost Backend API"
            )
        
        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            from .database import get_db_manager, get_redis_manager
            
            health_status = {
                "api": "healthy",
                "timestamp": time.time()
            }
            
            # Check database health
            try:
                db_manager = get_db_manager()
                health_status["database"] = "healthy" if db_manager.health_check() else "unhealthy"
            except Exception as e:
                health_status["database"] = f"error: {str(e)}"
            
            # Check Redis health
            try:
                redis_manager = get_redis_manager()
                health_status["redis"] = "healthy" if redis_manager.health_check() else "unhealthy"
            except Exception as e:
                health_status["redis"] = f"error: {str(e)}"
            
            return APIResponse.success(
                data=health_status,
                message="Health check completed"
            )
        
        @app.get("/metrics")
        @self.limiter.limit("10/minute")
        async def metrics(request: Request):
            """Basic metrics endpoint."""
            return APIResponse.success(
                data={
                    "requests_tracked": len(self.request_tracker.requests),
                    "timestamp": time.time()
                },
                message="Metrics retrieved"
            )
    
    def get_current_user(self, credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))) -> Optional[TokenData]:
        """Dependency to get current authenticated user."""
        if not credentials:
            return None
        
        token_data = self.auth_manager.verify_token(credentials.credentials)
        return token_data
    
    def require_auth(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
        """Dependency to require authentication."""
        token_data = self.auth_manager.verify_token(credentials.credentials)
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid authentication token")
        return token_data
    
    def require_api_key(self, api_key: str = Depends(lambda: None)):
        """Dependency to require API key (implement based on your needs)."""
        if not api_key:
            raise HTTPException(status_code=401, detail="API key required")
        
        token_data = self.auth_manager.verify_api_key(api_key)
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return token_data
    
    def create_router_with_auth(self, **kwargs):
        """Create an APIRouter with authentication middleware."""
        from fastapi import APIRouter
        
        router = APIRouter(**kwargs)
        # Add authentication dependency to all routes in this router
        router.dependencies.append(Depends(self.require_auth))
        return router
    
    def run(
        self, 
        host: Optional[str] = None, 
        port: Optional[int] = None, 
        **kwargs
    ):
        """Run the FastAPI application."""
        import uvicorn
        
        if not self.app:
            raise RuntimeError("App not created. Call create_app() first.")
        
        host = host or self.config.host
        port = port or self.config.port
        
        self.logger.info(f"Starting API server on {host}:{port}")
        
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            reload=self.config.reload,
            workers=self.config.workers,
            **kwargs
        )


# Utility functions for common API patterns
def paginate_query(query, page: int = 1, per_page: int = 20):
    """Paginate a SQLAlchemy query."""
    offset = (page - 1) * per_page
    total = query.count()
    items = query.offset(offset).limit(per_page).all()
    return items, total


def validate_json_payload(required_fields: List[str]):
    """Decorator to validate JSON payload has required fields."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                raise ValueError("Request object not found")
            
            try:
                payload = await request.json()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid JSON payload")
            
            missing_fields = [field for field in required_fields if field not in payload]
            if missing_fields:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Missing required fields: {', '.join(missing_fields)}"
                )
            
            kwargs['payload'] = payload
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# Global API manager instance
_api_manager: Optional[APIManager] = None


def get_api_manager() -> APIManager:
    """Get the global API manager instance."""
    global _api_manager
    if _api_manager is None:
        _api_manager = APIManager()
    return _api_manager
