#!/bin/bash

# Google Cloud IAM Manager (Standard Roles)
# Usage: ./script.sh [setup|remove] [EMAIL_ADDRESS]

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
# Using Standard Roles instead of Custom Roles
# 1. roles/bigquery.user: Grants bigquery.datasets.create, jobs.create, etc.
ROLES=("roles/bigquery.admin")

# Helper Functions
print_status() { echo -e "${GREEN}[‚úì]${NC} $1"; }
print_error() { echo -e "${RED}[‚úó]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }

usage() {
    echo "Usage: $0 [setup|remove] [EMAIL_ADDRESS]"
    echo "Examples:"
    echo "  $0 setup user@example.com"
    echo "  $0 remove service-account@project.iam.gserviceaccount.com"
    exit 1
}

# 1. Validate Arguments
ACTION=$1
TARGET_EMAIL=$2

if [[ -z "$ACTION" || -z "$TARGET_EMAIL" ]]; then
    print_error "Missing arguments."
    usage
fi

if [[ "$ACTION" != "setup" && "$ACTION" != "remove" ]]; then
    print_error "Invalid action: $ACTION"
    usage
fi

# 2. Validate Dependencies
if ! command -v gcloud &> /dev/null; then
    print_error "gcloud CLI is not installed."
    exit 1
fi

# 3. Get Project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    print_error "No default project set via gcloud."
    echo "Please run: gcloud config set project [PROJECT_ID]"
    exit 1
fi

print_status "Target Project: $PROJECT_ID"
print_status "Target Member:  $TARGET_EMAIL"

# Determine Member Type (User or Service Account)
if [[ "$TARGET_EMAIL" == *"gserviceaccount.com"* ]]; then
    MEMBER="serviceAccount:$TARGET_EMAIL"
else
    MEMBER="user:$TARGET_EMAIL"
fi

# --- MAIN LOGIC ---

if [[ "$ACTION" == "setup" ]]; then
    print_status "Starting Setup..."
    
    # Iterate through the standard roles and grant them
    for ROLE in "${ROLES[@]}"; do
        print_status "Granting $ROLE to $MEMBER..."
        gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="$MEMBER" \
            --role="$ROLE" \
            --condition=None \
            --quiet
    done
        
    print_status "Success! Standard roles granted."

elif [[ "$ACTION" == "remove" ]]; then
    print_status "Starting Removal..."
    
    # Iterate through the standard roles and remove them
    for ROLE in "${ROLES[@]}"; do
        # We use 'set +e' temporarily because remove-iam-policy-binding returns error if binding doesn't exist
        set +e
        OUTPUT=$(gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
            --member="$MEMBER" \
            --role="$ROLE" \
            --quiet 2>&1)
        EXIT_CODE=$?
        set -e

        if [ $EXIT_CODE -eq 0 ]; then
            print_status "Removed $ROLE from $MEMBER."
        else
            # Check if failure was just because binding didn't exist
            if [[ "$OUTPUT" == *"Policy binding not found"* ]]; then
                print_warning "User did not have $ROLE assigned (nothing to remove)."
            else
                print_error "Failed to remove $ROLE:"
                echo "$OUTPUT"
            fi
        fi
    done
    
    print_status "Removal process complete."
fi
