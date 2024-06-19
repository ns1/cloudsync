import unittest
from unittest.mock import patch, MagicMock
import os
import sys

current_dir = os.path.join(os.path.dirname(__file__))
sys.path.append(os.path.join(current_dir, '../../src/shared_layer/'))

from src.dns_snapshot_list.app import lambda_handler
from tests.resources.zones import ZONES

class TestLambdaHandler(unittest.TestCase):
    @patch('boto3.client')
    @patch('common.get_tags_for_zones')
    def test_lambda_handler_success(self, mock_get_tags_for_zones, mock_boto_client):
        mock_route53_client = MagicMock()
        mock_boto_client.return_value = mock_route53_client
        mock_route53_client.list_hosted_zones.return_value = ZONES
        mock_get_tags_for_zones.return_value = {
            "Z02924353K4BU30DZ0RYC": {},
            "Z014482635TU0BYFTNNCH": {
                "Name": "test"
            },
            "Z01267492FV5DJCQZCIVI": {},
            "Z07373449H5X5X4NX6X7": {},
            "Z09090592WZ3H9FL4ISQP": {}
        }

        event = {}
        context = {}

        result = lambda_handler(event, context)

        self.assertEqual(result['hosted_zones'], ZONES["HostedZones"])
        self.assertEqual(result['zones_count'], ZONES["zones_count"])
        self.assertEqual(result['current_zone_index'],
                         ZONES["current_zone_index"])
        self.assertEqual(
            mock_get_tags_for_zones.return_value, ZONES["tags"])

    @ patch('boto3.client')
    def test_lambda_handler_failure(self, mock_boto_client):
        mock_route53_client = MagicMock()
        mock_route53_client.list_hosted_zones.return_value = {
            'ResponseMetadata': {
                'HTTPStatusCode': 500
            }
        }
        mock_boto_client.return_value = mock_route53_client

        event = {}
        context = {}

        with self.assertRaises(Exception):
            lambda_handler(event, context)


if __name__ == '__main__':
    unittest.main()
