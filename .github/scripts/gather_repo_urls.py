from github import Github
import os
import re

def find_interfaces(repo, path=""):
    interfaces = []
    try:
        contents = repo.get_contents(path, ref="main")
        for content in contents:
            if content.type == "dir":
                interfaces.extend(find_interfaces(repo, content.path))
            elif content.name.endswith('.cs'):
                file_content = repo.get_contents(content.path).decoded_content.decode()
                matches = re.findall(r'public class [A-Za-z0-9_]+ : ([A-Za-z0-9_,\s]+)', file_content)
                for match in matches:
                    for item in match.split(","):
                        item = item.strip()
                        if item.startswith("I"):
                            interfaces.append(item)
    except Exception as e:
        print(f"Error while finding interfaces in {repo.name}: {e}")

    return list(set(interfaces))  # Remove duplicates


def generate_markdown_file(repos):
    with open('README.md', 'w') as file:
        file.write("# Essentials Plugin Library\n\n")
        file.write("| Repository                          | Visibility     | Current Release | Interfaces |\n")
        file.write("|-------------------------------------|----------------|-----------------|------------|\n")
        for repo in sorted(repos, key=lambda x: x.name):
            if repo.name.startswith('epi-'):
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
    g = Github(os.getenv('GITHUB_TOKEN'))
    org = g.get_organization(os.getenv('ORG_NAME'))

    repos = list(org.get_repos(type='all'))  # Fetch all types of repositories

    print(f"Number of repos before filtering: {len(repos)}")  # Debugging line

    generate_markdown_file(repos)

if __name__ == "__main__":
    main()
