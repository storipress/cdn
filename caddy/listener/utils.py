import json
import os
from sentry_sdk import capture_message, push_scope

caddyPath = '/usr/local/caddy'
caddyFilesPath = '/usr/local/caddy/files'
fileLockPath = '/usr/local/caddy/locks'

caddyChannel = 'caddy_cdn'


def caddy_reload():
    # reload the caddy services
    os.system('caddy reload --config ' + caddyPath + '/Caddyfile')


def get_meta_key(tenant):
    return 'cdn_meta_' + tenant


def write_caddy_file(tenant, meta):
    content = make_custom_content(meta['custom']['domain'], meta['reverse_path'], meta['custom']['redirect_domain'])

    filename = caddyFilesPath + '/' + tenant

    with open(filename, "w") as output:
        output.write(content)


def remove_caddy_file(tenant):
    filename = caddyFilesPath + '/' + tenant
    if os.path.exists(filename):
        os.remove(filename)


def make_custom_content(domain, reverse, redirect):
    template_path = caddyPath + '/custom.caddy'
    with open(template_path, 'r') as file:
        content = file.read()

    content = content.replace('REVERSE_PATH', reverse)
    content = content.replace('DOMAIN', domain)

    # contains redirect domain
    if redirect == '':
        return content

    redirect_template_path = caddyPath + '/redirect.caddy'
    with open(redirect_template_path, 'r') as file:
        redirect_content = file.read()

    redirect_content = redirect_content.replace('DOMAIN', redirect)
    redirect_content = redirect_content.replace('REDIRECT', domain)
    content = redirect_content + content

    return content


def get_meta_data(redis, tenant):
    meta_key = get_meta_key(tenant)
    message = redis.get(meta_key)

    # publication meta not exists or domain not exists
    if message is None:
        sentry_capture('invalid meta data', {'content': 'none', 'key': meta_key})
        return None

    try:
        meta = json.loads(message.decode())
    except:
        sentry_capture('invalid meta data', {'content': message, 'key': meta_key})
        return None

    return meta


def sentry_capture(message, args):
    with push_scope() as scope:
        for key in args:
            scope.set_extra(key, args[key])
        capture_message(message)


def terminate(tenant):
    remove_caddy_file(tenant)
    print("[Debug] terminate %s" % (tenant), flush=True)


def sync(tenant, meta):
    filename = fileLockPath + '/' + tenant
    if os.path.exists(filename):
        with open(filename, "r") as content:
            timestamp = content.read()

        if timestamp >= str(meta['timestamp']):
            return

    write_caddy_file(tenant, meta)

    print("[Debug] sync %s %s" % (tenant, meta['timestamp']), flush=True)

    with open(filename, "w") as output:
        output.write(str(meta['timestamp']))


def listen(redis):
    # get redis pub/sub
    sub = redis.pubsub()

    # compatible for cdn_caddy
    sub.subscribe(['cdn_caddy', 'cdn_caddy_' + os.getenv('ENVIRONMENT')])

    try:
        # listen redis caddy channel
        for message in sub.listen():
            # ignore the first message (subscribe message)
            if message['type'] == 'subscribe':
                continue

            if not isinstance(message.get('data'), bytes):
                continue

            payload = json.loads(message['data'].decode())

            if 'event' not in payload or 'tenant' not in payload:
                sentry_capture('invalid payload', {'message': message})
                continue

            event = payload['event']
            tenant = payload['tenant']

            if event == 'terminate':
                terminate(tenant)
            # update caddyfile config
            elif event == 'sync':
                # get meta key
                meta = get_meta_data(redis, tenant)

                if meta is None:
                    continue

                if 'custom' not in meta:
                    terminate(tenant)
                    continue

                sync(tenant, meta)
            else:
                sentry_capture('invalid event', {'event': event, 'payload': payload, 'tenant': tenant})
                continue

            # reload caddy
            caddy_reload()
    except KeyboardInterrupt:
        redis.close()


def download(redis):
    print('[Debug] download start', flush=True)

    keys = []
    for key in redis.scan_iter(match='cdn_meta_*', count=100):
        keys.append(key.decode())

    for i in range(0, len(keys), 50):
        group_keys = keys[i:i + 50]
        contents = redis.mget(group_keys)

        for idx, content in enumerate(contents):
            key = group_keys[idx]
            pattern = key.split('_')

            if len(pattern) != 3:
                sentry_capture('unknown key', {'key': key})
                continue

            try:
                meta = json.loads(content.decode())
            except:
                sentry_capture('invalid meta data', {'content': content, 'key': key})
                continue

            tenant = pattern[2]

            if 'custom' not in meta:
                continue

            sync(tenant, meta)

    redis.close()

    # reload caddy
    caddy_reload()

    print('[Debug] download end', flush=True)
