from github import Github
import os
import logging
import re
import concurrent.futures  # Add this import

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

def process_single_repo(repo, max_repo_name, max_release, max_build_tag, max_min_essentials):
    """
    Processes a single repository and returns the data needed for the markdown table.
    """
    if not repo.name.startswith('epi-'):
        return None

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

    return {
        "repo_name": repo_name,
        "repo_url": repo.html_url,
        "visibility": visibility,
        "release": release,
        "build_tag": build_tag,
        "min_essentials": min_essentials,
        "current_release": current_release
    }

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

    # --- CONCURRENT PROCESSING START ---
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(
                process_single_repo, repo, max_repo_name, max_release, max_build_tag, max_min_essentials
            )
            for repo in repo_list
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
                total_epi_repos += 1
                norm = normalize_release_tag(result["current_release"], result["repo_name"])
                if norm == "1":
                    total_release_1_x += 1
                elif norm == "2":
                    total_release_2_x += 1
                elif result["current_release"] == "N/A":
                    total_release_na += 1
    # --- CONCURRENT PROCESSING END ---

    with open('README.md', 'w', newline='\n') as file:
        file.write("# Essentials Plugin Library\n\n")

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
        for result in sorted(results, key=lambda x: x["repo_name"]):
            file.write(
                f"| [{result['repo_name']}]({result['repo_url']}) | {result['visibility']} | {result['release']} | {result['build_tag']} | {result['min_essentials']} |\n"
            )


def truncate(s, max_length):
    return s if len(s) <= max_length else s[:max_length - 3] + "..."


def normalize_release_tag(tag, repo_name=None):
    """
    Normalize the release tag to handle 'v1.', '1.', etc.
    Returns the major version as a string, or None if not matched.
    """
    print(f"[normalize_release_tag] Repo: '{repo_name}', Raw tag value: '{tag}'")  # Debug print
    if tag and tag != "N/A":
        m = re.match(r"v?(\d+)\.", tag)
        if m:
            print(f"[normalize_release_tag] Repo: '{repo_name}', Matched major version: '{m.group(1)}'")  # Debug print
            return m.group(1)
    return None

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
