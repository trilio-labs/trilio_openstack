# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot import run_module


class TestWorkloadSnapshotModule(unittest.TestCase):

    def setUp(self):
        self.mock_workload = {
            'id': '7b47b4e8-8db9-4670-8b1e-0679815049cf',
            'name': 'production-web-cluster',
            'status': 'available'
        }
        self.mock_snapshot_incremental = {
            'id': 'snap-inc-uuid-1',
            'name': 'production-web-cluster - Incremental Backup',
            'description': 'On-demand incremental backup',
            'workload_id': '7b47b4e8-8db9-4670-8b1e-0679815049cf',
            'snapshot_type': 'incremental',
            'status': 'executing'
        }
        self.mock_snapshot_full = {
            'id': 'snap-full-uuid-2',
            'name': 'Pre-Upgrade Full Backup',
            'description': 'Full baseline backup',
            'workload_id': '7b47b4e8-8db9-4670-8b1e-0679815049cf',
            'snapshot_type': 'full',
            'status': 'available'
        }

    def test_incremental_backup_by_name_default(self):
        """Test creating an incremental backup by workload name (default behavior)."""
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'workload': 'production-web-cluster',
            'workload_name': None,
            'snapshot_id': None,
            'snapshot_type': 'incremental',
            'full': None,
            'name': None,
            'description': 'On-demand incremental backup',
            'wait': False,
            'timeout': 600,
            'poll_interval': 10,
            'project_id': 'proj-123'
        }

        mock_client = MagicMock()
        mock_client.get_workload_by_name.return_value = self.mock_workload
        mock_client.create_snapshot.return_value = self.mock_snapshot_incremental

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.get_workload_by_name.assert_called_once_with('production-web-cluster', project_id='proj-123')
                mock_client.create_snapshot.assert_called_once_with(
                    workload_id='7b47b4e8-8db9-4670-8b1e-0679815049cf',
                    name='production-web-cluster - Incremental Backup',
                    description='On-demand incremental backup',
                    full=False,
                    project_id='proj-123'
                )
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(call_kwargs['changed'])
                self.assertEqual(call_kwargs['snapshot']['snapshot_type'], 'incremental')
                self.assertEqual(call_kwargs['snapshot']['id'], 'snap-inc-uuid-1')

    def test_full_backup_by_uuid_with_wait(self):
        """Test creating a full backup by workload UUID and waiting for completion."""
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'workload': '7b47b4e8-8db9-4670-8b1e-0679815049cf',
            'workload_name': None,
            'snapshot_id': None,
            'snapshot_type': 'full',
            'full': None,
            'name': 'Pre-Upgrade Full Backup',
            'description': 'Full baseline backup',
            'wait': True,
            'timeout': 1200,
            'poll_interval': 15,
            'project_id': None
        }

        mock_client = MagicMock()
        mock_client.get_workload.return_value = self.mock_workload
        mock_client.create_snapshot.return_value = dict(self.mock_snapshot_full, status='executing')
        mock_client.wait_for_snapshot.return_value = self.mock_snapshot_full

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.get_workload.assert_called_once_with('7b47b4e8-8db9-4670-8b1e-0679815049cf', project_id=None)
                mock_client.create_snapshot.assert_called_once_with(
                    workload_id='7b47b4e8-8db9-4670-8b1e-0679815049cf',
                    name='Pre-Upgrade Full Backup',
                    description='Full baseline backup',
                    full=True,
                    project_id=None
                )
                mock_client.wait_for_snapshot.assert_called_once_with(
                    snapshot_id='snap-full-uuid-2',
                    target_status='available',
                    timeout=1200,
                    poll_interval=15,
                    project_id=None
                )
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(call_kwargs['changed'])
                self.assertEqual(call_kwargs['snapshot']['status'], 'available')

    def test_full_boolean_flag_override(self):
        """Test that full: true overrides snapshot_type: incremental."""
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'workload': '7b47b4e8-8db9-4670-8b1e-0679815049cf',
            'workload_name': None,
            'snapshot_id': None,
            'snapshot_type': 'incremental',
            'full': True,
            'name': 'Override Full',
            'description': None,
            'wait': False,
            'timeout': 600,
            'poll_interval': 10,
            'project_id': None
        }

        mock_client = MagicMock()
        mock_client.get_workload.return_value = self.mock_workload
        mock_client.create_snapshot.return_value = self.mock_snapshot_full

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.create_snapshot.assert_called_once_with(
                    workload_id='7b47b4e8-8db9-4670-8b1e-0679815049cf',
                    name='Override Full',
                    description=None,
                    full=True,
                    project_id=None
                )

    def test_check_mode(self):
        """Test check_mode returns changed=True without making create API call."""
        mock_module = MagicMock()
        mock_module.check_mode = True
        mock_module.params = {
            'state': 'present',
            'workload': 'production-web-cluster',
            'workload_name': None,
            'snapshot_id': None,
            'snapshot_type': 'incremental',
            'full': None,
            'name': None,
            'description': None,
            'wait': False,
            'timeout': 600,
            'poll_interval': 10,
            'project_id': None
        }

        mock_client = MagicMock()
        mock_client.get_workload_by_name.return_value = self.mock_workload

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.create_snapshot.assert_not_called()
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(call_kwargs['changed'])
                self.assertEqual(call_kwargs['snapshot']['id'], 'check-mode-dummy-snapshot-id')
                self.assertEqual(call_kwargs['snapshot']['snapshot_type'], 'incremental')

    def test_delete_snapshot_absent(self):
        """Test deleting a snapshot with state: absent."""
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'absent',
            'workload': None,
            'workload_name': None,
            'snapshot_id': 'snap-to-delete-123',
            'snapshot_type': 'incremental',
            'full': None,
            'name': None,
            'description': None,
            'wait': False,
            'timeout': 600,
            'poll_interval': 10,
            'project_id': 'proj-123'
        }

        mock_client = MagicMock()
        mock_client.get_snapshot.return_value = {'id': 'snap-to-delete-123', 'status': 'available'}

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.get_snapshot.assert_called_once_with('snap-to-delete-123', project_id='proj-123')
                mock_client.delete_snapshot.assert_called_once_with('snap-to-delete-123', project_id='proj-123')
                mock_module.exit_json.assert_called_once_with(changed=True, msg="Snapshot 'snap-to-delete-123' deleted successfully.")

    def test_workload_not_found_fails(self):
        """Test that missing workload raises module failure."""
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'workload': 'nonexistent-workload',
            'workload_name': None,
            'snapshot_id': None,
            'snapshot_type': 'incremental',
            'full': None,
            'name': None,
            'description': None,
            'wait': False,
            'timeout': 600,
            'poll_interval': 10,
            'project_id': None
        }

        mock_client = MagicMock()
        mock_client.get_workload_by_name.return_value = None

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_snapshot.TrilioClient', return_value=mock_client):
                run_module()

                mock_module.fail_json.assert_called_once_with(msg="Workload with name 'nonexistent-workload' not found.")


if __name__ == '__main__':
    unittest.main()
