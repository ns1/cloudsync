import os
import boto3
import app
import json
import requests
from util import transform_dict_key

route53 = boto3.client('route53')


soa_value_map = ['nameserver', 'hostmaster', 'serial', 'refresh', 'retry', 'expiry', 'nx_ttl']

def cast_int(val):
    try:
        ret = int(val)
    except ValueError:
        return val
    return ret

def build_response(event, status):
    """A utility function used to build a response to CloudFormation"""

    response_data = {
        'Status': status,
        'PhysicalResourceId': 'ns1cloudsync::{}'.format(event['LogicalResourceId']),
        'Data': {},
        'RequestId': event['RequestId'],
        "LogicalResourceId": event["LogicalResourceId"],
        "StackId": event["StackId"],
    }
    return response_data

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

def lambda_handler(event, context):
    print(event)
    # try:
    #     request_type = event['RequestType']

    #     if request_type == "Create":
    #         msgs = list()
    #         aws_account_id = context.invoked_function_arn.split(":")[4]
    #         marker = None

    #         if (endpoint := os.environ.get('ENDPOINT')) and endpoint is None:
    #             print("ENDPOINT env variable not set")
    #             raise Exception

    #         while True:
    #             kwargs = dict()
    #             if marker is not None:
    #                 kwargs['marker'] = marker

    #             response = route53.list_hosted_zones(**kwargs)
    #             print(response)
    #             zones = response['HostedZones']

    #             for zone in zones:
    #                 msg = {
    #                     'event': 'CreateHostedZone',
    #                     'time': None,
    #                     'aws_account_id': aws_account_id
    #                 }
    #                 msg.update(build_zone(zone))

    #                 if msg['num_records'] > 2:
    #                     # TODO: deal with a truncated list
    #                     records = route53.list_resource_record_sets(HostedZoneId=f"/hostedzone/{msg['zone_id']}")
    #                     print(records)
    #                     # field names are not consistent with regard to capitalization, so lowercase the first letter
    #                     # and don't include SOA records. NS1 zones already include SOA data
    #                     msg['records'] = [transform_dict_key(r) for r in records['ResourceRecordSets'] if r['Type'] != 'SOA']

    #                 msgs.append(msg)
                
    #             # send zones
    #             payload = {
    #                 "event": "ZoneSnapshot",
    #                 "length": len(msgs),
    #                 "zones": msgs
    #             }
    #             json_payload = json.dumps(payload)
    #             headers = {
    #                 'content-type' : 'application/json',
    #                 'content-length' : str(len(json_payload))
    #             }

    #             put_response = requests.put(endpoint, data=json_payload, headers=headers)

    #             if put_response.status_code != 200:
    #                 print(f"PUT to {endpoint} failed with {put_response.status_code}: {put_response.content}")
    #                 raise Exception

    #             if not response['IsTruncated']:
    #                 break

    #             marker = response['NextMarker']

    #         response_data = build_response(event, 'SUCCESS')
        
    #     else:
    #         # TODO: fill in for the delete action
    #         response_data = build_response(event, 'SUCCESS')

    # except Exception:
    #     # Catch any exceptions and ensure we always return a response
    #     response_data = build_response(event, 'FAILED')

    # print(response_data)

    print(1)
    msg = json.loads(event['Records'][0]['Sns']['Message'])
    print(2)
    response_data = {
        'Status': 'SUCCESS',
        'PhysicalResourceId': 'ns1cloudsync::{}'.format(msg['LogicalResourceId']),
        'Data': {},
        'RequestId': msg['RequestId'],
        'LogicalResourceId': msg['LogicalResourceId'],
        'StackId': msg['StackId'],
    }
    print(3)
    # Respond to Cloudformation to let it know we are done
    result = requests.post(msg['ResponseURL'], data=json.dumps(response_data))
    print(4)
    return result