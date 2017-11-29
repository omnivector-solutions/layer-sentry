# Overview

This charm provides Redis Server. Redis is an open source (BSD licensed), in-memory data structure store, used as a database, cache and message broker. It supports data structures such as strings, hashes, lists, sets, sorted sets with range queries, bitmaps, hyperloglogs and geospatial indexes with radius queries. Redis has built-in replication, Lua scripting, LRU eviction, transactions and different levels of on-disk persistence, and provides high availability via Redis Sentinel and automatic partitioning with Redis Cluster.

### Usage

Step by step instructions on using the charm:

```
juju deploy redis
```

### metrics

It is possible to collect metrics for this charm by using `juju metrics redis`. You will receive the following output: 

```
UNIT   	           TIMESTAMP	           METRIC	 VALUE
redis/3	2017-09-27T21:15:09Z	  blocked_clients	     0
redis/3	2017-09-27T21:15:09Z	connected_clients	     1
redis/3	2017-09-27T21:15:09Z	       juju-units	     1
redis/3	2017-09-27T21:15:09Z	      used_memory	508800

```

### Scale out Usage


## Known Limitations and Issues


### Configuration


### Contact Information


### Redis Info

  - https://redis.io/
  - https://github.com/antirez/redis/issues
  - https://groups.google.com/forum/?fromgroups#!forum/redis-db

