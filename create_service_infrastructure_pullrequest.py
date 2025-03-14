#!/usr/bin/env python3
import subprocess
import requests
import os
import sys
import logging
import datetime

# Configure logging for debugging and informational messages.
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

def get_git_config(key):
    """Retrieve a value from the global Git configuration."""
    result = subprocess.run(['git', 'config', '--global', key],
                            capture_output=True, text=True)
    if result.returncode != 0:
        logging.error("Error retrieving git config for %s", key)
        return None
    return result.stdout.strip()

def set_git_config(key, value):
    """Set a value in the global Git configuration."""
    result = subprocess.run(['git', 'config', '--global', key, value])
    if result.returncode != 0:
        logging.error("Error setting git config for %s", key)
    else:
        logging.debug("Set git config for %s", key)

def get_github_token():
    """Get the GitHub personal access token from git config or prompt the user."""
    token = get_git_config("github.token")
    if not token:
        token = input("Enter your GitHub personal access token: ").strip()
        if token:
            set_git_config("github.token", token)
        else:
            logging.error("No token provided, exiting.")
            sys.exit(1)
    else:
        logging.debug("GitHub token found in git config.")
    return token

def get_github_username(token):
    """Retrieve GitHub username from config or via the API if missing."""
    username = get_git_config("github.user")
    if not username:
        logging.debug("GitHub username not found in git config, retrieving from API...")
        headers = {'Authorization': f'token {token}'}
        response = requests.get("https://api.github.com/user", headers=headers)
        if response.status_code == 200:
            username = response.json().get("login")
            if username:
                set_git_config("github.user", username)
                logging.debug("GitHub username '%s' retrieved and stored.", username)
            else:
                logging.error("Could not retrieve username from API response.")
                sys.exit(1)
        else:
            logging.error("Failed to retrieve username from GitHub API: %s", response.content)
            sys.exit(1)
    else:
        logging.debug("GitHub username found in git config: %s", username)
    return username

def run_command(command, cwd=None):
    """Execute a shell command with optional working directory."""
    logging.debug("Running command: %s", " ".join(command))
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        logging.error("Command failed: %s", result.stderr)
        sys.exit(1)
    return result.stdout.strip()

def clone_repository(repo_ssh_url, target_dir):
    """Clone a repository using its SSH URL."""
    logging.debug("Cloning repository %s into %s", repo_ssh_url, target_dir)
    if os.path.exists(target_dir):
        logging.debug("Target directory '%s' already exists, skipping clone.", target_dir)
    else:
        run_command(["git", "clone", repo_ssh_url, target_dir])
    logging.debug("Repository cloned successfully.")

def create_branch(branch_name, repo_dir):
    """Create and checkout a new branch."""
    logging.debug("Creating branch %s", branch_name)
    run_command(["git", "checkout", "-b", branch_name], cwd=repo_dir)
    logging.debug("Branch %s created and checked out.", branch_name)

def read_template_file(template_path):
    """Read the content of the template file."""
    try:
        with open(template_path, "r") as f:
            content = f.read()
        logging.debug("Template file '%s' read successfully.", template_path)
        return content
    except Exception as e:
        logging.error("Failed to read template file '%s': %s", template_path, e)
        sys.exit(1)

def determine_environment_from_path(path):
    """Determine environment (prod, stage, dev) based on directory path."""
    lower_path = path.lower()
    if "prod" in lower_path:
        return "prod"
    elif "stage" in lower_path:
        return "stage"
    elif "dev" in lower_path:
        return "dev"
    else:
        return "unknown"

def create_file_from_template(file_path, template_content):
    """Create a file from the template content, replacing the environment placeholder."""
    env_value = determine_environment_from_path(file_path)
    # Use the placeholder '{environment}' if present; otherwise replace a default placeholder.
    if "{environment}" in template_content:
        generated_content = template_content.format(environment=env_value)
    else:
        generated_content = template_content.replace("replace_with_environment", env_value)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        f.write(generated_content)
    logging.debug("Created file %s with environment '%s'", file_path, env_value)

def commit_changes(branch_name, repo_dir):
    """Stage all changes and commit them with a message."""
    logging.debug("Staging changes.")
    run_command(["git", "add", "."], cwd=repo_dir)
    logging.debug("Committing changes.")
    run_command(["git", "commit", "-m", "Add terragrunt.hcl files in multiple directories"], cwd=repo_dir)
    logging.debug("Changes committed on branch %s.", branch_name)

def push_branch(branch_name, repo_dir):
    """Push the new branch to the remote repository."""
    logging.debug("Pushing branch %s", branch_name)
    run_command(["git", "push", "--set-upstream", "origin", branch_name], cwd=repo_dir)
    logging.debug("Branch pushed successfully.")

def create_pull_request(token, branch_name, base="main"):
    """Create a pull request using the GitHub API."""
    url = "https://api.github.com/repos/PearlHealth/infrastructure-live/pulls"
    headers = {'Authorization': f'token {token}'}
    data = {
        "title": "Add terragrunt.hcl to services directories",
        "head": branch_name,
        "base": base,
        "body": ("This pull request adds the terragrunt.hcl file to multiple service directories. "
                 "The file is generated from a template and the environment value is populated based on the filepath.")
    }
    logging.debug("Creating pull request via GitHub API.")
    response = requests.post(url, headers=headers, json=data)
    if response.status_code in [200, 201]:
        pr_url = response.json().get("html_url")
        logging.info("Pull request created successfully: %s", pr_url)
    else:
        logging.error("Failed to create pull request: %s", response.content)
        sys.exit(1)

def main():
    logging.info("Script started.")

    # Step 1: Authentication
    token = get_github_token()
    username = get_github_username(token)

    # Step 2: Clone repository via SSH
    repo_ssh_url = "git@github.com:PearlHealth/infrastructure-live.git"
    repo_dir = "infrastructure-live"
    clone_repository(repo_ssh_url, repo_dir)

    # Step 3: Create a new branch with a unique name
    branch_name = f"add-terragrunt-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    create_branch(branch_name, repo_dir)

    # Step 4: Read the template file for terragrunt.hcl
    template_file_path = "terragrunt.hcl"  # Ensure the template file is in the same directory as this script
    template_content = read_template_file(template_file_path)

    # Define target directories for adding the file
    directories = [
        "app-prod/us-east-2/prod/services",
        "app-stage/us-east-2/stage/services",
        "app-dev/us-east-2/dev/services"
    ]

    # Step 5: Create the terragrunt.hcl file in each specified directory using the template
    for directory in directories:
        file_path = os.path.join(repo_dir, directory, "terragrunt.hcl")
        create_file_from_template(file_path, template_content)

    # Step 6: Stage, commit, and push the new branch with changes
    commit_changes(branch_name, repo_dir)
    push_branch(branch_name, repo_dir)

    # Step 7: Create a pull request via the GitHub API
    create_pull_request(token, branch_name)

    logging.info("Script completed successfully.")

if __name__ == "__main__":
    main()
