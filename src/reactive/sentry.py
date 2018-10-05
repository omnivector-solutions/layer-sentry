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
    is_leader,
    local_unit,
    log,
    open_port,
    status_set,
    unit_private_ip,
)

from charmhelpers.core import unitdata

from charmhelpers.core.host import service_stop

from charms.layer.sentry import (
    gen_random_string,
    render_sentry_config,
    render_web_override,
    start_restart,
    SENTRY_BIN,
    SENTRY_WEB_SERVICE,
    SENTRY_WORKER_SERVICE,
    SENTRY_CRON_SERVICE
)

from charms.leadership import leader_set


SENTRY_HTTP_PORT = 9000


kv = unitdata.kv()


# Do this ASAP to prevent the systemd services installed by the snap to restart
# in a loop because the configuration is missing
@when('snap.installed.sentry')
@when_not('sentry.init.available')
def sentry_init():
    service_stop(SENTRY_WEB_SERVICE)
    service_stop(SENTRY_WORKER_SERVICE)
    service_stop(SENTRY_CRON_SERVICE)
    call('{} init'.format(SENTRY_BIN).split())
    set_flag('sentry.init.available')


@hook('start')
def set_started_flag():
    set_flag('sentry.juju.started')


@when_not('leadership.set.system_secret_key')
@when('leadership.is_leader')
def set_sentry_system_key_to_leader():
    conf = config()
    system_secret_key = conf.get('system-secret-key')
    if system_secret_key:
        pass
    else:
        system_secret_key = gen_random_string()
    leader_set(system_secret_key=system_secret_key)


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


@when_any('config.changed.github-app-id',
          'config.changed.github-api-secret',
          'config.changed.github-extended-permissions',
          'config.changed.social-auth-redirect-is-https')
def check_user_provided_github():
    options = {
       'github_app_id': config('github-app-id'),
       'github_api_secret': config('github-api-secret'),
       'github_extended_permissions': config('github-extended-permissions'),
       'social_auth_redirect_is_https': config('social-auth-redirect-is-https')
    }
    {kv.set(k, v) for k, v in options.items()}
    clear_flag('sentry.config.available')


@when_any('config.changed.slack-client-id',
          'config.changed.slack-client-secret')
def check_user_provided_slack():
    options = {
       'slack_client_id': config('slack-client-id'),
       'slack_client_secret': config('slack-client-secret'),
       'slack_verification_token': config('slack-verification-token'),
    }
    {kv.set(k, v) for k, v in options.items()}
    clear_flag('sentry.config.available')


@when_any('config.changed.email-server-host'
          'config.changed.email-server-port',
          'config.changed.email-server-username',
          'config.changed.email-server-password',
          'config.changed.email-server-tls',
          'config.changed.email-from')
def update_email_settings():
    options = {
       'email_server_host': config('email-server-host'),
       'email_server_port': config('email-server-port'),
       'email_server_username': config('email-server-username'),
       'email_server_password': config('email-server-password'),
       'email_server_tls': config('email-server-tls'),
       'email_from': config('email-from'),
    }
    {kv.set(k, v) for k, v in options.items()}
    clear_flag('sentry.config.available')


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


@when('snap.installed.sentry',
      'leadership.set.system_secret_key')
@when_any('sentry.juju.redis.available',
          'sentry.manual.redis.available')
@when_any('sentry.juju.database.available',
          'sentry.manual.database.available')
@when_not('sentry.config.available')
def init_sentry():
    """Write out sentry configs, restart daemons to initialize.
    """
    status_set('maintenance', 'Configuring Sentry')

    render_sentry_config()

    start_restart(SENTRY_WEB_SERVICE)
    start_restart(SENTRY_WORKER_SERVICE)
    start_restart(SENTRY_CRON_SERVICE)

    status_set('active', 'Sentry configured')
    set_flag('sentry.config.available')


@when('sentry.config.available',
      'leadership.is_leader')
