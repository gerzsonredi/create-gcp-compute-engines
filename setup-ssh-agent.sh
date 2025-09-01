#!/bin/bash

# Setup SSH Agent with passphrase
# This adds the SSH key to the agent so no manual passphrase entry is needed

set -e

# Logging configuration
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/ssh-agent-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$LOG_DIR"

# Logging function
log_secure() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

log_secure "INFO" "Starting SSH agent setup"

# Load credentials
if [[ -f "credentials.env" ]]; then
    source credentials.env >/dev/null 2>&1
    if [[ -n "$SSH_PASSPHRASE" ]]; then
        log_secure "INFO" "🔑 SSH credentials loaded successfully"
    else
        log_secure "ERROR" "❌ SSH_PASSPHRASE not found in credentials.env"
        exit 1
    fi
else
    log_secure "ERROR" "❌ credentials.env not found"
    exit 1
fi

# Check if ssh-agent is running
if ! pgrep -x ssh-agent > /dev/null; then
    log_secure "INFO" "🚀 Starting SSH agent..."
    eval $(ssh-agent -s) >> "$LOG_FILE" 2>&1
fi

# Add SSH key to agent with passphrase (secure - no passphrase logging)
log_secure "INFO" "🔐 Adding SSH key to agent..."
expect -c "
    spawn ssh-add /Users/borosgerzson/.ssh/google_compute_engine
    expect \"Enter passphrase*\"
    send \"$SSH_PASSPHRASE\r\"
    expect eof
" >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    log_secure "SUCCESS" "✅ SSH key added to agent successfully!"
    log_secure "INFO" "🎯 SSH commands can now run without manual passphrase entry"
else
    log_secure "ERROR" "❌ Failed to add SSH key to agent"
    exit 1
fi
