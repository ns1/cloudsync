import boto3

from common import get_tags_for_zones

def lambda_handler(event, context):
    route53_client = boto3.client('route53')

    zones_response = route53_client.list_hosted_zones()

    if zones_response['ResponseMetadata']['HTTPStatusCode'] != 200:
        print(f"list_hosted_zones failed with status code: {zones_response['ResponseMetadata']['HTTPStatusCode']}. {zones_response}")
        raise Exception

    zones = zones_response['HostedZones']
    zone_ids = [z['Id'].split('/')[-1] for z in zones]

    # single zone snapshot case
    if 'zone_name' in event:
        target_zone = event['zone_name'] if event['zone_name'].endswith('.') else event['zone_name'] + '.'
        
        for z in zones_response['HostedZones']:
            if z['Name'] == target_zone:
                zones = [z]
                zone_ids = [z['Id'].split('/')[-1]]
                break
    
    tags = get_tags_for_zones(route53_client, zone_ids)

    return {
        'hosted_zones': zones,
        'zones_count': len(zones),
        'current_zone_index': 0,
        'tags': tags
    }
