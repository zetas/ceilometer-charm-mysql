from charmhelpers.core.hookenv import (
    relation_ids,
    relation_get,
    related_units,
    config
)

from charmhelpers.contrib.openstack.utils import os_release

from charmhelpers.contrib.openstack.context import (
    OSContextGenerator,
    context_complete,
    ApacheSSLContext as SSLContext,
)

from charmhelpers.contrib.hahelpers.cluster import (
    determine_apache_port,
    determine_api_port
)

CEILOMETER_DB = 'ceilometer'


class LoggingConfigContext(OSContextGenerator):
    def __call__(self):
        return {'debug': config('debug'), 'verbose': config('verbose')}


class SharedDBContext(OSContextGenerator):
    interfaces = ['mongodb', 'mysql']

    MYSQL_RELATION = {
        'hostname': 'host',
        'port': 3306,
        'db_select': 'mysql',
        'relations': []
    }

    MONGO_RELATION = {
        'hostname': 'hostname',
        'port': 'port',
        'db_select': 'mongodb',
        'relations': []
    }

    def __call__(self):
        db_servers = []
        replset = None
        use_replset = os_release('ceilometer-api') >= 'icehouse'
        db_relation = []

        #These next 9 lines need to be refactored into something better but this 
        # shows the general idea.
        mongo_relations = relation_ids('shared-db')
        mysql_relations = relation_ids('shared-db-mysql')

        if len(mongo_relations):
            db_relation = self.MONGO_RELATION
            db_relation.update(relations=mongo_relations)
        elif len(mysql_relations):
            db_relation = self.MYSQL_RELATION
            db_relation.update(relations=mysql_relations)
        else:
            db_relation['relations'] = []

        for relid in db_relation['relations']:
            rel_units = related_units(relid)
            use_replset = use_replset and (len(rel_units) > 1)

            for unit in rel_units:

                host = relation_get(db_relation['hostname'], unit, relid)

                if type(db_relation['port']) == int:
                    port = db_relation['port']
                else:
                    port = relation_get(db_relation['port'], unit, relid)

                conf = {
                    "db_host": host,
                    "db_port": port,
                    "db_name": CEILOMETER_DB,
                    "db_select": db_relation['db_select']
                }

                if not context_complete(conf):
                    continue

                if not use_replset:
                    return conf

                if replset is None:
                    replset = relation_get('replset', unit, relid)

                db_servers.append('{}:{}'.format(host, port))

        if db_servers:
            return {
                'db_servers': ','.join(db_servers),
                'db_name': CEILOMETER_DB,
                'db_replset': replset,
                'db_select': db_relation['db_select']
            }

        return {}

CEILOMETER_PORT = 8777


class CeilometerContext(OSContextGenerator):
    def __call__(self):
        # Lazy-import to avoid a circular dependency in the imports
        from ceilometer_utils import get_shared_secret

        ctxt = {
            'port': CEILOMETER_PORT,
            'metering_secret': get_shared_secret()
        }
        return ctxt


class CeilometerServiceContext(OSContextGenerator):
    interfaces = ['ceilometer-service']

    def __call__(self):
        for relid in relation_ids('ceilometer-service'):
            for unit in related_units(relid):
                conf = relation_get(unit=unit, rid=relid)
                if context_complete(conf):
                    return conf
        return {}


class HAProxyContext(OSContextGenerator):
    interfaces = ['ceilometer-haproxy']

    def __call__(self):
        '''Extends the main charmhelpers HAProxyContext with a port mapping
        specific to this charm.
        '''
        haproxy_port = CEILOMETER_PORT
        api_port = determine_api_port(CEILOMETER_PORT, singlenode_mode=True)
        apache_port = determine_apache_port(CEILOMETER_PORT,
                                            singlenode_mode=True)

        ctxt = {
            'service_ports': {'ceilometer_api': [haproxy_port, apache_port]},
            'port': api_port
        }
        return ctxt


class ApacheSSLContext(SSLContext):

    external_ports = [CEILOMETER_PORT]
    service_namespace = "ceilometer"
