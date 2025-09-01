# 🐍 pygit
A lightweight, educational reimplementation of Git in Python.
This project demonstrates how Git works under the hood by managing commits, branches, trees, and blobs without relying on Git itself.
---
## 🚀 Getting Started
Clone the Repository
```
    git clone https://github.com/vedantvisoliya/Python-Git-Clone.git
```

Run Commands

Use python or python3 prefix depending on your system:

```python
    python main.py <command>
```

---
## 📖 Commands
1. Initialize Repository

```python
    python main.py init
```
Creates a .pygit folder containing:

objects/ → Stores Git objects (blobs, commits, trees).

ref/heads/ → Stores branch references.

index → Staging area (dictionary of file paths → SHA-1).

HEAD → Stores current branch.

2. Add Files 

```python
    python main.py add hello.txt # files
    python main.py add . # direcotry
    python main.py add hi.txt index.py go.txt # list of files
```

Stages files in the index (staging area).

Uses relative paths as keys and SHA-1 hashes as values.

3. Commit Changes

```python
    python main.py commit -m "message"
    python main.py commit -m "message" --author "Name <email>"
```

Creates a tree object for the whole directory.

Stores commit with:

    commit message
    timestamp
    author
    parent hashes

After committing:

index is cleared (stagging area emptied).

Commit object saved in .pygit/objects/.

4. Checkout Branch

```python
    python main.py checkout -b newbranch
    python main.py checkout branchname
```

checkout -b: Creates a new branch under .pygit/ref/heads/branchname.

checkout branchname: Switches branch, rebuilds the directory from the tree hash.

5. Branch Management

```python
    python main.py branch -b branchname   # Create & switch
    python main.py branch -d branchname   # Delete & move to master
    python main.py branch                 # List all branches
```

6. View Commit Logs

```python
    python main.py log
```

Displays up to 10 commits from current branch:

commit hash

author

7. Repository Status

```python
    python main.py status
```

Shows:

    Changes to be committed
    Unstaged files
    Deleted files
    Untracked files

---

## 🏗️ Core Concepts

GitObject Class → Base class for Git objects.

Blob → Stores file content.

Tree → Represents directory structure.

Commit → Stores commit metadata.

All objects are stored in .pygit/objects/ and referenced via SHA-1.

--- 

## 🌱 Future Improvements

1. Garbage collector for unused objects.

2. Stash functionality.

3. Merge branches.

4. Cherry-pick commits.

5. Checkout a commit (detached HEAD).

6. Tag support.

---

## 🤝 Contributing

Pull requests and feedback are welcome! Open an issue or suggest improvements.

---