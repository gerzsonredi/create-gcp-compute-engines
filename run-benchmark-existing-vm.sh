#!/bin/bash

# Quick Benchmark Runner for Existing VM
# This script runs the benchmark on an already created VM

set -e

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration (can be overridden with env vars)
VM_NAME=${VM_NAME:-"image-benchmark-vm"}
VM_ZONE=${VM_ZONE:-"europe-west1-b"}

# Load SSH passphrase from credentials file
if [[ -f "credentials.env" ]]; then
    source credentials.env
    export SSH_PASSPHRASE
    echo "🔑 Loaded SSH passphrase from credentials.env"
fi

log() {
    echo -e "${CYAN}[$(date '+%H:%M:%S')] $1${NC}"
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

main() {
    echo -e "${YELLOW}🚀 Complete Benchmark Runner${NC}"
    echo "================================="
    echo "VM: $VM_NAME"
    echo "Zone: $VM_ZONE"
    echo ""
    
    # Setup SSH agent first
    log "Setting up SSH agent..."
    if [[ -f "setup-ssh-agent.sh" ]]; then
        ./setup-ssh-agent.sh
    else
        log "SSH agent setup script not found, proceeding with manual auth"
    fi
    
    log "Checking VM status..."
    local vm_status=$(gcloud compute instances describe $VM_NAME --zone=$VM_ZONE --format='get(status)' 2>/dev/null || echo "NOT_FOUND")
    
    if [[ "$vm_status" == "NOT_FOUND" ]]; then
        echo "❌ VM '$VM_NAME' not found in zone '$VM_ZONE'"
        echo "💡 Use 'full-deploy-benchmark.sh' to create a new VM"
        exit 1
    fi
    
    if [[ "$vm_status" != "RUNNING" ]]; then
        log "Starting VM (current status: $vm_status)..."
        gcloud compute instances start $VM_NAME --zone=$VM_ZONE
        log "Waiting for VM to be ready..."
        sleep 30
    fi
    
    log "Copying latest files to VM..."
    gcloud compute scp image_download_benchmark.py requirements.txt Dockerfile .dockerignore $VM_NAME:~/ --zone=$VM_ZONE --quiet
    
    log "Rebuilding Docker image..."
    gcloud compute ssh $VM_NAME --zone=$VM_ZONE --command='sudo docker build -t image-download-benchmark .' --quiet
    
    log "Preparing benchmark environment..."
    gcloud compute ssh $VM_NAME --zone=$VM_ZONE --command='mkdir -p ~/benchmark-results && sudo chmod 777 ~/benchmark-results' --quiet
    
    echo ""
    echo -e "${YELLOW}======================================${NC}"
    echo -e "${YELLOW}    RUNNING BENCHMARK...              ${NC}"
    echo -e "${YELLOW}======================================${NC}"
    
    # Run benchmark
    gcloud compute ssh $VM_NAME --zone=$VM_ZONE --command='sudo docker run --rm -v ~/benchmark-results:/app/downloads image-download-benchmark'
    
    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}    BENCHMARK COMPLETED!              ${NC}"
    echo -e "${GREEN}======================================${NC}"
    
    log "Collecting results summary..."
    local file_count=$(gcloud compute ssh $VM_NAME --zone=$VM_ZONE --command='ls -1 ~/benchmark-results/ | wc -l' --quiet 2>/dev/null || echo "0")
    local total_size=$(gcloud compute ssh $VM_NAME --zone=$VM_ZONE --command='du -sh ~/benchmark-results/ | cut -f1' --quiet 2>/dev/null || echo "0")
    
    echo ""
    echo -e "${CYAN}📊 BENCHMARK RESULTS:${NC}"
    echo "  📁 Total files: $file_count"
    echo "  💾 Total size: $total_size"
    echo ""
    echo -e "${CYAN}💻 VM Info:${NC}"
    echo "  🌐 External IP: $(gcloud compute instances describe $VM_NAME --zone=$VM_ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)' --quiet)"
    echo "  📍 Zone: $VM_ZONE"
    echo ""
    echo -e "${CYAN}🛠️  Quick Commands:${NC}"
    echo "  📁 View files: gcloud compute ssh $VM_NAME --zone=$VM_ZONE --command='ls -la ~/benchmark-results/'"
    echo "  🛑 Stop VM: gcloud compute instances stop $VM_NAME --zone=$VM_ZONE"
    echo "  🗑️  Delete VM: gcloud compute instances delete $VM_NAME --zone=$VM_ZONE"
    
    success "✨ Complete benchmark pipeline finished successfully!"
}

main "$@"
