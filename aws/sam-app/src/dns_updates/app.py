import os
import json

import requests
import boto3

from common import dns_post
from secret_handler import SecretHandler

endpoint = os.environ.get('ENDPOINT')
zone_omit_enabled = os.environ.get('ENABLE_ZONE_OMIT', True)
zone_sync_tag = os.environ.get('ZONE_SYNC_TAG', 'CloudSync')
account_id = os.environ.get('ACCOUNT_ID')
snapshot_dest = os.environ.get('SYNC_DEST')

route53_client = boto3.client('route53')
secret_handler = SecretHandler()


def record_handler(record):
    try: 
        body = json.loads(record['body'])

    except json.JSONDecodeError:
        print(f"error decoding body as JSON")
        print(record['body'])
        return record['messageId']
    
    # discard changes made by CloudSync-outbound
    user_identity_arn = body['detail']['userIdentity']['arn']
    cloudsync_arn = f"arn:aws:sts::{account_id}:assumed-role/NS1_CloudSync_Role/cloudsync-{account_id}"
    
    if user_identity_arn == cloudsync_arn:
        print("skipping updates from CloudSync-outbound")
        return
    
    event_name = body['detail'].get('eventName')
    
    match event_name:
        case None:
            return record['messageId']
        
        case 'CreateHostedZone':
            zone_id = body['detail']['responseElements']['hostedZone']['id'].split('/')[-1]
            return handle_zones_and_records(zone_id, record)
        
        case 'ChangeResourceRecordSets':
            zone_id = body['detail']['requestParameters']['hostedZoneId'].split('/')[-1]
            return handle_zones_and_records(zone_id, record)

        case 'DeleteHostedZone':
            zone_id = body['detail']['requestParameters']['id']
            return handle_zones_and_records(zone_id, record)

        case 'ChangeTagsForResource':
            if body['detail']['requestParameters']['resourceType'] != 'hostedzone':
                # TODO: handle health check tags, which are used for health check names, apparently.
                return
            
            zone_id = body['detail']['requestParameters']['resourceId']
            return handle_zones_and_records(zone_id, record)
        
        case 'CreateHealthCheck' | 'DeleteHealthCheck':
            return handle_health_checks(record)
    

def handle_health_checks(record):
    try: 
        body = json.loads(record['body'])

    except json.JSONDecodeError:
        print(f"error decoding body as JSON")
        print(record['body'])
        return record['messageId']
    

    msg = {
        'source': 'route53',
        'dest': snapshot_dest,
        'version': 1,
        'account_id': account_id,
        'msg_type': 'update',
        'zone_name': 'health-checks',
        'page': 1,
        'truncated': False,
        'payload': body['detail']
    }
    
    response = dns_post(endpoint, msg, secret_handler)

    if response.status_code != 202:
        print(f"POST to {endpoint} failed with {response.status_code}: {response.content}")
        return record['messageId'] 
        
def handle_zones_and_records(zone_id, record):
    try: 
        body = json.loads(record['body'])
    except json.JSONDecodeError:
        print(f"error decoding body as JSON")
        print(record['body'])
        return record['messageId']
    
    # get zone metadata
    r = route53_client.get_hosted_zone(Id=zone_id)    

    event_name = body['detail'].get('eventName')
    if event_name != 'DeleteHostedZone':
        tags = route53_client.list_tags_for_resource(
            ResourceType='hostedzone',
            ResourceId=zone_id,
        )

        tags = tags['ResourceTagSet'].get('Tags', [])

        if zone_omit_enabled:
            # check whether the zone_sync tag was just added
            if event_name == 'ChangeTagsForResource':
                new_tags = body['detail']['requestParameters'].get('addTags', [])

                if zone_sync_tag in [t['key'] for t in new_tags]:
                    # the zone_omit tag may have been added. in fact, all tags show up here
                    # regardless of whether they were just added, so we'll have to snapshot
                    # in case the tag was just added. 
                    # TODO: Consider using state to determine if a snapshot is needed.
                    response = boto3.client('stepfunctions').start_execution(
                        stateMachineArn=os.environ.get('STATE_MACHINE_ARN'),
                        input=json.dumps({"zone_name": r['HostedZone']['Name']})
                    )
                    
                    if response['ResponseMetadata']['HTTPStatusCode'] != 200:
                        print(f"list_hosted_zones failed with status code: {response['ResponseMetadata']['HTTPStatusCode']}. {zones_response}")
                        raise Exception

                    return

            if zone_sync_tag not in [t['Key'] for t in tags]:
                # skip zone
                return


    msg = {
        'source': 'route53',
        'dest': snapshot_dest,
        'version': 1,
        'account_id': account_id,
        'msg_type': 'update',
        'zone_id': zone_id,
        'zone_name': r['HostedZone']['Name'],
        'page': 1,
        'truncated': False,
        'payload': body['detail']
    }

    response = dns_post(endpoint, msg, secret_handler)

    if response.status_code != 202:
        print(f"POST to {endpoint} failed with {response.status_code}: {response.content}")
        return record['messageId'] 


def handler(event, context):
    print(event)
    response = {"batchItemFailures": []}
    for record in event.get('Records'):
        if (failedMessageId := record_handler(record)) is not None:
            response['batchItemFailures'].append({"itemIdentifier": failedMessageId})
    
    print(response)
    return response
