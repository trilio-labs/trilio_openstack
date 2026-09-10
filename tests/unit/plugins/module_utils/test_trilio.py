# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.trilio.trilio_openstack.plugins.module_utils.trilio import (
    trilio_argument_spec,
    TrilioClient
)


class TestTrilioModuleUtils(unittest.TestCase):

    def test_trilio_argument_spec(self):
        spec = trilio_argument_spec()
        self.assertIn('cloud', spec)
        self.assertIn('auth', spec)
        self.assertIn('auth_type', spec)
        self.assertIn('region_name', spec)
        self.assertIn('validate_certs', spec)
        self.assertIn('interface', spec)
        self.assertIn('trilio_endpoint', spec)
        self.assertEqual(spec['interface']['default'], 'public')
        self.assertTrue(spec['validate_certs']['default'])

    def test_format_endpoint(self):
        module = MagicMock()
        module.params = {
            'trilio_endpoint': 'http://192.168.1.10:8780/v1/%(project_id)s/',
            'validate_certs': True,
            'timeout': 30
        }

        with patch.object(TrilioClient, '_authenticate', return_value=None):
            client = TrilioClient(module)
            client.project_id = 'test-proj-uuid-123'
            formatted = client._format_endpoint('http://192.168.1.10:8780/v1/%(tenant_id)s/')
            self.assertEqual(formatted, 'http://192.168.1.10:8780/v1/test-proj-uuid-123')

    def test_resolve_endpoint_from_override(self):
        module = MagicMock()
        module.params = {
            'trilio_endpoint': 'http://trilio.internal:8780/v1/proj-123',
            'validate_certs': True,
            'timeout': 30
        }
        with patch.object(TrilioClient, '_authenticate', return_value=None):
            client = TrilioClient(module)
            client._resolve_endpoint()
            self.assertEqual(client.endpoint, 'http://trilio.internal:8780/v1/proj-123')

    def test_resolve_endpoint_from_catalog(self):
        module = MagicMock()
        module.params = {
            'trilio_endpoint': None,
            'interface': 'public',
            'validate_certs': True,
            'timeout': 30
        }
        with patch.object(TrilioClient, '_authenticate', return_value=None):
            client = TrilioClient(module)
            client.project_id = 'proj-999'
            client._catalog = [
                {
                    'type': 'compute',
                    'name': 'nova',
                    'endpoints': [{'interface': 'public', 'url': 'http://nova:8774/v2.1'}]
                },
                {
                    'type': 'workloads',
                    'name': 'workloadmgr',
                    'endpoints': [
                        {'interface': 'internal', 'url': 'http://trilio-internal:8780/v1/%(tenant_id)s'},
                        {'interface': 'public', 'url': 'http://trilio-public:8780/v1/%(project_id)s'}
                    ]
                }
            ]
            client._resolve_endpoint()
            self.assertEqual(client.endpoint, 'http://trilio-public:8780/v1/proj-999')

    def test_list_workloads_request(self):
        module = MagicMock()
        module.params = {
            'trilio_endpoint': 'http://trilio:8780',
            'validate_certs': True,
            'timeout': 30
        }
        mock_workloads = [
            {'id': 'wl-1', 'name': 'prod-backup', 'status': 'available'},
            {'id': 'wl-2', 'name': 'dev-backup', 'status': 'available'}
        ]

        with patch.object(TrilioClient, '_authenticate', return_value=None):
            client = TrilioClient(module)
            client.endpoint = 'http://trilio:8780'
            client.project_id = 'proj-123'

            with patch.object(client, 'get', return_value={'workloads': mock_workloads}) as mock_get:
                res = client.list_workloads(detailed=True)
                self.assertEqual(len(res), 2)
                mock_get.assert_called_once_with('/v1/proj-123/workloads/detail', params={})


if __name__ == '__main__':
    unittest.main()