@when_not('sentry.database.available')
def init_sentry_db():
    """Initialize the sentry database
    """
    status_set('maintenance', 'Migrating Sentry DB')

    call('{} upgrade --noinput'.format(SENTRY_BIN).split())

    start_restart(SENTRY_WEB_SERVICE)
    start_restart(SENTRY_WORKER_SERVICE)
    start_restart(SENTRY_CRON_SERVICE)

    status_set('active', 'Sentry database available')
    set_flag('sentry.database.available')


@when('sentry.database.available',
      'leadership.is_leader')
@when_not('sentry.superuser.available')
def create_sentry_superuser():
    status_set('maintenance', 'Creating Sentry superuser')

    ctxt = {'bin': SENTRY_BIN,
            'email': config('admin-email'),
            'password': config('admin-password')}

    cmd = ('{bin} createuser --email {email} --password {password} '
           '--superuser --no-input'.format(**ctxt))

    call(cmd.split())
    leader_set(superuser_created=True)
    status_set('active', 'Sentry superuser available')
    set_flag('sentry.superuser.available')


# This is needed to set the flag on non-leader units
# so that they won't try to create the superuser should
# they become leader later on.
@when('leadership.set.superuser_created')
@when_not('sentry.superuser.available')
def set_superuser_flag():
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


@when('sentry.juju.started',
      'config.changed.web-override')
def update_web_override():
    render_web_override()
    call(['systemctl', 'daemon-reload'])
    start_restart(SENTRY_WEB_SERVICE)


@hook('upgrade-charm')
def migrate_sentry_db_on_upgrade():
    if is_leader():
        status_set('maintenance', 'Migrating Sentry DB')
        call('{} upgrade --noinput'.format(SENTRY_BIN).split())
        status_set('active', 'Sentry DB migration complete')


# Set up Nagios checks when the nrpe-external-master subordinate is related
@when('nrpe-external-master.available')
@when_not('sentry.nagios-setup.complete')
def setup_nagios(nagios):
    conf = config()
    unit_name = local_unit()
    check_base = '/usr/lib/nagios/plugins/'
    process_check = check_base + 'check_procs'

    web_check = [process_check, '-c', '4:4', '-a', '"[Sentry] uWSGI"']
    nagios.add_check(web_check, name="sentry.web_process",
                     description="Check for sentry.web processes",
                     context=conf['nagios_context'],
                     servicegroups=conf['nagios_servicegroups'],
                     unit=unit_name)

    worker_check = [process_check, '-c', '2:2', '-a', 'celeryd']
    nagios.add_check(worker_check, name="sentry.worker_process",
                     description="Check for sentry.worker processes",
                     context=conf['nagios_context'],
                     servicegroups=conf['nagios_servicegroups'],
                     unit=unit_name)

    cron_check = [process_check, '-c', '1:1', '-a', '"celery beat"']
    nagios.add_check(cron_check, name="sentry.cron_process",
                     description="Check for sentry.cron processes",
                     context=conf['nagios_context'],
                     servicegroups=conf['nagios_servicegroups'],
                     unit=unit_name)
    set_flag('sentry.nagios-setup.complete')


# This is triggered on any config-changed, and after an upgrade-charm - you
# don't get the latter with @when('config.changed')
@hook('config-changed')
def set_nrpe_flag():
    clear_flag('sentry.nagios-setup.complete')


@when('endpoint.aws-elb.joined',
      'endpoint.aws.joined')
@when_not('aws-elb.data.sent')
def send_data_to_aws_elb_endpoint():
    aws_elb_endpoint = endpoint_from_flag('endpoint.aws-elb.joined')
    aws_integrator_endpoint = endpoint_from_flag('endpoint.aws.joined')
    aws_elb_endpoint.configure(
        instance_id=aws_integrator_endpoint.instance_id,
        instance_region=aws_integrator_endpoint.region,
        instance_port=SENTRY_HTTP_PORT,
        health_check_endpoint="/"
    )
    set_flag('aws-elb.data.sent')


@when_not('endpoint.aws-elb.joined')
def remove_aws_elb_data_sent_flag():
    clear_flag('aws-elb.data.sent')
