from github import Github
from github import RateLimitExceededException
import os
import logging
import re
import concurrent.futures
import time
import random

logging.basicConfig(level=logging.DEBUG)

def handle_rate_limit(g, operation_name="API operation"):
    """
    Check rate limit and wait if necessary before making API calls.
    """
    try:
        rate_limit = g.get_rate_limit()
        core_remaining = rate_limit.core.remaining
        core_reset_time = rate_limit.core.reset
        
        logging.debug(f"Rate limit status for {operation_name}: {core_remaining} requests remaining")
        
        if core_remaining < 10:  # Conservative threshold
            wait_time = (core_reset_time - time.time()) + 5  # Add 5 second buffer
            if wait_time > 0:
                logging.warning(f"Rate limit nearly exceeded. Waiting {wait_time:.1f} seconds before {operation_name}")
                time.sleep(wait_time)
    except Exception as e:
        logging.warning(f"Could not check rate limit: {e}")

def retry_with_backoff(func, max_retries=3, base_delay=1):
    """
    Retry a function with exponential backoff for rate limit and network errors.
    """
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            error_str = str(e).lower()
            if "rate limit" in error_str or "403" in error_str or "502" in error_str or "503" in error_str:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logging.warning(f"Rate limit or server error encountered, retrying in {delay:.1f} seconds (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(delay)
                    continue
            raise e
    return None

def extract_min_essentials_version(repo):
    """
    Extracts the MinimumEssentialsFrameworkVersion from CS files containing 'factory' in their name,
    or from .csproj files where it might be defined as an XML element or property.
    """
    logging.debug(f"Searching for MinimumEssentialsFrameworkVersion in repo: {repo.name}")
    try:
        def get_contents():
            return repo.get_contents("")
        
        contents = retry_with_backoff(get_contents)
        if not contents:
            return "N/A"
            
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                def get_dir_contents():
                    return repo.get_contents(file_content.path)
                dir_contents = retry_with_backoff(get_dir_contents)
                if dir_contents:
                    contents.extend(dir_contents)
            elif file_content.type == "file":
                # Check factory CS files (original logic)
                if "factory" in file_content.name.lower() and file_content.name.endswith(".cs"):
                    logging.debug(f"Found potential factory file: {file_content.path}")
                    
                    def get_file_content():
                        return repo.get_contents(file_content.path).decoded_content.decode("utf-8")
                    
                    file_data = retry_with_backoff(get_file_content)
                    if not file_data:
                        continue
                        
                    # Pattern 1: MinimumEssentialsFrameworkVersion = "version"; (original pattern)
                    match = re.search(r'MinimumEssentialsFrameworkVersion\s*=\s*"([^"]+)"\s*;', file_data)
                    if match:
                        version = match.group(1).strip()  # Extract and clean the version string
                        logging.debug(f"Found MinimumEssentialsFrameworkVersion in factory file: {version}")
                        return version
                    
                    # Pattern 2: public const string MinumumEssentialsVersion = "version"; (alternate pattern found in some repos)
                    match = re.search(r'const\s+string\s+MinumumEssentialsVersion\s*=\s*"([^"]+)"\s*;', file_data)
                    if match:
                        version = match.group(1).strip()
                        logging.debug(f"Found MinumumEssentialsVersion (const) in factory file: {version}")
                        return version
                    
                    # Pattern 3: MinumumEssentialsVersion = "version"; (without const keyword)
                    match = re.search(r'MinumumEssentialsVersion\s*=\s*"([^"]+)"\s*;', file_data)
                    if match:
                        version = match.group(1).strip()
                        logging.debug(f"Found MinumumEssentialsVersion in factory file: {version}")
                        return version
                
                # Also check .csproj files for MinimumEssentialsFrameworkVersion (new logic)
                elif file_content.name.endswith(".csproj"):
                    logging.debug(f"Found csproj file: {file_content.path}")
                    
                    def get_csproj_content():
                        return repo.get_contents(file_content.path).decoded_content.decode("utf-8")
                    
                    file_data = retry_with_backoff(get_csproj_content)
                    if not file_data:
                        continue
                        
                    # Look for MinimumEssentialsFrameworkVersion in XML format
                    # Pattern 1: <MinimumEssentialsFrameworkVersion>version</MinimumEssentialsFrameworkVersion>
                    match = re.search(r'<MinimumEssentialsFrameworkVersion>([^<]+)</MinimumEssentialsFrameworkVersion>', file_data)
                    if match:
                        version = match.group(1).strip()
                        logging.debug(f"Found MinimumEssentialsFrameworkVersion in csproj (XML element): {version}")
                        return version
                    
                    # Pattern 2: <Property Name="MinimumEssentialsFrameworkVersion">version</Property>
                    match = re.search(r'<Property\s+Name="MinimumEssentialsFrameworkVersion">([^<]+)</Property>', file_data)
                    if match:
                        version = match.group(1).strip()
                        logging.debug(f"Found MinimumEssentialsFrameworkVersion in csproj (Property element): {version}")
                        return version
                    
                    # Pattern 3: MinimumEssentialsFrameworkVersion="version" (attribute style)
                    match = re.search(r'MinimumEssentialsFrameworkVersion="([^"]+)"', file_data)
                    if match:
                        version = match.group(1).strip()
                        logging.debug(f"Found MinimumEssentialsFrameworkVersion in csproj (attribute): {version}")
                        return version
    except Exception as e:
        logging.error(f"Error processing repo {repo.name}: {e}")
    return "N/A"

def extract_pepperdash_essentials_package_version(repo):
    """
    Extracts the PepperDashEssentials package version from packages.config or .csproj files.
    """
    logging.debug(f"Searching for PepperDashEssentials package reference in repo: {repo.name}")
    try:
        def get_contents():
            return repo.get_contents("")
        
        contents = retry_with_backoff(get_contents)
        if not contents:
            return "N/A"
            
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                def get_dir_contents():
                    return repo.get_contents(file_content.path)
                dir_contents = retry_with_backoff(get_dir_contents)
                if dir_contents:
                    contents.extend(dir_contents)
            elif file_content.type == "file":
                # Fetch file content only once per file
                file_data = None
                
                # Check packages.config files
                if file_content.name == "packages.config":
                    logging.debug(f"Found packages.config file: {file_content.path}")
                    
                    def get_packages_config():
                        return repo.get_contents(file_content.path).decoded_content.decode("utf-8")
                    
                    file_data = retry_with_backoff(get_packages_config)
                    if not file_data:
                        continue
                        
                    # Look for PepperDashEssentials package in packages.config (attribute order agnostic)
                    for pkg_match in re.finditer(r'<package\b[^>]*>', file_data):
                        pkg_tag = pkg_match.group(0)
                        id_match = re.search(r'id="([^"]+)"', pkg_tag)
                        version_match = re.search(r'version="([^"]+)"', pkg_tag)
                        if id_match and id_match.group(1) == "PepperDashEssentials" and version_match:
                            version = version_match.group(1).strip()
                            logging.debug(f"Found PepperDashEssentials version in packages.config: {version}")
                            return version
                
                # Check .csproj files for PackageReference
                elif file_content.name.endswith(".csproj"):
                    logging.debug(f"Found csproj file: {file_content.path}")
                    
                    def get_csproj_content():
                        return repo.get_contents(file_content.path).decoded_content.decode("utf-8")
                    
                    file_data = retry_with_backoff(get_csproj_content)
                    if not file_data:
                        continue
                        
                    # Look for PackageReference to PepperDashEssentials (attribute order agnostic)
                    for pkg_match in re.finditer(r'<PackageReference\b[^>]*>', file_data):
                        pkg_tag = pkg_match.group(0)
                        include_match = re.search(r'Include="([^"]+)"', pkg_tag)
                        version_match = re.search(r'Version="([^"]+)"', pkg_tag)
                        if include_match and include_match.group(1) == "PepperDashEssentials" and version_match:
                            version = version_match.group(1).strip()
                            logging.debug(f"Found PepperDashEssentials version in csproj: {version}")
                            return version
                    
                    # Also check for the alternative format
                    match = re.search(r'<PackageReference\s+Include="PepperDashEssentials"[^>]*>\s*<Version>([^<]+)</Version>', file_data, re.DOTALL)
                    if match:
                        version = match.group(1).strip()
                        logging.debug(f"Found PepperDashEssentials version in csproj (Version element): {version}")
                        return version
    except Exception as e:
        logging.error(f"Error processing repo {repo.name}: {e}")
    return "N/A"

def process_single_repo(repo, max_repo_name, max_release, max_build_tag, max_min_essentials, g=None):
    """
    Processes a single repository and returns the data needed for the markdown table.
    """
    if not repo.name.startswith('epi-'):
        return None

    logging.debug(f"Processing Repository: {repo.name}, Visibility: {'Public' if not repo.private else 'Internal/Private'}")
    
    # Check rate limit before processing each repo
    if g:
        handle_rate_limit(g, f"processing repo {repo.name}")
    
    visibility = "Public" if not repo.private else "Internal"

    # Convert PaginatedList to list before accessing with rate limit handling
    def get_releases():
        return list(repo.get_releases())
    
    def get_tags():
        return list(repo.get_tags())
    
    releases = retry_with_backoff(get_releases) or []
    tags = retry_with_backoff(get_tags) or []

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
    package_version = extract_pepperdash_essentials_package_version(repo)

    repo_name = truncate(repo.name, max_repo_name)
    release = truncate(current_release, max_release)
    build_tag = truncate(latest_build_tag, max_build_tag)
    min_essentials = truncate(min_essentials_version, max_min_essentials)
    pkg_version = truncate(package_version, max_min_essentials)

    return {
        "repo_name": repo_name,
        "repo_url": repo.html_url,
        "visibility": visibility,
        "release": release,
        "build_tag": build_tag,
        "min_essentials": min_essentials,
        "package_version": pkg_version,
        "current_release": current_release
    }

def process_repositories(repo_list, g):
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

    # Check initial rate limit
    handle_rate_limit(g, "starting repository processing")

    # --- CONCURRENT PROCESSING START ---
    # Reduced max_workers to be more conservative with rate limits
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(
                process_single_repo, repo, max_repo_name, max_release, max_build_tag, max_min_essentials, g
            )
            for repo in repo_list
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
                total_epi_repos += 1
                norm = normalize_release_tag(result["package_version"], result["repo_name"])
                if norm == "1":
                    total_release_1_x += 1
                elif norm == "2":
                    total_release_2_x += 1
                elif result["min_essentials"] == "N/A":
                    total_release_na += 1
    # --- CONCURRENT PROCESSING END ---

    # Separate results by Essentials version
    essentials_1_repos = []
    essentials_2_repos = []
    other_repos = []
    
    for result in results:
        norm = normalize_release_tag(result["package_version"], result["repo_name"])
        if norm == "1":
            essentials_1_repos.append(result)
        elif norm == "2":
            essentials_2_repos.append(result)
        else:
            other_repos.append(result)

    with open('README.md', 'w', newline='\n') as file:
        file.write("# Essentials Plugin Library\n\n")
        file.write(f"[Click here to see the Readme Diff](https://pepperdash.github.io/Essentials-Plugin-Library/readme-diff.html)\n")
        # Write the counts to the markdown file in a table format
        file.write("| Metric                 | Count |\n")
        file.write("|------------------------|-------|\n")
        file.write(f"| Total repos            | {total_epi_repos} |\n")
        file.write(f"| Total Essentials v1    | {total_release_1_x} |\n")
        file.write(f"| Total Essentials v2    | {total_release_2_x} |\n")
        file.write(f"| Total Essentials N/A   | {total_release_na} |\n\n\n")

        # Write Essentials 1 table
        if essentials_1_repos:
            file.write("## Essentials Framework v1 Repositories\n\n")
            file.write("| Repository                          | Visibility | Release | Build Output | Min Essentials | Package Version |\n")
            file.write("|-------------------------------------|------------|---------|--------------|----------------|----------------|\n")
            for result in sorted(essentials_1_repos, key=lambda x: x["repo_name"]):
                file.write(
                    f"| [{result['repo_name']}]({result['repo_url']}) | {result['visibility']} | {result['release']} | {result['build_tag']} | {result['min_essentials']} | {result['package_version']} |\n"
                )
            file.write("\n")

        # Write Essentials 2 table
        if essentials_2_repos:
            file.write("## Essentials Framework v2 Repositories\n\n")
            file.write("| Repository                          | Visibility | Release | Build Output | Min Essentials | Package Version |\n")
            file.write("|-------------------------------------|------------|---------|--------------|----------------|----------------|\n")
            for result in sorted(essentials_2_repos, key=lambda x: x["repo_name"]):
                file.write(
                    f"| [{result['repo_name']}]({result['repo_url']}) | {result['visibility']} | {result['release']} | {result['build_tag']} | {result['min_essentials']} | {result['package_version']} |\n"
                )
            file.write("\n")

        # Write other repositories table (N/A or unclear versions)
        if other_repos:
            file.write("## Other Repositories\n\n")
            file.write("| Repository                          | Visibility | Release | Build Output | Min Essentials | Package Version |\n")
            file.write("|-------------------------------------|------------|---------|--------------|----------------|----------------|\n")
            for result in sorted(other_repos, key=lambda x: x["repo_name"]):
                file.write(
                    f"| [{result['repo_name']}]({result['repo_url']}) | {result['visibility']} | {result['release']} | {result['build_tag']} | {result['min_essentials']} | {result['package_version']} |\n"
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
        
        def get_repos():
            return org.get_repos(type='all')
        
        repos = retry_with_backoff(get_repos)
        if not repos:
            logging.error("Failed to fetch repositories after retries")
            return
            
        logging.debug(f"Repos object type: {type(repos)}")

        # Check rate limit before iterating through repos
        handle_rate_limit(g, "fetching repository list")

        # Explicitly iterate over the PaginatedList to collect repositories
        repo_list = []
        for repo in repos:
            logging.debug(f"Fetched repo: {repo.name}")
            repo_list.append(repo)
            
            # Check rate limit periodically during repo fetching
            if len(repo_list) % 20 == 0:  # Check every 20 repos
                handle_rate_limit(g, f"fetching repositories (processed {len(repo_list)})")
                
        logging.debug(f"Number of repos after iteration: {len(repo_list)}")

        # Process the repositories after the list is fully populated
        process_repositories(repo_list, g)
    except Exception as e:
        logging.error(f"Error accessing organization or repositories: {e}")
        # Log rate limit info if available
        try:
            rate_limit = g.get_rate_limit()
            logging.error(f"Current rate limit: {rate_limit.core.remaining}/{rate_limit.core.limit} remaining, resets at {rate_limit.core.reset}")
        except:
            pass


if __name__ == "__main__":
    main()
