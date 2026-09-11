# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.trilio.trilio_openstack.plugins.modules.workload import run_module


class TestWorkloadModule(unittest.TestCase):

    def setUp(self):
        self.mock_workload = {
            'id': 'wl-uuid-1',
            'name': 'web-tier-backup',
            'description': 'Daily backup of web tier',
            'status': 'available',
            'instances': [{'id': 'vm-1'}, {'id': 'vm-2'}],
            'workload_type_id': 'type-parallel-uuid',
            'backup_target_types': 'btt-uuid-1',
            'jobschedule': {
                'enabled': True,
                'interval': '24 hr',
                'start_time': '02:00 AM',
                'timezone': 'UTC'
            },
            'metadata': {'env': 'prod'}
        }

    def test_workload_create_new(self):
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'name': 'web-tier-backup',
            'workload_id': None,
            'description': 'Daily backup of web tier',
            'workload_type': 'Parallel',
            'instances': ['vm-1', 'vm-2'],
            'backup_target_type': 'primary-nfs-target',
            'jobschedule': {'enabled': True, 'interval': '24 hr'},
            'metadata': {'env': 'prod'},
            'source_platform': 'openstack',
            'project_id': 'proj-123'
        }

        mock_client = MagicMock()
        mock_client.get_workload_by_name.return_value = None
        mock_client.find_backup_target_type.return_value = {'id': 'btt-uuid-1', 'name': 'primary-nfs-target'}
        mock_client.list_workload_types.return_value = [{'id': 'type-parallel-uuid', 'name': 'Parallel'}]
        mock_client.create_workload.return_value = self.mock_workload

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.create_workload.assert_called_once_with(
                    name='web-tier-backup',
                    instances=['vm-1', 'vm-2'],
                    workload_type_id='type-parallel-uuid',
                    description='Daily backup of web tier',
                    backup_target_types='btt-uuid-1',
                    jobschedule={'enabled': True, 'interval': '24 hr'},
                    metadata={'env': 'prod'},
                    source_platform='openstack',
                    project_id='proj-123'
                )
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(call_kwargs['changed'])
                self.assertEqual(call_kwargs['workload']['id'], 'wl-uuid-1')

    def test_workload_idempotent_no_changes(self):
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'name': 'web-tier-backup',
            'workload_id': None,
            'description': 'Daily backup of web tier',
            'workload_type': None,
            'instances': ['vm-1', 'vm-2'],
            'backup_target_type': None,
            'jobschedule': {
                'enabled': True,
                'interval': '24 hr',
                'start_time': '02:00 AM',
                'timezone': 'UTC'
            },
            'metadata': {'env': 'prod'},
            'source_platform': 'openstack',
            'project_id': 'proj-123'
        }

        mock_client = MagicMock()
        mock_client.get_workload_by_name.return_value = dict(self.mock_workload)

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.create_workload.assert_not_called()
                mock_client.update_workload.assert_not_called()
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertFalse(call_kwargs['changed'])

    def test_workload_update_instances(self):
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'name': 'web-tier-backup',
            'workload_id': None,
            'description': 'Daily backup of web tier',
            'workload_type': None,
            'instances': ['vm-1', 'vm-2', 'vm-3'],
            'backup_target_type': None,
            'jobschedule': None,
            'metadata': None,
            'source_platform': 'openstack',
            'project_id': 'proj-123'
        }

        mock_client = MagicMock()
        mock_client.get_workload_by_name.return_value = dict(self.mock_workload)
        updated_wl = dict(self.mock_workload)
        updated_wl['instances'] = [{'id': 'vm-1'}, {'id': 'vm-2'}, {'id': 'vm-3'}]
        mock_client.update_workload.return_value = updated_wl

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.update_workload.assert_called_once()
                call_args = mock_client.update_workload.call_args
                self.assertEqual(call_args[0][0], 'wl-uuid-1')
                self.assertEqual(set(call_args[1]['instances']), {'vm-1', 'vm-2', 'vm-3'})
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(call_kwargs['changed'])

    def test_workload_delete_absent(self):
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'absent',
            'name': 'web-tier-backup',
            'workload_id': 'wl-uuid-1',
            'description': None,
            'workload_type': None,
            'instances': [],
            'backup_target_type': None,
            'jobschedule': None,
            'metadata': None,
            'source_platform': 'openstack',
            'project_id': 'proj-123'
        }

        mock_client = MagicMock()
        mock_client.get_workload.return_value = self.mock_workload

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.delete_workload.assert_called_once_with('wl-uuid-1', project_id='proj-123')
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(call_kwargs['changed'])


if __name__ == '__main__':
    unittest.main()
