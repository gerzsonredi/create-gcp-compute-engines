#!/bin/bash

# Complete Image Download Benchmark Deployment Script
# This script handles everything from VM creation to results display

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging configuration
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/full-deploy-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$LOG_DIR"

# Secure logging functions
log_info() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${CYAN}[$timestamp] $message${NC}" | tee -a "$LOG_FILE"
}

error() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[$timestamp] [ERROR] $message${NC}" | tee -a "$LOG_FILE" >&2
    exit 1
}

success() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[$timestamp] [SUCCESS] $message${NC}" | tee -a "$LOG_FILE"
}

warning() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}[$timestamp] [WARNING] $message${NC}" | tee -a "$LOG_FILE"
}

# Configuration
PROJECT_ID=${PROJECT_ID:-"remix-466614"}
ZONE=${ZONE:-"europe-west1-b"}
INSTANCE_NAME="image-benchmark-vm-$(date +%s)"  # Unique name with timestamp
MACHINE_TYPE="e2-medium"  # 2 vCPUs, 4GB RAM
BOOT_DISK_SIZE="100GB"
IMAGE_FAMILY="ubuntu-2204-lts"
IMAGE_PROJECT="ubuntu-os-cloud"

# Load GCP credentials from credentials file (secure)
if [[ -f "credentials.env" ]]; then
    source credentials.env >/dev/null 2>&1
    
    # Setup GCP Service Account authentication
    if [[ -n "$GCP_SA_KEY" ]]; then
        log_info "Setting up GCP Service Account authentication..."
        
        # Create temp service account file
        SA_FILE="/tmp/gcp-sa-key-$$.json"
        
        # Check if base64 encoded or raw JSON
        if echo "$GCP_SA_KEY" | base64 -d >/dev/null 2>&1; then
            echo "$GCP_SA_KEY" | base64 -d > "$SA_FILE"
        else
            echo "$GCP_SA_KEY" > "$SA_FILE"
        fi
        
        # Set environment variable for gcloud
        export GOOGLE_APPLICATION_CREDENTIALS="$SA_FILE"
        
        # Authenticate with service account
        if gcloud auth activate-service-account --key-file="$SA_FILE" >/dev/null 2>&1; then
            log_info "GCP Service Account authentication successful"
        else
            warning "GCP Service Account authentication failed"
        fi
        
        chmod 600 "$SA_FILE"
        
    elif [[ -n "$SSH_PASSPHRASE" ]]; then
        export SSH_PASSPHRASE
        log_info "SSH credentials loaded (fallback mode)"
    else
        warning "No authentication credentials found in credentials.env"
    fi
else
    warning "credentials.env not found - using default gcloud authentication"
fi

# SSH wrapper function with automatic passphrase
ssh_with_passphrase() {
    local vm_name="$1"
    local zone="$2"
    local command="$3"
    
    if [[ -n "$SSH_PASSPHRASE" ]]; then
        # Use expect to automatically enter passphrase
        expect -c "
            spawn gcloud compute ssh $vm_name --zone=$zone --command='$command' --quiet
            expect \"Enter passphrase for key*\"
            send \"$SSH_PASSPHRASE\r\"
            expect eof
        " 2>/dev/null
    else
        # Fall back to manual entry
        gcloud compute ssh "$vm_name" --zone="$zone" --command="$command" --quiet
    fi
}

# SCP wrapper function with automatic passphrase
scp_with_passphrase() {
    local files="$1"
    local vm_name="$2"
    local zone="$3"
    local destination="$4"
    
    if [[ -n "$SSH_PASSPHRASE" ]]; then
        # Use expect to automatically enter passphrase
        expect -c "
            spawn gcloud compute scp $files $vm_name:$destination --zone=$zone --quiet
            expect \"Enter passphrase for key*\"
            send \"$SSH_PASSPHRASE\r\"
            expect eof
        " 2>/dev/null
    else
        # Fall back to manual entry
        gcloud compute scp "$files" "$vm_name:$destination" --zone="$zone" --quiet
    fi
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        error "gcloud CLI not found. Please install Google Cloud SDK first."
    fi
    
    # Check if expect is installed (for automatic passphrase entry)
    if ! command -v expect &> /dev/null; then
        warning "expect not found. Installing expect for automatic SSH passphrase handling..."
        if command -v brew &> /dev/null; then
            brew install expect
        elif command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y expect
        else
            warning "Could not install expect automatically. SSH may require manual passphrase entry."
        fi
    fi
    
    # Check authentication
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        error "Not authenticated with gcloud. Please run: gcloud auth log_infoin"
    fi
    
    # Check if required files exist
    for file in "image_download_benchmark.py" "requirements.txt" "Dockerfile" ".dockerignore"; do
        if [[ ! -f "$file" ]]; then
            error "Required file not found: $file"
        fi
    done
    
    success "Prerequisites check passed"
}

