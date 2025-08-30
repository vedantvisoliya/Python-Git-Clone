import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Dict, List, Tuple
import zlib

class GitObject:
    def __init__(self, obj_type: str, content: bytes):
        self.type = obj_type
        self.content = content        

    def hash(self) -> str:
        # SHA1(hash_type) -> <obj_type> <size of the content>\0<content>
        header = f"{self.type} {len(self.content)}\0".encode()
        return hashlib.sha1(header + self.content).hexdigest()

    # lose less compression of content 
    def serialize(self) -> bytes:
        header = f"{self.type} {len(self.content)}\0".encode()
        return zlib.compress(header + self.content)

    # decompression to get actual gitobject    
    @classmethod
    def deserialize(cls, data: bytes) -> "GitObject":
        decompressed = zlib.decompress(data)
        null_idx = decompressed.find(b"\0")
        header = decompressed[0:null_idx].decode()
        content = decompressed[null_idx+1:]

        obj_type, size = header.split(" ")

        return cls(obj_type, content)        

# Binary Large Object
class BLOB(GitObject):
    def __init__(self, content: bytes):
        super().__init__("blob", content)

    def get_content(self) -> bytes:
        return self.content
    
# Tree Object
class Tree(GitObject):
    def __init__(self, entries: List[Tuple[str, str, str]] = None):
        self.entries = entries or []
        content = self._serialize_entries()
        super().__init__("tree", content)

    def _serialize_entries(self) -> bytes:
        # <mode> <name>\0<hash>
        # 100644 main.txt\0[20 bytes of content]
        content = b""
        for mode, name, obj_hash in sorted(self.entries):
            content += f"{mode} {name}\0".encode()
            content += bytes.fromhex(obj_hash)

        return content
    
    def add_entry(self, mode: str, name: str, obj_hash: str):
        self.entries.append((mode, name, obj_hash))
        self.content = self._serialize_entries()

    @classmethod
    def from_content(cls, content: bytes) -> "Tree":
        tree = cls()
        i = 0

        while i < len(content):
            null_idx = content.find(b"\0", i)
            if null_idx == -1:
                break
            mode_name = content[i:null_idx].decode()
            mode, name = mode_name.split(" ", 1)
            obj_hash = content[null_idx + 1: null_idx + 21].hex()
            tree.entries.append((mode, name, obj_hash))

            i = null_idx + 21

        return tree
    
