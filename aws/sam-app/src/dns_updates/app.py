# must be the first import in files with lambda function handlers
import lambdainit  # noqa: F401

import os
import json

import requests

import boto3
from botocore.exceptions import ClientError

from util import transform_dict_key

soa_value_map = ['nameserver', 'hostmaster', 'serial', 'refresh', 'retry', 'expiry', 'nx_ttl']

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
    
    msg['soa_ttl'] = None
    for record in response['ResourceRecordSets']:
        if record['Type'] == 'SOA':
            msg['soa_ttl'] = record['TTL']
            values = [cast_int(v) for v in record['ResourceRecords'][0]['Value'].split()]
            
            if len(values) != len(soa_value_map):
                print('malformed SOA value map')
                return
            
            msg.update(dict(zip(soa_value_map, values)))
            break

        elif record['Type'] == 'NS':
            msg['ns_ttl'] = record['TTL']
            msg['nameservers'] = [v['Value'] for v in record['ResourceRecords']]
    
    if msg['soa_ttl'] is None:
        print(f"SOA record not found for zone with id {msg['zone_id']}")
        return
    
    return msg

def handler(event, context):
    print(event)
    if (src := event.get('source')) is None or src != 'aws.route53':
        print(f'received out-of-band message')
        return
    
    detail = event.get('detail')
    if detail is None:
        print('malformed message')
        return

    msg = {
        'event': detail['eventName'],
        'time': detail['eventTime'],
        'aws_account_id': int(detail['userIdentity']['accountId'])
    }
    
    if detail['eventName'] == 'CreateHostedZone':
        msg.update(build_zone(detail['responseElements']['hostedZone']))

    elif detail['eventName'] == 'DeleteHostedZone':
        msg['zone_id'] = detail['requestParameters']['id']

    elif detail['eventName'] == 'ChangeResourceRecordSets':
        msg['changes'] = detail['requestParameters']['changeBatch']['changes']
        msg['zone_id'] = detail['requestParameters']['hostedZoneId']


    # insert NS1 org id
    msg['org_id'] = os.environ.get('ORG_ID')

    if (endpoint := os.environ.get('ENDPOINT')) and endpoint is None:
        print("ENDPOINT env variable not set")
        return
    
    json_msg = json.dumps(msg)
    headers = {
        'content-type' : 'application/json',
        'content-length' : str(len(json_msg))
    }
    response = requests.put(endpoint, data=json_msg, headers=headers)

    if response.status_code != 200:
        print(f"PUT to {endpoint} failed with {response.status_code}: {response.content}")
        return
        
    return msg
