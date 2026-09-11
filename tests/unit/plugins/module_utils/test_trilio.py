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
        self.assertIn('verify', spec['validate_certs']['aliases'])

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

    def test_resolve_endpoint_triliovaultwlm_catalog(self):
        module = MagicMock()
        module.params = {
            'trilio_endpoint': None,
            'interface': 'public',
            'validate_certs': True,
            'timeout': 30
        }
        with patch.object(TrilioClient, '_authenticate', return_value=None):
            client = TrilioClient(module)
            client.project_id = None
            client._catalog = [
                {
                    'type': 'workloads',
                    'name': 'TrilioVaultWLM',
                    'endpoints': [
                        {'interface': 'admin', 'region': 'regionOne', 'url': 'http://172.22.5.22:8781/v1/3f366be9754044209cf669d62f402bfc'},
                        {'interface': 'internal', 'region': 'regionOne', 'url': 'http://172.22.5.22:8781/v1/3f366be9754044209cf669d62f402bfc'},
                        {'interface': 'public', 'region': 'regionOne', 'url': 'http://172.22.5.22:8781/v1/3f366be9754044209cf669d62f402bfc'}
                    ]
                }
            ]
            client._resolve_endpoint()
            self.assertEqual(client.endpoint, 'http://172.22.5.22:8781/v1/3f366be9754044209cf669d62f402bfc')
            self.assertEqual(client.project_id, '3f366be9754044209cf669d62f402bfc')

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

    def test_list_workloads_s3_filter(self):
        module = MagicMock()
        module.params = {'trilio_endpoint': 'http://trilio:8780', 'validate_certs': True, 'timeout': 30}
        mock_workloads = [
            {'id': 'wl-1', 'name': 'nfs-backup', 'storage_url': '192.168.1.10:/backups'},
            {'id': 'wl-2', 'name': 's3-backup', 'storage_url': 's3://company-openstack-backups'}
        ]
        with patch.object(TrilioClient, '_authenticate', return_value=None):
            client = TrilioClient(module)
            client.endpoint = 'http://trilio:8780'
            client.project_id = 'proj-123'

            with patch.object(client, 'get', return_value={'workloads': mock_workloads}):
                res = client.list_workloads(s3_bucket='company-openstack-backups')
                self.assertEqual(len(res), 1)
                self.assertEqual(res[0]['id'], 'wl-2')
                self.assertEqual(res[0]['name'], 's3-backup')

    def test_base_endpoint(self):
        module = MagicMock()
        module.params = {'trilio_endpoint': 'http://tvm.internal:8780/v1/3f366be9754044209cf669d62f402bfc', 'validate_certs': True, 'timeout': 30}
        with patch.object(TrilioClient, '_authenticate', return_value=None):
            client = TrilioClient(module)
            client.endpoint = 'http://tvm.internal:8780/v1/3f366be9754044209cf669d62f402bfc'
            self.assertEqual(client.base_endpoint, 'http://tvm.internal:8780')

    def test_validate_dms_support_success(self):
        module = MagicMock()
        module.params = {'trilio_endpoint': 'http://tvm.internal:8780', 'validate_certs': True, 'timeout': 30}
        with patch.object(TrilioClient, '_authenticate', return_value=None):
            client = TrilioClient(module)
            with patch.object(client, 'dms_request', return_value={'backup_targets': []}):
                self.assertTrue(client.validate_dms_support())

    def test_validate_dms_support_failure(self):
        module = MagicMock()
        module.params = {'trilio_endpoint': 'http://tvm.internal:8780', 'validate_certs': True, 'timeout': 30}
        with patch.object(TrilioClient, '_authenticate', return_value=None):
            client = TrilioClient(module)
            with patch.object(client, 'dms_request', return_value=None):
                client.validate_dms_support()
                module.fail_json.assert_called_once()
                call_kwargs = module.fail_json.call_args[1]
                self.assertIn("Trilio 6.2 or newer is required", call_kwargs['msg'])

    def test_create_backup_target_nfs(self):
        module = MagicMock()
        module.params = {'trilio_endpoint': 'http://tvm.internal:8780', 'validate_certs': True, 'timeout': 30}
        with patch.object(TrilioClient, '_authenticate', return_value=None):
            client = TrilioClient(module)
            mock_bt = {
                'id': 'bt-nfs-1',
                'type': 'nfs',
                'filesystem_export': '192.168.1.50:/var/nfs/backups',
                'status': 'online',
                'btt_name': 'nfs-btt'
            }
            with patch.object(client, 'dms_request', return_value={'backup_target': mock_bt}) as mock_dms:
                res = client.create_backup_target(
                    target_type='nfs',
                    filesystem_export='192.168.1.50:/var/nfs/backups',
                    nfs_mount_opts='nolock,soft',
                    btt_name='nfs-btt',
                    is_default=1
                )
                self.assertEqual(res['id'], 'bt-nfs-1')
                mock_dms.assert_called_once_with('POST', '/backup_targets', json_data={
                    'backup_target': {
                        'type': 'nfs',
                        'is_default': 1,
                        'btt_name': 'nfs-btt',
                        'filesystem_export': '192.168.1.50:/var/nfs/backups',
                        'nfs_mount_opts': 'nolock,soft'
                    }
                })

    def test_create_backup_target_s3_with_barbican_secret(self):
        module = MagicMock()
        module.params = {'trilio_endpoint': 'http://tvm.internal:8780', 'validate_certs': True, 'timeout': 30}
        with patch.object(TrilioClient, '_authenticate', return_value=None):
            client = TrilioClient(module)
            mock_bt = {
                'id': 'bt-s3-1',
                'type': 's3',
                's3_endpoint_url': 'https://s3.amazonaws.com',
                's3_bucket': 'prod-backups',
                'status': 'online'
            }
            with patch.object(client, 'dms_request', return_value={'backup_target': mock_bt}) as mock_dms:
                res = client.create_backup_target(
                    target_type='s3',
                    s3_endpoint_url='https://s3.amazonaws.com',
                    s3_bucket='prod-backups',
                    secret_ref='https://barbican:9311/v1/secrets/sec-123',
                    btt_name='s3-btt',
                    immutable=1
                )
                self.assertEqual(res['id'], 'bt-s3-1')
                mock_dms.assert_called_once_with('POST', '/backup_targets', json_data={
                    'backup_target': {
                        'type': 's3',
                        'is_default': 0,
                        'btt_name': 's3-btt',
                        's3_endpoint_url': 'https://s3.amazonaws.com',
                        's3_bucket': 'prod-backups',
                        'secret_ref': 'https://barbican:9311/v1/secrets/sec-123',
                        'immutable': 1
                    }
                })

    def test_create_workload(self):
        module = MagicMock()
        module.params = {'trilio_endpoint': 'http://tvm.internal:8780', 'validate_certs': True, 'timeout': 30}
        with patch.object(TrilioClient, '_authenticate', return_value=None):
            client = TrilioClient(module)
            client.endpoint = 'http://tvm.internal:8780'
            client.project_id = 'proj-123'
            mock_wl = {
                'id': 'wl-created-1',
                'name': 'web-tier-backup',
                'status': 'available'
            }
            with patch.object(client, 'list_workload_types', return_value=[{'id': 'type-parallel', 'name': 'Parallel'}]):
                with patch.object(client, 'post', return_value={'workload': mock_wl}) as mock_post:
                    res = client.create_workload(
                        name='web-tier-backup',
                        instances=['vm-uuid-1', {'id': 'vm-uuid-2'}],
                        description='Backup for web tier',
                        backup_target_types='btt-uuid-1',
                        jobschedule={'enabled': True, 'interval': '24 hr'}
                    )
                    self.assertEqual(res['id'], 'wl-created-1')
                    mock_post.assert_called_once_with('/v1/proj-123/workloads', json_data={
                        'workload': {
                            'name': 'web-tier-backup',
                            'workload_type_id': 'type-parallel',
                            'source_platform': 'openstack',
                            'instances': [{'instance-id': 'vm-uuid-1'}, {'instance-id': 'vm-uuid-2'}],
                            'description': 'Backup for web tier',
                            'backup_target_types': 'btt-uuid-1',
                            'jobschedule': {'enabled': True, 'interval': '24 hr'}
                        }
                    })


if __name__ == '__main__':
    unittest.main()

