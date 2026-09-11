# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.trilio.trilio_openstack.plugins.modules.workload_info import run_module


class TestWorkloadInfoModule(unittest.TestCase):

    def setUp(self):
        self.mock_workloads = [
            {
                'id': '7b47b4e8-8db9-4670-8b1e-0679815049cf',
                'name': 'production-web',
                'status': 'available',
                'project_id': 'proj-100',
                'storage_url': '192.168.10.50:/var/nfs/trilio',
                'backup_media_target': '192.168.10.50:/var/nfs/trilio',
                'backup_target_types': 'btt-nfs-1',
                'instances': [{'id': 'vm-1', 'name': 'web-1'}]
            },
            {
                'id': '8c58c5f9-9ea0-4781-9c2f-1780926150da',
                'name': 'production-db',
                'status': 'available',
                'project_id': 'proj-100',
                'storage_url': 's3://company-openstack-backups',
                'backup_media_target': 'company-openstack-backups',
                'backup_target_types': 'btt-s3-1',
                'instances': [{'id': 'vm-2', 'name': 'db-1'}]
            },
            {
                'id': '9d69d6a0-0fb1-4892-0d3a-2891037261eb',
                'name': 'staging-web',
                'status': 'available',
                'project_id': 'proj-100',
                'storage_url': 's3://staging-openstack-backups',
                'backup_media_target': 'staging-openstack-backups',
                'backup_target_types': 'btt-s3-staging',
                'instances': [{'id': 'vm-3', 'name': 'staging-1'}]
            }
        ]

    def test_workload_info_list_all(self):
        mock_ansible_module = MagicMock()
        mock_ansible_module.params = {
            'name': None,
            'workload_id': None,
            'all_projects': False,
            'project_id': None,
            'detailed': True,
            'nfs_share': None,
            's3_bucket': None,
            'backup_target': None,
            'backup_target_type': None
        }

        mock_client = MagicMock()
        mock_client.list_workloads.return_value = self.mock_workloads

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_info.AnsibleModule', return_value=mock_ansible_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_info.TrilioClient', return_value=mock_client):
                run_module()

                mock_ansible_module.exit_json.assert_called_once()
                call_kwargs = mock_ansible_module.exit_json.call_args[1]
                self.assertFalse(call_kwargs['changed'])
                self.assertEqual(len(call_kwargs['workloads']), 3)

    def test_workload_info_filter_by_name(self):
        mock_ansible_module = MagicMock()
        mock_ansible_module.params = {
            'name': 'production-*',
            'workload_id': None,
            'all_projects': False,
            'project_id': None,
            'detailed': True,
            'nfs_share': None,
            's3_bucket': None,
            'backup_target': None,
            'backup_target_type': None
        }

        mock_client = MagicMock()
        mock_client.list_workloads.return_value = self.mock_workloads

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_info.AnsibleModule', return_value=mock_ansible_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_info.TrilioClient', return_value=mock_client):
                run_module()

                mock_ansible_module.exit_json.assert_called_once()
                call_kwargs = mock_ansible_module.exit_json.call_args[1]
                workloads = call_kwargs['workloads']
                self.assertEqual(len(workloads), 2)
                self.assertTrue(all('production-' in w['name'] for w in workloads))

    def test_workload_info_filter_by_s3_bucket(self):
        mock_ansible_module = MagicMock()
        mock_ansible_module.params = {
            'name': None,
            'workload_id': None,
            'all_projects': False,
            'project_id': None,
            'detailed': True,
            'nfs_share': None,
            's3_bucket': 'company-openstack-backups',
            'backup_target': None,
            'backup_target_type': None
        }

        mock_client = MagicMock()
        mock_client.list_workloads.return_value = [self.mock_workloads[1]]

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_info.AnsibleModule', return_value=mock_ansible_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_info.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.list_workloads.assert_called_once_with(
                    project_id=None,
                    all_projects=False,
                    detailed=True,
                    nfs_share=None,
                    s3_bucket='company-openstack-backups',
                    backup_target=None,
                    backup_target_type=None
                )
                mock_ansible_module.exit_json.assert_called_once()
                call_kwargs = mock_ansible_module.exit_json.call_args[1]
                self.assertEqual(len(call_kwargs['workloads']), 1)
                self.assertEqual(call_kwargs['workloads'][0]['name'], 'production-db')

    def test_workload_info_filter_by_backup_target(self):
        mock_ansible_module = MagicMock()
        mock_ansible_module.params = {
            'name': None,
            'workload_id': None,
            'all_projects': False,
            'project_id': None,
            'detailed': True,
            'nfs_share': None,
            's3_bucket': None,
            'backup_target': '192.168.10.50:/var/nfs/trilio',
            'backup_target_type': None
        }

        mock_client = MagicMock()
        mock_client.list_workloads.return_value = [self.mock_workloads[0]]

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_info.AnsibleModule', return_value=mock_ansible_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_info.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.list_workloads.assert_called_once_with(
                    project_id=None,
                    all_projects=False,
                    detailed=True,
                    nfs_share=None,
                    s3_bucket=None,
                    backup_target='192.168.10.50:/var/nfs/trilio',
                    backup_target_type=None
                )
                mock_ansible_module.exit_json.assert_called_once()
                call_kwargs = mock_ansible_module.exit_json.call_args[1]
                self.assertEqual(len(call_kwargs['workloads']), 1)
                self.assertEqual(call_kwargs['workloads'][0]['id'], '7b47b4e8-8db9-4670-8b1e-0679815049cf')

    def test_workload_info_by_id(self):
        mock_ansible_module = MagicMock()
        mock_ansible_module.params = {
            'name': None,
            'workload_id': '7b47b4e8-8db9-4670-8b1e-0679815049cf',
            'all_projects': False,
            'project_id': None,
            'detailed': True,
            'nfs_share': None,
            's3_bucket': None,
            'backup_target': None,
            'backup_target_type': None
        }

        mock_client = MagicMock()
        mock_client.get_workload.return_value = self.mock_workloads[0]

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_info.AnsibleModule', return_value=mock_ansible_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_info.TrilioClient', return_value=mock_client):
                run_module()

                mock_ansible_module.exit_json.assert_called_once()
                call_kwargs = mock_ansible_module.exit_json.call_args[1]
                workloads = call_kwargs['workloads']
                self.assertEqual(len(workloads), 1)
                self.assertEqual(workloads[0]['id'], '7b47b4e8-8db9-4670-8b1e-0679815049cf')


if __name__ == '__main__':
    unittest.main()

