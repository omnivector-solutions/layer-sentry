import os
import string
import random

from jinja2 import Environment, FileSystemLoader

from charmhelpers.core import unitdata
from charmhelpers.core.hookenv import charm_dir, config

from charmhelpers.core.host import (
    mkdir,
    service_running,
    service_start,
    service_restart
)

from charms.leadership import leader_get


SENTRY_WEB_SERVICE = 'snap.sentry.web'

SENTRY_WORKER_SERVICE = 'snap.sentry.worker'

SENTRY_CRON_SERVICE = 'snap.sentry.cron'

SENTRY_CONF_DIR = \
    os.path.join('/', 'root', 'snap', 'sentry',
                 'current', '.sentry')

SENTRY_CONFIG_PY = \
    os.path.join(SENTRY_CONF_DIR, 'sentry.conf.py')

SENTRY_CONFIG_YML = \
    os.path.join(SENTRY_CONF_DIR, 'config.yml')

SENTRY_BIN = \
    os.path.join('/', 'snap', 'bin', 'sentry')

SENTRY_WEB_SERVICE_OVERRIDE = \
    os.path.join('/', 'etc', 'systemd', 'system',
                 SENTRY_WEB_SERVICE + '.service.d',
                 'override.conf')

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


def render_web_override():
    """ Render override.conf for the sentry.web systemd service
    """
    if os.path.exists(SENTRY_WEB_SERVICE_OVERRIDE):
        os.remove(SENTRY_WEB_SERVICE_OVERRIDE)

    conf = config()
    env = conf['web-override']

    if not env:
        return

    mkdir(os.path.dirname(SENTRY_WEB_SERVICE_OVERRIDE))

    web_override_tmpl = \
        load_template(
            'web.override.conf.j2').render(environment=env)
    spew(SENTRY_WEB_SERVICE_OVERRIDE, web_override_tmpl)


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

    if secrets:
        secrets_mod = secrets
    else:
        secrets_mod = {}

    for k in ('redis_host',
              'redis_port',
              'postgresql_host',
              'postgresql_port',
              'postgresql_user',
              'postgresql_password',
              'postgresql_dbname',
              'github_app_id',
              'github_api_secret',
              'github_extended_permissions',
              'social_auth_redirect_is_https',
              'email_server_host',
              'email_server_port',
              'email_server_username',
              'email_server_password',
              'email_server_tls',
              'email_from',
              'enable_statsd'):
        secrets_mod[k] = kv.get(k)

    secrets_mod['system_secret_key'] = leader_get('system_secret_key')

    return secrets_mod
