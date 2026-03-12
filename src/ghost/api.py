"""
API Management Module

Provides FastAPI application setup, middleware configuration, and common API utilities.
Includes rate limiting, CORS, authentication middleware, and response formatting.
"""

from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import time
import uuid
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from .config import get_config
from .logging import LoggerMixin
from .auth import TokenData, get_auth_manager

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST,
    )
    PROMETHEUS_AVAILABLE = True
    REQUEST_COUNT = Counter(
        "ghost_http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )
    REQUEST_LATENCY = Histogram(
        "ghost_http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "endpoint"],
    )
    ACTIVE_REQUESTS = Gauge(
        "ghost_http_requests_active",
        "Currently active HTTP requests",
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    import os as _os

    _otel_endpoint = _os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if _otel_endpoint:
        _resource = Resource.create({
            "service.name": _os.getenv("OTEL_SERVICE_NAME", "ghost-backend"),
        })
        _provider = TracerProvider(resource=_resource)
        _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=_otel_endpoint)))
        trace.set_tracer_provider(_provider)
        OTEL_AVAILABLE = True
    else:
        OTEL_AVAILABLE = False
except ImportError:
    OTEL_AVAILABLE = False


class APIResponse:
    """Standardized API response format."""

    @staticmethod
    def success(
        data: Any = None, message: str = "Success", meta: Optional[Dict] = None
    ):
        """Create a successful response."""
        response = {
            "success": True,
            "message": message,
            "data": data,
            "timestamp": time.time(),
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
            "error": {"code": code, "details": details or {}},
            "timestamp": time.time(),
        }
        return response

    @staticmethod
    def paginated(
        data: List[Any], page: int, per_page: int, total: int, message: str = "Success"
    ):
        """Create a paginated response."""
        return APIResponse.success(
            data=data,
            message=message,
            meta={
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page,
                }
            },
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
            "status": "in_progress",
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
        enable_websockets: bool = True,
        **kwargs,
    ) -> FastAPI:
        """Create and configure FastAPI application."""
        app = FastAPI(
            title=title or get_config().project_name,
            description=description,
            version=version,
            debug=self.config.debug,
            **kwargs,
        )

        self._setup_middleware(app)
        self._setup_exception_handlers(app)
        self._setup_routes(app)

        # Wire WebSocket routes if enabled
        if enable_websockets:
            try:
                from .websocket import add_websocket_routes

                add_websocket_routes(app)
                self.logger.info("WebSocket routes registered")
            except ImportError:
                self.logger.debug("WebSocket module not available, skipping")

        # OpenTelemetry auto-instrumentation
        if OTEL_AVAILABLE:
            FastAPIInstrumentor.instrument_app(app)
            self.logger.info("OpenTelemetry tracing enabled")

        self.app = app
        self.logger.info(f"FastAPI application created: {title}")
        return app

    def _setup_middleware(self, app: FastAPI):
        """Set up middleware stack."""

        # Request tracking middleware with Prometheus metrics
        @app.middleware("http")
        async def request_tracking_middleware(request: Request, call_next):
            request_id = str(uuid.uuid4())
            request.state.request_id = request_id
            start = time.time()

            self.request_tracker.start_request(
                request_id,
                request.url.path,
                request.method,
                request.client.host if request.client else "unknown",
            )

            if PROMETHEUS_AVAILABLE:
                ACTIVE_REQUESTS.inc()

            response = await call_next(request)
            duration = time.time() - start

            self.request_tracker.end_request(request_id, response.status_code)

            if PROMETHEUS_AVAILABLE:
                ACTIVE_REQUESTS.dec()
                endpoint = request.url.path
                REQUEST_COUNT.labels(request.method, endpoint, response.status_code).inc()
                REQUEST_LATENCY.labels(request.method, endpoint).observe(duration)

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response

        # Rate limiting middleware
        app.state.limiter = self.limiter

        @app.exception_handler(RateLimitExceeded)
        async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
            response = JSONResponse(
                status_code=429,
                content=APIResponse.error(message="Rate limit exceeded", code=429),
            )
            # Apply rate limit handler logic if needed
            enhanced_response = _rate_limit_exceeded_handler(request, exc)
            return enhanced_response

        app.add_middleware(SlowAPIMiddleware)

        # CORS middleware — restrict origins in production
        cors_origins = self.config.cors_origins
        if get_config().environment == "production" and cors_origins == ["*"]:
            cors_origins = [
                "https://grayghostdata.com",
                "https://*.grayghostdata.com",
            ]

        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Trusted host middleware for production
        if get_config().environment == "production":
            config = get_config()
            allowed = getattr(config, "allowed_hosts", None) or [
                "grayghostdata.com",
                "*.grayghostdata.com",
                "localhost",
            ]
            app.add_middleware(
                TrustedHostMiddleware,
                allowed_hosts=allowed,
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
                content=APIResponse.error(message=exc.detail, code=exc.status_code),
            )

        @app.exception_handler(ValueError)
        async def value_error_handler(request: Request, exc: ValueError):
            return JSONResponse(
                status_code=400, content=APIResponse.error(message=str(exc), code=400)
            )

        @app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            self.logger.error(f"Unhandled exception: {exc}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content=APIResponse.error(message="Internal server error", code=500),
            )

    def _setup_routes(self, app: FastAPI):
        """Set up default API routes."""

        @app.get("/")
        async def root():
            """Root endpoint."""
            return APIResponse.success(
                data={"name": get_config().project_name, "version": "1.0.0"},
                message="Welcome to Ghost Backend API",
            )

        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            from .database import get_db_manager, get_redis_manager

            health_status = {"api": "healthy", "timestamp": time.time()}

            # Check database health
            try:
                db_manager = get_db_manager()
                health_status["database"] = (
                    "healthy" if db_manager.health_check() else "unhealthy"
                )
            except Exception as e:
                health_status["database"] = f"error: {str(e)}"

            # Check Redis health
            try:
                redis_manager = get_redis_manager()
                health_status["redis"] = (
                    "healthy" if redis_manager.health_check() else "unhealthy"
                )
            except Exception as e:
                health_status["redis"] = f"error: {str(e)}"

            return APIResponse.success(
                data=health_status, message="Health check completed"
            )

        @app.get("/metrics")
        @self.limiter.limit("30/minute")
        async def metrics(request: Request):
            """Prometheus-format metrics endpoint (OpenMetrics)."""
            if PROMETHEUS_AVAILABLE:
                return Response(
                    content=generate_latest(),
                    media_type=CONTENT_TYPE_LATEST,
                )
            # Fallback JSON if prometheus-client not installed
            return APIResponse.success(
                data={
                    "requests_tracked": len(self.request_tracker.requests),
                    "timestamp": time.time(),
                },
                message="Metrics retrieved (install prometheus-client for OpenMetrics format)",
            )

        @app.post("/token")
        @self.limiter.limit("5/minute")
        async def token(request: Request):
            """Refresh access token using a valid refresh token."""
            try:
                body = await request.json()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid JSON payload")

            refresh_token = body.get("refresh_token")
            if not refresh_token:
                raise HTTPException(
                    status_code=400, detail="refresh_token is required"
                )

            new_access = self.auth_manager.refresh_access_token(refresh_token)
            if not new_access:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid or expired refresh token",
                )

            return APIResponse.success(
                data={"access_token": new_access, "token_type": "bearer"},
                message="Token refreshed",
            )

        @app.post("/login")
        @self.limiter.limit("5/minute")
        async def login(request: Request):
            """Authenticate user and return access + refresh tokens.

            Falls back to 501 if database models are not available.
            """
            try:
                from .models import UserRepository
                from .database import get_db_manager
            except ImportError:
                raise HTTPException(
                    status_code=501,
                    detail="Login requires database models. Use project-specific auth routes.",
                )

            try:
                body = await request.json()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid JSON payload")

            username = body.get("username")
            password = body.get("password")
            if not username or not password:
                raise HTTPException(
                    status_code=400,
                    detail="Both 'username' and 'password' are required",
                )

            try:
                db_manager = get_db_manager()
                with db_manager.get_session() as session:
                    repo = UserRepository(session)
                    user = repo.authenticate(username, password)

                    if not user:
                        raise HTTPException(
                            status_code=401, detail="Invalid credentials"
                        )

                    if not user.is_active:
                        raise HTTPException(
                            status_code=403, detail="Account is disabled"
                        )

                    if user.is_locked:
                        raise HTTPException(
                            status_code=403, detail="Account is temporarily locked"
                        )

                    # Build auth.User dataclass for token generation
                    from .auth import User as AuthUser, UserRole

                    role_names = [r.name for r in user.roles] if user.roles else ["user"]
                    auth_user = AuthUser(
                        id=str(user.id),
                        username=user.username,
                        email=user.email,
                        roles=[UserRole(r) for r in role_names],
                    )

                    access_token = self.auth_manager.create_access_token(auth_user)
                    refresh_token = self.auth_manager.create_refresh_token(auth_user)

                    return APIResponse.success(
                        data={
                            "access_token": access_token,
                            "refresh_token": refresh_token,
                            "token_type": "bearer",
                            "user": {
                                "id": str(user.id),
                                "username": user.username,
                                "email": user.email,
                            },
                        },
                        message="Login successful",
                    )
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Login error: {e}")
                raise HTTPException(
                    status_code=501,
                    detail="Login requires a configured database connection.",
                )

        @app.post("/forgot-password")
        @self.limiter.limit("3/minute")
        async def forgot_password(request: Request):
            """Request a password reset token.

            Always returns 200 to prevent email enumeration.
            Level 3 consumers wire this to UserRepository + EmailManager.
            """
            try:
                body = await request.json()
            except Exception:
                # Still return 200 to prevent enumeration
                return APIResponse.success(
                    message="If an account with that email exists, a reset link has been sent."
                )

            # Framework stub — always returns success.
            # Level 3 projects override to look up user and send email.
            return APIResponse.success(
                message="If an account with that email exists, a reset link has been sent."
            )

        @app.post("/reset-password")
        @self.limiter.limit("5/minute")
        async def reset_password(request: Request):
            """Reset password using a valid reset token.

            Validates the token and returns the verified user_id.
            Level 3 consumers wire this to User.set_password().
            """
            try:
                body = await request.json()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid JSON payload")

            token = body.get("token")
            new_password = body.get("new_password")

            if not token or not new_password:
                raise HTTPException(
                    status_code=400,
                    detail="Both 'token' and 'new_password' are required",
                )

            result = self.auth_manager.verify_reset_token(token)
            if not result:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid or expired reset token",
                )

            return APIResponse.success(
                data={"user_id": result["user_id"]},
                message="Password reset token verified. Level 3 consumer should update the password.",
            )

    def get_current_user(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(
            HTTPBearer(auto_error=False)
        ),
    ) -> Optional[TokenData]:
        """Dependency to get current authenticated user."""
        if not credentials:
            return None

        token_data = self.auth_manager.verify_token(credentials.credentials)
        return token_data

    def require_auth(
        self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
    ):
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

    def run(self, host: Optional[str] = None, port: Optional[int] = None, **kwargs):
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
            **kwargs,
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

            missing_fields = [
                field for field in required_fields if field not in payload
            ]
            if missing_fields:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required fields: {', '.join(missing_fields)}",
                )

            kwargs["payload"] = payload
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
