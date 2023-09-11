import os

from common import get_tags_for_zones, snapshot_zone

import boto3
from crhelper import CfnResource

helper = CfnResource(json_logging=False, log_level='DEBUG', boto_level='CRITICAL', sleep_on_delete=120, ssl_verify=None)

MAX_PAGE_SIZE = 100 # in terms of records

try:
    route53_client = boto3.client('route53')
    endpoint = os.environ.get('ENDPOINT')
    zone_omit_enabled = os.environ.get('ENABLE_ZONE_OMIT', True)
    zone_omit_tag = os.environ.get('ZONE_OMIT_TAG', 'CloudSync')

except Exception as e:
    helper.init_failure(e)


@helper.create
def create(event, context):
    print(event)

    aws_account_id = context.invoked_function_arn.split(":")[4]
    marker = None

    if (endpoint := os.environ.get('ENDPOINT')) is None:
        print("ENDPOINT env variable not set")
        raise Exception

    while True:
        kwargs = dict()
        if marker is not None:
            kwargs['Marker'] = marker

        zones_response = route53_client.list_hosted_zones(**kwargs)
        zone_ids = [z['Id'].split('/')[-1] for z in zones_response['HostedZones']]
        tags = get_tags_for_zones(route53_client, zone_ids)
        
        for zone in zones_response['HostedZones']:
            zone_id = zone['Id'].split('/')[-1]
            zone_tags = tags[zone_id]

            if zone_omit_enabled and zone_omit_tag not in zone_tags:
                continue

            snapshot_zone(route53_client, zone_id, zone['Name'], aws_account_id, endpoint, tags)

        if not zones_response['IsTruncated']:
            break

        marker = zones_response['NextMarker']


def lambda_handler(event, context):
    helper(event, context)