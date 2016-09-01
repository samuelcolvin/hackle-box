import logging
import click

from app.files import setup
from app.http import run, get_app

logger = logging.getLogger('hacklebox')
logger.setLevel(logging.DEBUG)
hdl = logging.StreamHandler()
hdl.setLevel(logging.DEBUG)
logger.addHandler(hdl)


@click.command()
@click.argument('user')
@click.argument('repo')
@click.argument('oauth_token', required=False)
def main(user, repo, oauth_token):
    setup(user, repo, oauth_token)
    run()


def run_direct(loop):
    setup('samuelcolvin', 'gaugemore.com', None)
    return get_app(loop)


if __name__ == '__main__':
    main()
