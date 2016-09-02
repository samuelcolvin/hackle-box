import asyncio
import json
import logging
import ssl

from aiohttp import web
from pathlib import Path

from .files import file_tree, get_changes, read_file, write_file, fs_path

THIS_DIR = Path(__file__).resolve().parent

logger = logging.getLogger('hacklebox')


def api_response(data):
    content = json.dumps(data, indent=2, sort_keys=True)
    return web.Response(body=content.encode('utf8'), content_type='application/javascript')


def index(request):
    named_resources = request.app.router.named_resources()

    def get_url(path):
        return named_resources['files'].url(parts={'path': path})

    data = {
        'changes': get_changes(),
        'files': file_tree(get_url)
    }
    return api_response(data)


async def file_content(request):
    path = request.match_info['path']
    _fs_path = fs_path(path)
    if _fs_path.is_dir():
        raise web.HTTPForbidden(body='403: directory not file: "{}"\n'.format(path).encode())
    if request.method == 'GET':
        try:
            content = read_file(path)
        except FileNotFoundError:
            raise web.HTTPNotFound(body='404: file not found: "{}"\n'.format(path).encode())
        return web.Response(body=content, content_type='text/plain')
    elif request.method in {'POST', 'PUT'}:
        data = await request.post()
        file_existed = _fs_path.exists()
        try:
            content = data['content'].encode()
        except KeyError:
            raise web.HTTPBadRequest(body=b'400: content not found in post\n')
        write_file(path, content)
        return web.Response(status=200 if file_existed else 201)


def create_app(loop=None):
    loop = loop or asyncio.get_event_loop()
    app = web.Application(loop=loop)
    ar = app.router.add_route
    ar('GET', '/', index, name='index')
    ar('*', '/files/{path:[^{}]+}', file_content, name='files')
    return app


def run_web_app(app):
    logger.debug('starting web server')

    # ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    # ssl_context.load_cert_chain('/path/to/server.crt', '/path/to/server.key')
    ssl_context = None

    handler = app.make_handler(access_log_format='%r %s %b')
    loop = app.loop
    srv = loop.run_until_complete(loop.create_server(handler, '0.0.0.0', 8000, ssl=ssl_context, backlog=128))

    try:
        loop.run_forever()
    except KeyboardInterrupt:  # pragma: no branch
        pass
    finally:
        srv.close()
        loop.run_until_complete(srv.wait_closed())
        loop.run_until_complete(app.shutdown())
        loop.run_until_complete(handler.finish_connections(2))
        loop.run_until_complete(app.cleanup())
    loop.close()

