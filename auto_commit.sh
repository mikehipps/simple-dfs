#!/bin/bash

# Auto-commit script for code subtasks
# This script automatically stages and commits changes with a descriptive message

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[AUTO-COMMIT]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "Not a git repository"
    exit 1
fi

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)
print_status "Current branch: $CURRENT_BRANCH"

# Check for changes
if git diff-index --quiet HEAD --; then
    print_warning "No changes to commit"
    exit 0
fi

# Show what will be committed
print_status "Changes to be committed:"
git status --short

# Generate commit message based on task context
if [ -n "$1" ]; then
    COMMIT_MESSAGE="$1"
else
    # Auto-generate message based on changed files
    CHANGED_FILES=$(git diff --name-only HEAD)
    if echo "$CHANGED_FILES" | grep -q "\.py$"; then
        COMMIT_MESSAGE="Update: Python code changes"
    elif echo "$CHANGED_FILES" | grep -q "\.md$"; then
        COMMIT_MESSAGE="Update: Documentation"
    elif echo "$CHANGED_FILES" | grep -q "\.js$\|\.html$\|\.css$"; then
        COMMIT_MESSAGE="Update: Frontend files"
    else
        COMMIT_MESSAGE="Update: Code changes"
    fi
    
    # Add timestamp for uniqueness
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
    COMMIT_MESSAGE="$COMMIT_MESSAGE - $TIMESTAMP"
fi

# Stage all changes
print_status "Staging changes..."
git add .

# Commit changes
print_status "Committing with message: $COMMIT_MESSAGE"
if git commit -m "$COMMIT_MESSAGE"; then
    print_success "Successfully committed changes"
    
    # Show commit summary
    print_status "Commit summary:"
    git log --oneline -1
    
    # Show files changed
    print_status "Files changed in this commit:"
    git show --stat --oneline HEAD
    
else
    print_error "Failed to commit changes"
    exit 1
fi

print_success "Auto-commit completed successfully!"