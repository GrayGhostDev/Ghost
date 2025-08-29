#!/usr/bin/env python3
"""
Ghost Backend Framework - Architecture & Scalability Review
Comprehensive analysis of backend implementation completeness and scalability.
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
import subprocess
import json

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class BackendArchitectureReview:
    """Comprehensive backend architecture and scalability reviewer."""
    
    def __init__(self):
        self.base_path = Path(__file__).parent.parent
        self.review_results = {}
    
    def analyze_core_architecture(self) -> Dict[str, Any]:
        """Analyze core architectural patterns and completeness."""
        results = {
            "layered_architecture": self._check_layered_architecture(),
            "separation_of_concerns": self._check_separation_of_concerns(),
            "dependency_injection": self._check_dependency_injection(),
            "configuration_management": self._check_configuration_management(),
            "error_handling": self._check_error_handling(),
            "logging_strategy": self._check_logging_strategy(),
        }
        return results
    
    def analyze_scalability_factors(self) -> Dict[str, Any]:
        """Analyze scalability and performance considerations."""
        results = {
            "database_optimization": self._check_database_optimization(),
            "caching_strategy": self._check_caching_strategy(),
            "async_support": self._check_async_support(),
            "connection_pooling": self._check_connection_pooling(),
            "rate_limiting": self._check_rate_limiting(),
            "horizontal_scaling": self._check_horizontal_scaling(),
            "monitoring_observability": self._check_monitoring(),
        }
        return results
    
    def analyze_security_implementation(self) -> Dict[str, Any]:
        """Analyze security implementations and best practices."""
        results = {
            "authentication": self._check_authentication(),
            "authorization": self._check_authorization(),
            "input_validation": self._check_input_validation(),
            "cors_security": self._check_cors_security(),
            "secrets_management": self._check_secrets_management(),
            "sql_injection_protection": self._check_sql_injection_protection(),
        }
        return results
    
    def analyze_development_experience(self) -> Dict[str, Any]:
        """Analyze developer experience and maintainability."""
        results = {
            "code_organization": self._check_code_organization(),
            "testing_infrastructure": self._check_testing_infrastructure(),
            "documentation": self._check_documentation(),
            "type_hints": self._check_type_hints(),
            "development_tools": self._check_development_tools(),
            "api_documentation": self._check_api_documentation(),
        }
        return results
    
    def analyze_production_readiness(self) -> Dict[str, Any]:
        """Analyze production readiness factors."""
        results = {
            "containerization": self._check_containerization(),
            "environment_configuration": self._check_environment_config(),
            "health_checks": self._check_health_checks(),
            "graceful_shutdown": self._check_graceful_shutdown(),
            "backup_recovery": self._check_backup_recovery(),
            "deployment_automation": self._check_deployment_automation(),
        }
        return results
    
    def analyze_multi_frontend_integration(self) -> Dict[str, Any]:
        """Analyze multi-frontend support capabilities."""
        results = {
            "frontend_detection": self._check_frontend_detection(),
            "cors_configuration": self._check_cors_configuration(),
            "api_versioning": self._check_api_versioning(),
            "websocket_support": self._check_websocket_support(),
            "frontend_specific_routing": self._check_frontend_routing(),
            "development_integration": self._check_development_integration(),
        }
        return results
    
    # Core Architecture Checks
    def _check_layered_architecture(self) -> Dict[str, Any]:
        """Check if proper layered architecture is implemented."""
        layers = {
            "presentation": (self.base_path / "src" / "ghost" / "api.py").exists(),
            "business_logic": (self.base_path / "src" / "ghost" / "auth.py").exists(),
            "data_access": (self.base_path / "src" / "ghost" / "database.py").exists(),
            "configuration": (self.base_path / "src" / "ghost" / "config.py").exists(),
            "utilities": (self.base_path / "src" / "ghost" / "utils.py").exists(),
        }
        score = sum(layers.values()) / len(layers)
        return {
            "score": score,
            "status": "excellent" if score >= 0.9 else "good" if score >= 0.7 else "needs_improvement",
            "layers": layers,
            "recommendation": "All core layers present" if score >= 0.9 else "Consider adding missing layers"
        }
    
    def _check_separation_of_concerns(self) -> Dict[str, Any]:
        """Check separation of concerns implementation."""
        concerns = {
            "config_separate": self._file_contains("src/ghost/config.py", "class.*Config"),
            "auth_separate": self._file_contains("src/ghost/auth.py", "class.*Auth"),
            "database_separate": self._file_contains("src/ghost/database.py", "class.*Database"),
            "api_separate": self._file_contains("src/ghost/api.py", "class.*API"),
            "logging_separate": self._file_contains("src/ghost/logging.py", "class.*Log"),
        }
        score = sum(concerns.values()) / len(concerns)
        return {
            "score": score,
            "status": "excellent" if score >= 0.8 else "good" if score >= 0.6 else "needs_improvement",
            "concerns": concerns
        }
    
    def _check_dependency_injection(self) -> Dict[str, Any]:
        """Check dependency injection patterns."""
        patterns = {
            "config_injection": self._file_contains("src/ghost", "get_config()"),
            "logger_injection": self._file_contains("src/ghost", "get_logger"),
            "db_injection": self._file_contains("src/ghost", "get_db_manager"),
            "manager_pattern": self._file_contains("src/ghost", "Manager"),
        }
        score = sum(patterns.values()) / len(patterns)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "patterns": patterns
        }
    
    def _check_configuration_management(self) -> Dict[str, Any]:
        """Check configuration management implementation."""
        config_features = {
            "env_support": (self.base_path / ".env").exists(),
            "yaml_support": any(self.base_path.glob("config*.yaml")),
            "env_specific": (self.base_path / ".env.production.example").exists(),
            "config_validation": self._file_contains("src/ghost/config.py", "dataclass"),
            "secrets_handling": self._file_contains("src/ghost/config.py", "password|secret"),
        }
        score = sum(config_features.values()) / len(config_features)
        return {
            "score": score,
            "status": "excellent" if score >= 0.8 else "good" if score >= 0.6 else "needs_improvement",
            "features": config_features
        }
    
    def _check_error_handling(self) -> Dict[str, Any]:
        """Check error handling implementation."""
        error_handling = {
            "custom_exceptions": self._file_contains("src/ghost", "Exception|Error"),
            "try_catch_blocks": self._file_contains("src/ghost", "try:|except:"),
            "error_responses": self._file_contains("src/ghost/api.py", "error|Error"),
            "logging_errors": self._file_contains("src/ghost", "logger.error|self.logger.error"),
        }
        score = sum(error_handling.values()) / len(error_handling)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": error_handling
        }
    
    def _check_logging_strategy(self) -> Dict[str, Any]:
        """Check logging strategy implementation."""
        logging_features = {
            "structured_logging": self._file_contains("src/ghost/logging.py", "json|structured"),
            "log_levels": self._file_contains("src/ghost/logging.py", "INFO|DEBUG|ERROR|WARNING"),
            "log_rotation": self._file_contains("src/ghost/logging.py", "rotation|RotatingFileHandler"),
            "contextual_logging": self._file_contains("src/ghost", "LoggerMixin|get_logger"),
        }
        score = sum(logging_features.values()) / len(logging_features)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": logging_features
        }
    
    # Scalability Checks
    def _check_database_optimization(self) -> Dict[str, Any]:
        """Check database optimization features."""
        optimizations = {
            "connection_pooling": self._file_contains("src/ghost/database.py", "pool_size|QueuePool"),
            "async_support": self._file_contains("src/ghost/database.py", "async|AsyncSession"),
            "query_optimization": self._file_contains("src/ghost/database.py", "index|Index"),
            "migration_support": (self.base_path / "scripts" / "database_migrations.py").exists(),
            "database_health_checks": self._file_contains("src/ghost", "health|ping"),
        }
        score = sum(optimizations.values()) / len(optimizations)
        return {
            "score": score,
            "status": "excellent" if score >= 0.8 else "good" if score >= 0.6 else "needs_improvement",
            "optimizations": optimizations
        }
    
    def _check_caching_strategy(self) -> Dict[str, Any]:
        """Check caching implementation."""
        caching = {
            "redis_integration": self._file_contains("src/ghost", "redis|Redis"),
            "cache_configuration": self._file_contains("src/ghost/config.py", "redis|cache"),
            "cache_utilities": self._file_contains("src/ghost/utils.py", "cache|Cache"),
            "session_caching": self._file_contains("src/ghost", "session.*cache|cache.*session"),
        }
        score = sum(caching.values()) / len(caching)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": caching
        }
    
    def _check_async_support(self) -> Dict[str, Any]:
        """Check asynchronous programming support."""
        async_features = {
            "async_database": self._file_contains("src/ghost/database.py", "async def|AsyncSession"),
            "async_api": self._file_contains("src/ghost/api.py", "async def"),
            "async_context_managers": self._file_contains("src/ghost", "@asynccontextmanager|asynccontextmanager"),
            "async_middleware": self._file_contains("src/ghost/api.py", "async.*middleware"),
        }
        score = sum(async_features.values()) / len(async_features)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": async_features
        }
    
    def _check_connection_pooling(self) -> Dict[str, Any]:
        """Check connection pooling configuration."""
        pooling = {
            "database_pooling": self._file_contains("src/ghost/database.py", "pool_size|poolclass"),
            "redis_pooling": self._file_contains("src/ghost", "ConnectionPool|pool"),
            "pool_configuration": self._file_contains("src/ghost/config.py", "pool_size|max_overflow"),
            "pool_monitoring": self._file_contains("src/ghost", "pool.*status|pool.*health"),
        }
        score = sum(pooling.values()) / len(pooling)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": pooling
        }
    
    def _check_rate_limiting(self) -> Dict[str, Any]:
        """Check rate limiting implementation."""
        rate_limiting = {
            "api_rate_limiting": self._file_contains("src/ghost/api.py", "Limiter|rate_limit|slowapi"),
            "rate_limit_middleware": self._file_contains("src/ghost/api.py", "SlowAPIMiddleware|RateLimitExceeded"),
            "configurable_limits": self._file_contains("config", "rate|limit"),
            "frontend_specific_limits": self._file_contains("config", "frontend.*rate|rate.*frontend"),
        }
        score = sum(rate_limiting.values()) / len(rate_limiting)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": rate_limiting
        }
    
    def _check_horizontal_scaling(self) -> Dict[str, Any]:
        """Check horizontal scaling readiness."""
        scaling = {
            "stateless_design": not self._file_contains("src/ghost", "global.*state|class.*singleton"),
            "docker_support": (self.base_path / "docker-compose.yml").exists(),
            "config_externalization": (self.base_path / ".env").exists(),
            "load_balancer_ready": self._file_contains("src/ghost", "health.*check|/health"),
            "session_externalization": self._file_contains("src/ghost", "redis.*session|session.*redis"),
        }
        score = sum(scaling.values()) / len(scaling)
        return {
            "score": score,
            "status": "excellent" if score >= 0.8 else "good" if score >= 0.6 else "needs_improvement",
            "features": scaling
        }
    
    def _check_monitoring(self) -> Dict[str, Any]:
        """Check monitoring and observability."""
        monitoring = {
            "health_endpoints": self._file_contains("src/ghost", "/health|health_check"),
            "metrics_collection": self._file_contains("src/ghost", "metrics|prometheus"),
            "structured_logging": self._file_contains("src/ghost/logging.py", "json|structured"),
            "error_tracking": self._file_contains("src/ghost", "sentry|error.*tracking"),
            "performance_monitoring": self._file_contains("src/ghost/api.py", "time|duration|performance"),
        }
        score = sum(monitoring.values()) / len(monitoring)
        return {
            "score": score,
            "status": "excellent" if score >= 0.8 else "good" if score >= 0.6 else "needs_improvement",
            "features": monitoring
        }
    
    # Security Checks
    def _check_authentication(self) -> Dict[str, Any]:
        """Check authentication implementation."""
        auth_features = {
            "jwt_tokens": self._file_contains("src/ghost/auth.py", "JWT|jwt|token"),
            "password_hashing": self._file_contains("src/ghost/auth.py", "bcrypt|hash|password"),
            "token_validation": self._file_contains("src/ghost/auth.py", "verify.*token|validate.*token"),
            "auth_middleware": self._file_contains("src/ghost/api.py", "auth.*middleware|HTTPBearer"),
        }
        score = sum(auth_features.values()) / len(auth_features)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": auth_features
        }
    
    def _check_authorization(self) -> Dict[str, Any]:
        """Check authorization (RBAC) implementation."""
        authz_features = {
            "role_based_access": self._file_contains("src/ghost/auth.py", "role|Role|RBAC"),
            "permission_system": self._file_contains("src/ghost/auth.py", "permission|Permission"),
            "access_control": self._file_contains("src/ghost/api.py", "require.*role|check.*permission"),
            "user_roles": self._file_contains("src/ghost/auth.py", "UserRole|user.*role"),
        }
        score = sum(authz_features.values()) / len(authz_features)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": authz_features
        }
    
    def _check_input_validation(self) -> Dict[str, Any]:
        """Check input validation implementation."""
        validation = {
            "pydantic_models": self._file_contains("src/ghost", "BaseModel|pydantic"),
            "request_validation": self._file_contains("src/ghost/api.py", "validate|validation"),
            "sanitization": self._file_contains("src/ghost", "sanitize|clean|escape"),
            "type_checking": self._file_contains("src/ghost", "typing|Type|Optional"),
        }
        score = sum(validation.values()) / len(validation)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": validation
        }
    
    def _check_cors_security(self) -> Dict[str, Any]:
        """Check CORS security implementation."""
        cors_security = {
            "cors_middleware": self._file_contains("src/ghost/api.py", "CORSMiddleware|CORS"),
            "origin_validation": self._file_contains("src/ghost", "allowed.*origin|origin.*validation"),
            "dynamic_cors": self._file_contains("backend_manager.py", "setup_cors|cors.*config"),
            "secure_defaults": self._file_contains("src/ghost/api.py", "credentials|allow_credentials"),
        }
        score = sum(cors_security.values()) / len(cors_security)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": cors_security
        }
    
    def _check_secrets_management(self) -> Dict[str, Any]:
        """Check secrets management."""
        secrets = {
            "env_secrets": (self.base_path / ".env").exists(),
            "keychain_integration": self._file_contains("scripts", "keychain|security"),
            "secret_validation": self._file_contains("src/ghost/config.py", "required.*secret|secret.*required"),
            "no_hardcoded_secrets": not self._file_contains("src/ghost", "password.*=.*['\"]|secret.*=.*['\"]"),
        }
        score = sum(secrets.values()) / len(secrets)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": secrets
        }
    
    def _check_sql_injection_protection(self) -> Dict[str, Any]:
        """Check SQL injection protection."""
        protection = {
            "orm_usage": self._file_contains("src/ghost/database.py", "SQLAlchemy|ORM|query"),
            "parameterized_queries": self._file_contains("src/ghost", "bind|parameter|:"),
            "input_sanitization": self._file_contains("src/ghost", "sanitize|escape|clean"),
            "no_string_concatenation": not self._file_contains("src/ghost", "SELECT.*\\+|query.*\\+.*string"),
        }
        score = sum(protection.values()) / len(protection)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": protection
        }
    
    # Development Experience Checks
    def _check_code_organization(self) -> Dict[str, Any]:
        """Check code organization and structure."""
        organization = {
            "modular_structure": len(list((self.base_path / "src" / "ghost").glob("*.py"))) >= 5,
            "clear_naming": self._file_contains("src/ghost", "Manager|Config|Utils"),
            "separation_by_concern": all((self.base_path / "src" / "ghost" / f).exists() 
                                       for f in ["api.py", "database.py", "auth.py", "config.py"]),
            "script_organization": (self.base_path / "scripts").exists(),
        }
        score = sum(organization.values()) / len(organization)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": organization
        }
    
    def _check_testing_infrastructure(self) -> Dict[str, Any]:
        """Check testing infrastructure."""
        testing = {
            "test_directory": (self.base_path / "tests").exists(),
            "pytest_config": (self.base_path / "pyproject.toml").exists(),
            "test_fixtures": self._file_contains("tests", "fixture|@pytest"),
            "coverage_config": self._file_contains("pyproject.toml", "coverage|cov"),
        }
        score = sum(testing.values()) / len(testing)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": testing
        }
    
    def _check_documentation(self) -> Dict[str, Any]:
        """Check documentation quality."""
        documentation = {
            "readme_exists": (self.base_path / "README.md").exists(),
            "docs_directory": (self.base_path / "docs").exists(),
            "api_docstrings": self._file_contains("src/ghost", '""".*"""'),
            "examples_directory": (self.base_path / "examples").exists(),
        }
        score = sum(documentation.values()) / len(documentation)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": documentation
        }
    
    def _check_type_hints(self) -> Dict[str, Any]:
        """Check type hints usage."""
        type_hints = {
            "function_annotations": self._file_contains("src/ghost", "def.*->|: .*="),
            "typing_imports": self._file_contains("src/ghost", "from typing import|import typing"),
            "generic_types": self._file_contains("src/ghost", "Dict|List|Optional|Union"),
            "class_type_hints": self._file_contains("src/ghost", "self\\..*: .*=|: .*Type"),
        }
        score = sum(type_hints.values()) / len(type_hints)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": type_hints
        }
    
    def _check_development_tools(self) -> Dict[str, Any]:
        """Check development tools and utilities."""
        dev_tools = {
            "makefile": (self.base_path / "Makefile").exists(),
            "dev_scripts": len(list((self.base_path / "scripts").glob("*.py"))) > 0 if (self.base_path / "scripts").exists() else False,
            "development_env": (self.base_path / ".env.example").exists(),
            "pre_commit": (self.base_path / ".pre-commit-config.yaml").exists(),
        }
        score = sum(dev_tools.values()) / len(dev_tools)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": dev_tools
        }
    
    def _check_api_documentation(self) -> Dict[str, Any]:
        """Check API documentation features."""
        api_docs = {
            "openapi_support": self._file_contains("src/ghost/api.py", "openapi|OpenAPI"),
            "swagger_ui": self._file_contains("src/ghost/api.py", "/docs|swagger"),
            "redoc_support": self._file_contains("src/ghost/api.py", "/redoc|ReDoc"),
            "endpoint_descriptions": self._file_contains("src/ghost", "description=|summary="),
        }
        score = sum(api_docs.values()) / len(api_docs)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": api_docs
        }
    
    # Production Readiness Checks
    def _check_containerization(self) -> Dict[str, Any]:
        """Check containerization support."""
        containerization = {
            "dockerfile": (self.base_path / "Dockerfile").exists(),
            "docker_compose": (self.base_path / "docker-compose.yml").exists(),
            "dockerignore": (self.base_path / ".dockerignore").exists(),
            "multi_stage_build": self._file_contains("Dockerfile", "FROM.*as|stage"),
        }
        score = sum(containerization.values()) / len(containerization)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": containerization
        }
    
    def _check_environment_config(self) -> Dict[str, Any]:
        """Check environment configuration management."""
        env_config = {
            "env_examples": (self.base_path / ".env.example").exists(),
            "production_config": (self.base_path / ".env.production.example").exists(),
            "yaml_configs": len(list(self.base_path.glob("config*.yaml"))) > 0,
            "environment_detection": self._file_contains("src/ghost/config.py", "ENVIRONMENT|environment"),
        }
        score = sum(env_config.values()) / len(env_config)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": env_config
        }
    
    def _check_health_checks(self) -> Dict[str, Any]:
        """Check health check implementation."""
        health_checks = {
            "health_endpoint": self._file_contains("src/ghost", "/health|health_check"),
            "database_health": self._file_contains("src/ghost", "database.*health|health.*database"),
            "redis_health": self._file_contains("src/ghost", "redis.*health|health.*redis"),
            "comprehensive_health": self._file_contains("src/ghost", "status.*check|system.*health"),
        }
        score = sum(health_checks.values()) / len(health_checks)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": health_checks
        }
    
    def _check_graceful_shutdown(self) -> Dict[str, Any]:
        """Check graceful shutdown implementation."""
        shutdown = {
            "signal_handling": self._file_contains("src/ghost", "signal|Signal|SIGTERM"),
            "cleanup_handlers": self._file_contains("src/ghost", "cleanup|shutdown|close"),
            "connection_draining": self._file_contains("src/ghost", "drain|graceful"),
            "uvicorn_lifecycle": self._file_contains("src/ghost", "startup|shutdown|lifespan"),
        }
        score = sum(shutdown.values()) / len(shutdown)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": shutdown
        }
    
    def _check_backup_recovery(self) -> Dict[str, Any]:
        """Check backup and recovery capabilities."""
        backup = {
            "migration_scripts": (self.base_path / "scripts" / "database_migrations.py").exists(),
            "backup_scripts": self._file_contains("scripts", "backup|dump"),
            "recovery_docs": self._file_contains("docs", "backup|recovery|restore"),
            "data_seeding": self._file_contains("scripts", "seed|sample.*data"),
        }
        score = sum(backup.values()) / len(backup)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": backup
        }
    
    def _check_deployment_automation(self) -> Dict[str, Any]:
        """Check deployment automation."""
        deployment = {
            "makefile_targets": self._file_contains("Makefile", "deploy|build|run"),
            "deployment_scripts": self._file_contains("scripts", "deploy|setup"),
            "ci_cd_config": any(self.base_path.glob(".github/workflows/*.yml")),
            "deployment_docs": (self.base_path / "docs" / "DEPLOYMENT_GUIDE.md").exists(),
        }
        score = sum(deployment.values()) / len(deployment)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": deployment
        }
    
    # Multi-Frontend Integration Checks
    def _check_frontend_detection(self) -> Dict[str, Any]:
        """Check frontend detection capabilities."""
        detection = {
            "detection_script": (self.base_path / "scripts" / "frontend_detector.py").exists(),
            "framework_support": self._file_contains("tools/scripts/frontend_detector.py", "react|angular|vue"),
            "config_generation": self._file_contains("tools/scripts/frontend_detector.py", "generate.*config|save_config"),
            "env_generation": self._file_contains("tools/scripts/frontend_detector.py", "generate.*env|env.*file"),
        }
        score = sum(detection.values()) / len(detection)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": detection
        }
    
    def _check_cors_configuration(self) -> Dict[str, Any]:
        """Check CORS configuration for multi-frontend."""
        cors_config = {
            "dynamic_cors": self._file_contains("backend_manager.py", "setup_cors|cors.*config"),
            "frontend_specific": self._file_contains("config", "cors.*origin|allowed.*origin"),
            "cors_middleware": self._file_contains("src/ghost/api.py", "CORSMiddleware"),
            "origin_validation": self._file_contains("backend_manager.py", "origin.*validation|validate.*origin"),
        }
        score = sum(cors_config.values()) / len(cors_config)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": cors_config
        }
    
    def _check_api_versioning(self) -> Dict[str, Any]:
        """Check API versioning support."""
        versioning = {
            "version_prefix": self._file_contains("src/ghost", "v1|version|api.*v"),
            "versioned_routes": self._file_contains("backend_manager.py", "api.*prefix|prefix.*api"),
            "frontend_specific_routes": self._file_contains("backend_manager.py", "frontend.*route|route.*frontend"),
            "version_header": self._file_contains("src/ghost/api.py", "version.*header|api.*version"),
        }
        score = sum(versioning.values()) / len(versioning)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": versioning
        }
    
    def _check_websocket_support(self) -> Dict[str, Any]:
        """Check WebSocket support for real-time features."""
        websocket = {
            "websocket_implementation": (self.base_path / "src" / "ghost" / "websocket.py").exists(),
            "websocket_manager": self._file_contains("src/ghost/websocket.py", "WebSocketManager|WebSocket"),
            "channel_support": self._file_contains("src/ghost/websocket.py", "channel|subscribe"),
            "frontend_specific_ws": self._file_contains("config", "websocket|realtime"),
        }
        score = sum(websocket.values()) / len(websocket)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": websocket
        }
    
    def _check_frontend_routing(self) -> Dict[str, Any]:
        """Check frontend-specific routing."""
        routing = {
            "dynamic_routing": self._file_contains("backend_manager.py", "create.*route|route.*mapping"),
            "prefix_support": self._file_contains("backend_manager.py", "api.*prefix|prefix.*api"),
            "route_configuration": self._file_contains("config", "route|path|prefix"),
            "middleware_routing": self._file_contains("backend_manager.py", "middleware.*route|route.*middleware"),
        }
        score = sum(routing.values()) / len(routing)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": routing
        }
    
    def _check_development_integration(self) -> Dict[str, Any]:
        """Check development environment integration."""
        integration = {
            "multi_backend_manager": (self.base_path / "backend_manager.py").exists(),
            "frontend_watcher": (self.base_path / "scripts" / "frontend_watcher.py").exists(),
            "auto_reload": self._file_contains("backend_manager.py", "reload|watch"),
            "development_startup": (self.base_path / "start_multi_backend.py").exists(),
        }
        score = sum(integration.values()) / len(integration)
        return {
            "score": score,
            "status": "excellent" if score >= 0.75 else "good" if score >= 0.5 else "needs_improvement",
            "features": integration
        }
    
    # Helper Methods
    def _file_contains(self, path_pattern: str, regex_pattern: str) -> bool:
        """Check if any file matching path_pattern contains the regex_pattern."""
        import re
        import glob
        
        if "/" in path_pattern:
            # Specific file
            file_path = self.base_path / path_pattern
            if file_path.exists():
                try:
                    content = file_path.read_text()
                    return bool(re.search(regex_pattern, content, re.IGNORECASE))
                except:
                    pass
        else:
            # Pattern matching
            for file_path in self.base_path.glob(f"**/{path_pattern}*"):
                if file_path.is_file():
                    try:
                        content = file_path.read_text()
                        if re.search(regex_pattern, content, re.IGNORECASE):
                            return True
                    except:
                        continue
        return False
    
    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate a comprehensive architecture review report."""
        print("🔍 Analyzing Ghost Backend Framework Architecture...")
        print("=" * 60)
        
        # Run all analyses
        core_arch = self.analyze_core_architecture()
        scalability = self.analyze_scalability_factors()
        security = self.analyze_security_implementation()
        dev_exp = self.analyze_development_experience()
        production = self.analyze_production_readiness()
        multi_frontend = self.analyze_multi_frontend_integration()
        
        # Calculate overall scores
        categories = {
            "Core Architecture": core_arch,
            "Scalability": scalability,
            "Security": security,
            "Developer Experience": dev_exp,
            "Production Readiness": production,
            "Multi-Frontend Integration": multi_frontend
        }
        
        # Generate report
        report = {
            "overall_assessment": self._calculate_overall_assessment(categories),
            "categories": categories,
            "recommendations": self._generate_recommendations(categories),
            "missing_critical_features": self._identify_missing_critical_features(categories),
            "scalability_bottlenecks": self._identify_scalability_bottlenecks(categories),
            "security_concerns": self._identify_security_concerns(categories)
        }
        
        return report
    
    def _calculate_overall_assessment(self, categories: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall assessment score and status."""
        total_score = 0
        category_scores = []
        
        for category_name, category_data in categories.items():
            category_score = sum(item["score"] for item in category_data.values()) / len(category_data)
            category_scores.append(category_score)
            total_score += category_score
        
        overall_score = total_score / len(categories)
        
        if overall_score >= 0.85:
            status = "🎉 EXCELLENT - Production Ready"
            readiness = "production_ready"
        elif overall_score >= 0.75:
            status = "🎯 VERY GOOD - Minor Improvements Needed"
            readiness = "near_production"
        elif overall_score >= 0.65:
            status = "✅ GOOD - Some Enhancements Required"
            readiness = "development_ready"
        elif overall_score >= 0.5:
            status = "⚠️ FAIR - Significant Improvements Needed"
            readiness = "needs_work"
        else:
            status = "❌ POOR - Major Architectural Changes Required"
            readiness = "major_refactor_needed"
        
        return {
            "score": overall_score,
            "status": status,
            "readiness": readiness,
            "category_scores": dict(zip(categories.keys(), category_scores))
        }
    
    def _generate_recommendations(self, categories: Dict[str, Any]) -> List[str]:
        """Generate specific recommendations based on analysis."""
        recommendations = []
        
        for category_name, category_data in categories.items():
            for feature_name, feature_data in category_data.items():
                if feature_data["score"] < 0.7:
                    recommendations.append(
                        f"{category_name}: Improve {feature_name.replace('_', ' ')} "
                        f"(current score: {feature_data['score']:.2f})"
                    )
        
        return recommendations[:10]  # Top 10 recommendations
    
    def _identify_missing_critical_features(self, categories: Dict[str, Any]) -> List[str]:
        """Identify missing critical features."""
        critical_features = []
        
        # Check for critical security features
        security = categories["Security"]
        if security["authentication"]["score"] < 0.8:
            critical_features.append("Authentication system needs strengthening")
        if security["authorization"]["score"] < 0.7:
            critical_features.append("Authorization/RBAC system needs improvement")
        
        # Check for critical scalability features
        scalability = categories["Scalability"]
        if scalability["database_optimization"]["score"] < 0.7:
            critical_features.append("Database optimization features missing")
        if scalability["caching_strategy"]["score"] < 0.6:
            critical_features.append("Caching strategy needs implementation")
        
        # Check for critical production features
        production = categories["Production Readiness"]
        if production["health_checks"]["score"] < 0.7:
            critical_features.append("Health check system needs improvement")
        if production["monitoring_observability"]["score"] < 0.6:
            critical_features.append("Monitoring and observability features missing")
        
        return critical_features
    
    def _identify_scalability_bottlenecks(self, categories: Dict[str, Any]) -> List[str]:
        """Identify potential scalability bottlenecks."""
        bottlenecks = []
        
        scalability = categories["Scalability"]
        
        if scalability["connection_pooling"]["score"] < 0.7:
            bottlenecks.append("Database connection pooling not optimized")
        if scalability["caching_strategy"]["score"] < 0.6:
            bottlenecks.append("Lack of proper caching strategy")
        if scalability["async_support"]["score"] < 0.7:
            bottlenecks.append("Limited asynchronous operation support")
        if scalability["rate_limiting"]["score"] < 0.6:
            bottlenecks.append("Rate limiting not properly implemented")
        if scalability["horizontal_scaling"]["score"] < 0.7:
            bottlenecks.append("Architecture not optimized for horizontal scaling")
        
        return bottlenecks
    
    def _identify_security_concerns(self, categories: Dict[str, Any]) -> List[str]:
        """Identify security concerns."""
        concerns = []
        
        security = categories["Security"]
        
        if security["input_validation"]["score"] < 0.7:
            concerns.append("Input validation needs strengthening")
        if security["secrets_management"]["score"] < 0.7:
            concerns.append("Secrets management could be improved")
        if security["cors_security"]["score"] < 0.7:
            concerns.append("CORS security configuration needs review")
        if security["sql_injection_protection"]["score"] < 0.8:
            concerns.append("SQL injection protection needs verification")
        
        return concerns
    
    def print_detailed_report(self, report: Dict[str, Any]) -> None:
        """Print a detailed, formatted report."""
        print("\\n" + "=" * 80)
        print("🏗️  GHOST BACKEND FRAMEWORK - COMPREHENSIVE ARCHITECTURE REVIEW")
        print("=" * 80)
        
        # Overall Assessment
        overall = report["overall_assessment"]
        print(f"\\n🎯 OVERALL ASSESSMENT: {overall['status']}")
        print(f"📊 Overall Score: {overall['score']:.2f}/1.00 ({overall['score']*100:.1f}%)")
        print(f"🚀 Readiness Level: {overall['readiness'].replace('_', ' ').title()}")
        
        # Category Breakdown
        print("\\n📋 CATEGORY BREAKDOWN:")
        print("-" * 50)
        for category, score in overall["category_scores"].items():
            status_emoji = "🎉" if score >= 0.85 else "🎯" if score >= 0.75 else "✅" if score >= 0.65 else "⚠️" if score >= 0.5 else "❌"
            print(f"{status_emoji} {category:<25} {score:.2f}/1.00 ({score*100:.1f}%)")
        
        # Detailed Category Analysis
        for category_name, category_data in report["categories"].items():
            print(f"\\n🔍 {category_name.upper()} ANALYSIS:")
            print("-" * 40)
            for feature_name, feature_data in category_data.items():
                status_emoji = "✅" if feature_data["score"] >= 0.75 else "⚠️" if feature_data["score"] >= 0.5 else "❌"
                feature_display = feature_name.replace("_", " ").title()
                print(f"{status_emoji} {feature_display:<30} {feature_data['score']:.2f} ({feature_data['status']})")
        
        # Critical Issues
        if report["missing_critical_features"]:
            print("\\n🚨 MISSING CRITICAL FEATURES:")
            print("-" * 40)
            for feature in report["missing_critical_features"]:
                print(f"❌ {feature}")
        
        # Scalability Bottlenecks
        if report["scalability_bottlenecks"]:
            print("\\n🔧 SCALABILITY BOTTLENECKS:")
            print("-" * 40)
            for bottleneck in report["scalability_bottlenecks"]:
                print(f"⚠️ {bottleneck}")
        
        # Security Concerns
        if report["security_concerns"]:
            print("\\n🔒 SECURITY CONCERNS:")
            print("-" * 40)
            for concern in report["security_concerns"]:
                print(f"🚨 {concern}")
        
        # Top Recommendations
        if report["recommendations"]:
            print("\\n💡 TOP RECOMMENDATIONS:")
            print("-" * 40)
            for i, recommendation in enumerate(report["recommendations"][:5], 1):
                print(f"{i}. {recommendation}")
        
        # Final Summary
        print("\\n" + "=" * 80)
        readiness = overall["readiness"]
        if readiness == "production_ready":
            print("🎉 CONCLUSION: Your backend is PRODUCTION READY with excellent architecture!")
            print("   Minor optimizations recommended, but ready for production deployment.")
        elif readiness == "near_production":
            print("🎯 CONCLUSION: Your backend is VERY GOOD with minor improvements needed.")
            print("   Address the recommendations above for full production readiness.")
        elif readiness == "development_ready":
            print("✅ CONCLUSION: Your backend is SOLID for development with some enhancements needed.")
            print("   Good foundation, focus on scalability and security improvements.")
        elif readiness == "needs_work":
            print("⚠️ CONCLUSION: Your backend needs SIGNIFICANT IMPROVEMENTS before production.")
            print("   Focus on critical features and architectural enhancements.")
        else:
            print("❌ CONCLUSION: Your backend requires MAJOR ARCHITECTURAL CHANGES.")
            print("   Consider redesigning core components before proceeding.")
        
        print("=" * 80)


def main():
    """Main function to run the comprehensive architecture review."""
    reviewer = BackendArchitectureReview()
    report = reviewer.generate_comprehensive_report()
    reviewer.print_detailed_report(report)
    
    # Save detailed report to file
    import json
    report_file = Path(__file__).parent.parent / "architecture_review_report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\\n📄 Detailed report saved to: {report_file}")


if __name__ == "__main__":
    main()
