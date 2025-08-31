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
    
    # Use the direct method that works
    nohup python cmo_agent/scripts/run_web.py > /tmp/cmo_api.log 2>&1 &
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

case "${1:-help}" in
    start)
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
        start_api
        start_frontend
        status
        ;;
    status)
        status
        ;;
    logs)
        logs "${2:-both}"
        ;;
    api)
        case "${2:-start}" in
            start) stop_all; start_api ;;
            stop) kill_service "API" "$API_PORT" "$PIDFILE_API" ;;
            restart) kill_service "API" "$API_PORT" "$PIDFILE_API"; start_api ;;
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
        echo "CMO Agent Development Server Manager"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  start          Start both API and frontend servers"
        echo "  stop           Stop all services"
        echo "  restart        Restart all services"
        echo "  status         Show service status"
        echo "  logs [service] Show logs (api|frontend|both)"
        echo ""
        echo "Service-specific:"
        echo "  api start|stop|restart|logs"
        echo "  frontend start|stop|restart|logs"
        echo ""
        echo "Examples:"
        echo "  $0 start                    # Start everything"
        echo "  $0 api restart             # Restart just API"
        echo "  $0 logs api                # Follow API logs"
        echo "  $0 status                  # Check what's running"
        ;;
esac
