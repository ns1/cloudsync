import boto3

from common import get_tags_for_zones

def lambda_handler(event, context):
    route53_client = boto3.client('route53')

    zones_response = route53_client.list_hosted_zones()

    if zones_response['ResponseMetadata']['HTTPStatusCode'] != 200:
        print(f"list_hosted_zones failed with status code: {zones_response['ResponseMetadata']['HTTPStatusCode']}. {response}")
        raise Exception


    zone_ids = [z['Id'].split('/')[-1] for z in zones_response['HostedZones']]

    tags = get_tags_for_zones(route53_client, zone_ids)
    return {
        'hosted_zones': [{'Id': '/hostedzone/Z09090592WZ3H9FL4ISQP', 'Name': 'cbert.co.', 'CallerReference': 'b645b276-bb25-47ec-895e-af8585f974b9', 'Config': {'Comment': '', 'PrivateZone': False}, 'ResourceRecordSetCount': 12}],
        'zones_count': 1,
        'current_zone_index': 0,
        'tags': tags
    }

