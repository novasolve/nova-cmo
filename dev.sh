#!/bin/bash
# CMO Agent Development Server Manager

set -e

API_PORT=8000
FRONTEND_PORT=3000
PIDFILE_API="/tmp/cmo_api.pid"
PIDFILE_FRONTEND="/tmp/cmo_frontend.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[CMO]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Kill processes by port or PID
kill_service() {
    local service=$1
    local port=$2
    local pidfile=$3

    # Kill by PID file first
    if [[ -f "$pidfile" ]]; then
        local pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null && sleep 1
            kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null
        fi
        rm -f "$pidfile"
    fi

    # Kill by port as backup
    local pids=$(lsof -ti:$port 2>/dev/null || echo "")
    if [[ -n "$pids" ]]; then
        echo "$pids" | xargs kill -TERM 2>/dev/null || true
        sleep 1
        echo "$pids" | xargs kill -KILL 2>/dev/null || true
    fi

    log "Stopped $service"
}

start_api() {
    log "Starting API server on port $API_PORT..."
    cd "$(dirname "$0")"
    
    # Load environment if not already loaded
    if [[ -z "$GITHUB_TOKEN" && -z "$OPENAI_API_KEY" ]]; then
        load_env
    fi

    # Start API server (environment already loaded)
    python cmo_agent/scripts/run_web.py > /tmp/cmo_api.log 2>&1 &
    echo $! > "$PIDFILE_API"

    # Wait and verify
    sleep 3
    if curl -s http://localhost:$API_PORT/ >/dev/null 2>&1; then
        success "API server started successfully"
        log "API running at http://localhost:$API_PORT"
        log "API logs: tail -f /tmp/cmo_api.log"
    else
        error "API server failed to start. Check logs: tail -f /tmp/cmo_api.log"
        return 1
    fi
}

# Load environment variables from .env files
load_env() {
    local script_dir="$(cd "$(dirname "$0")" && pwd)"
    
    # Try multiple .env locations in order of preference
    local env_files=(
        "$script_dir/.env"                    # Root .env
        "$script_dir/cmo_agent/.env"          # CMO agent .env  
        "$HOME/.cmo_agent.env"               # User global .env
    )
    
    local env_loaded=false
    for env_file in "${env_files[@]}"; do
        if [[ -f "$env_file" ]]; then
            log "📄 Loading environment from: $env_file"
            set -a  # Export all variables
            source "$env_file"
            set +a  # Stop exporting
            env_loaded=true
            break
        fi
    done
    
    if [[ "$env_loaded" = false ]]; then
        warn "No .env file found. Create one from .env.example for full functionality."
        warn "Locations checked: ${env_files[*]}"
    fi
}

# Start everything in foreground with live logs
start_dev() {
    log "Starting development environment..."
    
    # Load environment variables first
    load_env
    
    # Validate environment
    log "🔍 Checking environment..."
    if [[ -f "tools/check_env.py" ]]; then
        if ! python tools/check_env.py --dry-run; then
            error "Environment validation failed. Please fix the issues above."
            exit 1
        fi
    else
        warn "Environment checker not found, skipping validation"
    fi
    
    stop_all

    cd "$(dirname "$0")"

    # Start API in background (environment already loaded)
    log "🚀 Starting API server..."
    python cmo_agent/scripts/run_web.py > /tmp/cmo_api.log 2>&1 &
    local api_pid=$!
    echo $api_pid > "$PIDFILE_API"

    # Wait for API
    sleep 3
    if ! curl -s http://localhost:$API_PORT/ >/dev/null 2>&1; then
        error "API failed to start. Check logs: tail -f /tmp/cmo_api.log"
        return 1
    fi
    success "API running at http://localhost:$API_PORT"

    # Start frontend in background
    log "🎨 Starting frontend..."
    cd frontend
    if [[ ! -d "node_modules" ]]; then
        log "Installing dependencies..."
        npm install
    fi
    npm run dev > /tmp/cmo_frontend.log 2>&1 &
    local frontend_pid=$!
    echo $frontend_pid > "$PIDFILE_FRONTEND"
    cd ..

    # Wait for frontend
    sleep 5
    if ! curl -s http://localhost:$FRONTEND_PORT/ >/dev/null 2>&1; then
        warn "Frontend may still be starting..."
    else
        success "Frontend running at http://localhost:$FRONTEND_PORT"
    fi

    success "🎉 Development environment ready!"
    echo ""
    echo "📱 Frontend: http://localhost:$FRONTEND_PORT"
    echo "🔧 API:      http://localhost:$API_PORT"
    echo "📚 API Docs: http://localhost:$API_PORT/docs"
    echo ""
    log "Press Ctrl+C to stop all services"
    echo ""

    # Setup trap to cleanup on exit
    trap 'log "Shutting down..."; kill $api_pid $frontend_pid 2>/dev/null; stop_all; exit 0' INT TERM

    # Follow logs in foreground
    tail -f /tmp/cmo_api.log /tmp/cmo_frontend.log
}

