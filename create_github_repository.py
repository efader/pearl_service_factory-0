import os
import sys
import subprocess
import requests

DEBUG = True

def debug(message):
    if DEBUG:
        print(f"DEBUG: {message}")

def get_git_config_value(key):
    """Retrieve a configuration value from the global git config."""
    try:
        debug(f"Attempting to retrieve git config value for '{key}'")
        value = subprocess.check_output(["git", "config", "--global", key])
        result = value.strip().decode('utf-8')
        debug(f"Retrieved '{key}': {result}")
        return result
    except subprocess.CalledProcessError as e:
        debug(f"Error retrieving git config '{key}': {e}")
        return None

def get_authenticated_username(headers):
    """Retrieve the authenticated user's username using the GitHub API."""
    try:
        debug("Requesting authenticated user info from GitHub API...")
        response = requests.get("https://api.github.com/user", headers=headers)
        debug(f"Received response with status code: {response.status_code}")
        response.raise_for_status()
        user_info = response.json()
        debug(f"Authenticated user info: {user_info}")
        return user_info.get("login")
    except Exception as e:
        debug(f"Error retrieving authenticated user: {e}")
        return None

def clone_repository(github_username, repo_name):
    """
    Clone the repository to the parent directory of the current working directory using SSH.
    Ensure your SSH keys are configured with GitHub for this to work.
    """
    # Use SSH URL for cloning, which avoids embedding the token in the URL.
    repo_url = f"git@github.com:{github_username}/{repo_name}.git"
    parent_dir = os.path.dirname(os.getcwd())
    target_dir = os.path.join(parent_dir, repo_name)
    debug(f"Cloning repository from {repo_url} to {target_dir}")
    
    if os.path.exists(target_dir):
        print(f"WARNING: The target directory '{target_dir}' already exists. Skipping clone.")
        return

    try:
        subprocess.run(["git", "clone", repo_url, target_dir], check=True)
        print(f"SUCCESS: Repository cloned to '{target_dir}'.")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to clone repository: {e}")
        sys.exit(1)

def main():
    print("============================================")
    print("  GitHub Repository Setup CLI")
    print("  This tool creates a new GitHub repository,")
    print("  sets up a 'develop' branch based on 'main',")
    print("  and then clones the repository to the parent directory using SSH.")
    print("============================================\n")

    # Retrieve GitHub token from global Git configuration.
    github_token = get_git_config_value("github.token")
    if not github_token:
        print("GitHub token not found in your global git configuration.")
        github_token = input("Please enter your GitHub personal access token: ").strip()
        if not github_token:
            print("ERROR: No token provided. Exiting.")
            sys.exit(1)
        # Store the token in the global Git configuration.
        try:
            subprocess.run(["git", "config", "--global", "github.token", github_token], check=True)
            print("SUCCESS: GitHub token stored in global git configuration.")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to store token in git configuration: {e}")
            sys.exit(1)
    else:
        print("SUCCESS: Retrieved GitHub token from configuration.")

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Attempt to get GitHub username from global configuration.
    github_username = get_git_config_value("github.user")
    if not github_username:
        debug("GitHub username not found in config; attempting to retrieve via API.")
        github_username = get_authenticated_username(headers)
        if not github_username:
            print("ERROR: Unable to retrieve GitHub username.")
            sys.exit(1)
        else:
            print(f"SUCCESS: Authenticated as GitHub user: {github_username}")
    else:
        print(f"SUCCESS: Using GitHub username from config: {github_username}")

    # Prompt the user for the repository name.
    repo_name = input("Enter the name for the new GitHub repository: ").strip()
    if not repo_name:
        print("ERROR: Repository name cannot be empty.")
        sys.exit(1)
    debug(f"Repository name provided: {repo_name}")

    # Step 1: Create the repository with auto initialization (creates a README).
    print(f"\nCreating repository '{repo_name}'...")
    create_repo_url = "https://api.github.com/user/repos"
    debug(f"Repository creation URL: {create_repo_url}")
    repo_payload = {
        "name": repo_name,
        "auto_init": True,    # Creates an initial commit with a README.
        "private": False      # Change to True for a private repository.
    }
    debug(f"Repository creation payload: {repo_payload}")
    try:
        repo_response = requests.post(create_repo_url, json=repo_payload, headers=headers)
        debug(f"Repository creation response status: {repo_response.status_code}")
        debug(f"Repository creation response content: {repo_response.text}")
        repo_response.raise_for_status()
    except Exception as e:
        print(f"ERROR: Failed to create repository: {e}")
        print("Response:", repo_response.text if 'repo_response' in locals() else "No response")
        sys.exit(1)
    print(f"SUCCESS: Repository '{repo_name}' created successfully.")

    # Step 2: Retrieve the commit SHA for the default 'main' branch.
    print("Retrieving 'main' branch commit SHA...")
    get_ref_url = f"https://api.github.com/repos/{github_username}/{repo_name}/git/ref/heads/main"
    debug(f"Retrieving main branch from URL: {get_ref_url}")
    try:
        ref_response = requests.get(get_ref_url, headers=headers)
        debug(f"Main branch retrieval response status: {ref_response.status_code}")
        debug(f"Main branch retrieval response content: {ref_response.text}")
        ref_response.raise_for_status()
    except Exception as e:
        print(f"ERROR: Failed to retrieve 'main' branch reference: {e}")
        print("Response:", ref_response.text if 'ref_response' in locals() else "No response")
        sys.exit(1)
    main_ref = ref_response.json()
    main_sha = main_ref["object"]["sha"]
    print(f"SUCCESS: Retrieved 'main' branch commit SHA: {main_sha}")

    # Step 3: Create the 'develop' branch based on the main branch commit SHA.
    print("Creating 'develop' branch...")
    create_ref_url = f"https://api.github.com/repos/{github_username}/{repo_name}/git/refs"
    develop_payload = {
        "ref": "refs/heads/develop",
        "sha": main_sha
    }
    debug(f"Develop branch creation URL: {create_ref_url}")
    debug(f"Develop branch payload: {develop_payload}")
    try:
        develop_response = requests.post(create_ref_url, json=develop_payload, headers=headers)
        debug(f"Develop branch creation response status: {develop_response.status_code}")
        debug(f"Develop branch creation response content: {develop_response.text}")
        develop_response.raise_for_status()
    except Exception as e:
        print(f"ERROR: Failed to create 'develop' branch: {e}")
        print("Response:", develop_response.text if 'develop_response' in locals() else "No response")
        sys.exit(1)
    print("SUCCESS: 'develop' branch created successfully.")

    # Step 4: Clone the repository to the parent directory using SSH.
    clone_repository(github_username, repo_name)

if __name__ == '__main__':
    main()
