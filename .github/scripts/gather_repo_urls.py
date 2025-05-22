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

def process_repositories(repo_list):
    """
    Processes the repositories to calculate counts and generate the markdown file.
    """
    logging.debug("Processing repositories to calculate counts and generate markdown.")

    # Initialize counters
    total_epi_repos = 0
    total_release_1_x = 0
    total_release_2_x = 0
    total_release_na = 0

    # Define maximum lengths for truncation
    max_repo_name = 32
    max_release = 10
    max_build_tag = 24
    max_min_essentials = 8

    with open('README.md', 'w', newline='\n') as file:
        file.write("# Essentials Plugin Library\n\n")

        # Iterate through repos to calculate counts
        for repo in sorted(repo_list, key=lambda x: x.name):
            if repo.name.startswith('epi-'):
                logging.debug(f"Processing repository: {repo.name}")
                total_epi_repos += 1

                # Convert PaginatedList to list before accessing
                releases = list(repo.get_releases())
                tags = list(repo.get_tags())

                current_release = "N/A"
                latest_build_tag = "N/A"

                # Get the latest release
                if releases:
                    for release in releases:
                        if not release.prerelease:
                            current_release = release.tag_name
                            break
                else:
                    logging.warning(f"No releases found for repository: {repo.name}")

                # Get the latest build tag
                if tags:
                    latest_build_tag = tags[0].name  # Get the most recent tag
                else:
                    latest_build_tag = "N/A"  # Handle empty tags list
                    logging.warning(f"No tags found for repository: {repo.name}")

                # Count based on release version
                if current_release.startswith("1."):
                    total_release_1_x += 1
                elif current_release.startswith("2."):
                    total_release_2_x += 1
                elif current_release == "N/A":
                    total_release_na += 1

        # Write the counts to the markdown file in a table format
        file.write("| Metric                 | Count |\n")
        file.write("|------------------------|-------|\n")
        file.write(f"| Total repos            | {total_epi_repos} |\n")
        file.write(f"| Total Essentials v1    | {total_release_1_x} |\n")
        file.write(f"| Total Essentials v2    | {total_release_2_x} |\n")
        file.write(f"| Total Essentials N/A   | {total_release_na} |\n\n\n")

        # Write the table header
        file.write("| Repository                          | Visibility | Release | Build Output | Min Essentials |\n")
        file.write("|-------------------------------------|------------|---------|--------------|----------------|\n")

        # Write the table rows
        for repo in sorted(repo_list, key=lambda x: x.name):
            if repo.name.startswith('epi-'):
                logging.debug(f"Processing Repository: {repo.name}, Visibility: {'Public' if not repo.private else 'Internal/Private'}")
                visibility = "Public" if not repo.private else "Internal"

                # Convert PaginatedList to list before accessing
                releases = list(repo.get_releases())
                tags = list(repo.get_tags())

                current_release = "N/A"
                latest_build_tag = "N/A"

                # Get the latest release
                if releases:
                    for release in releases:
                        if not release.prerelease:
                            current_release = release.tag_name
                            break

                # Get the latest build tag
                if tags:
                    latest_build_tag = tags[0].name  # Get the most recent tag

                min_essentials_version = extract_min_essentials_version(repo)

                repo_name = truncate(repo.name, max_repo_name)
                release = truncate(current_release, max_release)
                build_tag = truncate(latest_build_tag, max_build_tag)
                min_essentials = truncate(min_essentials_version, max_min_essentials)

                file.write(f"| [{repo_name}]({repo.html_url}) | {visibility} | {release} | {build_tag} | {min_essentials} |\n")


def truncate(s, max_length):
    return s if len(s) <= max_length else s[:max_length - 3] + "..."


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
        repos = org.get_repos(type='all')
        logging.debug(f"Repos object type: {type(repos)}")

        # Explicitly iterate over the PaginatedList to collect repositories
        repo_list = []
        for repo in repos:
            logging.debug(f"Fetched repo: {repo.name}")
            repo_list.append(repo)
        logging.debug(f"Number of repos after iteration: {len(repo_list)}")

        # Process the repositories after the list is fully populated
        process_repositories(repo_list)
    except Exception as e:
        logging.error(f"Error accessing organization or repositories: {e}")


if __name__ == "__main__":
    main()