class Commit(GitObject):
    def __init__(
        self, 
        tree_hash: str, 
        parent_hashes: List[str], 
        author: str, 
        committer: str, 
        message: str,
        timestamp: int = None,
    ):
        self.tree_hash = tree_hash
        self.parent_hashes = parent_hashes
        self.author = author
        self.committer = committer
        self.message = message
        self.timestamp = timestamp or int(time.time())
        content = self._serialize_commit()
        super().__init__("commit", content)

    def _serialize_commit(self):
        lines = [f"tree {self.tree_hash}"]

        for parent in self.parent_hashes:
            lines.append(f"parent {parent}")

        lines.append(f"author {self.author} {self.timestamp} +0000")
        lines.append(f"committer {self.committer} {self.timestamp} +0000")
        lines.append("")
        lines.append(self.message)

        return ("\n".join(lines)).encode()

    @classmethod
    def from_content(cls, content: bytes) -> "Commit":
        lines = content.decode().split("\n")
        tree_hash = None
        parent_hashes = []
        author = None
        committer = None
        message_start = 0

        for i, line in enumerate(lines):
            if line.startswith("tree"):
                tree_hash = line[5:]
            elif line.startswith("parent "):
                parent_hashes.append(line[7:])
            elif line.startswith("author "):
                author_parts = line[7:].rsplit(" ", 2)
                author = author_parts[0]
                timestamp = int(author_parts[1])
            elif line.startswith("committer "):
                committer_parts = line[10:].rsplit(" ", 2)
                committer = committer_parts[0]
                timestamp = int(committer_parts[1])
            elif line == "":
                message_start = i + 1
                break
        message = "\n".join(lines[message_start: ])
        commit = cls(tree_hash, parent_hashes, author, committer, message, timestamp)
        return commit

    
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

        self.save_index({})

        print(f"Initialized empty pygit repository in {self.git_dir}")
        return True
    
    def load_index(self) -> Dict[str, str]:
        if not self.index_file.exists():
            return {}
        
        try:
            return json.loads(self.index_file.read_text())
        except:
            return {}
        
    def save_index(self, index: dict[str, str]) -> None:
        self.index_file.write_text(json.dumps(index, indent=2))

    # There are four (4) type of objects.
    # 1. BLOB - Binary Large Objects
    # 2. Commit
    # 3. Trees
    # 4. Tags - (not going to use this, focusing on the above three)

    def store_gitobject(self, obj: GitObject) -> str:
        obj_hash = obj.hash()
        obj_dir = self.objects_dir / obj_hash[:2]
        obj_file = obj_dir / obj_hash[2:]

        if not obj_file.exists():
            obj_dir.mkdir(exist_ok=True)
            obj_file.write_bytes(obj.serialize())

        return obj_hash

    # add files function
    def add_file(self, path: str):
        full_path = self.path / path

        if not full_path.exists():
            raise FileNotFoundError(f"Path {path} is not found.")

        # read the file content
        content = full_path.read_bytes()

        # create BLOB object from content
        blob = BLOB(content)

        # store the blob object in databse (.pygit/objects)
        blob_hash = self.store_gitobject(blob)

        # update index to include the file or directory
        index = self.load_index()
        index[path] = blob_hash

        # save the index file
        self.save_index(index)

        print(f"Added {path}")

    # add directory function
    def add_directory(self, path: str):
        full_path = self.path / path

        if not full_path.exists():
            raise FileNotFoundError(f"Directory at {path} not found.")
        
        if not full_path.is_dir():
            raise ValueError(f"{path} is not a directory.")

        # loading the index
        index = self.load_index()
        added_count = 0
        # recursively traverse the directory
        # '*' - we get everything the directory has.
        for file_path in full_path.rglob('*'):
            if file_path.is_file():
                # ignoring the files in the .pygit and .git folders
                if ".pygit" in file_path.parts:
                    continue
                if ".git" in file_path.parts:
                    continue

                content = file_path.read_bytes()
                # create a blob object.
                blob = BLOB(content)
                # store the blob object in database
                blob_hash = self.store_gitobject(blob)
                # update the index
                rel_path = str(file_path.relative_to(self.path))
                index[rel_path] = blob_hash
                added_count += 1

                print(f"Added {file_path}")

        # save the index 
        self.save_index(index)

        if added_count > 0:
            print(f"Added {added_count} files from directory {path}")
        else:
            print(f"Directory {path} is already up to date.")
    
    def add_path(self, path: str) -> None:
        full_path = self.path / path

        # raise error if that path does not exists
        if not full_path.exists():
            raise FileNotFoundError(f"Path {path} not found.")

        # if it is a file then call add_file()
        if full_path.is_file():
            self.add_file(path)

        # if it is a file then call add_dir()
        elif full_path.is_dir():
            self.add_directory(path)
        else:
            raise ValueError(f"{path} is neither a file nor a directory.")
    
    # general function for loading any git object
    def load_object(self, obj_hash: str):
        obj_dir = self.objects_dir / obj_hash[:2]
        obj_file = obj_dir / obj_hash[2:]

        if not obj_file.exists():
            raise FileNotFoundError(f"Object {obj_hash} not found.")
        
        return GitObject.deserialize(obj_file.read_bytes())

    # create tree method
    def create_tree_from_index(self):
        index = self.load_index()

        if not index:
            tree = Tree()
            return self.store_gitobject(tree)
        
        dirs = {}
        files = {}

        for file_path, blob_hash in index.items():
            parts = file_path.split('/')

            if (len(parts)) == 1:
                files[parts[0]] = blob_hash
            else:
                dir_name = parts[0]

                if dir_name not in dirs:
                    dirs[dir_name] = {}

                current = dirs[dir_name]
                
                for part in parts[1: -1]:

                    if part not in current:
                        current[part] = {}

                    current = current[part]

                current[parts[-1]] = blob_hash

        def create_tree_recursive(entries_dict: Dict):
            tree = Tree()

            for name, blob_hash in entries_dict.items():
                if isinstance(blob_hash, str):
                    tree.add_entry("100644", name, blob_hash)

                if isinstance(blob_hash, dict):
                    subtree_hash = create_tree_recursive(blob_hash)
                    tree.add_entry("40000", name, subtree_hash)
                
            return self.store_gitobject(tree)

        root_entries = {**files}
        for dir_name, dir_contents in dirs.items():
            root_entries[dir_name] = dir_contents

        return create_tree_recursive(root_entries) 

    # gets current branch from the HEAD file 
    def get_current_branch(self) -> str:
        if not self.head_file.exists():
            return "master"
        head_content = self.head_file.read_text().strip()
        if head_content.startswith("ref: refs./heads/"):
            return head_content[17:]
        
        return "HEAD" # detached HEAD

    # creates a file with the branch name in ref/heads/ and return the latest commit
    def get_branch_commit(self, current_branch: str):
        branch_file = self.head_dir / current_branch 
        if branch_file.exists():
            return branch_file.read_text().strip()
        return None

    # rewrites the latest branch commit
    def set_branch_commit(self, current_branch: str, commit_hash: str):
        branch_file = self.head_dir / current_branch 

        branch_file.write_text(commit_hash + "\n")
        
    # commit function
    def commit(self, message: str, author: str = "PyGit User <user@pygit.com>"):
        # create a tree object from the index (staging area).
        tree_hash = self.create_tree_from_index()

        current_branch = self.get_current_branch()
        parent_commit = self.get_branch_commit(current_branch)
        parent_hashes = [parent_commit] if parent_commit else []

        index = self.load_index()

        if not index:
            print("nothing to commit, working tree clean")
            return None
        
        if parent_commit:
            parent_git_commit_obj = self.load_object(parent_commit)

            parent_commit_data = Commit.from_content(parent_git_commit_obj.content)

            if tree_hash == parent_commit_data.tree_hash:
                print("nothing to commit, working tree clean.")
                self.save_index({})
                return None

        commit = Commit(
            tree_hash = tree_hash,
            author = author,
            committer = author,
            message = message,
            parent_hashes = parent_hashes
        )

        commit_hash = self.store_gitobject(commit)
        self.set_branch_commit(current_branch, commit_hash)
        self.save_index({})
        print(f"Created commit {commit_hash} on branch {current_branch}")
        return commit_hash

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
        help="Initialize a new repository.",
    )

    # add command
    add_parser = subparsers.add_parser(
        "add",
        help="Add files and folder to the repository.",
    )

    # '+' - at least one argument or more
    # '?' - zero or one argument can be null (optional argument)
    # '*' - zero or more argument

    add_parser.add_argument(
        "paths", 
        nargs='+',
        help="Files and Directories to Add.",
    )

    # commit command

    commit_parser = subparsers.add_parser(
        "commit",
        help="Create a commit.",
    )

    commit_parser.add_argument(
        "-m", 
        "--message",
        required=True,
        help="Commit Message.",
    )

    commit_parser.add_argument(
        "--author",
        help="Author name and email.",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # creating a repo object at global    
    repo = Repository()

    try:
        # init command
        if args.command == "init":
            if not(repo.init()):
                print("Repository already exists.")
                return
        # add command
        elif args.command == "add":
            if not(repo.git_dir.exists()):
                print("Not a git repository.")
                return
            for path in args.paths:
                repo.add_path(path)
        elif args.command == "commit":
            if not repo.git_dir.exists():
                print("Not a git repository.")
                return
            author = args.author or "PyGit user <user@pygit.com>"
            repo.commit(args.message, author)
            


    except Exception as e:
        print(f"PyGit Error: {e}")
        sys.exit(1)


main()