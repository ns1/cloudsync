import unittest
from unittest.mock import patch, MagicMock
import os
import sys

current_dir = os.path.join(os.path.dirname(__file__))
sys.path.append(os.path.join(current_dir, '../../src/shared_layer/'))

from src.dns_snapshot_list.app import lambda_handler
from tests.resources.zones import ZONES

MOCK_TAGS = {
    "Z02924353K4BU30DZ0RYC": {},
    "Z014482635TU0BYFTNNCH": {"Name": "test"},
    "Z01267492FV5DJCQZCIVI": {},
    "Z07373449H5X5X4NX6X7": {},
    "Z09090592WZ3H9FL4ISQP": {}
}


def _make_paginator_mock(zones):
    """Return a mock paginator that yields all zones in a single page."""
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = iter([{'HostedZones': zones}])
    return mock_paginator


class TestLambdaHandler(unittest.TestCase):

    @patch('common.get_tags_for_zones')
    @patch('src.dns_snapshot_list.app.route53_client')
    def test_all_zones_returned_when_no_filter(self, mock_r53, mock_get_tags):
        """All zones are returned when no zone_name filter is provided."""
        mock_r53.get_paginator.return_value = _make_paginator_mock(ZONES['HostedZones'])
        mock_get_tags.return_value = MOCK_TAGS

        result = lambda_handler({}, {})

        self.assertEqual(result['hosted_zones'], ZONES['HostedZones'])
        self.assertEqual(result['zones_count'], len(ZONES['HostedZones']))
        self.assertEqual(result['current_zone_index'], 0)

    @patch('common.get_tags_for_zones')
    @patch('src.dns_snapshot_list.app.route53_client')
    def test_single_zone_filter_matches(self, mock_r53, mock_get_tags):
        """When zone_name is provided and found, only that zone is returned."""
        mock_r53.get_paginator.return_value = _make_paginator_mock(ZONES['HostedZones'])
        mock_get_tags.return_value = {"Z014482635TU0BYFTNNCH": {"Name": "test"}}

        result = lambda_handler({'zone_name': 'omar.com'}, {})

        self.assertEqual(len(result['hosted_zones']), 1)
        self.assertEqual(result['hosted_zones'][0]['Name'], 'omar.com.')
        self.assertEqual(result['zones_count'], 1)

    @patch('common.get_tags_for_zones')
    @patch('src.dns_snapshot_list.app.route53_client')
    def test_single_zone_filter_with_trailing_dot(self, mock_r53, mock_get_tags):
        """zone_name with trailing dot already present is matched correctly."""
        mock_r53.get_paginator.return_value = _make_paginator_mock(ZONES['HostedZones'])
        mock_get_tags.return_value = {"Z014482635TU0BYFTNNCH": {"Name": "test"}}

        result = lambda_handler({'zone_name': 'omar.com.'}, {})

        self.assertEqual(result['hosted_zones'][0]['Name'], 'omar.com.')

    @patch('src.dns_snapshot_list.app.route53_client')
    def test_single_zone_not_found_raises(self, mock_r53):
        """When zone_name is not in the account, RuntimeError is raised.

        This prevents the silent fallthrough that previously caused all zones
        in the account to be snapshotted (CLD-559).
        """
        mock_r53.get_paginator.return_value = _make_paginator_mock(ZONES['HostedZones'])

        with self.assertRaises(RuntimeError) as ctx:
            lambda_handler({'zone_name': 'doesnotexist.com'}, {})

        self.assertIn('doesnotexist.com.', str(ctx.exception))

    @patch('common.get_tags_for_zones')
    @patch('src.dns_snapshot_list.app.route53_client')
    def test_pagination_collects_all_pages(self, mock_r53, mock_get_tags):
        """Zones across multiple pages are all collected before filtering.

        Regression test for CLD-559: accounts with >100 zones were silently
        truncated to the first page, causing zones on later pages to be missed.
        """
        page1 = ZONES['HostedZones'][:3]
        page2 = ZONES['HostedZones'][3:]  # light.io. is here

        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = iter([
            {'HostedZones': page1},
            {'HostedZones': page2},
        ])
        mock_r53.get_paginator.return_value = mock_paginator
        mock_get_tags.return_value = {"Z02924353K4BU30DZ0RYC": {}}

        result = lambda_handler({'zone_name': 'light.io'}, {})

        self.assertEqual(result['hosted_zones'][0]['Name'], 'light.io.')

    @patch('src.dns_snapshot_list.app.route53_client')
    def test_zone_on_second_page_not_found_without_pagination_raises(self, mock_r53):
        """Zone on page 2 is not found when only page 1 is scanned — confirms
        the bug that pagination fixes."""
        page1_only = ZONES['HostedZones'][:3]  # light.io. is NOT here

        mock_r53.get_paginator.return_value = _make_paginator_mock(page1_only)

        with self.assertRaises(RuntimeError):
            lambda_handler({'zone_name': 'light.io'}, {})


if __name__ == '__main__':
    unittest.main()
