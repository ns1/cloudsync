import boto3

from common import get_tags_for_zones

route53_client = boto3.client('route53')


def _list_all_hosted_zones():
    """Fetch all hosted zones across all pages."""
    zones = []
    paginator = route53_client.get_paginator('list_hosted_zones')
    for page in paginator.paginate():
        zones.extend(page['HostedZones'])
    return zones


def lambda_handler(event, context):
    zones = _list_all_hosted_zones()
    zone_ids = [z['Id'].split('/')[-1] for z in zones]

    # single zone snapshot case
    if 'zone_name' in event:
        target_zone = event['zone_name'] if event['zone_name'].endswith('.') else event['zone_name'] + '.'

        matched = [z for z in zones if z['Name'] == target_zone]
        if not matched:
            raise RuntimeError(
                f"zone_name '{target_zone}' not found in list_hosted_zones — "
                f"zone may not exist or may have been deleted."
            )
        zones = matched
        zone_ids = [matched[0]['Id'].split('/')[-1]]

    tags = get_tags_for_zones(route53_client, zone_ids)

    # state machine input
    return {
        'hosted_zones': zones,
        'zones_count': len(zones),
        'current_zone_index': 0,
        'tags': tags
    }
