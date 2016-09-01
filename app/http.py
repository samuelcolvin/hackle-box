import asyncio
import json
from datetime import datetime

from aiohttp import web
from pathlib import Path

from .files import file_tree, get_changes, read_file, write_file, fs_path

THIS_DIR = Path(__file__).resolve().parent


def api_response(data):
    content = json.dumps(data, indent=2, sort_keys=True)
    return web.Response(body=content.encode('utf8'), content_type='application/javascript')


def index(request):
    named_resources = request.app.router.named_resources()
    data = {
        'urls': {
            'files': named_resources['tree'].url(),
            'status': named_resources['dev-server-status'].url(),
        },
        'changes': get_changes(),
    }
    return api_response(data)


async def tree(request):
    named_resources = request.app.router.named_resources()

    def get_url(path):
        return named_resources['files'].url(parts={'path': path})
    data = file_tree(get_url)
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


DEV_SERVER = 'dev_server'
EPOCH = datetime(1970, 1, 1)


def timestamp():
    return (datetime.utcnow() - EPOCH).total_seconds()


async def dev_server_start(request):
    dev_server = request.app.get(DEV_SERVER)
    if dev_server and dev_server['process'].returncode is None:
        raise web.HTTPForbidden(body=b'403: dev server is currently running\n')
    dev_server_path = str(THIS_DIR / '../dev_server.sh')
    import subprocess
    p = await asyncio.create_subprocess_exec(dev_server_path, loop=request.app.loop,
                                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = await p.stdout.read(1000)
    request.app[DEV_SERVER] = {
        'process': p,
        'log': log,
        'start': timestamp(),
    }
    named_resources = request.app.router.named_resources()
    raise web.HTTPTemporaryRedirect(named_resources['dev-server-status'].url())


async def dev_server_stop(request):
    dev_server = request.app.get(DEV_SERVER)
    if not (dev_server and dev_server['process'].returncode is None):
        raise web.HTTPForbidden(body=b'403: dev server is not running\n')
    p = dev_server['process']
    p.terminate()
    try:
        await asyncio.wait_for(p.wait(), 5, loop=request.app.loop)
    except asyncio.TimeoutError:
        raise web.HTTPInternalServerError(body=b'500: dev server failed to stop\n')
    named_resources = request.app.router.named_resources()
    raise web.HTTPTemporaryRedirect(named_resources['dev-server-status'].url())


async def dev_server_restart(request):
    try:
        await dev_server_stop(request)
    except (web.HTTPTemporaryRedirect, web.HTTPForbidden):
        pass
    return await dev_server_start(request)


async def dev_server_status(request):
    dev_server = request.app.get(DEV_SERVER)
    named_resources = request.app.router.named_resources()
    data = {
        'status': 'not_running',
        'start_url': named_resources['dev-server-start'].url(),
    }
    if dev_server:
        p = dev_server['process']
        dev_server['log'] += await p.stdout.read(1000)
        data.update(
            log=list(filter(bool, dev_server['log'].decode().split('\n'))),
            start=dev_server['start'],
            duration=timestamp() - dev_server['start'],
        )
        try:
            await asyncio.wait_for(p.wait(), 0.1, loop=request.app.loop)
        except asyncio.TimeoutError:
            data['status'] = 'running'
            data.pop('start_url')
        else:
            data.update(
                status='terminated' if p.returncode else 'finished',
                returncode=p.returncode,
            )
    return api_response(data)


def run():
    web.run_app(get_app())


def get_app(loop=None):
    loop = loop or asyncio.get_event_loop()
    app = web.Application(loop=loop)
    ar = app.router.add_route
    ar('GET', '/', index, name='index')
    ar('GET', '/files', tree, name='tree')
    ar('*', '/files/{path:[^{}]+}', file_content, name='files')
    ar('POST', '/dev/start', dev_server_start, name='dev-server-start')
    ar('POST', '/dev/stop', dev_server_stop, name='dev-server-stop')
    ar('POST', '/dev/restart', dev_server_restart, name='dev-server-restart')
    ar('GET', '/dev/status', dev_server_status, name='dev-server-status')
    return app
