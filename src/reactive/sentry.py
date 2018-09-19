from subprocess import call
from urllib.parse import urlparse

from charms.reactive import (
    clear_flag,
    endpoint_from_flag,
    hook,
    set_flag,
    when,
    when_any,
    when_not,
)

from charmhelpers.core.hookenv import (
    config,
    log,
    open_port,
    status_set,
    unit_private_ip,
)

from charmhelpers.core import unitdata

from charms.layer.sentry import (
    render_sentry_config,
    start_restart,
    SENTRY_BIN,
    SENTRY_WEB_SERVICE,
    SENTRY_WORKER_SERVICE,
    SENTRY_CRON_SERVICE
)


SENTRY_HTTP_PORT = 9000


kv = unitdata.kv()


@hook('start')
def set_started_flag():
    set_flag('sentry.juju.started')


@when_not('manual.database.check.available')
def check_user_provided_database():
    if not config('db-uri'):
        clear_flag('sentry.manual.database.available')
        log("Manual database not configured")
    else:
        kv.set('db_uri', config('db-uri'))
        set_flag('sentry.manual.database.available')
        clear_flag('sentry.config.available')
        clear_flag('sentry.juju.database.available')
    set_flag('manual.database.check.available')


@when_not('manual.redis.check.available')
def check_user_provided_redis():
    if not config('redis-uri'):
        clear_flag('sentry.manual.redis.available')
        log("Manual redis not configured")
    else:
        o = urlparse(config('redis-uri'))
        kv.set('redis_uri', config('redis-uri'))
        kv.set('redis_host', o.hostname)
        kv.set('redis_port', o.port)
        if o.password:
            kv.set('redis_password', o.password)
        set_flag('sentry.manual.redis.available')
        clear_flag('sentry.config.available')
        clear_flag('sentry.juju.redis.available')
    set_flag('manual.redis.check.available')


@when('postgresql.connected')
@when_not('sentry.database.requested')
def request_postgresql_database(pgsql):
    """Request PGSql DB
    """

    conf = config()
    status_set('maintenance', 'Requesting database for sentry')

    pgsql.set_database(conf.get('db-name', 'sentry'))

    if conf.get('db-extensions'):
        pgsql.set_extensions(conf.get('db-extensions'))

    status_set('active', 'Database requested')
    set_flag('sentry.database.requested')


@when('postgresql.master.available',
      'sentry.database.requested')
@when_not('sentry.juju.database.available')
def get_set_juju_postgresql_data(pgsql):
    """Get/set postgresql details
    """
    status_set('maintenance', 'Database acquired, saving details')

    kv.set('postgresql_host', pgsql.master.host)
    kv.set('postgresql_port', pgsql.master.port)
    kv.set('postgresql_user', pgsql.master.user)
    kv.set('postgresql_password', pgsql.master.password)
    kv.set('postgresql_dbname', pgsql.master.dbname)

    status_set('active', 'Sentry database available')

    clear_flag('sentry.config.available')
    clear_flag('sentry.manual.database.available')
    set_flag('sentry.juju.database.available')


@when('endpoint.redis.available')
@when_not('sentry.juju.redis.available')
def get_redis_relation_info():
    """Get redis relation info
    """
    status_set('maintenance', 'Getting Redis info')
    endpoint = endpoint_from_flag('endpoint.redis.available')
    redis = endpoint.relation_data()[0]

    kv.set('redis_host', redis['host'])
    kv.set('redis_port', redis['port'])
    if redis.get('password'):
        kv.set('redis_password', redis['password'])

    status_set('active', 'Redis connection details saved.')

    set_flag('sentry.juju.redis.available')
    clear_flag('sentry.config.available')
    clear_flag('sentry.manual.redis.available')
    clear_flag('endpoint.redis.available')


@when('snap.installed.sentry')
@when_any('sentry.juju.redis.available',
          'sentry.manual.redis.available')
@when_any('sentry.juju.database.available',
          'sentry.manual.database.available')
@when_not('sentry.init.config.available')
def init_sentry():
    """Write out sentry configs, restart daemons to initialize.
    """

    status_set('maintenance', 'Configuring Sentry')

    render_sentry_config()

    start_restart(SENTRY_WEB_SERVICE)
    start_restart(SENTRY_WORKER_SERVICE)
    start_restart(SENTRY_CRON_SERVICE)

    status_set('active', 'Sentry configured')
    set_flag('sentry.init.config.available')


@when('sentry.init.config.available')
@when_not('sentry.database.available')
def init_sentry_db():
    """Initialize the sentry database
    """
    status_set('maintenance', 'Migrating Sentry DB')

    call('{} upgrade'.format(SENTRY_BIN).split())

    status_set('active', 'Sentry database available')
    set_flag('sentry.database.available')


@when('sentry.database.available')
@when_not('sentry.superuser.available')
def create_sentry_superuser():
    status_set('maintenance', 'Creating Sentry SU')

    ctxt = {'bin': SENTRY_BIN,
            'email': config('admin-email'),
            'password': config('admin-password')}

    cmd = ('{bin} createuser --email {email} --password {password} '
           '--superuser --no-input'.format(**ctxt))

    call(cmd.split())
    status_set('active', 'Sentry SU available')
    set_flag('sentry.superuser.available')


@when('sentry.database.available',
      'sentry.superuser.available')
@when_not('sentry.init.complete')
def set_sentry_init_complete():
    set_flag('sentry.init.complete')


@when('sentry.init.complete')
@when_not('sentry.http.port.available')
def open_sentry_port():
    open_port(SENTRY_HTTP_PORT)
    status_set('active', 'Sentry available')
    set_flag('sentry.http.port.available')


@when('http.available')
@when('sentry.http.port.available')
def set_http_relation_data():
    endpoint = endpoint_from_flag('http.available')
    endpoint.configure(SENTRY_HTTP_PORT)
    clear_flag('http.available')


@when('sentry.juju.started')
@when_not('postgresql.connected',
          'sentry.manual.database.available')
def block_on_no_db():
    status_set('blocked',
               "Need database info via config or relation to proceed")
    return


@when('sentry.juju.started')
@when_not('endpoint.redis.joined',
          'sentry.manual.redis.available')
def block_on_no_redis():
    status_set('blocked',
               "Need redis info via config or relation to proceed")
    return
