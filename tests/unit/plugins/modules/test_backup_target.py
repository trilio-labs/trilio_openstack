# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target import run_module


class TestBackupTargetModule(unittest.TestCase):

    def setUp(self):
        self.mock_nfs_target = {
            'id': 'bt-nfs-uuid-1',
            'type': 'nfs',
            'filesystem_export': '192.168.10.50:/var/nfs/trilio',
            'nfs_mount_opts': 'nolock,soft,timeo=600',
            'btt_name': 'primary-nfs-target',
            'status': 'online',
            'is_default': 1,
            'metadata': {'env': 'prod'}
        }
        self.mock_s3_target = {
            'id': 'bt-s3-uuid-1',
            'type': 's3',
            's3_endpoint_url': 'https://s3.eu-west-1.amazonaws.com',
            's3_bucket': 'prod-backups',
            'secret_ref': 'https://barbican:9311/v1/secrets/sec-uuid-1',
            'btt_name': 'primary-s3-target',
            'status': 'online',
            'is_default': 0,
            'immutable': 1
        }

    def test_backup_target_create_nfs(self):
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'target_type': 'nfs',
            'name': 'primary-nfs-target',
            'backup_target_id': None,
            'filesystem_export': '192.168.10.50:/var/nfs/trilio',
            'nfs_mount_opts': 'nolock,soft,timeo=600',
            's3_endpoint_url': None,
            's3_bucket': None,
            'secret_ref': None,
            'btt_name': 'primary-nfs-target',
            'is_default': True,
            'immutable': False,
            'metadata': {'env': 'prod'},
            'require_dms': True,
        }

        mock_client = MagicMock()
        mock_client.validate_dms_support.return_value = True
        mock_client.find_backup_target.return_value = None
        mock_client.create_backup_target.return_value = self.mock_nfs_target

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.validate_dms_support.assert_called_once_with(min_version="6.2")
                mock_client.create_backup_target.assert_called_once_with(
                    target_type='nfs',
                    filesystem_export='192.168.10.50:/var/nfs/trilio',
                    nfs_mount_opts='nolock,soft,timeo=600',
                    s3_endpoint_url=None,
                    s3_bucket=None,
                    secret_ref=None,
                    btt_name='primary-nfs-target',
                    is_default=1,
                    immutable=0,
                    metadata={'env': 'prod'}
                )
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(call_kwargs['changed'])
                self.assertEqual(call_kwargs['backup_target']['id'], 'bt-nfs-uuid-1')

    def test_backup_target_create_s3_with_secret_ref(self):
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'target_type': 's3',
            'name': 'primary-s3-target',
            'backup_target_id': None,
            'filesystem_export': None,
            'nfs_mount_opts': None,
            's3_endpoint_url': 'https://s3.eu-west-1.amazonaws.com',
            's3_bucket': 'prod-backups',
            'secret_ref': 'https://barbican:9311/v1/secrets/sec-uuid-1',
            'btt_name': 'primary-s3-target',
            'is_default': False,
            'immutable': True,
            'metadata': None,
            'require_dms': True,
        }

        mock_client = MagicMock()
        mock_client.validate_dms_support.return_value = True
        mock_client.find_backup_target.return_value = None
        mock_client.create_backup_target.return_value = self.mock_s3_target

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.create_backup_target.assert_called_once_with(
                    target_type='s3',
                    filesystem_export=None,
                    nfs_mount_opts=None,
                    s3_endpoint_url='https://s3.eu-west-1.amazonaws.com',
                    s3_bucket='prod-backups',
                    secret_ref='https://barbican:9311/v1/secrets/sec-uuid-1',
                    btt_name='primary-s3-target',
                    is_default=0,
                    immutable=1,
                    metadata=None
                )
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(call_kwargs['changed'])
                self.assertEqual(call_kwargs['backup_target']['type'], 's3')

    def test_backup_target_update_idempotent(self):
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'target_type': 'nfs',
            'name': 'primary-nfs-target',
            'backup_target_id': None,
            'filesystem_export': '192.168.10.50:/var/nfs/trilio',
            'nfs_mount_opts': 'nolock,soft,timeo=600',
            's3_endpoint_url': None,
            's3_bucket': None,
            'secret_ref': None,
            'btt_name': 'primary-nfs-target',
            'is_default': True,
            'immutable': False,
            'metadata': {'env': 'prod'},
            'require_dms': True,
        }

        mock_client = MagicMock()
        mock_client.validate_dms_support.return_value = True
        mock_client.find_backup_target.return_value = dict(self.mock_nfs_target)

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.create_backup_target.assert_not_called()
                mock_client.update_backup_target.assert_not_called()
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertFalse(call_kwargs['changed'])

    def test_backup_target_update_when_mount_opts_change(self):
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'present',
            'target_type': 'nfs',
            'name': 'primary-nfs-target',
            'backup_target_id': None,
            'filesystem_export': '192.168.10.50:/var/nfs/trilio',
            'nfs_mount_opts': 'nolock,soft,timeo=1200,retrans=5',
            's3_endpoint_url': None,
            's3_bucket': None,
            'secret_ref': None,
            'btt_name': 'primary-nfs-target',
            'is_default': True,
            'immutable': False,
            'metadata': {'env': 'prod'},
            'require_dms': True,
        }

        mock_client = MagicMock()
        mock_client.validate_dms_support.return_value = True
        mock_client.find_backup_target.return_value = dict(self.mock_nfs_target)
        updated_target = dict(self.mock_nfs_target)
        updated_target['nfs_mount_opts'] = 'nolock,soft,timeo=1200,retrans=5'
        mock_client.update_backup_target.return_value = updated_target

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.update_backup_target.assert_called_once_with(
                    'bt-nfs-uuid-1',
                    nfs_mount_opts='nolock,soft,timeo=1200,retrans=5'
                )
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(call_kwargs['changed'])

    def test_backup_target_delete_absent(self):
        mock_module = MagicMock()
        mock_module.check_mode = False
        mock_module.params = {
            'state': 'absent',
            'target_type': None,
            'name': 'primary-nfs-target',
            'backup_target_id': 'bt-nfs-uuid-1',
            'filesystem_export': None,
            'nfs_mount_opts': None,
            's3_endpoint_url': None,
            's3_bucket': None,
            'secret_ref': None,
            'btt_name': None,
            'is_default': False,
            'immutable': False,
            'metadata': None,
            'require_dms': True,
        }

        mock_client = MagicMock()
        mock_client.validate_dms_support.return_value = True
        mock_client.get_backup_target.return_value = self.mock_nfs_target

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target.TrilioClient', return_value=mock_client):
                run_module()

                mock_client.delete_backup_target.assert_called_once_with('bt-nfs-uuid-1')
                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertTrue(call_kwargs['changed'])


if __name__ == '__main__':
    unittest.main()
