from github import Github
import os
import re
import logging

logging.basicConfig(level=logging.DEBUG)

def find_interfaces(repo, path=""):
    logging.debug(f"Searching for interfaces in repo: {repo.name}, path: {path}")
    interfaces = []
    try:
        contents = repo.get_contents(path, ref="main")
        for content in contents:
            if content.type == "dir":
                logging.debug(f"Found directory: {content.path}")
                interfaces.extend(find_interfaces(repo, content.path))
            elif content.name.endswith('.cs'):
                logging.debug(f"Found C# file: {content.name}")
                file_content = repo.get_contents(content.path).decoded_content.decode()
                matches = re.findall(r'public (abstract )?class [A-Za-z0-9_]+ : ([A-Za-z0-9_,\s]+)', file_content)
                for match in matches:
                    for item in match[1].split(","):
                        item = item.strip()
                        if item.startswith("I"):
                            interfaces.append(item)
    except Exception as e:
        logging.error(f"Error while finding interfaces in {repo.name}: {e}")
        return interfaces  # Return whatever interfaces were found before the exception

    return list(set(interfaces))  # Remove duplicates

def generate_markdown_file(repos):
    logging.debug("Generating markdown file.")
    with open('README.md', 'w') as file:
        file.write("# Essentials Plugin Library\n\n")
        file.write("| Repository                          | Visibility     | Current Release | Interfaces |\n")
        file.write("|-------------------------------------|----------------|-----------------|------------|\n")
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

                interfaces = find_interfaces(repo)
                interfaces_str = ", ".join(interfaces) if interfaces else "N/A"

                file.write(f"| [{repo.name}]({repo.html_url}) | {visibility} | {current_release} | {interfaces_str} |\n")

def main():
    logging.debug("Starting script.")
    g = Github(os.getenv('GITHUB_TOKEN'))
    org = g.get_organization(os.getenv('ORG_NAME'))

    repos = list(org.get_repos(type='all'))  # Fetch all types of repositories

    logging.debug(f"Number of repos before filtering: {len(repos)}")  # Debugging line

    generate_markdown_file(repos)

if __name__ == "__main__":
    main()
