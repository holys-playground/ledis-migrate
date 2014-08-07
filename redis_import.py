#!/usr/bin/env python
# coding: utf-8

# refer: https://github.com/ideawu/ssdb/blob/master/tools/redis-import.php

# Notice: for zset, float score will be converted to integer.

import sys
import os
from collections import OrderedDict as od

import redis

total = 0
entries = 0


def scan_available(redis_client):
    """"Scan Command is available since redis-server 2.8.0"""

    if "scan" in dir(redis_client):
        info = redis_client.info()
        server_version = info["redis_version"]
        version_list = server_version.split(".")
        if len(version_list) > 2:
            n = int(version_list[0]) * 10 + int(version_list[1])
            if n > 28:
                return True
    return False


def copy_key(redis_client, ledis_client, key):
    global entries
    k_type = redis_client.type(key)
    if k_type == "string":
        value = redis_client.get(key)
        ledis_client.set(key, value)
        entries += 1

    elif k_type == "list":
        _list = redis_client.lrange(key, 0, -1)
        for value in _list:
            ledis_client.rpush(key, value)
        entries += 1

    elif k_type == "hash":
        mapping = redis_client.hgetall(key)
        ledis_client.hmset(key, od(mapping))
        entries += 1

    elif k_type == "zset":
        out = redis_client.zrange(key, 0, 1, withscores=True)
        pieces = od()
        for i in od(out).iteritems():
            pieces[i[0]] = int(i[1])
        ledis_client.zadd(key, **pieces)
        entries += 1

    else:
        print "This kind of data type is not supported by LedisDB."


def copy_keys(redis_client, ledis_client, keys):
    for key in keys:
        copy_key(redis_client, ledis_client, key)


def usage():
    usage = """
        Usage:
        python %s redis_host redis_port redis_db ledis_host ledis_port
        """
    print usage % os.path.basename(sys.argv[0])


def main():
    global total, entries
    if len(sys.argv) != 6:
        usage()
        sys.exit()

    (redis_host, redis_port, redis_db, ledis_host, ledis_port) = sys.argv[1:]

    redis_c = redis.Redis(host=redis_host, port=int(redis_port), db=int(redis_db))
    ledis_c = redis.Redis(host=ledis_host, port=int(ledis_port), db=int(redis_db))
    try:
        redis_c.ping()
    except redis.ConnectionError:
        print "Could not connect to Redis Server"
        sys.exit()

    try:
        ledis_c.ping()
    except redis.ConnectionError:
        print "Could not connect to LedisDB Server"
        sys.exit()

    if scan_available(redis_c):
        total = redis_c.dbsize()
        keys = redis_c.scan(cursor=int(redis_db), count=total)
        copy_keys(redis_c, ledis_c, keys)

    else:
        keys = redis_c.keys("*")
        total = len(keys)
        copy_keys(redis_c, ledis_c, keys)

    print "%d keys, %d entries copied" % (total, entries)
    print "done.\n\n"


if __name__ == "__main__":
    main()