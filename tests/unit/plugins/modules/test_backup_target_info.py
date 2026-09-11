# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Kevin Jackson
# Apache License, Version 2.0 (see LICENSE or https://www.apache.org/licenses/LICENSE-2.0)

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target_info import run_module


class TestBackupTargetInfoModule(unittest.TestCase):

    def setUp(self):
        self.mock_targets = [
            {
                'id': 'bt-1',
                'type': 'nfs',
                'filesystem_export': '192.168.1.10:/backups',
                'btt_name': 'nfs-target',
                'status': 'online'
            },
            {
                'id': 'bt-2',
                'type': 's3',
                's3_endpoint_url': 'https://s3.amazonaws.com',
                's3_bucket': 'prod-backups',
                'btt_name': 's3-target',
                'status': 'online'
            }
        ]
        self.mock_btts = [
            {
                'id': 'btt-1',
                'name': 'nfs-target',
                'backup_targets_id': 'bt-1',
                'is_public': True
            }
        ]

    def test_backup_target_info_list_all(self):
        mock_module = MagicMock()
        mock_module.params = {
            'backup_target_id': None,
            'name': None,
            'target_type': None,
            'include_target_types': True,
            'require_dms': True,
        }

        mock_client = MagicMock()
        mock_client.validate_dms_support.return_value = True
        mock_client.list_backup_targets.return_value = self.mock_targets
        mock_client.list_backup_target_types.return_value = self.mock_btts

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target_info.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target_info.TrilioClient', return_value=mock_client):
                run_module()

                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertFalse(call_kwargs['changed'])
                self.assertEqual(len(call_kwargs['backup_targets']), 2)
                self.assertEqual(len(call_kwargs['backup_target_types']), 1)

    def test_backup_target_info_filter_type(self):
        mock_module = MagicMock()
        mock_module.params = {
            'backup_target_id': None,
            'name': None,
            'target_type': 's3',
            'include_target_types': False,
            'require_dms': True,
        }

        mock_client = MagicMock()
        mock_client.validate_dms_support.return_value = True
        mock_client.list_backup_targets.return_value = self.mock_targets

        with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target_info.AnsibleModule', return_value=mock_module):
            with patch('ansible_collections.trilio.trilio_openstack.plugins.modules.backup_target_info.TrilioClient', return_value=mock_client):
                run_module()

                mock_module.exit_json.assert_called_once()
                call_kwargs = mock_module.exit_json.call_args[1]
                self.assertFalse(call_kwargs['changed'])
                self.assertEqual(len(call_kwargs['backup_targets']), 1)
                self.assertEqual(call_kwargs['backup_targets'][0]['type'], 's3')


if __name__ == '__main__':
    unittest.main()
