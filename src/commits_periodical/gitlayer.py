import dataclasses
import os.path
import pickle

import git


@dataclasses.dataclass
class CachedCommit:
    githash: str
    author: str
    summary: str
    message: str
    authored_date: int
    modified_files: list[str]

    @classmethod
    def from_gitcommit(cls, commit: git.Commit):
        return cls(
            githash=str(commit.hexsha),
            author=str(commit.author),
            summary=str(commit.summary),
            message=str(commit.message),
            authored_date=int(commit.authored_date),
            modified_files=[str(p) for p in commit.stats.files],
        )


class CachedRepo:
    def __init__(self, git_dirname: str, cache_filename: str) -> None:
        self.git_dirname = git_dirname
        self.cache_filename = cache_filename
        self.repo = None
        self.gitcommits = None
        self.trust_cache = False

    def add_cache(self, filename):
        if self.gitcommits is None:
            self.gitcommits = {}
        with open(filename, "rb") as fp:
            cache_gitcommits = pickle.load(fp)
            self.gitcommits.update(cache_gitcommits)
        self.trust_cache = True

    def _setup_gitcommits(self):
        if os.path.exists(self.cache_filename):
            with open(self.cache_filename, "rb") as fp:
                self.gitcommits = pickle.load(fp)
            self.trust_cache = True
        else:
            # We can't trust a cache that doesn't exist
            self.trust_cache = False
            self.gitcommits = {}

        if not self.trust_cache:
            self._load_actual_repo()

    def _load_actual_repo(self):
        # Load the git repo and ensure that it's clean
        self.repo = git.Repo(self.git_dirname)
        if self.repo.is_dirty():
            raise SystemError("Repo is dirty; resolve")

    def save(self):
        with open(self.cache_filename, "wb") as fp:
            pickle.dump(self.gitcommits, fp)

    def get_head_hash(self):
        if self.repo is None:
            self._load_actual_repo()
        return self.repo.head.commit.hexsha

    def get_githashes(self):
        return self.gitcommits.keys()

    def ensure_cached(self, start_after: str, end_including: str):
        if self.gitcommits is None:
            self._setup_gitcommits()
        if start_after in self.gitcommits and end_including in self.gitcommits:
            return

        if self.repo is None:
            self._load_actual_repo()

        githashes = self.repo.git.rev_list(
            f"{start_after}..{end_including}", reverse=True, first_parent=True
        )

        modified = False
        for githash in githashes.splitlines():
            if githash not in self.gitcommits:
                commit = CachedCommit.from_gitcommit(self.repo.commit(githash))
                self.gitcommits[githash] = commit
                modified = True

        if modified:
            self.save()

    def get_commit(
        self, githash: str, allow_partial: bool = False
    ) -> CachedCommit:
        """Return the commit indicated by githash, or None.  If allow_partial
        is True, short forms (i.e. abc123 rather than the full 40-char string)
        can be used.
        """
        if self.gitcommits is None:
            self._setup_gitcommits()

        length = len(githash)

        if length > 40:
            raise ValueError(f"{githash} is more than 40 chars")
        if length < 40 and not allow_partial:
            raise ValueError(f"{githash} is less than 40 chars")

        # Handle full hashes
        if length == 40:
            if githash in self.gitcommits:
                return self.gitcommits[githash]
            return None

        # Handle partial hashes
        assert allow_partial is True
        matches = [
            v for k, v in self.gitcommits.items() if k.startswith(githash)
        ]
        if not matches:
            return None
        if len(matches) > 1:
            assert NotImplementedError("Too many githash matches")
        return matches[0]
