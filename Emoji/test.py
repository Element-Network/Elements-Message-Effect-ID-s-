import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ==========================
# CONFIG
# ==========================
TOKEN = ""

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
}

BACKUP_DIR = "Backup"
MAX_WORKERS = 4

# Skip any repository whose name starts with these prefixes
SKIP_PREFIXES = (
    "android",
    "wzml_new",
)

os.makedirs(BACKUP_DIR, exist_ok=True)

print_lock = threading.Lock()


def log(*args):
    with print_lock:
        print(*args)


# ==========================
# FETCH REPOSITORIES
# ==========================
def get_all_repos():
    repos = []
    page = 1

    while True:
        url = f"https://api.github.com/user/repos?per_page=100&page={page}"

        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()

        data = r.json()

        if not data:
            break

        repos.extend(data)
        page += 1

    return repos


# ==========================
# FETCH BRANCHES
# ==========================
def get_all_branches(owner, repo):
    branches = []
    page = 1

    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/branches?per_page=100&page={page}"

        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()

        data = r.json()

        if not data:
            break

        branches.extend(data)
        page += 1

    return branches


# ==========================
# DOWNLOAD ONE REPOSITORY
# ==========================
def clone_repository(owner, repo_name):
    try:

        # Skip android repositories
        if repo_name.lower().startswith(SKIP_PREFIXES):
            log(f"[SKIP] {repo_name}")
            return

        repo_dir = os.path.join(BACKUP_DIR, repo_name)
        os.makedirs(repo_dir, exist_ok=True)

        branches = get_all_branches(owner, repo_name)

        # Skip repository if every branch already exists
        completed = True

        for branch in branches:
            branch_dir = os.path.join(repo_dir, branch["name"])

            if not os.path.isdir(os.path.join(branch_dir, ".git")):
                completed = False
                break

        if completed:
            log(f"[SKIP] {repo_name} (already downloaded)")
            return

        clone_url = f"https://{TOKEN}@github.com/{owner}/{repo_name}.git"

        for branch in branches:

            branch_name = branch["name"]
            branch_dir = os.path.join(repo_dir, branch_name)

            # Skip already cloned branch
            if os.path.isdir(os.path.join(branch_dir, ".git")):
                log(f"[SKIP] {repo_name}/{branch_name}")
                continue

            log(f"[DOWNLOAD] {repo_name}/{branch_name}")

            result = subprocess.run(
                [
                    "git",
                    "clone",
                    "--single-branch",
                    "--branch",
                    branch_name,
                    clone_url,
                    branch_dir,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            if result.returncode == 0:
                log(f"[DONE] {repo_name}/{branch_name}")
            else:
                log(f"[FAILED] {repo_name}/{branch_name}")

    except Exception as e:
        log(f"[ERROR] {repo_name}: {e}")


# ==========================
# MAIN
# ==========================
def main():
    repos = get_all_repos()

    log(f"\nFound {len(repos)} repositories.\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

        futures = [
            executor.submit(
                clone_repository,
                repo["owner"]["login"],
                repo["name"],
            )
            for repo in repos
        ]

        for _ in as_completed(futures):
            pass

    log("\n✅ All repositories processed.")


if __name__ == "__main__":
    main()