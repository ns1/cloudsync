import os
import json

import boto3
from botocore.exceptions import ClientError

import requests

soa_value_map = ['nameserver', 'hostmaster', 'serial', 'refresh', 'retry', 'expiry', 'nx_ttl']

def cast_int(val):
    try:
        ret = int(val)
    except ValueError:
        return val
    return ret

def lambda_handler(event, context):
    try:
        route53 = boto3.client('route53')
    except ClientError as err:
        print(f"Error getting Route 53 client: {err}")

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
        'aws_account_id': detail['userIdentity']['accountId']
    }
    
    if msg['event'] == 'CreateHostedZone':
        zone_info = detail['responseElements']['hostedZone']
        msg['zone_id'] = zone_info['id'].split('/')[-1]
        msg['zone_name'] = zone_info['name']
        msg['zone_config'] = zone_info['config']
        msg['num_records'] = zone_info['resourceRecordSetCount']
        msg['nameservers'] = detail['responseElements']['delegationSet']['nameServers']

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
        
        if msg['soa_ttl'] is None:
            print(f"SOA record not found for zone with id {msg['zone_id']}")
            return

    elif msg['event'] == 'DeleteHostedZone':
        msg['zone_id'] = detail['requestParameters']['id']
        print(event)

    endpoint = os.environ.get('ENDPOINT')
    if endpoint is None:
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
