import argparse
import json
from pathlib import Path
import sys

class Repository:
    def __init__(self, path="."):
        self.path = Path(path).resolve() # git init
        # .pygit
        self.git_dir = self.path / ".pygit"

        # .pygit/objects
        self.objects_dir = self.git_dir / "objects"
        # .pygit/ref
        self.ref_dir = self.git_dir / "ref"
        self.head_dir = self.ref_dir / "heads"
        # HEAD file
        self.head_file = self.git_dir / "HEAD"

        # .pygit/index_file
        self.index_file = self.git_dir / "index"

    def init(self) -> bool:
        if (self.git_dir.exists()):
            return False

        # creating directories
        self.git_dir.mkdir()
        self.objects_dir.mkdir()
        self.ref_dir.mkdir()
        self.head_dir.mkdir()

        # create initial HEAD pointing to a branch
        self.head_file.write_text("ref: refs./heads/master\n")

        self.index_file.write_text(json.dumps({}, indent=2,))

        print(f"Initialized empty pygit repository in {self.git_dir}")
        return True

# main function 
def main():
    parser = argparse.ArgumentParser(
        description="PyGit - A Simple git clone!"
    )
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
    )

    # init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new reposiotry",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == "init":
            repo = Repository()
            if not(repo.init()):
                print("Repository already exists.")
                return
    except Exception as e:
        print(f"PyGit Error: {e}")
        sys.exit(1)


main()