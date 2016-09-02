import asyncio
import os

import aiohttp
from docker import Client

async def up(loop):
    name = 'test1'
    output_port = 5000
    cli = Client()
    volumes = cli.volumes()['Volumes']
    if volumes:
        volume = next((v for v in volumes if v['Name'] == name), None)
        if volume:
            print('deleting existing volume')
            cli.remove_volume(name)
    volume = cli.create_volume(name=name)
    vol_mount_point = volume['Mountpoint']

    github_oauth = os.getenv('GITHUB_OAUTH')
    assert github_oauth, 'GITHUB_OAUTH env variable not set'

    ctrl_port = output_port + 1
    con_name = '{}_ctrl'.format(name)
    ctrl_con = cli.create_container(
        image='hackle-box:latest',
        name=con_name,
        environment={
            'GITHUB_USER': 'tutorcruncher',
            'GITHUB_REPO': 'tutorcruncher.com',
            'GITHUB_OAUTH': github_oauth,
        },
        volumes=['/src'],
        host_config=cli.create_host_config(
            port_bindings={8000: ctrl_port},
            binds=['{}:/src'.format(vol_mount_point)],
        )
    )
    cli.start(container=ctrl_con.get('Id'))

    url = 'http://localhost:{}'.format(ctrl_port)
    print('waiting for control server to start...')
    async with aiohttp.ClientSession(loop=loop) as session:
        for i in range(20):
            try:
                async with session.get(url) as r:
                    status = r.status
            except (aiohttp.ClientOSError, aiohttp.ClientResponseError) as e:
                await asyncio.sleep(1)
                continue
            print('ctrl server "{}" running at {}, status {}'.format(con_name, url, status))
            break

    dev_port = output_port
    con_name = '{}_dev'.format(name)
    await asyncio.sleep(1)  # make sure volumes have synced, otherwise jekyll can get ito a mess
    dev_con = cli.create_container(
        image='jekyll/jekyll',
        name=con_name,
        volumes=['/srv/jekyll'],
        working_dir='/srv/jekyll',
        command='/usr/bin/jekyll serve -H 0.0.0.0 --incremental',
        host_config=cli.create_host_config(
            port_bindings={4000: dev_port},
            binds=['{}:/srv/jekyll'.format(vol_mount_point)],
        )
    )
    cli.start(container=dev_con.get('Id'))
    print('dev server "{}" running at http://localhost:{}'.format(con_name, dev_port))

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(up(loop))
