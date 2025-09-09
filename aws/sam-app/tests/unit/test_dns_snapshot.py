
from unittest.mock import patch, MagicMock
import unittest
import sys
import os

current_dir = os.path.join(os.path.dirname(__file__))
sys.path.append(os.path.join(current_dir, '../../src/shared_layer/'))

from src.dns_snapshot.app import lambda_handler
from tests.resources.snapshot_zones import POSITIVE_ZONES, OMIT_ZONES

class TestLambdaHandler(unittest.TestCase):

    @patch.dict(os.environ, {
        'ENDPOINT': 'http://api.nszero.com/cloudsync/v1beta1',
        'ENABLE_ZONE_OMIT': 'true',
        'ZONE_SYNC_TAG': 'CloudSync',
        'SYNC_DEST': '',
    })
    @patch('common.snapshot_zone')
    def test_lambda_handler_success(self, mock_snapshot_zone):
        mock_snapshot_zone.return_value = {
            'StartRecordName': 'absci.cloudsync.nsone.co.',
            'StartRecordType': 'A',
            'IsTruncated': False,
            'hosted_zones': [
                {
                    'Id': '/hostedzone/Z09090592WZ3H9FL4ISQP',
                    'Name': 'cbert.co.',
                    'CallerReference': 'b645b276-bb25-47ec-895e-af8585f974b9',
                    'Config': {'Comment': '', 'PrivateZone': False},
                    'ResourceRecordSetCount': 10000
                },
                {
                    'Id': '/hostedzone/Z07373449H5X5X4NX6X7',
                    'Name': 'testing.yahoo.',
                    'CallerReference': '9c386bd5-341f-45da-a991-d5250a871892',
                    'Config': {'Comment': '', 'PrivateZone': False},
                    'ResourceRecordSetCount': 10000
                },
                {
                    'Id': '/hostedzone/Z014482635TU0BYFTNNCH',
                    'Name': 'omar.com.',
                    'CallerReference': 'omar.com;1716503589',
                    'Config': {'Comment': 'synced from ns1', 'PrivateZone': False},
                    'ResourceRecordSetCount': 10000
                },
                {
                    'Id': '/hostedzone/Z01267492FV5DJCQZCIVI',
                    'Name': 'cloudsync.nsone.co.',
                    'CallerReference': 'd40e6811-258f-412c-be9b-7a41b69bbb2a',
                    'Config': {'Comment': '', 'PrivateZone': False},
                    'ResourceRecordSetCount': 10000
                }
            ],
            'zones_count': 4,
            'current_zone_index': 3
        }

        event = POSITIVE_ZONES
        context = {}

        result = lambda_handler(event, context)

        self.assertEqual(result['zones_count'], 4)

    @patch.dict(os.environ, {
        'ENDPOINT': 'http://api.nszero.com/cloudsync/v1beta1',
        'ENABLE_ZONE_OMIT': 'True',
        'ZONE_SYNC_TAG': 'CloudSync',
        'SYNC_DEST': '',


    })
    @patch('common.snapshot_zone')
    def test_lambda_omit_zone(self, mock_snapshot_zone):
        mock_snapshot_zone.return_value = {}

        event = OMIT_ZONES
        context = {}

        result = lambda_handler(event, context)

        self.assertEqual(result, {})


if __name__ == '__main__':
    unittest.main()
