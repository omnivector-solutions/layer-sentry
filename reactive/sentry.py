from subprocess import call

from charms.reactive import (
    clear_flag,
    endpoint_from_flag,
    set_flag,
    when,
    when_not,
)

from charmhelpers.core.hookenv import (
    network_get,
    log,
    status_set,
    config,
    open_port
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


PRIVATE_IP = network_get('http')['ingress-addresses'][0]


kv = unitdata.kv()


# Do this ASAP to prevent the systemd services installed by the snap to restart
# in a loop because the configuration is missing
@when('snap.installed.sentry')
@when_not('sentry.init.available')
def sentry_init():
    call('{} init'.format(SENTRY_BIN).split())
    set_flag('sentry.init.available')


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
        redis_host = config('redis-uri').split(":")[0]
        redis_port = config('redis-uri').split(":")[1]
        kv.set('redis_host', redis_host)
        kv.set('redis_port', redis_port)
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

    if conf.get('db-extensions', ''):
        pgsql.set_extensions(conf.get('db-extensions'))

    status_set('active', 'Database requested')
    set_flag('sentry.database.requested')


@when('postgresql.master.available',
      'sentry.database.requested')
@when_not('sentry.juju.database.available')
def get_set_postgresql_data(pgsql):
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
def get_all_redis_relation_info():
    """Get redis info
    """
    status_set('maintenance', 'Getting Redis info')

    redis_nodes = endpoint_from_flag('endpoint.redis.available').relation_data()
    kv.set('redis_host', redis_nodes[0]['host'])
    kv.set('redis_port', redis_nodes[0]['port'])

    status_set('active', 'Redis connection details saved.')

    set_flag('sentry.juju.redis.available')
    clear_flag('sentry.config.available')
    clear_flag('sentry.manual.redis.available')


@when_not('sentry.config.available')
@when('snap.installed.sentry',
      'sentry.juju.redis.available',
      'sentry.juju.database.available')
def config_sentry():
    """Write out sentry configs
    """

    status_set('maintenance', 'Configuring Sentry')
    render_sentry_config()

    start_restart(SENTRY_WEB_SERVICE)
    start_restart(SENTRY_WORKER_SERVICE)
    start_restart(SENTRY_CRON_SERVICE)

    status_set('active', 'Sentry configured')
    set_flag('sentry.config.available')


@when('sentry.config.available')
@when_not('sentry.database.available')
def init_sentry_db():
    """Initialize the sentry database
    """
    status_set('maintenance', 'Migrating Sentry DB')

    call('{} upgrade --noinput'.format(SENTRY_BIN).split())

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


@when('sentry.config.available')
@when_not('sentry.port.available')
def open_sentry_port():
    open_port(9000)
    status_set('active', 'Sentry available')
    set_flag('sentry.port.available')


@when('http.available')
@when('sentry.port.available')
def set_http_relation_data():
    endpoint = endpoint_from_flag('http.available')
    ctxt = {'host': PRIVATE_IP, 'port': 9000}
    endpoint.configure(**ctxt)
    clear_flag('http.available')
