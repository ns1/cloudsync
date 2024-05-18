import os
import json

import requests
import boto3

from common import retrieve_secret, snapshot_zone

endpoint = os.environ.get('ENDPOINT')
zone_omit_enabled = os.environ.get('ENABLE_ZONE_OMIT', True)
zone_omit_tag = os.environ.get('ZONE_OMIT_TAG', 'CloudSync')
account_id = os.environ.get('ACCOUNT_ID')

route53_client = boto3.client('route53')


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
        'source': 'AWS-Route53',
        'version': 1,
        'account_id': account_id,
        'auth_key': retrieve_secret(os.environ['SECRET_NAME']),
        'msg_type': 'update',
        'zone_name': 'health-checks',
        'page': 1,
        'truncated': False,
        'payload': body['detail']
    }
    
    return send_message(msg, record['messageId'])

        
def handle_zones_and_records(zone_id, record):
    try: 
        body = json.loads(record['body'])

    except json.JSONDecodeError:
        print(f"error decoding body as JSON")
        print(record['body'])
        return record['messageId']
    
    event_name = body['detail'].get('eventName')

    tags = []
    zone_name = None

    if event_name != 'DeleteHostedZone':
    # TODO: Make zone name optional, because updates don't need it.
    # TODO: Why not pull the zone name from the payload for zone create?
        r = route53_client.get_hosted_zone(Id=zone_id)
        zone_name = r['HostedZone']['Name']

        tags = route53_client.list_tags_for_resource(
            ResourceType='hostedzone',
            ResourceId=zone_id,
        )

        tags = tags['ResourceTagSet'].get('Tags', [])

        if zone_omit_enabled:
            # check whether the zone_omit tag was added
            if event_name == 'ChangeTagsForResource':
                new_tags = body['detail']['requestParameters'].get('addTags', [])

                if zone_omit_tag in [t['key'] for t in new_tags]:
                    # the zone_omit tag may have been added. in fact, all tags show up here
                    # regardless of whether they were just added, so we'll have to snapshot
                    # in case the tag was just added. 
                    print("snapshotting")
                    #TODO: tweak snapshot call here
                    # snapshot_zone(route53_client, zone_id, zone_name, account_id, endpoint, tags)
                    return

            if zone_omit_tag not in [t['Key'] for t in tags]:
                # skip zone
                return

    msg = {
        'source': 'AWS-Route53',
        'version': 1,
        'account_id': account_id,
        'auth_key': retrieve_secret(os.environ['SECRET_NAME']),
        'msg_type': 'update',
        # 'zone_id': zone_id,
        'zone_name': zone_name,
        'page': 1,
        'truncated': False,
        'payload': body['detail']
    }
    
    return send_message(msg, record['messageId'])

def send_message(msg, message_id):
    json_msg = json.dumps(msg)
    headers = {
        'content-type' : 'application/json',
        'content-length' : str(len(json_msg))
    }
    response = requests.post(endpoint, data=json_msg, headers=headers)

    print(json_msg)

    if response.status_code != 202:
        print(f"POST to {endpoint} failed with {response.status_code}: {response.content}")
        return message_id 

def handler(event, context):
    print(event)
    response = {"batchItemFailures": []}
    for record in event.get('Records'):
        if (failedMessageId := record_handler(record)) is not None:
            response['batchItemFailures'].append({"itemIdentifier": failedMessageId})
    
    print(response)
    return response
