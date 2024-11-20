import os
import boto3

from common import snapshot_zone, SecretHandler

route53_client = boto3.client('route53')

secret_handler = SecretHandler()

zone_omit_enabled = os.environ.get('ENABLE_ZONE_OMIT', True)
zone_sync_tag = os.environ.get('ZONE_SYNC_TAG', 'CloudSync')
snapshot_dest = os.environ.get('SYNC_DEST')
s3_bucket_name = os.environ.get('SYNC_BUCKET')

def lambda_handler(event, context):
    if (endpoint := os.environ.get('ENDPOINT')) is None:
        print("ENDPOINT env variable not set")
        raise Exception

    # extract current zone info
    current_zone_index = event['iterator']['current_zone_index'] if 'iterator' in event else event['current_zone_index']
    current_zone = event['hosted_zones'][current_zone_index]
    current_zone_id = current_zone['Id'].split('/')[-1]
    current_zone_tags = {current_zone_id: event['tags'][current_zone_id]} 

    print(f"Now snapshotting {current_zone['Name']} zone with zone_id: {current_zone_id}")

    # check for pagination
    marker = None
    if 'iterator' in event and 'StartRecordName' in event['iterator']:
        marker = {
            'StartRecordName': event['iterator']['StartRecordName'],
            'StartRecordType': event['iterator']['StartRecordType'],
        }

        if bool(event['iterator'].get('StartRecordIdentifier', "")):
            marker['StartRecordIdentifier'] = event['iterator'].get('StartRecordIdentifier', "")


    if zone_omit_enabled and zone_sync_tag not in current_zone_tags[current_zone_id]:
        # update iterator
        return {
            'hosted_zones': event['hosted_zones'],
            'zones_count': event['zones_count'],
            'current_zone_index': current_zone_index + 1
        }
    
    out = snapshot_zone(
        route53_client, 
        current_zone_id, 
        current_zone['Name'], 
        endpoint, 
        current_zone_tags, 
        snapshot_dest, 
        s3_bucket_name, 
        secret_handler, 
        marker=marker
    )

    # update iterator
    out['hosted_zones'] = event['hosted_zones']
    out['zones_count'] = event['zones_count']
    out['current_zone_index'] = current_zone_index + 1 if not out['IsTruncated'] else current_zone_index
    
    return out
