#!/usr/bin/python

import amulet
import time
from ceilometerclient.v2 import client as ceilclient

from charmhelpers.contrib.openstack.amulet.deployment import (
    OpenStackAmuletDeployment
)

from charmhelpers.contrib.openstack.amulet.utils import (
    OpenStackAmuletUtils,
    DEBUG, # flake8: noqa
    ERROR
)

# Use DEBUG to turn on debug logging
u = OpenStackAmuletUtils(DEBUG)

# XXX Tests for ceilometer-service relation missing due to Bug#1421388


class CeilometerBasicDeployment(OpenStackAmuletDeployment):
    """Amulet tests on a basic ceilometer deployment."""

    def __init__(self, series, openstack=None, source=None, stable=True):
        """Deploy the entire test environment."""
        super(CeilometerBasicDeployment, self).__init__(series, openstack,
                                                        source, stable)
        self._add_services()
        self._add_relations()
        self._configure_services()
        self._deploy()
        self._initialize_tests()

    def _add_services(self):
        """Add services

           Add the services that we're testing, where ceilometer is local,
           and the rest of the service are from lp branches that are
           compatible with the local charm (e.g. stable or next).
           """
        this_service = {'name': 'ceilometer'}
        other_services = [{'name': 'mysql'},
                          {'name': 'rabbitmq-server'}, {'name': 'keystone'},
                          {'name': 'mongodb'}, {'name': 'ceilometer-agent'},
                          {'name': 'nova-compute'}]
        super(CeilometerBasicDeployment, self)._add_services(this_service,
                                                             other_services)

    def _add_relations(self):
        """Add all of the relations for the services."""
        relations = {
            'ceilometer:shared-db': 'mongodb:database',
            'ceilometer:amqp': 'rabbitmq-server:amqp',
            'ceilometer:identity-service': 'keystone:identity-service',
            'ceilometer:identity-notifications': 'keystone:'
                                                 'identity-notifications',
            'keystone:shared-db': 'mysql:shared-db',
            'ceilometer:ceilometer-service': 'ceilometer-agent:'
                                             'ceilometer-service',
            'nova-compute:nova-ceilometer': 'ceilometer-agent:nova-ceilometer',
        }
        super(CeilometerBasicDeployment, self)._add_relations(relations)

    def _configure_services(self):
        """Configure all of the services."""
        keystone_config = {'admin-password': 'openstack',
                           'admin-token': 'ubuntutesting'}
        configs = {'keystone': keystone_config}
        super(CeilometerBasicDeployment, self)._configure_services(configs)

    def _get_token(self):
        return self.keystone.service_catalog.catalog['token']['id']

    def _initialize_tests(self):
        """Perform final initialization before tests get run."""
        # Access the sentries for inspecting service units
        self.ceil_sentry = self.d.sentry.unit['ceilometer/0']
        self.mysql_sentry = self.d.sentry.unit['mysql/0']
        self.keystone_sentry = self.d.sentry.unit['keystone/0']
        self.rabbitmq_sentry = self.d.sentry.unit['rabbitmq-server/0']
        self.mongodb_sentry = self.d.sentry.unit['mongodb/0']
        self.compute_sentry = self.d.sentry.unit['nova-compute/0']

        # Let things settle a bit before moving forward
        time.sleep(30)

        # Authenticate admin with keystone
        self.keystone = u.authenticate_keystone_admin(self.keystone_sentry,
                                                      user='admin',
                                                      password='openstack',
                                                      tenant='admin')

        # Authenticate admin with neutron
        ep = self.keystone.service_catalog.url_for(service_type='metering',
                                                   endpoint_type='publicURL')
        self.ceil = ceilclient.Client(endpoint=ep, token=self._get_token)

    def test_api_connection(self):
        """Simple api call to check service is up and responding"""
        assert(self.ceil.meters.list() == [])

    def test_services(self):
        """Verify the expected services are running on the corresponding
           service units."""
        ceilometer_cmds = [
            'status ceilometer-agent-central',
            'status ceilometer-collector',
            'status ceilometer-api',
            'status ceilometer-alarm-evaluator',
            'status ceilometer-alarm-notifier',
            'status ceilometer-agent-notification',
        ]
        commands = {
            self.ceil_sentry: ceilometer_cmds,
            self.mysql_sentry: ['status mysql'],
            self.keystone_sentry: ['status keystone'],
            self.rabbitmq_sentry: ['service rabbitmq-server status'],
            self.mongodb_sentry: ['status mongodb'],
        }
        ret = u.validate_services(commands)
        if ret:
            amulet.raise_status(amulet.FAIL, msg=ret)

    def test_ceilometer_identity_relation(self):
        """Verify the ceilometer to keystone identity-service relation data"""
        unit = self.ceil_sentry
        relation = ['identity-service', 'keystone:identity-service']
        ceil_ip = unit.relation('identity-service',
                                'keystone:identity-service')['private-address']
        ceil_endpoint = "http://%s:8777" % (ceil_ip)

        expected = {
            'admin_url': ceil_endpoint,
            'internal_url': ceil_endpoint,
            'private-address': ceil_ip,
            'public_url': ceil_endpoint,
            'region': 'RegionOne',
            'requested_roles': 'ResellerAdmin',
            'service': 'ceilometer',
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('ceilometer identity-service', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_keystone_ceilometer_identity_relation(self):
        """Verify the keystone to ceilometer identity-service relation data"""
        unit = self.keystone_sentry
        relation = ['identity-service', 'ceilometer:identity-service']
        id_relation = unit.relation('identity-service',
                                    'ceilometer:identity-service')
        id_ip = id_relation['private-address']
        expected = {
            'admin_token': 'ubuntutesting',
            'auth_host': id_ip,
            'auth_port': "35357",
            'auth_protocol': 'http',
            'private-address': id_ip,
            'service_host': id_ip,
            'service_password': u.not_null,
            'service_port': "5000",
            'service_protocol': 'http',
            'service_tenant': 'services',
            'service_tenant_id': u.not_null,
            'service_username': 'ceilometer',
        }
        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('keystone identity-service', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_keystone_ceilometer_identity_notes_relation(self):
        """Verify ceilometer to keystone identity-notifications relation"""
        unit = self.keystone_sentry
        relation = ['identity-service', 'ceilometer:identity-notifications']
        expected = {
            'ceilometer-endpoint-changed': u.not_null,
        }
        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('keystone identity-notifications', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_ceilometer_amqp_relation(self):
        """Verify the ceilometer to rabbitmq-server amqp relation data"""
        unit = self.ceil_sentry
        relation = ['amqp', 'rabbitmq-server:amqp']
        expected = {
            'username': 'ceilometer',
            'private-address': u.valid_ip,
            'vhost': 'openstack'
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('ceilometer amqp', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_amqp_ceilometer_relation(self):
        """Verify the rabbitmq-server to ceilometer amqp relation data"""
        unit = self.rabbitmq_sentry
        relation = ['amqp', 'ceilometer:amqp']
        expected = {
            'hostname': u.valid_ip,
            'private-address': u.valid_ip,
            'password': u.not_null,
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('rabbitmq amqp', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_ceilometer_to_mongodb_relation(self):
        """Verify the ceilometer to mongodb relation data"""
        unit = self.ceil_sentry
        relation = ['shared-db', 'mongodb:database']
        expected = {
            'ceilometer_database': 'ceilometer',
            'private-address': u.valid_ip,
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('ceilometer shared-db', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_mongodb_to_ceilometer_relation(self):
        """Verify the mongodb to ceilometer relation data"""
        unit = self.mongodb_sentry
        relation = ['database', 'ceilometer:shared-db']
        expected = {
            'hostname': u.valid_ip,
            'port': '27017',
            'private-address': u.valid_ip,
            'replset': 'myset',
            'type': 'database',
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('mongodb database', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_z_restart_on_config_change(self):
        """Verify that the specified services are restarted when the config
           is changed.

           Note(coreycb): The method name with the _z_ is a little odd
           but it forces the test to run last.  It just makes things
           easier because restarting services requires re-authorization.
           """
        conf = '/etc/ceilometer/ceilometer.conf'
        self.d.configure('ceilometer', {'debug': 'True'})
        services = [
            'ceilometer-agent-central',
            'ceilometer-collector',
            'ceilometer-api',
            'ceilometer-alarm-evaluator',
            'ceilometer-alarm-notifier',
            'ceilometer-agent-notification',
        ]

        time = 20
        for s in services:
            if not u.service_restarted(self.ceil_sentry, s, conf,
                                       pgrep_full=True, sleep_time=time):
                self.d.configure('ceilometer', {'debug': 'False'})
                msg = "service {} didn't restart after config change".format(s)
                amulet.raise_status(amulet.FAIL, msg=msg)
            time = 0

        self.d.configure('ceilometer', {'debug': 'False'})

    def test_ceilometer_config(self):
        """Verify the data in the ceilometer config file."""
        unit = self.ceil_sentry
        rabbitmq_relation = self.rabbitmq_sentry.relation('amqp',
                                                          'ceilometer:amqp')
        ks_rel = self.keystone_sentry.relation('identity-service',
                                               'ceilometer:identity-service')
        auth_uri = '%s://%s:%s/' % (ks_rel['service_protocol'],
                                    ks_rel['service_host'],
                                    ks_rel['service_port'])
        db_relation = self.mongodb_sentry.relation('database',
                                                   'ceilometer:shared-db')
        db_conn = 'mongodb://%s:%s/ceilometer' % (db_relation['hostname'],
                                                  db_relation['port'])
        conf = '/etc/ceilometer/ceilometer.conf'
        expected = {
            'DEFAULT': {
                'verbose': 'False',
                'debug': 'False',
                'use_syslog': 'False',
                'rabbit_userid': 'ceilometer',
                'rabbit_virtual_host': 'openstack',
                'rabbit_password': rabbitmq_relation['password'],
                'rabbit_host': rabbitmq_relation['hostname'],
            },
            'api': {
                'port': '8767',
            },
            'service_credentials': {
                'os_auth_url': auth_uri + 'v2.0',
                'os_tenant_name': 'services',
                'os_username': 'ceilometer',
                'os_password': ks_rel['service_password'],
            },
            'database': {
                'connection': db_conn,
            },
            'keystone_authtoken': {
                'auth_uri': auth_uri,
                'auth_host': ks_rel['auth_host'],
                'auth_port': ks_rel['auth_port'],
                'auth_protocol':  ks_rel['auth_protocol'],
                'admin_tenant_name': 'services',
                'admin_user': 'ceilometer',
                'admin_password': ks_rel['service_password'],
            },
        }

        for section, pairs in expected.iteritems():
            ret = u.validate_config_data(unit, conf, section, pairs)
            if ret:
                message = "ceilometer config error: {}".format(ret)
                amulet.raise_status(amulet.FAIL, msg=message)
