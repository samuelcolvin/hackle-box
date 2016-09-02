import logging
import mimetypes
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Dict, Set

SRC_DIR = Path(os.getenv('SRC_DIR', '/tmp/hackle-src'))

logger = logging.getLogger('hacklebox')


def run(*args):
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    if p.returncode != 0:
        raise RuntimeError('command "{}" return code {}, output: \n{}'.format(' '.join(args), p.returncode, p.stdout))
    return p


def setup(user, repo, oauth_token):
    if SRC_DIR.exists():
        assert SRC_DIR.is_dir()
        files = list(SRC_DIR.iterdir())
        if files:
            logger.debug('code dir already exists, emptying')
            for p in SRC_DIR.iterdir():
                if p.is_dir():
                    shutil.rmtree(str(p))
                else:
                    p.unlink()
    else:
        SRC_DIR.mkdir(parents=True)
        logger.debug('creating code dir "%s"', SRC_DIR)

    url = 'https://{}@github.com/{}/{}.git'.format(oauth_token or '', user, repo)
    logger.info('cloning %s > %s', url, SRC_DIR)
    p = run('git', 'clone', '--depth=50', url, str(SRC_DIR))
    logger.debug('clone output: %s', p.stdout)
    os.chdir(str(SRC_DIR))
    gemfile = SRC_DIR / 'Gemfile'
    gemfile.exists() and gemfile.unlink()


def fs_path(path: str) -> Path:
    return SRC_DIR / path.strip('./').replace('..', '.')


def read_file(path: str) -> bytes:
    return fs_path(path).read_bytes()


def write_file(path: str, content: bytes):
    fs_path(path).write_bytes(content)


STATUS_DELETED = 'deleted'
STATUS_UNKNOWN = 'unchanged'
STATUS_LOOKUP = {
    'M': 'modified',
    'A': 'added',
    'D': STATUS_DELETED,
    'R': 'renamed',
    '??': 'untracked',
}


def get_changes() -> Dict[str, str]:
    changes = run('git', 'status', '--porcelain', '-uall').stdout
    changes = [l.strip().split() for l in changes.split('\n') if l]
    return {p: STATUS_LOOKUP[s] for s, p in changes}


def get_ignored() -> Set[str]:
    ignored = run('git', 'ls-files', '-o', '-i', '--exclude-standard').stdout.split('\n')
    return {i for i in ignored if i}


def file_tree(get_url: Callable[[str], str]):
    changes = get_changes()
    ignored = get_ignored()

    def _file_tree(path: Path):
        tree = {}
        for _p in path.iterdir():
            if _p.is_dir():
                if _p.name == '.git':
                    continue
                tree[_p.name] = _file_tree(_p)
            else:
                relative_path = str(_p.relative_to(SRC_DIR))
                if relative_path in ignored:
                    continue
                stat = _p.stat()
                tree[_p.name] = {
                    'size_raw': stat.st_size,
                    'size_human': _fmt_size(stat.st_size),
                    'file_path': relative_path,
                    'status': changes.get(relative_path, STATUS_UNKNOWN),
                    'url': get_url(relative_path),
                    'mime_type': _mime_type(_p.name),
                }
        return tree

    tree = _file_tree(SRC_DIR)
    # have to add deleted files:
    for path, status in changes.items():
        if status == STATUS_DELETED:
            parts = path.split('/')
            directory = tree
            for part in parts[:-1]:
                if part in directory:
                    directory = directory[part]
                else:
                    new_directory = {}
                    directory[part] = new_directory
                    directory = new_directory
            directory[parts[-1]] = {
                'file_path': path,
                'status': STATUS_DELETED,
                'url': get_url(path),
                'mime_type': _mime_type(path),
            }
    return tree

KB = 1024
MB = KB**2


def _fmt_size(num):
    if num == '':
        return ''
    if num < KB:
        return '{:0.0f}B'.format(num)
    elif num < MB:
        return '{:0.1f}KB'.format(num / KB)
    else:
        return '{:0.1f}MB'.format(num / MB)


def _mime_type(name: str) -> str:
    return mimetypes.guess_type(name)[0] or 'text/plain'
