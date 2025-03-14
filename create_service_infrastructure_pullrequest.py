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
    """Execute a shell command with an optional working directory."""
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

def create_file_from_template(file_path, template_content, extra_vars, environment):
    """
    Create a file from the template content.
    Substitutions include the explicit environment, service name, and other configuration variables.
    """
    substitutions = {"environment": environment}
    substitutions.update(extra_vars)
    try:
        generated_content = template_content.format(**substitutions)
    except KeyError as e:
        logging.error("Missing placeholder value for %s in template substitution.", e)
        sys.exit(1)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        f.write(generated_content)
    logging.debug("Created file %s with substitutions: %s", file_path, substitutions)

def commit_changes(branch_name, repo_dir, service_name):
    """Stage all changes and commit them with a detailed, templated commit message."""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    commit_message = (
        f"Pearl Service Factory Commit: Add terragrunt.hcl for service '{service_name}'\n\n"
        "This commit was automatically generated by the Pearl Service Factory automated script. "
        "It adds the terragrunt.hcl configuration file for the service into the appropriate directories "
        "for prod, stage, and dev environments.\n\n"
        "Troubleshooting/Debug Info:\n"
        f"- Generated branch name: {branch_name}\n"
        f"- Timestamp: {timestamp}\n"
        "- Repository: PearlHealth/infrastructure-live\n\n"
        "## What\n"
        "<!-- Provide a summary of what's being changed. Link to PRs if deploying module version updates. -->\n\n"
        "## Why\n"
        "<!-- Link to related tickets and provide an explanation for changes. -->\n\n"
        "## Plan Explanation\n"
        "<!-- Once Pipelines provides a plan, summarize the changes for the reviewers. -->\n"
    )
    logging.debug("Staging changes.")
    run_command(["git", "add", "."], cwd=repo_dir)
    logging.debug("Committing changes with detailed message.")
    run_command(["git", "commit", "-m", commit_message], cwd=repo_dir)
    logging.debug("Changes committed on branch %s.", branch_name)

def push_branch(branch_name, repo_dir):
    """Push the new branch to the remote repository."""
    logging.debug("Pushing branch %s", branch_name)
    run_command(["git", "push", "--set-upstream", "origin", branch_name], cwd=repo_dir)
    logging.debug("Branch pushed successfully.")

def create_pull_request(token, branch_name, service_name, base="main"):
    """Create a pull request using the GitHub API with a detailed description."""
    pr_title = f"Pearl Service Factory: Add terragrunt.hcl for service '{service_name}'"
    pr_body = (
        "## What\n"
        f"Automatically added terragrunt.hcl configuration for service '{service_name}' to prod, stage, and dev environments.\n\n"
        "## Why\n"
        "This commit is part of the automated process by the Pearl Service Factory to streamline service deployments. "
        "It includes the necessary configuration files generated from a template with service- and environment-specific values.\n\n"
        "## Plan Explanation\n"
        "The automated script cloned the repository, created a new branch, generated configuration files using a provided template "
        "(populated with explicit environment, service name, and other variables), committed the changes with detailed troubleshooting/debug "
        "information, pushed the branch, and created this pull request.\n"
    )
    url = "https://api.github.com/repos/PearlHealth/infrastructure-live/pulls"
    headers = {'Authorization': f'token {token}'}
    data = {
        "title": pr_title,
        "head": branch_name,
        "base": base,
        "body": pr_body
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

    # Get GitHub authentication details.
    token = get_github_token()
    username = get_github_username(token)

    # Get service name and additional configuration variables.
    if len(sys.argv) > 1:
        service_name = sys.argv[1]
    else:
        service_name = input("Enter the service name: ").strip()
    if not service_name:
        logging.error("Service name is required.")
        sys.exit(1)

    # Additional configuration variable.
    if len(sys.argv) > 2:
        some_variable = sys.argv[2]
    else:
        some_variable = input("Enter value for 'some_variable' (or press Enter for default 'default_value'): ").strip() or "default_value"

    extra_vars = {"service_name": service_name, "some_variable": some_variable}

    # Clone repository via SSH.
    repo_ssh_url = "git@github.com:PearlHealth/infrastructure-live.git"
    repo_dir = "infrastructure-live"
    clone_repository(repo_ssh_url, repo_dir)

    # Create a new branch with a unique name.
    branch_name = f"add-terragrunt-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    create_branch(branch_name, repo_dir)

    # Read the template file for terragrunt.hcl.
    template_file_path = "terragrunt.hcl"  # Template file must be in the same directory as this script.
    template_content = read_template_file(template_file_path)

    # Define explicit environment and base directory pairs.
    env_dirs = [
        {"environment": "prod", "base_dir": "app-prod/us-east-2/prod/services"},
        {"environment": "stage", "base_dir": "app-stage/us-east-2/stage/services"},
        {"environment": "dev", "base_dir": "app-dev/us-east-2/dev/services"}
    ]

    # For each environment, create the file under the service subdirectory.
    for env_info in env_dirs:
        final_dir = os.path.join(repo_dir, env_info["base_dir"], service_name)
        file_path = os.path.join(final_dir, "terragrunt.hcl")
        create_file_from_template(file_path, template_content, extra_vars, env_info["environment"])

    # Stage, commit, and push the new branch with changes.
    commit_changes(branch_name, repo_dir, service_name)
    push_branch(branch_name, repo_dir)

    # Create a pull request via the GitHub API.
    create_pull_request(token, branch_name, service_name)

    logging.info("Script completed successfully.")

if __name__ == "__main__":
    main()
