import jinja2

from invoke import task

DOCKER_TAG = 'keydb:latest'

DOCKER_COMPOSE_TEMPLATE = """
version: "3"
services:

  memtier:
    image: redislabs/memtier_benchmark:latest
    container_name: memtier
    hostname: memtier
    command: "sleep infinity"
    networks:
      keydb-network:
        ipv4_address: 10.5.0.4
    restart: "no"

{% for service_name, details in services.items() -%}

{{ service_name | indent(2, True) }}:
    image: {{ docker_image }}
    environment:
    {% for env_name, env_value in details.environment.items() -%}
        {{ '-' | indent(2, True ) }} {{ env_name }}={{ env_value }}
    {% endfor -%}
    container_name: {{ service_name }}
    hostname: {{ service_name }}
    networks:
      keydb-network:
        ipv4_address: {{ details.ipv4_address }}
    restart: "no"

{% endfor -%}

networks:
  keydb-network:
    driver: bridge
    ipam:
      driver: default
      config:
        - subnet: 10.5.0.0/24

"""


MASTER_IP = '10.5.0.5'

SERVICES = [
    ('keydb-master', 'master', MASTER_IP),
    ('keydb-replica1', 'replica', '10.5.0.6'),
    ('keydb-replica2', 'replica', '10.5.0.7'),
    ('keydb-sentinel1', 'sentinel', '10.5.0.8'),
    ('keydb-sentinel2', 'sentinel', '10.5.0.9'),
    ('keydb-sentinel3', 'sentinel', '10.5.0.10'),
]


def do_template_render__string(template_str, data):
    template = jinja2.Environment(loader=jinja2.BaseLoader).from_string(template_str)
    return template.render(**data)


@task
def render_docker_compose(ctx):
    services = {}
    for service_name, instance_type, ip_address in SERVICES:
        services[service_name] = {
            'environment': {
                'MASTER_IP': MASTER_IP,
                'SELF_IP': ip_address,
                'INSTANCE_TYPE': instance_type
            },
            'ipv4_address': ip_address
        }
    context = {'services': services, 'docker_image': DOCKER_TAG}
    file_string = do_template_render__string(DOCKER_COMPOSE_TEMPLATE, context)
    with open('./docker-compose.yml', 'w') as f:
        f.write(file_string)


@task
def docker_build(ctx):
    with ctx.cd('./docker'):
        ctx.run(f'docker build -t {DOCKER_TAG} .')


@task
def benchmark(ctx):
    ctx.run('docker exec memtier memtier_benchmark -s 10.5.0.5 -p 6379 --hide-histogram --requests=80000 --clients=100 --pipeline=20 --data-size=128 --key-pattern=S:R --ratio=1:20 -t 3')


# note: you get higher performance if you pin threads to cores: https://docs.keydb.dev/blog/2019/10/07/blog-post/#benefits-of-multithreading