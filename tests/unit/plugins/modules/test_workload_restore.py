# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore import run_module


class TestWorkloadRestoreModule(unittest.TestCase):

    def setUp(self):
        self.mock_snapshot = {
            'id': 'snap-uuid-1234',
            'name': 'Production Snapshot 1',
            'workload_id': 'wl-uuid-5678',
            'status': 'available'
        }
        self.mock_restore_oneclick = {
            'id': 'restore-uuid-oneclick-1',
            'name': 'OneClick Restore',
            'description': 'OneClick restore triggered via Ansible',
            'snapshot_id': 'snap-uuid-1234',
            'status': 'available',
            'restore_type': 'restore',
            'restore_options': {
                'type': 'openstack',
                'restore_type': 'oneclick',
                'oneclickrestore': True,
                'openstack': {}
            }
        }
        self.mock_restore_inplace = {
            'id': 'restore-uuid-inplace-2',
            'name': 'Inplace Restore',
            'description': 'Inplace restore triggered via Ansible',
            'snapshot_id': 'snap-uuid-1234',
            'status': 'available',
            'restore_type': 'restore',
            'restore_options': {
                'type': 'openstack',
                'restore_type': 'inplace',
                'oneclickrestore': False,
                'openstack': {
                    'instances': [
                        {
                            'id': 'inst-uuid-1',
                            'include': True,
                            'restore_boot_disk': True,
                            'vdisks': [{'id': 'vol-uuid-1', 'restore_cinder_volume': True}]
                        }
                    ]
                }
            }
        }
        self.mock_restore_selective = {
            'id': 'restore-uuid-selective-3',
            'name': 'Selective Restore',
            'description': 'Selective restore triggered via Ansible',
            'snapshot_id': 'snap-uuid-1234',
            'status': 'available',
            'restore_type': 'restore',
            'restore_options': {
                'type': 'openstack',
                'restore_type': 'selective',
                'oneclickrestore': False,
                'openstack': {
                    'instances': [
                        {
                            'id': 'inst-uuid-1',
                            'name': 'restored-vm-1',
                            'include': True,
                            'availability_zone': 'nova',
                            'server_group': 'sg-uuid-1'
                        }
                    ],
                    'restore_topology': False,
                    'networks_mapping': {
                        'networks': [
                            {
                                'snapshot_network': {'id': 'net-old', 'subnet': {'id': 'sub-old'}},
                                'target_network': {'id': 'net-new', 'name': 'internal', 'subnet': {'id': 'sub-new'}}
                            }
                        ]
                    }
                }
            }
        }

    def test_oneclick_restore_by_snapshot_uuid(self):
        """Test one-click restore using snapshot UUID."""
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'restore_type': 'one-click',
            'snapshot': 'snap-uuid-1234',
            'snapshot_name': None,
            'workload': None,
            'workload_name': None,
            'restore_id': None,
            'name': None,
            'description': None,
            'instances': None,
            'restore_topology': False,
            'networks_mapping': None,
            'options': None,
            'restore_file': None,
            'wait': False,
            'timeout': 1200,
            'poll_interval': 10,
            'project_id': 'proj-123'
        }

        mock_client = MagicMock()
        mock_client.resolve_snapshot.return_value = self.mock_snapshot
        mock_client.create_restore.return_value = dict(self.mock_restore_oneclick, status='restoring')

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.resolve_snapshot.assert_called_once_with(
                    snapshot_identifier='snap-uuid-1234',
                    workload_identifier=None,
                    project_id='proj-123'
                )
                mock_client.create_restore.assert_called_once()
                call_args = mock_client.create_restore.call_args[1]
                self.assertEqual(call_args['snapshot_id'], 'snap-uuid-1234')
                self.assertEqual(call_args['restore_type'], 'oneclick')
                self.assertTrue(call_args['options']['oneclickrestore'])
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(call_kwargs['changed'])
                self.assertEqual(call_kwargs['restore']['id'], 'restore-uuid-oneclick-1')

    def test_oneclick_restore_by_workload_with_wait(self):
        """Test one-click restore resolving latest snapshot of a workload with synchronous wait."""
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'restore_type': 'oneclick',
            'snapshot': None,
            'snapshot_name': None,
            'workload': 'production-web-cluster',
            'workload_name': None,
            'restore_id': None,
            'name': 'Emergency Rollback',
            'description': 'Rollback to latest available backup',
            'instances': None,
            'restore_topology': False,
            'networks_mapping': None,
            'options': None,
            'restore_file': None,
            'wait': True,
            'timeout': 600,
            'poll_interval': 5,
            'project_id': None
        }

        mock_client = MagicMock()
        mock_client.resolve_snapshot.return_value = self.mock_snapshot
        mock_client.create_restore.return_value = dict(self.mock_restore_oneclick, id='rest-999', status='restoring')
        mock_client.wait_for_restore.return_value = dict(self.mock_restore_oneclick, id='rest-999', status='available')

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.resolve_snapshot.assert_called_once_with(
                    snapshot_identifier=None,
                    workload_identifier='production-web-cluster',
                    project_id=None
                )
                mock_client.wait_for_restore.assert_called_once_with(
                    restore_id='rest-999',
                    target_status='available',
                    timeout=600,
                    poll_interval=5,
                    project_id=None
                )
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertEqual(call_kwargs['restore']['status'], 'available')

    def test_inplace_restore(self):
        """Test in-place restore with instance and volume configs."""
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'restore_type': 'in-place',
            'snapshot': 'snap-uuid-1234',
            'snapshot_name': None,
            'workload': None,
            'workload_name': None,
            'restore_id': None,
            'name': 'DB Volume Rollback',
            'description': 'Overwriting volumes in-place',
            'instances': [
                {
                    'id': 'inst-uuid-1',
                    'include': True,
                    'restore_boot_disk': True,
                    'vdisks': [{'id': 'vol-uuid-1', 'restore_cinder_volume': True}]
                }
            ],
            'restore_topology': False,
            'networks_mapping': None,
            'options': None,
            'restore_file': None,
            'wait': False,
            'timeout': 1200,
            'poll_interval': 10,
            'project_id': None
        }

        mock_client = MagicMock()
        mock_client.resolve_snapshot.return_value = self.mock_snapshot
        mock_client.create_restore.return_value = self.mock_restore_inplace

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.TrilioClient', return_value=mock_client):
                run_module()

                call_args = mock_client.create_restore.call_args[1]
                self.assertEqual(call_args['restore_type'], 'inplace')
                self.assertFalse(call_args['options']['oneclickrestore'])
                self.assertEqual(len(call_args['options']['openstack']['instances']), 1)
                self.assertTrue(call_args['options']['openstack']['instances'][0]['restore_boot_disk'])

    def test_selective_restore(self):
        """Test selective restore with custom instance rename, AZ, server group, and network mapping."""
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'restore_type': 'selective',
            'snapshot': 'snap-uuid-1234',
            'snapshot_name': None,
            'workload': None,
            'workload_name': None,
            'restore_id': None,
            'name': 'Staging Clone',
            'description': 'Granular clone to staging',
            'instances': [
                {
                    'id': 'inst-uuid-1',
                    'name': 'restored-vm-1',
                    'include': True,
                    'availability_zone': 'nova',
                    'server_group': 'sg-uuid-1'
                }
            ],
            'restore_topology': False,
            'networks_mapping': {
                'networks': [
                    {
                        'snapshot_network': {'id': 'net-old', 'subnet': {'id': 'sub-old'}},
                        'target_network': {'id': 'net-new', 'name': 'internal', 'subnet': {'id': 'sub-new'}}
                    }
                ]
            },
            'options': None,
            'restore_file': None,
            'wait': False,
            'timeout': 1200,
            'poll_interval': 10,
            'project_id': None
        }

        mock_client = MagicMock()
        mock_client.resolve_snapshot.return_value = self.mock_snapshot
        mock_client.create_restore.return_value = self.mock_restore_selective

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.TrilioClient', return_value=mock_client):
                run_module()

                call_args = mock_client.create_restore.call_args[1]
                self.assertEqual(call_args['restore_type'], 'selective')
                self.assertFalse(call_args['options']['oneclickrestore'])
                self.assertFalse(call_args['options']['openstack']['restore_topology'])
                self.assertEqual(call_args['options']['openstack']['instances'][0]['name'], 'restored-vm-1')
                self.assertIn('networks_mapping', call_args['options']['openstack'])

    def test_restore_from_external_json_file(self):
        """Test restore loading options from a CLI restore.json template file."""
        template_content = {
            'restore': {
                'name': 'File Loaded Restore',
                'description': 'Loaded from test file',
                'options': {
                    'type': 'openstack',
                    'restore_type': 'selective',
                    'oneclickrestore': False,
                    'openstack': {
                        'instances': [{'id': 'inst-from-file', 'include': True}]
                    }
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tf:
            json.dump(template_content, tf)
            tf_path = tf.name

        try:
            mock_module = MagicMock()
            mock_module.check_mode = False
            mock_module.params = {
                'state': 'present',
                'restore_type': 'selective',
                'snapshot': 'snap-uuid-1234',
                'snapshot_name': None,
                'workload': None,
                'workload_name': None,
                'restore_id': None,
                'name': None,
                'description': None,
                'instances': None,
                'restore_topology': False,
                'networks_mapping': None,
                'options': None,
                'restore_file': tf_path,
                'wait': False,
                'timeout': 1200,
                'poll_interval': 10,
                'project_id': None
            }

            mock_client = MagicMock()
            mock_client.resolve_snapshot.return_value = self.mock_snapshot
            mock_client.create_restore.return_value = dict(self.mock_restore_selective, name='File Loaded Restore')

            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.AnsibleModule', return_value=mock_module):
                with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.TrilioClient', return_value=mock_client):
                    run_module()

                    call_args = mock_client.create_restore.call_args[1]
                    self.assertEqual(call_args['name'], 'File Loaded Restore')
                    self.assertEqual(call_args['description'], 'Loaded from test file')
                    self.assertEqual(call_args['options']['openstack']['instances'][0]['id'], 'inst-from-file')
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_restore_check_mode(self):
        """Test check mode returns predicted changed status without creating restore."""
        mock_module = MagicMock()
        mock_module.check_mode = True
        mock_module.params = {
            'state': 'present',
            'restore_type': 'oneclick',
            'snapshot': 'snap-uuid-1234',
            'snapshot_name': None,
            'workload': None,
            'workload_name': None,
            'restore_id': None,
            'name': 'Check Mode Restore',
            'description': None,
            'instances': None,
            'restore_topology': False,
            'networks_mapping': None,
            'options': None,
            'restore_file': None,
            'wait': False,
            'timeout': 1200,
            'poll_interval': 10,
            'project_id': None
        }

        mock_client = MagicMock()
        mock_client.resolve_snapshot.return_value = self.mock_snapshot

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.create_restore.assert_not_called()
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(call_kwargs['changed'])
                self.assertEqual(call_kwargs['restore']['id'], 'check-mode-dummy-restore-id')

    def test_delete_restore(self):
        """Test deleting a restore record with state=absent."""
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'absent',
            'restore_type': 'oneclick',
            'snapshot': None,
            'snapshot_name': None,
            'workload': None,
            'workload_name': None,
            'restore_id': 'restore-to-delete',
            'name': None,
            'description': None,
            'instances': None,
            'restore_topology': False,
            'networks_mapping': None,
            'options': None,
            'restore_file': None,
            'wait': False,
            'timeout': 1200,
            'poll_interval': 10,
            'project_id': None
        }

        mock_client = MagicMock()
        mock_client.get_restore.return_value = {'id': 'restore-to-delete'}

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.delete_restore.assert_called_once_with('restore-to-delete', project_id=None)
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(call_kwargs['changed'])

    def test_cancel_restore(self):
        """Test cancelling an in-progress restore with state=cancelled."""
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'cancelled',
            'restore_type': 'oneclick',
            'snapshot': None,
            'snapshot_name': None,
            'workload': None,
            'workload_name': None,
            'restore_id': 'restore-to-cancel',
            'name': None,
            'description': None,
            'instances': None,
            'restore_topology': False,
            'networks_mapping': None,
            'options': None,
            'restore_file': None,
            'wait': False,
            'timeout': 1200,
            'poll_interval': 10,
            'project_id': None
        }

        mock_client = MagicMock()
        mock_client.get_restore.side_effect = [
            {'id': 'restore-to-cancel', 'status': 'restoring'},
            {'id': 'restore-to-cancel', 'status': 'cancelled'}
        ]

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.cancel_restore.assert_called_once_with('restore-to-cancel', project_id=None)
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(call_kwargs['changed'])
                self.assertEqual(call_kwargs['restore']['status'], 'cancelled')

    def test_missing_snapshot_and_workload_fails(self):
        """Test module failure when neither snapshot nor workload identifier is provided."""
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'restore_type': 'oneclick',
            'snapshot': None,
            'snapshot_name': None,
            'workload': None,
            'workload_name': None,
            'restore_id': None,
            'name': None,
            'description': None,
            'instances': None,
            'restore_topology': False,
            'networks_mapping': None,
            'options': None,
            'restore_file': None,
            'wait': False,
            'timeout': 1200,
            'poll_interval': 10,
            'project_id': None
        }

        mock_client = MagicMock()

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.workload_restore.TrilioClient', return_value=mock_client):
                run_module()

                mock_module.fail_json.assert_called_once()
                self.assertIn("Either 'snapshot'", mock_module.fail_json.call_args[1]['msg'])


if __name__ == '__main__':
    unittest.main()
