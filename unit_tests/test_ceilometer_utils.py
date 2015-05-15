from mock import patch, call, MagicMock

import ceilometer_utils as utils

from test_utils import CharmTestCase

TO_PATCH = [
    'get_os_codename_package',
    'get_os_codename_install_source',
    'configure_installation_source',
    'templating',
    'LoggingConfigContext',
    'MongoDBContext',
    'CeilometerContext',
    'config',
    'log',
    'apt_install',
    'apt_update',
    'apt_upgrade',
]


class CeilometerUtilsTest(CharmTestCase):

    def setUp(self):
        super(CeilometerUtilsTest, self).setUp(utils, TO_PATCH)
        self.config.side_effect = self.test_config.get

    def tearDown(self):
        super(CeilometerUtilsTest, self).tearDown()

    def test_register_configs(self):
        configs = utils.register_configs()
        calls = []
        for conf in utils.CONFIG_FILES:
            calls.append(call(conf,
                              utils.CONFIG_FILES[conf]['hook_contexts']))
        configs.register.assert_has_calls(calls, any_order=True)

    def test_restart_map(self):
        restart_map = utils.restart_map()
        self.assertEquals(
            restart_map,
            {'/etc/ceilometer/ceilometer.conf': [
                'ceilometer-agent-central',
                'ceilometer-collector',
                'ceilometer-api',
                'ceilometer-alarm-evaluator',
                'ceilometer-alarm-notifier',
                'ceilometer-agent-notification'],
             '/etc/haproxy/haproxy.cfg': ['haproxy'],
             "/etc/apache2/sites-available/openstack_https_frontend": [
                 'apache2'],
             "/etc/apache2/sites-available/openstack_https_frontend.conf": [
                 'apache2']
             }
        )

    def test_get_ceilometer_conf(self):
        class TestContext():

            def __call__(self):
                return {'data': 'test'}
        with patch.dict(utils.CONFIG_FILES,
                        {'/etc/ceilometer/ceilometer.conf': {
                            'hook_contexts': [TestContext()]
                        }}):
            self.assertTrue(utils.get_ceilometer_context(),
                            {'data': 'test'})

    def test_do_openstack_upgrade(self):
        self.config.side_effect = self.test_config.get
        self.test_config.set('openstack-origin', 'cloud:precise-havana')
        self.get_os_codename_install_source.return_value = 'havana'
        configs = MagicMock()
        utils.do_openstack_upgrade(configs)
        configs.set_release.assert_called_with(openstack_release='havana')
        self.log.assert_called()
        self.apt_update.assert_called_with(fatal=True)
        dpkg_opts = [
            '--option', 'Dpkg::Options::=--force-confnew',
            '--option', 'Dpkg::Options::=--force-confdef',
        ]
        self.apt_install.assert_called_with(
            packages=utils.CEILOMETER_PACKAGES,
            options=dpkg_opts, fatal=True
        )
        self.configure_installation_source.assert_called_with(
            'cloud:precise-havana'
        )

    def test_get_packages(self):
        self.get_os_codename_install_source.return_value = 'havana'
        self.assertEqual(utils.get_packages(),
                         utils.CEILOMETER_PACKAGES)

    def test_get_packages_icehouse(self):
        self.get_os_codename_install_source.return_value = 'icehouse'
        self.assertEqual(utils.get_packages(),
                         utils.CEILOMETER_PACKAGES + utils.ICEHOUSE_PACKAGES)
