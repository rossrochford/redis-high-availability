import jinja2
import uuid


REDIS_CONF_TEMPLATE = """
port {{ port }}

{% if replicaof_ip %}
replicaof {{ replicaof_ip }} {{ replicaof_port }}
{% else %}
appendonly yes
appendfilename "appendonly.aof"
{% endif %}

dbfilename dump.rdb
dir {{ data_dir }}

logfile {{ log_filepath }}

io-threads 4
io-threads-do-reads yes
"""


SENTINEL_CONF_TEMPLATE = """
port {{ port }}

sentinel monitor {{ primary_name }} {{ sentinelof_ip }} {{ sentinelof_port }} {{ quorum_threshold }}
sentinel down-after-milliseconds {{ primary_name }} 9000
sentinel failover-timeout {{ primary_name }} 40000
# sentinel auth-pass {{ name_name }} <password_of_master>

# not sure this is used by sentinel
dir {{ data_dir }}  

logfile {{ log_filepath }}
"""

CLUSTER_CONF_TEMPLATE = """
port {{ port }}
cluster-enabled yes
cluster-config-file /tmp/redis-node-{{ uid }}.conf
cluster-node-timeout 9000
appendonly yes
appendfilename "appendonly.aof"

dbfilename dump.rdb
dir {{ data_dir }}

logfile {{ log_filepath }}
"""

# you can further optimize multithreading by pinning threads to specific CPU cores: https://www.fatalerrors.org/a/multithreaded-io-for-redis6-new-features.html


def do_template_render__string(template_str, data):
    rtemplate = jinja2.Environment(loader=jinja2.BaseLoader).from_string(template_str)
    return rtemplate.render(**data)


def create_redis_config(ctx, port, replicaof_addr=None):

    replicaof_ip, replicaof_port = None, None
    if replicaof_addr:
        replicaof_ip, replicaof_port = replicaof_addr.split(':')

    uid = uuid.uuid4().hex[:10]
    log_filepath = f"/tmp/redis-{uid}.log"
    data_dir = f'/tmp/redis-data-{uid}'

    context = {
        'uid': uid,
        'port': port,
        'replicaof_ip': replicaof_ip,
        'replicaof_port': replicaof_port,
        'log_filepath': log_filepath,
        'data_dir': data_dir
    }
    conf_string = do_template_render__string(REDIS_CONF_TEMPLATE, context)

    config_filepath = f"/tmp/redis-{uid}.conf"
    with open(config_filepath, 'w') as f:
        f.write(conf_string)

    ctx.run(f'mkdir -p {data_dir}')
    ctx.run(f'touch {log_filepath}')

    return config_filepath, log_filepath, port


def create_sentinel_config(ctx, port, sentinelof_addr, primary_name, quorum_threshold):

    sentinelof_ip, sentinelof_port = sentinelof_addr.split(':')

    uid = uuid.uuid4().hex[:10]
    log_filepath = f"/tmp/redis-sentinel-{uid}.log"
    data_dir = f'/tmp/redis-data-{uid}'

    context = {
        'uid': uid,
        'port': port,
        'sentinelof_ip': sentinelof_ip,
        'sentinelof_port': sentinelof_port,
        'quorum_threshold': quorum_threshold,
        'primary_name': primary_name,
        'log_filepath': log_filepath,
        'data_dir': data_dir
    }
    conf_string = do_template_render__string(SENTINEL_CONF_TEMPLATE, context)

    config_filepath = f"/tmp/redis-sentinel-{uid}.conf"
    with open(config_filepath, 'w') as f:
        f.write(conf_string)

    ctx.run(f'mkdir -p {data_dir}')
    ctx.run(f'touch {log_filepath}')

    return config_filepath, log_filepath, port


def create_cluster_config(ctx, port):

    uid = uuid.uuid4().hex[:10]
    log_filepath = f"/tmp/redis-cluster-{uid}.log"
    data_dir = f'/tmp/redis-data-{uid}'

    context = {
        'uid': uid,
        'port': port,
        'log_filepath': log_filepath,
        'data_dir': data_dir
    }

    conf_string = do_template_render__string(CLUSTER_CONF_TEMPLATE, context)

    config_filepath = f"/tmp/redis-cluster-{uid}.conf"
    with open(config_filepath, 'w') as f:
        f.write(conf_string)

    ctx.run(f'mkdir -p {data_dir}')
    ctx.run(f'touch {log_filepath}')

    return config_filepath, log_filepath, port
