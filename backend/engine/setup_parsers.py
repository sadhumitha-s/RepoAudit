import os
import subprocess
from tree_sitter import Language

def main():
    engine_dir = os.path.dirname(os.path.abspath(__file__))
    vendor_dir = os.path.join(engine_dir, "vendor")
    build_dir = os.path.join(engine_dir, "build")

    os.makedirs(vendor_dir, exist_ok=True)
    os.makedirs(build_dir, exist_ok=True)

    repos = {
        "tree-sitter-r": "https://github.com/r-lib/tree-sitter-r",
        "tree-sitter-julia": "https://github.com/tree-sitter/tree-sitter-julia"
    }

    # Clone repos if they don't exist
    for name, url in repos.items():
        repo_path = os.path.join(vendor_dir, name)
        if not os.path.exists(repo_path):
            print(f"Cloning {name}...")
            subprocess.check_call(["git", "clone", "--depth", "1", url, repo_path])

    # Build the libraries into build/languages.so
    lib_path = os.path.join(build_dir, "languages.so")
    print(f"Building tree-sitter library to {lib_path}...")
    vendor_paths = [os.path.join(vendor_dir, name) for name in repos.keys()]

    Language.build_library(
        lib_path,
        vendor_paths
    )
    print("Build successful.")

if __name__ == "__main__":
    main()
