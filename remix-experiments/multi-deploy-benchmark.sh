#!/bin/bash

# Multi-Instance Image Download Benchmark Deployment
# This script creates multiple VM instances and runs benchmarks on all of them

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
LOG_FILE="$LOG_DIR/multi-deploy-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$LOG_DIR"

# Default config file
CONFIG_FILE="deployment-config.conf"

# Arrays to store instance data
declare -a INSTANCE_NAMES=()
declare -a INSTANCE_IPS=()
declare -a INSTANCE_ZONES=()

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

progress() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[$timestamp] [PROGRESS] $message${NC}" | tee -a "$LOG_FILE"
}

# Function to load configuration
load_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        error "Configuration file $CONFIG_FILE not found!"
    fi
    
    log_info "Loading configuration from $CONFIG_FILE..."
    source "$CONFIG_FILE"
    
    # Validate required settings
    if [[ -z "$INSTANCE_COUNT" || "$INSTANCE_COUNT" -lt 1 || "$INSTANCE_COUNT" -gt 20 ]]; then
        error "INSTANCE_COUNT must be between 1 and 20. Current value: $INSTANCE_COUNT"
    fi
    
    success "Configuration loaded successfully"
}

# Function to setup GCP authentication
setup_gcp_auth() {
    log_info "Setting up GCP authentication..."
    
    if [[ -f "credentials.env" ]]; then
        source credentials.env >/dev/null 2>&1
        
        # Check for GCP Service Account key
        if [[ -n "$GCP_SA_KEY" ]]; then
            log_info "Setting up GCP Service Account authentication..."
            
            # Create temp service account file
            local sa_file="/tmp/gcp-sa-key-$$.json"
            
            # Check if base64 encoded or raw JSON
            if echo "$GCP_SA_KEY" | base64 -d >/dev/null 2>&1; then
                echo "$GCP_SA_KEY" | base64 -d > "$sa_file"
            else
                echo "$GCP_SA_KEY" > "$sa_file"
            fi
            
            # Set environment variable for gcloud
            export GOOGLE_APPLICATION_CREDENTIALS="$sa_file"
            
            # Authenticate with service account
            if gcloud auth activate-service-account --key-file="$sa_file" >/dev/null 2>&1; then
                log_info "GCP Service Account authentication successful"
            else
                warning "GCP Service Account authentication failed, trying fallback methods..."
            fi
            
            chmod 600 "$sa_file"
            
        elif [[ -n "$SSH_PASSPHRASE" ]] && [[ -f "setup-ssh-agent.sh" ]]; then
            log_info "Falling back to SSH agent setup..."
            if ./setup-ssh-agent.sh >> "$LOG_FILE" 2>&1; then
                log_info "SSH agent configured successfully"
            else
                warning "SSH agent setup failed"
            fi
        else
            warning "No authentication method available - gcloud may prompt for credentials"
        fi
    else
        warning "credentials.env not found - using default gcloud authentication"
    fi
}

# Function to create startup script
create_startup_script() {
    log_info "Creating startup script for VM instances..."
    
    cat > startup-script-multi.sh << 'SCRIPT_EOF'
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
SCRIPT_EOF
    
    success "Startup script created"
}

# Function to create a single VM instance
create_instance() {
    local instance_num=$1
    local instance_name="${INSTANCE_NAME_PREFIX}-$(date +%s)-${instance_num}"
    
    progress "Creating VM instance $instance_num/$INSTANCE_COUNT: $instance_name"
    
    # Build tags
    local tags=""
    if [[ "$ENABLE_HTTP_SERVER" == "true" ]]; then
        tags="${tags}http-server,"
    fi
    if [[ "$ENABLE_HTTPS_SERVER" == "true" ]]; then
        tags="${tags}https-server,"
    fi
    tags=${tags%,}  # Remove trailing comma
    
    # Create the VM instance
    gcloud compute instances create "$instance_name" \
        --zone="$ZONE" \
        --machine-type="$MACHINE_TYPE" \
        --network-interface=network-tier=PREMIUM,stack-type=IPV4_ONLY,subnet=default \
        --metadata-from-file startup-script=startup-script-multi.sh \
        --maintenance-policy=MIGRATE \
        --provisioning-model=STANDARD \
        --scopes=https://www.googleapis.com/auth/devstorage.read_only,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/trace.append \
        --tags="$tags" \
        --create-disk=auto-delete=yes,boot=yes,device-name="$instance_name",image=projects/"$IMAGE_PROJECT"/global/images/family/"$IMAGE_FAMILY",mode=rw,size="$BOOT_DISK_SIZE",type=projects/"$PROJECT_ID"/zones/"$ZONE"/diskTypes/pd-standard \
        --no-shielded-secure-boot \
        --shielded-vtpm \
        --shielded-integrity-monitoring \
        --labels=environment=benchmark,application=image-download,instance-num="$instance_num" \
        --reservation-affinity=any \
        --project="$PROJECT_ID" \
        --quiet
    
    # Get IP addresses
    local external_ip=$(gcloud compute instances describe "$instance_name" --zone="$ZONE" --project="$PROJECT_ID" --format='get(networkInterfaces[0].accessConfigs[0].natIP)' --quiet)
    local internal_ip=$(gcloud compute instances describe "$instance_name" --zone="$ZONE" --project="$PROJECT_ID" --format='get(networkInterfaces[0].networkIP)' --quiet)
    
    # Store instance data
    INSTANCE_NAMES+=("$instance_name")
    INSTANCE_IPS+=("$external_ip")
    INSTANCE_ZONES+=("$ZONE")
    
    success "VM $instance_num created: $instance_name (IP: $external_ip)"
}

