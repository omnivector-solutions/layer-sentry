import os
import string
import random

from jinja2 import Environment, FileSystemLoader

from charmhelpers.core import unitdata
from charmhelpers.core.hookenv import charm_dir, config

from charmhelpers.core.host import (
    service_running,
    service_start,
    service_restart
)

from charms.leadership import leader_get


SENTRY_WEB_SERVICE = 'snap.sentry.sentry-web'

SENTRY_WORKER_SERVICE = 'snap.sentry.sentry-web'

SENTRY_CRON_SERVICE = 'snap.sentry.sentry-web'

SENTRY_CONF_DIR = \
    os.path.join('/', 'var', 'snap', 'sentry',
                 'common', 'etc', 'sentry')

SENTRY_CONFIG_PY = \
    os.path.join(SENTRY_CONF_DIR, 'sentry.conf.py')

SENTRY_CONFIG_YML = \
    os.path.join(SENTRY_CONF_DIR, 'config.yml')

SENTRY_BIN = \
    os.path.join('/', 'snap', 'bin', 'sentry.sentry-cli')


kv = unitdata.kv()


def gen_random_string(size=50, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def start_restart(service):
    if service_running(service):
        service_restart(service)
    else:
        service_start(service)


def render_sentry_config(secrets=None):
    """Render config.py
    """

    if not secrets:
        secrets = {}

    # Render config source and target
    if os.path.exists(SENTRY_CONFIG_YML):
        os.remove(SENTRY_CONFIG_YML)

    if os.path.exists(SENTRY_CONFIG_PY):
        os.remove(SENTRY_CONFIG_PY)

    # Load templates
    sentry_config_yml_tmpl = \
        load_template(
            'config.yml.j2').render(
                secrets=return_secrets(secrets))

    sentry_config_py_tmpl = \
        load_template(
            'sentry.conf.py.j2').render(
                secrets=return_secrets(secrets))

    # Spew configs into source
    spew(SENTRY_CONFIG_YML, sentry_config_yml_tmpl)
    spew(SENTRY_CONFIG_PY, sentry_config_py_tmpl)


def load_template(name, path=None):
    """ load template file
    :param str name: name of template file
    :param str path: alternate location of template location
    """
    if path is None:
        path = os.path.join(charm_dir(), 'templates')
    env = Environment(
        loader=FileSystemLoader(path))
    return env.get_template(name)


def spew(path, data):
    """ Writes data to path
    :param str path: path of file to write to
    :param str data: contents to write
    :param str owner: optional owner of file
    """
    with open(path, 'w') as f:
        f.write(data)


def return_secrets(secrets=None):
    """Return secrets dict
    """

    conf = config()
    if secrets:
        secrets_mod = secrets
    else:
        secrets_mod = {}

    secrets_mod['redis_host'] = kv.get('redis_host')
    secrets_mod['redis_port'] = kv.get('redis_port')
    secrets_mod['postgresql_host'] = kv.get('postgresql_host')
    secrets_mod['postgresql_port'] = kv.get('postgresql_port')
    secrets_mod['postgresql_user'] = kv.get('postgresql_user')
    secrets_mod['postgresql_password'] = kv.get('postgresql_password')
    secrets_mod['postgresql_dbname'] = kv.get('postgresql_dbname')
    secrets_mod['system_secret_key'] = leader_get('system_secret_key')

    if conf.get('aws-key'):
        secrets_mod['AWS_KEY'] = config('aws-key')
    if conf.get('aws-secret'):
        secrets_mod['AWS_SECRET'] = config('aws-secret')
    if conf.get('aws-region'):
        secrets_mod['AWS_REGION'] = config('aws-region')

    if conf.get('secrets', ''):
        secrets_from_config = config('secrets').strip().split(",")
        for secret in secrets_from_config:
            s = secret.split("=")
            secrets_mod[s[0]] = s[1]
    return secrets_mod
