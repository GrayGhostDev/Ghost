# Ghost Backend API - Dedicated Port Management

This directory contains scripts for managing the Ghost Backend API with exclusive access to ports 8000 and 8001.

## Available Scripts

### `./run_api.sh` 
**Main API Server (Default: Port 8000)**
- Automatically cleans up any processes using ports 8000/8001 before starting
- Loads secure credentials from macOS Keychain
- Runs on port 8000 by default (configurable via API_PORT environment variable)
- Includes graceful shutdown handling

### `./run_api_8001.sh`
**Alternate Port Server (Port 8001)**
- Same as main script but forces port 8001
- Useful for running multiple instances or testing

### `./stop_api.sh`
**Clean Shutdown**
- Gracefully stops all Ghost Backend API instances
- Attempts SIGTERM first, then SIGKILL if needed
- Frees up both ports 8000 and 8001

## Usage Examples

```bash
# Start the API on default port (8000)
./run_api.sh

# Start the API on port 8001 
./run_api_8001.sh

# Stop all running APIs
./stop_api.sh

# Start with custom port
API_PORT=8000 ./run_api.sh
```

## Port Management

The scripts ensure **exclusive access** to ports 8000 and 8001 by:
1. Checking for existing processes on these ports
2. Cleanly terminating any conflicting processes
3. Waiting for ports to be fully available
4. Starting the Ghost Backend API with dedicated access

## Security Features

- ✅ All credentials loaded from macOS Keychain
- ✅ No hardcoded secrets in configuration
- ✅ Secure environment variable patterns
- ✅ Runtime environment generated from keychain
- ✅ Proper cleanup and graceful shutdown

## API Endpoints

Once running, the API will be available at:
- **Main**: http://localhost:8000
- **Health Check**: http://localhost:8000/
- **Interactive Docs**: http://localhost:8000/docs
- **OpenAPI Schema**: http://localhost:8000/openapi.json

The API includes:
- JWT-based authentication
- Rate limiting
- CORS configuration
- Request logging
- Database integration
- WebSocket support
