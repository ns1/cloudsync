# must be the first import in files with lambda function handlers
import lambdainit  # noqa: F401

import os
import json

import requests

import boto3
from botocore.exceptions import ClientError

from util import transform_dict_key

soa_value_map = ['nameserver', 'hostmaster', 'serial', 'refresh', 'retry', 'expiry', 'nx_ttl']

endpoint = os.environ.get('ENDPOINT')

route53 = boto3.client('route53')

def cast_int(val):
    try:
        ret = int(val)
    except ValueError:
        return val
    return ret

def build_zone(zone_info):
    msg = dict()
    zone_info = transform_dict_key(zone_info)
    msg = {
        'zone_id': zone_info['id'].split('/')[-1],
        'zone_name': zone_info['name'],
        'zone_config': zone_info['config'],
        'num_records': zone_info['resourceRecordSetCount']
    }

    # Get the SOA and NS records
    try:
        response = route53.list_resource_record_sets(HostedZoneId=msg['zone_id'])
    except route53.exceptions.NoSuchHostedZone:
        print(f"zone with id {msg['zone_id']} not found")
        raise Exception

    msg['soa_ttl'] = None
    for record in response['ResourceRecordSets']:
        if record['Type'] == 'SOA':
            msg['soa_ttl'] = record['TTL']
            values = [cast_int(v) for v in record['ResourceRecords'][0]['Value'].split()]
            
            if len(values) != len(soa_value_map):
                print('malformed SOA value map')
                raise Exception
            
            msg.update(dict(zip(soa_value_map, values)))
            break

        elif record['Type'] == 'NS':
            msg['ns_ttl'] = record['TTL']
            msg['nameservers'] = [v['Value'] for v in record['ResourceRecords']]
    
    if msg['soa_ttl'] is None:
        print(f"SOA record not found for zone with id {msg['zone_id']}")
        raise Exception
    
    return msg

def record_handler(record):
    try:
        body = json.loads(record['body'])
    except json.JSONDecodeError:
        print('malformed message body from Route 53')
        return record['messageId']
    
    detail = body.get('detail')
    if detail is None:
        print('malformed message')
        return record['messageId']

    msg = {
        'event': detail['eventName'],
        'time': detail['eventTime'],
        'aws_account_id': int(detail['userIdentity']['accountId'])
    }
    
    if detail['eventName'] == 'CreateHostedZone':
        try:
            msg.update(build_zone(detail['responseElements']['hostedZone']))
        except:
            return record['messageId']

    elif detail['eventName'] == 'DeleteHostedZone':
        msg['zone_id'] = detail['requestParameters']['id']

    elif detail['eventName'] == 'ChangeResourceRecordSets':
        msg['changes'] = detail['requestParameters']['changeBatch']['changes']
        msg['zone_id'] = detail['requestParameters']['hostedZoneId']
    
    json_msg = json.dumps({"message": msg})
    headers = {
        'content-type' : 'application/json',
        'content-length' : str(len(json_msg))
    }
    response = requests.post(endpoint, data=json_msg, headers=headers)

    if response.status_code != 200:
        print(f"POST to {endpoint} failed with {response.status_code}: {response.content}")
        return record['messageId']
        
    return


def handler(event, context):
    if endpoint is None:
        print("ENDPOINT env variable not set")
        # Fail the whole batch
        return ""

    print(event)
    response = {"batchItemFailures": []}
    for record in event.get('Records'):
        if (failedMessageId := record_handler(record)) is not None:
            response['batchItemFailures'].append({"itemIdentifier": failedMessageId})
    
    print(response)
    return response