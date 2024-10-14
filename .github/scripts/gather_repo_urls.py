from github import Github
import os
import re
import logging

logging.basicConfig(level=logging.DEBUG)

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


                file.write(f"| [{repo.name}]({repo.html_url}) | {visibility} | {current_release} |\n")

def main():
    logging.debug("Starting script.")
    g = Github(os.getenv('GITHUB_TOKEN'))
    org = g.get_organization(os.getenv('ORG_NAME'))

    repos = list(org.get_repos(type='all'))  # Fetch all types of repositories

    logging.debug(f"Number of repos before filtering: {len(repos)}")  # Debugging line

    generate_markdown_file(repos)

if __name__ == "__main__":
    main()