# Function to create VM
create_vm() {
    log_info "Creating GCP Compute Engine instance: $INSTANCE_NAME"
    
    # Enable required APIs
    log_info "Enabling required APIs..."
    gcloud services enable compute.googleapis.com --project=$PROJECT_ID
    
    # Create startup script content
    cat > startup-script-auto.sh << 'EOF'
#!/bin/bash
set -e
echo "Starting VM setup..."

# Update system
apt-get update -y
apt-get upgrade -y

# Install Docker
echo "Installing Docker..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start Docker
systemctl start docker
systemctl enable docker

echo "VM setup completed successfully!"
EOF
    
    # Create the VM
    gcloud compute instances create $INSTANCE_NAME \
        --zone=$ZONE \
        --machine-type=$MACHINE_TYPE \
        --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
        --metadata-from-file startup-script=startup-script-auto.sh \
        --maintenance-policy=MIGRATE \
        --provisioning-model=STANDARD \
        --scopes=https://www.googleapis.com/auth/devstorage.read_only,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/trace.append \
        --tags=http-server,https-server \
        --create-disk=auto-delete=yes,boot=yes,device-name=$INSTANCE_NAME,image=projects/$IMAGE_PROJECT/global/images/family/$IMAGE_FAMILY,mode=rw,size=$BOOT_DISK_SIZE,type=projects/$PROJECT_ID/zones/$ZONE/diskTypes/pd-standard \
        --no-shielded-secure-boot \
        --shielded-vtpm \
        --shielded-integrity-monitoring \
        --labels=environment=benchmark,application=image-download \
        --reservation-affinity=any \
        --project=$PROJECT_ID
    
    success "VM created successfully: $INSTANCE_NAME"
    
    # Get IP addresses
    EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
    INTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --format='get(networkInterfaces[0].networkIP)')
    
    log_info "VM Details:"
    echo "  Name: $INSTANCE_NAME"
    echo "  Zone: $ZONE"
    echo "  External IP: $EXTERNAL_IP"
    echo "  Internal IP: $INTERNAL_IP"
    echo "  Machine Type: $MACHINE_TYPE"
}

# Function to wait for VM to be ready
wait_for_vm() {
    log_info "Waiting for VM to be ready and startup script to complete..."
    
    local max_attempts=30
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        log_info "Attempt $attempt/$max_attempts: Checking VM status..."
        
        # Check if VM is running
        local vm_status=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --format='get(status)')
        if [[ "$vm_status" != "RUNNING" ]]; then
            log_info "VM status: $vm_status. Waiting..."
            sleep 10
            ((attempt++))
            continue
        fi
        
        # Try to connect via SSH
        if gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command='echo "SSH connection successful"' --quiet >/dev/null 2>&1; then
            # Check if Docker is installed
            if gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command='docker --version' --quiet >/dev/null 2>&1; then
                success "VM is ready and Docker is installed"
                return 0
            else
                log_info "Docker not yet installed. Waiting..."
            fi
        else
            log_info "SSH not yet available. Waiting..."
        fi
        
        sleep 15
        ((attempt++))
    done
    
    error "VM failed to become ready within expected time"
}