start_frontend() {
    log "Starting frontend server on port $FRONTEND_PORT..."
    cd "$(dirname "$0")/frontend"

    # Install deps if needed
    if [[ ! -d "node_modules" ]]; then
        log "Installing frontend dependencies..."
        npm install
    fi

    nohup npm run dev > /tmp/cmo_frontend.log 2>&1 &
    echo $! > "$PIDFILE_FRONTEND"

    # Wait and verify
    sleep 5
    if curl -s http://localhost:$FRONTEND_PORT/ >/dev/null 2>&1; then
        success "Frontend server started successfully"
        log "Frontend running at http://localhost:$FRONTEND_PORT"
        log "Frontend logs: tail -f /tmp/cmo_frontend.log"
    else
        warn "Frontend server may still be starting. Check logs: tail -f /tmp/cmo_frontend.log"
    fi
}

stop_all() {
    log "Stopping all services..."
    kill_service "API" "$API_PORT" "$PIDFILE_API"
    kill_service "Frontend" "$FRONTEND_PORT" "$PIDFILE_FRONTEND"
    success "All services stopped"
}

status() {
    log "Service Status:"

    # API Status
    if curl -s http://localhost:$API_PORT/ >/dev/null 2>&1; then
        echo -e "  API:      ${GREEN}✓ Running${NC} (http://localhost:$API_PORT)"
    else
        echo -e "  API:      ${RED}✗ Not running${NC}"
    fi

    # Frontend Status
    if curl -s http://localhost:$FRONTEND_PORT/ >/dev/null 2>&1; then
        echo -e "  Frontend: ${GREEN}✓ Running${NC} (http://localhost:$FRONTEND_PORT)"
    else
        echo -e "  Frontend: ${RED}✗ Not running${NC}"
    fi

    # PID files
    echo ""
    log "Process Info:"
    if [[ -f "$PIDFILE_API" ]]; then
        echo "  API PID: $(cat $PIDFILE_API)"
    fi
    if [[ -f "$PIDFILE_FRONTEND" ]]; then
        echo "  Frontend PID: $(cat $PIDFILE_FRONTEND)"
    fi
}

logs() {
    local service=${1:-"both"}
    case $service in
        api)
            log "Following API logs..."
            tail -f /tmp/cmo_api.log
            ;;
        frontend)
            log "Following frontend logs..."
            tail -f /tmp/cmo_frontend.log
            ;;
        both|*)
            log "Following all logs..."
            tail -f /tmp/cmo_api.log /tmp/cmo_frontend.log
            ;;
    esac
}

case "${1:-dev}" in
    dev|start)
        start_dev
        ;;
    bg|background)
        load_env
        stop_all
        start_api
        start_frontend
        status
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        sleep 2
        start_dev
        ;;
    status)
        status
        ;;
    logs)
        logs "${2:-both}"
        ;;
    api)
        case "${2:-start}" in
            start) load_env; stop_all; start_api ;;
            stop) kill_service "API" "$API_PORT" "$PIDFILE_API" ;;
            restart) load_env; kill_service "API" "$API_PORT" "$PIDFILE_API"; start_api ;;
            logs) logs api ;;
        esac
        ;;
    frontend)
        case "${2:-start}" in
            start) kill_service "Frontend" "$FRONTEND_PORT" "$PIDFILE_FRONTEND"; start_frontend ;;
            stop) kill_service "Frontend" "$FRONTEND_PORT" "$PIDFILE_FRONTEND" ;;
            restart) kill_service "Frontend" "$FRONTEND_PORT" "$PIDFILE_FRONTEND"; start_frontend ;;
            logs) logs frontend ;;
        esac
        ;;
    help|*)
        echo "🚀 CMO Agent Development Server Manager"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Single-pane commands:"
        echo "  ./dev.sh                   # Start everything with live logs (default)"
        echo "  ./dev.sh dev               # Same as above"
        echo "  ./dev.sh restart           # Restart everything with live logs"
        echo ""
        echo "Background mode:"
        echo "  ./dev.sh bg                # Start in background, return to shell"
        echo "  ./dev.sh stop              # Stop all services"
        echo "  ./dev.sh status            # Check what's running"
        echo "  ./dev.sh logs              # Follow logs"
        echo ""
        echo "Service-specific:"
        echo "  ./dev.sh api restart       # Restart just API"
        echo "  ./dev.sh frontend logs     # Just frontend logs"
        echo ""
        echo "Examples:"
        echo "  ./dev.sh                   # One command - start everything!"
        echo "  ./dev.sh bg                # Background mode"
        echo "  ./dev.sh api restart       # Fix API issues"
        echo ""
        echo "🌐 URLs:"
        echo "  Frontend: http://localhost:3000"
        echo "  API:      http://localhost:8000"
        echo "  API Docs: http://localhost:8000/docs"
        ;;
esac
