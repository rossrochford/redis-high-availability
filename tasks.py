import psutil
import re
import time

from invoke import task
from invoke.watchers import Responder

from util.redis_conf import create_redis_config, create_sentinel_config, create_cluster_config


NODES_REGEX = r':(?P<port>\d+)@'


# stop redis:
#  $ sudo systemctl stop redis-server


@task
def example_one(ctx):
    """
    one primary, one replica
    """
    stop_all(ctx)

    configs = [
        create_redis_config(ctx, 6379),
        create_redis_config(ctx, 6380, replicaof_addr='127.0.0.1:6379')
    ]
    for config_fp, log_fp, port in configs:
        ctx.run(f'redis-server {config_fp} --daemonize yes')

    log_args = ' '.join(tup[1] for tup in configs)
    ctx.run(f'tail -f {log_args}')


@task
def example_two(ctx):
    """
    one primary, two replicas, three sentinels
    """
    stop_all(ctx)

    configs = [
        create_redis_config(ctx, 6379),
        create_redis_config(ctx, 6380, replicaof_addr='127.0.0.1:6379'),
        create_redis_config(ctx, 6381, replicaof_addr='127.0.0.1:6379')
    ]
    for config_fp, log_fp, port in configs:
        time.sleep(0.2)
        ctx.run(f'redis-server {config_fp} --daemonize yes')

    primary = 'myprimary'
    sentinel_configs = [
        create_sentinel_config(ctx, 6382, '127.0.0.1:6379', primary, 2),
        create_sentinel_config(ctx, 6383, '127.0.0.1:6379', primary, 2),
        create_sentinel_config(ctx, 6384, '127.0.0.1:6379', primary, 2)
    ]
    for config_fp, log_fp, port in sentinel_configs:
        ctx.run(f'redis-server {config_fp} --daemonize yes --sentinel')

    log_args = ' '.join(tup[1] for tup in configs + sentinel_configs)
    ctx.run(f'tail -f {log_args}')

    # to introspect on the cluster, connect to any sentinel and run:
    # - SENTINEL master myprimary
    # - SENTINEL get-master-addr-by-name <primary_name>
    # - SENTINEL replicas <primary_name>
    # - SENTINEL sentinels myprimary


@task
def example_three(ctx):

    configs = [
        create_cluster_config(ctx, port) for port in range(7000, 7006)
    ]
    for config_fp, log_fp, port in configs:
        ctx.run(f'redis-server {config_fp} --daemonize yes')

    time.sleep(2)

    # when creating the cluster we are passing 6 instances and specifying 1 replica
    # per shard, therefore the cluster will have 3 shards, each replicated once
    addr_args = ' '.join([f'127.0.0.1:{port}' for port in range(7000, 7006)])
    ctx.run(f'echo yes | redis-cli -p 7000 --cluster create {addr_args} --cluster-replicas 1')

    print('\n------------------------------------------------------------------------\n')
    time.sleep(1)

    log_args = ' '.join(tup[1] for tup in configs)
    ctx.run(f'tail -f {log_args}')

    # introspecting the cluster
    # - cluster slots


@task
def example_three_add_shard(ctx):

    # start shard instances
    configs = [
        create_cluster_config(ctx, port) for port in range(7006, 7008)
    ]
    for config_fp, log_fp, port in configs:
        ctx.run(f'redis-server {config_fp} --daemonize yes')

    # add new primary shard
    time.sleep(0.3)
    ctx.run(f'redis-cli -p 7000 --cluster add-node 127.0.0.1:7006 127.0.0.1:7000')
    time.sleep(0.8)

    # get id of newly added shard
    primary_id = None
    res = ctx.run(f'redis-cli -p 7000 cluster nodes')
    for line in res.stdout.split('\n'):
        match = re.search(NODES_REGEX, line)
        if match is None:
            import pdb; pdb.set_trace()
        port = match.groupdict()['port']
        if port == '7006':
            primary_id = line.split(' ')[0]
            break
    if primary_id is None:  # node not found!
        import pdb; pdb.set_trace()
        print()

    # add 127.0.0.1:7007 as a replica of shard at 127.0.0.1:7006
    ctx.run(f'redis-cli -p 7000 --cluster add-node 127.0.0.1:7007 127.0.0.1:7000 --cluster-slave --cluster-master-id {primary_id}')
    time.sleep(0.5)

    # print slots
    res = ctx.run(f'redis-cli -p 7000 cluster slots', hide='both')
    print(res.stdout)

    _reshard(ctx, 7000, primary_id, 4096)
    # ctx.run('redis-cli -p 7000 --cluster reshard 127.0.0.1:7000')  # { echo "4096"; echo "' + primary_id + '"; echo "all"; echo "yes"; } |
    time.sleep(1)

    # print slots
    res = ctx.run(f'redis-cli -p 7000 cluster slots', hide='both')
    print(res.stdout)


def _reshard(ctx, redis_port, receiving_node_id, num_slots):

    watchers = [
        Responder(
            pattern=r'How many slots do you want to move.*',
            response=f'{num_slots}\n'
        ),
        Responder(
            pattern=r'What is the receiving node ID.*',
            response=f'{receiving_node_id}\n'
        ),
        Responder(
            pattern=r'Please enter all the source node IDs.*',
            response='all\n'
        ),
        Responder(
            pattern=r'Do you want to proceed with the proposed reshard plan.*',
            response='yes\n'
        )
    ]
    ctx.run(f'redis-cli -p {redis_port} --cluster reshard 127.0.0.1:{redis_port}', watchers=watchers)


@task
def stop_all(ctx):
    systemctl_stop_called = False
    for proc in psutil.process_iter():
        if proc.cmdline() and '[cluster]' in proc.cmdline()[0]:
            proc.kill()  # catch these before the systemd block to avoid unnecessary sudo
            continue
        if proc.name() == 'redis-server':
            if proc.parent().name() == 'systemd' and not systemctl_stop_called:
                # this is for any systemd redis-server instances, but cluster instances may
                # also have systemd as a parent so we must also use proc.kill()
                ctx.run('sudo systemctl stop redis-server')
                systemctl_stop_called = True
                time.sleep(0.2)
                # also attempt to kill
                try:
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass
                continue

            proc.kill()

        if proc.name() == 'redis-cli':
            if 'monitor' in proc.cmdline():
                proc.kill()


@task
def stop_monitors(ctx):
    for proc in psutil.process_iter():
        if proc.name() == 'redis-cli':
            if 'monitor' in proc.cmdline():
                proc.kill()


# Redis cluster does not allow you to intersect, union, or difference
# sets or zsets that are not on the same node
# here is a workaround: https://redis-py-cluster.readthedocs.io/en/master/limitations-and-differences.html

# note: pub-sub performance is worse on clusters: https://redis-py-cluster.readthedocs.io/en/master/pubsub.html#scalability-issues
# this doc recommends using a separate instance for pub-sub

# for detailed docs on clustering see:  https://redis.io/topics/cluster-spec

# very helpful doc: https://redis.io/topics/partitioning
# it suggests running many (e.g. 32, 64) redis instances on a single node and as you scale move the instances across machines

# this redis proxy may also help: https://github.com/twitter/twemproxy

# Docker example of cluster: https://github.com/Grokzen/docker-redis-cluster

# some notes on networking issues when using docker, may also apply to Nomad: https://redis.io/topics/sentinel#sentinel-docker-nat-and-possible-issues

# useful article: https://severalnines.com/database-blog/hash-slot-resharding-and-rebalancing-redis-cluster
