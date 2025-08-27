import argparse
import hashlib
import json
from pathlib import Path
import sys
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
        header = decompressed[0:null_idx]
        content = decompressed[null_idx+1:]

        obj_type, size = header.split(" ")

        return cls(obj_type, content)        

# Binary Large Object
class BLOB(GitObject):
    def __init__(self, content: bytes):
        super().__init__("blob", content)

    def get_content(self) -> bytes:
        return self.content

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
    
    def load_index(self) -> dict[str, str]:
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

    except Exception as e:
        print(f"PyGit Error: {e}")
        sys.exit(1)


main()