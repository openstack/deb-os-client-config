# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import copy

from keystoneauth1 import plugin as ksa_plugin
from keystoneauth1 import session as ksa_session
import mock

from os_client_config import cloud_config
from os_client_config import defaults
from os_client_config import exceptions
from os_client_config.tests import base


fake_config_dict = {'a': 1, 'os_b': 2, 'c': 3, 'os_c': 4}
fake_services_dict = {
    'compute_api_version': '2',
    'compute_endpoint': 'http://compute.example.com',
    'compute_region_name': 'region-bl',
    'interface': 'public',
    'image_service_type': 'mage',
    'identity_interface': 'admin',
    'identity_service_name': 'locks',
    'volume_api_version': '1',
    'auth': {'password': 'hunter2', 'username': 'AzureDiamond'},
}


class TestCloudConfig(base.TestCase):

    def test_arbitrary_attributes(self):
        cc = cloud_config.CloudConfig("test1", "region-al", fake_config_dict)
        self.assertEqual("test1", cc.name)
        self.assertEqual("region-al", cc.region)

        # Look up straight value
        self.assertEqual(1, cc.a)

        # Look up prefixed attribute, fail - returns None
        self.assertEqual(None, cc.os_b)

        # Look up straight value, then prefixed value
        self.assertEqual(3, cc.c)
        self.assertEqual(3, cc.os_c)

        # Lookup mystery attribute
        self.assertIsNone(cc.x)

        # Test default ipv6
        self.assertFalse(cc.force_ipv4)

    def test_iteration(self):
        cc = cloud_config.CloudConfig("test1", "region-al", fake_config_dict)
        self.assertTrue('a' in cc)
        self.assertFalse('x' in cc)

    def test_equality(self):
        cc1 = cloud_config.CloudConfig("test1", "region-al", fake_config_dict)
        cc2 = cloud_config.CloudConfig("test1", "region-al", fake_config_dict)
        self.assertEqual(cc1, cc2)

    def test_inequality(self):
        cc1 = cloud_config.CloudConfig("test1", "region-al", fake_config_dict)

        cc2 = cloud_config.CloudConfig("test2", "region-al", fake_config_dict)
        self.assertNotEqual(cc1, cc2)

        cc2 = cloud_config.CloudConfig("test1", "region-xx", fake_config_dict)
        self.assertNotEqual(cc1, cc2)

        cc2 = cloud_config.CloudConfig("test1", "region-al", {})
        self.assertNotEqual(cc1, cc2)

    def test_verify(self):
        config_dict = copy.deepcopy(fake_config_dict)
        config_dict['cacert'] = None

        config_dict['verify'] = False
        cc = cloud_config.CloudConfig("test1", "region-xx", config_dict)
        (verify, cert) = cc.get_requests_verify_args()
        self.assertFalse(verify)

        config_dict['verify'] = True
        cc = cloud_config.CloudConfig("test1", "region-xx", config_dict)
        (verify, cert) = cc.get_requests_verify_args()
        self.assertTrue(verify)

    def test_verify_cacert(self):
        config_dict = copy.deepcopy(fake_config_dict)
        config_dict['cacert'] = "certfile"

        config_dict['verify'] = False
        cc = cloud_config.CloudConfig("test1", "region-xx", config_dict)
        (verify, cert) = cc.get_requests_verify_args()
        self.assertFalse(verify)

        config_dict['verify'] = True
        cc = cloud_config.CloudConfig("test1", "region-xx", config_dict)
        (verify, cert) = cc.get_requests_verify_args()
        self.assertEqual("certfile", verify)

    def test_cert_with_key(self):
        config_dict = copy.deepcopy(fake_config_dict)
        config_dict['cacert'] = None
        config_dict['verify'] = False

        config_dict['cert'] = 'cert'
        config_dict['key'] = 'key'

        cc = cloud_config.CloudConfig("test1", "region-xx", config_dict)
        (verify, cert) = cc.get_requests_verify_args()
        self.assertEqual(("cert", "key"), cert)

    def test_ipv6(self):
        cc = cloud_config.CloudConfig(
            "test1", "region-al", fake_config_dict, force_ipv4=True)
        self.assertTrue(cc.force_ipv4)

    def test_getters(self):
        cc = cloud_config.CloudConfig("test1", "region-al", fake_services_dict)

        self.assertEqual(['compute', 'identity', 'image', 'volume'],
                         sorted(cc.get_services()))
        self.assertEqual({'password': 'hunter2', 'username': 'AzureDiamond'},
                         cc.get_auth_args())
        self.assertEqual('public', cc.get_interface())
        self.assertEqual('public', cc.get_interface('compute'))
        self.assertEqual('admin', cc.get_interface('identity'))
        self.assertEqual('region-al', cc.get_region_name())
        self.assertEqual('region-al', cc.get_region_name('image'))
        self.assertEqual('region-bl', cc.get_region_name('compute'))
        self.assertEqual(None, cc.get_api_version('image'))
        self.assertEqual('2', cc.get_api_version('compute'))
        self.assertEqual('mage', cc.get_service_type('image'))
        self.assertEqual('compute', cc.get_service_type('compute'))
        self.assertEqual('1', cc.get_api_version('volume'))
        self.assertEqual('volume', cc.get_service_type('volume'))
        self.assertEqual('http://compute.example.com',
                         cc.get_endpoint('compute'))
        self.assertEqual(None,
                         cc.get_endpoint('image'))
        self.assertEqual(None, cc.get_service_name('compute'))
        self.assertEqual('locks', cc.get_service_name('identity'))

    def test_volume_override(self):
        cc = cloud_config.CloudConfig("test1", "region-al", fake_services_dict)
        cc.config['volume_api_version'] = '2'
        self.assertEqual('volumev2', cc.get_service_type('volume'))

    def test_get_session_no_auth(self):
        config_dict = defaults.get_defaults()
        config_dict.update(fake_services_dict)
        cc = cloud_config.CloudConfig("test1", "region-al", config_dict)
        self.assertRaises(
            exceptions.OpenStackConfigException,
            cc.get_session)

    @mock.patch.object(ksa_session, 'Session')
    def test_get_session(self, mock_session):
        config_dict = defaults.get_defaults()
        config_dict.update(fake_services_dict)
        cc = cloud_config.CloudConfig(
            "test1", "region-al", config_dict, auth_plugin=mock.Mock())
        cc.get_session()
        mock_session.assert_called_with(
            auth=mock.ANY,
            verify=True, cert=None, timeout=None)

    @mock.patch.object(ksa_session, 'Session')
    def test_get_session_with_timeout(self, mock_session):
        config_dict = defaults.get_defaults()
        config_dict.update(fake_services_dict)
        config_dict['api_timeout'] = 9
        cc = cloud_config.CloudConfig(
            "test1", "region-al", config_dict, auth_plugin=mock.Mock())
        cc.get_session()
        mock_session.assert_called_with(
            auth=mock.ANY,
            verify=True, cert=None, timeout=9)

    @mock.patch.object(ksa_session, 'Session')
    def test_override_session_endpoint(self, mock_session):
        config_dict = defaults.get_defaults()
        config_dict.update(fake_services_dict)
        cc = cloud_config.CloudConfig(
            "test1", "region-al", config_dict, auth_plugin=mock.Mock())
        self.assertEqual(
            cc.get_session_endpoint('compute'),
            fake_services_dict['compute_endpoint'])

    @mock.patch.object(cloud_config.CloudConfig, 'get_session')
    def test_session_endpoint_identity(self, mock_get_session):
        mock_session = mock.Mock()
        mock_get_session.return_value = mock_session
        config_dict = defaults.get_defaults()
        config_dict.update(fake_services_dict)
        cc = cloud_config.CloudConfig(
            "test1", "region-al", config_dict, auth_plugin=mock.Mock())
        cc.get_session_endpoint('identity')
        mock_session.get_endpoint.assert_called_with(
            interface=ksa_plugin.AUTH_INTERFACE)

    @mock.patch.object(cloud_config.CloudConfig, 'get_session')
    def test_session_endpoint(self, mock_get_session):
        mock_session = mock.Mock()
        mock_get_session.return_value = mock_session
        config_dict = defaults.get_defaults()
        config_dict.update(fake_services_dict)
        cc = cloud_config.CloudConfig(
            "test1", "region-al", config_dict, auth_plugin=mock.Mock())
        cc.get_session_endpoint('orchestration')
        mock_session.get_endpoint.assert_called_with(
            interface='public',
            service_name=None,
            region_name='region-al',
            service_type='orchestration')

    @mock.patch.object(cloud_config.CloudConfig, 'get_session_endpoint')
    def test_legacy_client_object_store(self, mock_get_session_endpoint):
        mock_client = mock.Mock()
        mock_get_session_endpoint.return_value = 'http://example.com/v2'
        config_dict = defaults.get_defaults()
        config_dict.update(fake_services_dict)
        cc = cloud_config.CloudConfig(
            "test1", "region-al", config_dict, auth_plugin=mock.Mock())
        cc.get_legacy_client('object-store', mock_client)
        mock_client.assert_called_with(
            preauthtoken=mock.ANY,
            os_options={
                'auth_token': mock.ANY,
                'region_name': 'region-al',
                'object_storage_url': 'http://example.com/v2'
            },
            preauthurl='http://example.com/v2',
            auth_version='2.0')

    @mock.patch.object(cloud_config.CloudConfig, 'get_session_endpoint')
    def test_legacy_client_object_store_timeout(
            self, mock_get_session_endpoint):
        mock_client = mock.Mock()
        mock_get_session_endpoint.return_value = 'http://example.com/v2'
        config_dict = defaults.get_defaults()
        config_dict.update(fake_services_dict)
        config_dict['api_timeout'] = 9
        cc = cloud_config.CloudConfig(
            "test1", "region-al", config_dict, auth_plugin=mock.Mock())
        cc.get_legacy_client('object-store', mock_client)
        mock_client.assert_called_with(
            preauthtoken=mock.ANY,
            os_options={
                'auth_token': mock.ANY,
                'region_name': 'region-al',
                'object_storage_url': 'http://example.com/v2'
            },
            preauthurl='http://example.com/v2',
            auth_version='2.0',
            timeout=9.0)

    def test_legacy_client_object_store_endpoint(self):
        mock_client = mock.Mock()
        config_dict = defaults.get_defaults()
        config_dict.update(fake_services_dict)
        config_dict['object_store_endpoint'] = 'http://example.com/v2'
        cc = cloud_config.CloudConfig(
            "test1", "region-al", config_dict, auth_plugin=mock.Mock())
        cc.get_legacy_client('object-store', mock_client)
        mock_client.assert_called_with(
            preauthtoken=mock.ANY,
            os_options={
                'auth_token': mock.ANY,
                'region_name': 'region-al',
                'object_storage_url': 'http://example.com/v2'
            },
            preauthurl='http://example.com/v2',
            auth_version='2.0')

    @mock.patch.object(cloud_config.CloudConfig, 'get_session_endpoint')
    def test_legacy_client_image(self, mock_get_session_endpoint):
        mock_client = mock.Mock()
        mock_get_session_endpoint.return_value = 'http://example.com/v2'
        config_dict = defaults.get_defaults()
        config_dict.update(fake_services_dict)
        cc = cloud_config.CloudConfig(
            "test1", "region-al", config_dict, auth_plugin=mock.Mock())
        cc.get_legacy_client('image', mock_client)
        mock_client.assert_called_with(
            '2',
            service_name=None,
            endpoint='http://example.com',
            region_name='region-al',
            interface='public',
            session=mock.ANY,
            # Not a typo - the config dict above overrides this
            service_type='mage'
        )

    @mock.patch.object(cloud_config.CloudConfig, 'get_session_endpoint')
    def test_legacy_client_network(self, mock_get_session_endpoint):
        mock_client = mock.Mock()
        mock_get_session_endpoint.return_value = 'http://example.com/v2'
        config_dict = defaults.get_defaults()
        config_dict.update(fake_services_dict)
        cc = cloud_config.CloudConfig(
            "test1", "region-al", config_dict, auth_plugin=mock.Mock())
        cc.get_legacy_client('network', mock_client)
        mock_client.assert_called_with(
            '2.0',
            endpoint_type='public',
            region_name='region-al',
            service_type='network',
            session=mock.ANY,
            service_name=None)

    @mock.patch.object(cloud_config.CloudConfig, 'get_session_endpoint')
    def test_legacy_client_compute(self, mock_get_session_endpoint):
        mock_client = mock.Mock()
        mock_get_session_endpoint.return_value = 'http://example.com/v2'
        config_dict = defaults.get_defaults()
        config_dict.update(fake_services_dict)
        cc = cloud_config.CloudConfig(
            "test1", "region-al", config_dict, auth_plugin=mock.Mock())
        cc.get_legacy_client('compute', mock_client)
        mock_client.assert_called_with(
            '2',
            endpoint_type='public',
            region_name='region-al',
            service_type='compute',
            session=mock.ANY,
            service_name=None)

    @mock.patch.object(cloud_config.CloudConfig, 'get_session_endpoint')
    def test_legacy_client_identity(self, mock_get_session_endpoint):
        mock_client = mock.Mock()
        mock_get_session_endpoint.return_value = 'http://example.com/v2'
        config_dict = defaults.get_defaults()
        config_dict.update(fake_services_dict)
        cc = cloud_config.CloudConfig(
            "test1", "region-al", config_dict, auth_plugin=mock.Mock())
        cc.get_legacy_client('identity', mock_client)
        mock_client.assert_called_with(
            '2.0',
            endpoint='http://example.com/v2',
            endpoint_type='admin',
            region_name='region-al',
            service_type='identity',
            session=mock.ANY,
            service_name='locks')

    @mock.patch.object(cloud_config.CloudConfig, 'get_session_endpoint')
    def test_legacy_client_identity_v3(self, mock_get_session_endpoint):
        mock_client = mock.Mock()
        mock_get_session_endpoint.return_value = 'http://example.com'
        config_dict = defaults.get_defaults()
        config_dict.update(fake_services_dict)
        config_dict['identity_api_version'] = '3'
        cc = cloud_config.CloudConfig(
            "test1", "region-al", config_dict, auth_plugin=mock.Mock())
        cc.get_legacy_client('identity', mock_client)
        mock_client.assert_called_with(
            '3',
            endpoint='http://example.com',
            endpoint_type='admin',
            region_name='region-al',
            service_type='identity',
            session=mock.ANY,
            service_name='locks')