# Function to wait for all VMs to be ready
wait_for_instances() {
    log_info "Waiting for all VM instances to be ready..."
    
    local max_attempts=30
    local ready_count=0
    
    for instance_name in "${INSTANCE_NAMES[@]}"; do
        progress "Checking readiness of $instance_name..."
        
        local attempt=1
        local instance_ready=false
        
        while [[ $attempt -le $max_attempts ]]; do
            # Check VM status
            local vm_status=$(gcloud compute instances describe "$instance_name" --zone="$ZONE" --format='get(status)' --quiet)
            if [[ "$vm_status" != "RUNNING" ]]; then
                sleep 5
                ((attempt++))
                continue
            fi
            
            # Check SSH and Docker
            if gcloud compute ssh "$instance_name" --zone="$ZONE" --command='docker --version' --quiet >/dev/null 2>&1; then
                success "$instance_name is ready!"
                instance_ready=true
                break
            fi
            
            sleep 10
            ((attempt++))
        done
        
        if [[ "$instance_ready" == "true" ]]; then
            ((ready_count++))
        else
            warning "$instance_name failed to become ready"
        fi
    done
    
    log_info "Ready instances: $ready_count/${#INSTANCE_NAMES[@]}"
}

# Function to deploy benchmark to all instances
deploy_benchmark_to_all() {
    log_info "Deploying benchmark to all instances..."
    
    for i in "${!INSTANCE_NAMES[@]}"; do
        local instance_name="${INSTANCE_NAMES[$i]}"
        local instance_ip="${INSTANCE_IPS[$i]}"
        
        progress "Deploying to $instance_name ($instance_ip)..."
        
        # Copy files
        gcloud compute scp image_download_benchmark.py requirements.txt Dockerfile .dockerignore "$instance_name:~/" --zone="$ZONE" --quiet
        
        # Build and run benchmark (in background for parallel execution)
        if [[ "$RUN_BENCHMARK_ON_CREATION" == "true" ]]; then
            {
                log_info "Running benchmark on $instance_name..."
                gcloud compute ssh "$instance_name" --zone="$ZONE" --command='sudo docker build -t image-download-benchmark . && mkdir -p ~/benchmark-results && sudo chmod 777 ~/benchmark-results && sudo docker run --rm -v ~/benchmark-results:/app/downloads image-download-benchmark' --quiet
                success "Benchmark completed on $instance_name"
            } &
        fi
    done
    
    # Wait for all background jobs to complete
    if [[ "$RUN_BENCHMARK_ON_CREATION" == "true" ]]; then
        log_info "Waiting for all benchmarks to complete..."
        wait
        success "All benchmarks completed!"
    fi
}

# Function to display all IP addresses
display_ip_addresses() {
    echo ""
    echo -e "${PURPLE}========================================${NC}"
    echo -e "${PURPLE}        VM INSTANCES & IP ADDRESSES    ${NC}"
    echo -e "${PURPLE}========================================${NC}"
    
    for i in "${!INSTANCE_NAMES[@]}"; do
        local instance_name="${INSTANCE_NAMES[$i]}"
        local external_ip="${INSTANCE_IPS[$i]}"
        local internal_ip=$(gcloud compute instances describe "$instance_name" --zone="$ZONE" --project="$PROJECT_ID" --format='get(networkInterfaces[0].networkIP)' --quiet)
        
        echo -e "${CYAN}Instance $((i+1)):${NC}"
        echo "  Name: $instance_name"
        echo "  External IP: $external_ip"
        echo "  Internal IP: $internal_ip"
        echo "  Zone: $ZONE"
        echo ""
    done
}

# Function to collect results from all instances
collect_all_results() {
    if [[ "$RUN_BENCHMARK_ON_CREATION" != "true" ]]; then
        return
    fi
    
    log_info "Collecting benchmark results from all instances..."
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}        BENCHMARK RESULTS SUMMARY      ${NC}"
    echo -e "${GREEN}========================================${NC}"
    
    for i in "${!INSTANCE_NAMES[@]}"; do
        local instance_name="${INSTANCE_NAMES[$i]}"
        local external_ip="${INSTANCE_IPS[$i]}"
        
        echo -e "${CYAN}Results from $instance_name ($external_ip):${NC}"
        
        local file_count=$(gcloud compute ssh "$instance_name" --zone="$ZONE" --command='ls -1 ~/benchmark-results/ 2>/dev/null | wc -l' --quiet 2>/dev/null || echo "0")
        local total_size=$(gcloud compute ssh "$instance_name" --zone="$ZONE" --command='du -sh ~/benchmark-results/ 2>/dev/null | cut -f1' --quiet 2>/dev/null || echo "0")
        
        echo "  📁 Total files: $file_count"
        echo "  💾 Total size: $total_size"
        
        if [[ "$SHOW_DETAILED_RESULTS" == "true" ]]; then
            echo "  📋 Sample files:"
            gcloud compute ssh "$instance_name" --zone="$ZONE" --command='ls -la ~/benchmark-results/ | head -3' --quiet 2>/dev/null || echo "    No files found"
        fi
        echo ""
    done
}

