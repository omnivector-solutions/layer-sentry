# Sentry
Open-source error tracking that helps developers monitor and fix crashes in real time. Iterate continuously. Boost efficiency. Improve user experience.

This charm deploys the sentry snap found in the [snapstore](https://snapcraft.io/sentry).

You may optionally specify your own sentry.snap as a resource to this charm.


### Usage
##### 1. Deploy the primary components; sentry, postgresql, redis, haproxy.
```bash
juju deploy cs:~omnivector/sentry
juju deploy cs:~omnivector/redis
juju deploy postgresql
juju deploy haproxy
```

##### 2. Make the relations.
```bash
juju relate sentry redis
juju relate sentry postgresql:db
juju relate sentry haproxy
```
When the deploy is complete you may find the sentry service at the haproxy ip address endpoint.


### License
* AGPLv3 (see `LICENSE` file)
