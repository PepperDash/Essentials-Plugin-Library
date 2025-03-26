from github import Github
import os
import logging
import re

logging.basicConfig(level=logging.DEBUG)

def extract_min_essentials_version(repo):
    """
    Extracts the MinimumEssentialsFrameworkVersion from the CS file containing 'factory' in its name.
    """
    logging.debug(f"Searching for MinimumEssentialsFrameworkVersion in repo: {repo.name}")
    try:
        contents = repo.get_contents("")
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(repo.get_contents(file_content.path))
            elif file_content.type == "file" and "factory" in file_content.name.lower() and file_content.name.endswith(".cs"):
                logging.debug(f"Found potential file: {file_content.path}")
                file_data = repo.get_contents(file_content.path).decoded_content.decode("utf-8")
                # Adjusted regex to capture only the version string before ";"
                match = re.search(r'MinimumEssentialsFrameworkVersion\s*=\s*"([^"]+)"\s*;', file_data)
                if match:
                    version = match.group(1).strip()  # Extract and clean the version string
                    logging.debug(f"Found MinimumEssentialsFrameworkVersion: {version}")
                    return version
    except Exception as e:
        logging.error(f"Error processing repo {repo.name}: {e}")
    return "N/A"

def generate_markdown_file(repos):
    logging.debug("Generating markdown file.")
    with open('README.md', 'w') as file:
        file.write("# Essentials Plugin Library\n\n")
        file.write("| Repository                          | Visibility | Release | Min Essentials |\n")
        file.write("|-------------------------------------|------------|---------|----------------|\n")
        for repo in sorted(repos, key=lambda x: x.name):
            if repo.name.startswith('epi-'):
                logging.debug(f"Processing repo: {repo.name}, Public: {not repo.private}")
                visibility = "Public" if not repo.private else "Internal"
                releases = repo.get_releases()
                current_release = "N/A"
                for release in releases:
                    if not release.prerelease:
                        current_release = release.tag_name
                        break

                min_essentials_version = extract_min_essentials_version(repo)

                file.write(f"| [{repo.name}]({repo.html_url}) | {visibility} | {current_release} | {min_essentials_version} |\n")

def main():
    logging.debug("Starting script.")

    # Check if running in GitHub Actions
    is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'

    # Get the token
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        logging.error("GITHUB_TOKEN environment variable is not set or is empty. Ensure it is passed in the workflow or set locally.")
        return

    # Get the organization name
    org_name = os.getenv('ORG_NAME')
    if not org_name:
        if is_github_actions:
            logging.error("ORG_NAME environment variable is not set or is empty in GitHub Actions.")
            return
        else:
            org_name = input("Enter the organization name: ").strip()

    # Authenticate with GitHub
    g = Github(token)

    try:
        org = g.get_organization(org_name)
        repos = list(org.get_repos(type='all'))  # Fetch all types of repositories
        logging.debug(f"Number of repos before filtering: {len(repos)}")
        generate_markdown_file(repos)
    except Exception as e:
        logging.error(f"Error accessing organization or repositories: {e}")

if __name__ == "__main__":
    main()