# Function to save deployment summary
save_deployment_summary() {
    local summary_file="multi-deployment-$(date +%s).env"
    
    log_info "Saving deployment summary to $summary_file..."
    
    cat > "$summary_file" << EOF
# Multi-Instance Deployment Summary - $(date)
INSTANCE_COUNT=$INSTANCE_COUNT
PROJECT_ID=$PROJECT_ID
ZONE=$ZONE
MACHINE_TYPE=$MACHINE_TYPE

# Instance Details
EOF
    
    for i in "${!INSTANCE_NAMES[@]}"; do
        local instance_name="${INSTANCE_NAMES[$i]}"
        local external_ip="${INSTANCE_IPS[$i]}"
        local internal_ip=$(gcloud compute instances describe "$instance_name" --zone="$ZONE" --project="$PROJECT_ID" --format='get(networkInterfaces[0].networkIP)' --quiet)
        
        cat >> "$summary_file" << EOF
INSTANCE_${i}_NAME=$instance_name
INSTANCE_${i}_EXTERNAL_IP=$external_ip
INSTANCE_${i}_INTERNAL_IP=$internal_ip
INSTANCE_${i}_ZONE=$ZONE
EOF
    done
    
    cat >> "$summary_file" << EOF

# Management Commands
# SSH to instances:
$(for i in "${!INSTANCE_NAMES[@]}"; do
    echo "# gcloud compute ssh ${INSTANCE_NAMES[$i]} --zone=$ZONE"
done)

# Stop all instances:
# gcloud compute instances stop $(IFS=' '; echo "${INSTANCE_NAMES[*]}") --zone=$ZONE

# Delete all instances:
# gcloud compute instances delete $(IFS=' '; echo "${INSTANCE_NAMES[*]}") --zone=$ZONE
EOF
    
    success "Deployment summary saved to $summary_file"
}

# Function to display management commands
display_management_commands() {
    echo ""
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}        MANAGEMENT COMMANDS            ${NC}"
    echo -e "${YELLOW}========================================${NC}"
    
    echo -e "${CYAN}SSH to any instance:${NC}"
    for i in "${!INSTANCE_NAMES[@]}"; do
        echo "  gcloud compute ssh ${INSTANCE_NAMES[$i]} --zone=$ZONE"
    done
    
    echo ""
    echo -e "${CYAN}Stop all instances:${NC}"
    echo "  gcloud compute instances stop $(IFS=' '; echo "${INSTANCE_NAMES[*]}") --zone=$ZONE"
    
    echo ""
    echo -e "${CYAN}Delete all instances:${NC}"
    echo "  gcloud compute instances delete $(IFS=' '; echo "${INSTANCE_NAMES[*]}") --zone=$ZONE"
    
    echo ""
    echo -e "${CYAN}View results from all instances:${NC}"
    for i in "${!INSTANCE_NAMES[@]}"; do
        echo "  gcloud compute ssh ${INSTANCE_NAMES[$i]} --zone=$ZONE --command='ls -la ~/benchmark-results/'"
    done
}

# Main execution function
main() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Multi-Instance Benchmark Deployer   ${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    # Load configuration
    load_config
    
    # Setup GCP authentication  
    setup_gcp_auth
    
    # Create startup script
    create_startup_script
    
    # Enable required APIs
    log_info "Enabling required GCP APIs..."
    gcloud services enable compute.googleapis.com --project="$PROJECT_ID" --quiet
    
    # Create instances
    log_info "Creating $INSTANCE_COUNT VM instances..."
    for i in $(seq 1 "$INSTANCE_COUNT"); do
        create_instance "$i"
    done
    
    # Display IP addresses
    if [[ "$SHOW_IP_ADDRESSES" == "true" ]]; then
        display_ip_addresses
    fi
    
    # Wait for instances to be ready
    wait_for_instances
    
    # Deploy benchmark to all instances
    deploy_benchmark_to_all
    
    # Collect and display results
    if [[ "$RUN_BENCHMARK_ON_CREATION" == "true" ]]; then
        collect_all_results
    fi
    
    # Save deployment summary
    save_deployment_summary
    
    # Display management commands
    display_management_commands
    
    echo ""
    echo -e "${GREEN}🎉 Multi-instance deployment completed successfully!${NC}"
    echo -e "${CYAN}Created $INSTANCE_COUNT VM instances ready for benchmarking.${NC}"
    
    # Cleanup startup script
    rm -f startup-script-multi.sh
}

# Run main function
main "$@"
