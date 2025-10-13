#!/usr/bin/env ./venv/bin/python3
"""
Auto-commit utility for code subtasks
Automatically stages and commits changes with descriptive messages
"""

import subprocess
import sys
import os
from datetime import datetime
from typing import Optional, List


class AutoCommit:
    def __init__(self):
        self.colors = {
            'red': '\033[0;31m',
            'green': '\033[0;32m',
            'yellow': '\033[1;33m',
            'blue': '\033[0;34m',
            'nc': '\033[0m'
        }
    
    def print_status(self, message: str):
        """Print status message with blue color"""
        print(f"{self.colors['blue']}[AUTO-COMMIT]{self.colors['nc']} {message}")
    
    def print_success(self, message: str):
        """Print success message with green color"""
        print(f"{self.colors['green']}[SUCCESS]{self.colors['nc']} {message}")
    
    def print_warning(self, message: str):
        """Print warning message with yellow color"""
        print(f"{self.colors['yellow']}[WARNING]{self.colors['nc']} {message}")
    
    def print_error(self, message: str):
        """Print error message with red color"""
        print(f"{self.colors['red']}[ERROR]{self.colors['nc']} {message}")
    
    def run_command(self, command: List[str]) -> bool:
        """Run a shell command and return success status"""
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            if result.stdout:
                print(result.stdout)
            return True
        except subprocess.CalledProcessError as e:
            self.print_error(f"Command failed: {' '.join(command)}")
            if e.stderr:
                print(e.stderr)
            return False
    
    def is_git_repo(self) -> bool:
        """Check if current directory is a git repository"""
        return self.run_command(['git', 'rev-parse', '--git-dir'])
    
    def has_changes(self) -> bool:
        """Check if there are any changes to commit"""
        try:
            result = subprocess.run(
                ['git', 'diff-index', '--quiet', 'HEAD', '--'],
                capture_output=True
            )
            return result.returncode != 0
        except Exception:
            return False
    
    def get_current_branch(self) -> str:
        """Get current git branch"""
        try:
            result = subprocess.run(
                ['git', 'branch', '--show-current'],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"
    
    def generate_commit_message(self, custom_message: Optional[str] = None) -> str:
        """Generate a commit message based on changed files or use custom message"""
        if custom_message:
            return custom_message
        
        # Get changed files
        try:
            result = subprocess.run(
                ['git', 'diff', '--name-only', 'HEAD'],
                capture_output=True, text=True, check=True
            )
            changed_files = result.stdout.strip().split('\n')
            
            # Analyze file types to generate appropriate message
            if any(f.endswith('.py') for f in changed_files if f):
                message = "Update: Python code changes"
            elif any(f.endswith('.md') for f in changed_files if f):
                message = "Update: Documentation"
            elif any(f.endswith(('.js', '.html', '.css')) for f in changed_files if f):
                message = "Update: Frontend files"
            else:
                message = "Update: Code changes"
            
            # Add timestamp for uniqueness
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return f"{message} - {timestamp}"
            
        except Exception:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return f"Update: Code changes - {timestamp}"
    
    def commit_changes(self, message: Optional[str] = None) -> bool:
        """Stage and commit all changes"""
        # Check if we're in a git repository
        if not self.is_git_repo():
            self.print_error("Not a git repository")
            return False
        
        # Get current branch
        branch = self.get_current_branch()
        self.print_status(f"Current branch: {branch}")
        
        # Check for changes
        if not self.has_changes():
            self.print_warning("No changes to commit")
            return True
        
        # Show what will be committed
        self.print_status("Changes to be committed:")
        self.run_command(['git', 'status', '--short'])
        
        # Generate commit message
        commit_message = self.generate_commit_message(message)
        self.print_status(f"Committing with message: {commit_message}")
        
        # Stage all changes
        if not self.run_command(['git', 'add', '.']):
            return False
        
        # Commit changes
        if not self.run_command(['git', 'commit', '-m', commit_message]):
            return False
        
        # Show commit summary
        self.print_status("Commit summary:")
        self.run_command(['git', 'log', '--oneline', '-1'])
        
        self.print_success("Auto-commit completed successfully!")
        return True


def main():
    """Main function for command line usage"""
    auto_commit = AutoCommit()
    
    # Get custom message from command line if provided
    custom_message = None
    if len(sys.argv) > 1:
        custom_message = ' '.join(sys.argv[1:])
    
    success = auto_commit.commit_changes(custom_message)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()