import logging
import os

from app.files import setup
from app.http import run_web_app, create_app

hdl = logging.StreamHandler()
hdl.setLevel(logging.DEBUG)

hackle_logger = logging.getLogger('hacklebox')
hackle_logger.setLevel(logging.DEBUG)
hackle_logger.addHandler(hdl)

web_access_logger = logging.getLogger('aiohttp.access')
web_access_logger.setLevel(logging.DEBUG)
web_access_logger.addHandler(hdl)


def main(loop=None):
    github_user = os.getenv('GITHUB_USER')
    assert github_user, 'GITHUB_USER env variable not set'

    github_repo = os.getenv('GITHUB_REPO')
    assert github_repo, 'GITHUB_REPO env variable not set'

    github_oauth = os.getenv('GITHUB_OAUTH')
    assert github_oauth, 'GITHUB_OAUTH env variable not set'

    setup(github_user, github_repo, github_oauth)

    return create_app(loop)


if __name__ == '__main__':
    app = main()
    run_web_app(app)