# Function to deploy and run benchmark
deploy_and_run() {
    log_info "Setting up SSH agent for automatic authentication..."
    if [[ -f "setup-ssh-agent.sh" ]]; then
        ./setup-ssh-agent.sh
    fi
    
    log_info "Copying application files to VM..."
    
    # Copy files to VM using normal gcloud command
    gcloud compute scp image_download_benchmark.py requirements.txt Dockerfile .dockerignore "$INSTANCE_NAME:~/" --zone="$ZONE" --quiet
    
    success "Files copied successfully"
    
    log_info "Building Docker image and running complete benchmark..."
    echo -e "${PURPLE}======================================${NC}"
    echo -e "${PURPLE}  BENCHMARK EXECUTION STARTING...    ${NC}"
    echo -e "${PURPLE}======================================${NC}"
    
    # Run everything in one command: build Docker image, create results dir, and run benchmark
    gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command='sudo docker build -t image-download-benchmark . && mkdir -p ~/benchmark-results && sudo chmod 777 ~/benchmark-results && sudo docker run --rm -v ~/benchmark-results:/app/downloads image-download-benchmark'
    
    echo -e "${PURPLE}======================================${NC}"
    echo -e "${PURPLE}  BENCHMARK EXECUTION COMPLETED!     ${NC}"
    echo -e "${PURPLE}======================================${NC}"
    
    success "Docker image built and benchmark executed successfully"
}

# Function to display results
display_results() {
    log_info "Collecting benchmark results..."
    
    # Get file count and size using normal gcloud commands
    local file_count=$(gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command='ls -1 ~/benchmark-results/ | wc -l' --quiet 2>/dev/null || echo "0")
    local total_size=$(gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command='du -sh ~/benchmark-results/ | cut -f1' --quiet 2>/dev/null || echo "0")
    
    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}        BENCHMARK RESULTS SUMMARY     ${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo -e "${CYAN}VM Information:${NC}"
    echo "  Instance Name: $INSTANCE_NAME"
    echo "  External IP: $(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)' --quiet)"
    echo "  Zone: $ZONE"
    echo "  Machine Type: $MACHINE_TYPE"
    echo ""
    echo -e "${CYAN}Downloaded Files:${NC}"
    echo "  Total Images: $file_count"
    echo "  Total Size: $total_size"
    echo ""
    echo -e "${CYAN}Sample Files:${NC}"
    gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" --command='ls -la ~/benchmark-results/ | head -5' --quiet 2>/dev/null || true
    
    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}        DEPLOYMENT COMPLETED!         ${NC}"
    echo -e "${GREEN}======================================${NC}"
}

# Function to save deployment info
save_deployment_info() {
    local info_file="deployment-info-$(date +%s).env"
    
    log_info "Saving deployment information to $info_file..."
    
    cat > "$info_file" << EOF
# Deployment Information - $(date)
VM_NAME=$INSTANCE_NAME
VM_ZONE=$ZONE
VM_EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
VM_INTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --format='get(networkInterfaces[0].networkIP)')
PROJECT_ID=$PROJECT_ID
MACHINE_TYPE=$MACHINE_TYPE
BOOT_DISK_SIZE=$BOOT_DISK_SIZE

# Useful Commands:
# SSH to VM: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID
# Delete VM: gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID
# View results: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command='ls -la ~/benchmark-results/'
EOF
    
    success "Deployment info saved to $info_file"
}

# Function to cleanup on error
cleanup_on_error() {
    if [[ -n "$INSTANCE_NAME" ]]; then
        warning "Cleaning up VM due to error..."
        gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE --project=$PROJECT_ID --quiet 2>/dev/null || true
    fi
}

# Main execution
main() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Image Download Benchmark Deployer    ${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    # Set trap for cleanup on error
    trap cleanup_on_error ERR
    
    # Execute deployment steps
    check_prerequisites
    create_vm
    wait_for_vm
    deploy_and_run
    display_results
    save_deployment_info
    
    echo ""
    echo -e "${GREEN}🎉 Complete deployment finished successfully!${NC}"
    echo -e "${CYAN}VM '$INSTANCE_NAME' is ready and benchmark has been executed.${NC}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. SSH to VM: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE"
    echo "2. View results: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command='ls -la ~/benchmark-results/'"
    echo "3. Stop VM: gcloud compute instances stop $INSTANCE_NAME --zone=$ZONE"
    echo "4. Delete VM: gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE"
}

# Run main function
main "$@"
