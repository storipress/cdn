import argparse
import os
import redis
import sentry_sdk
from utils import listen, download

if __name__ == "__main__":
    sentry_sdk.init(
        dsn="SENTRY_DSN",
        environment=os.getenv('ENVIRONMENT'),
        traces_sample_rate=1.0
    )

    parser = argparse.ArgumentParser(description='redis handler.')
    parser.add_argument('action', help='listen or download')

    args = parser.parse_args()

    # connect to redis
    r = redis.StrictRedis(
        host='redis.example.com',
        db=int(os.getenv('REDIS_DB')),
        socket_connect_timeout=5,
        retry_on_timeout=True
    )

    if args.action == 'listen':
        listen(r)
    elif args.action == 'download':
        download(r)
    else:
        print('[Debug] invalid argument', flush=True)
