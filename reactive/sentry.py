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
    SENTRY_SERVICE
)


PRIVATE_IP = network_get('http')['ingress-addresses'][0]


kv = unitdata.kv()


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
        redis_host = config('redis-data-uri').split(":")[0]
        redis_port = config('redis-data-uri').split(":")[1]
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
    if conf.get('db-roles', ''):
        pgsql.set_roles(conf.get('db-roles'))
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


@when('redis.available')
def get_all_redis_relation_info():
    """Get redis info
    """
    status_set('maintenance', 'Getting Redis info')

    for redis_node in endpoint_from_flag('redis.available'):
        kv.set('redis_host', redis_node['host'])
        kv.set('redis_port', redis_node['port'])

    status_set('active', 'Redis connection details saved.')

    set_flag('sentry.juju.redis.available')
    clear_flag('sentry.config.available')
    clear_flag('sentry.manual.redis.available')
    clear_flag('redis.available')


@when_not('sentry.config.available')
@when('snap.installed.sentry',
      'sentry.juju.redis.available',
      'sentry.juju.database.available')
def config_sentry():
    """Write out sentry configs
    """

    status_set('maintenance', 'Configuring Sentry')
    render_sentry_config()

    start_restart(SENTRY_SERVICE)

    status_set('active', 'Sentry configured')
    set_flag('sentry.config.available')


@when('sentry.config.available')
@when_not('sentry.database.available')
def init_sentry_db():
    """Initialize the sentry database
    """
    status_set('maintenance', 'Migrating Sentry DB')

    render_sentry_config()
    call('/snap/bin/sentry upgrade'.split())

    status_set('maintenance', 'Configuring Sentry.')
    render_sentry_config()
    set_flag('sentry.database.available')


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
