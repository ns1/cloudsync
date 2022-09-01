import os
import boto3
import app
import json
import requests
from util import transform_dict_key

route53 = boto3.client('route53')

def snapshot(event, context):
    msgs = list()
    aws_account_id = context.invoked_function_arn.split(":")[4]
    marker = None

    if (endpoint := os.environ.get('ENDPOINT')) and endpoint is None:
        print("ENDPOINT env variable not set")
        return

    while True:
        kwargs = dict()
        if marker is not None:
            kwargs['marker'] = marker

        response = route53.list_hosted_zones(**kwargs)
        zones = response['HostedZones']

        for zone in zones:
            msg = {
                'event': 'CreateHostedZone',
                'time': None,
                'aws_account_id': aws_account_id
            }
            msg.update(app.build_zone(zone))

            if msg['num_records'] > 2:
                records = route53.list_resource_record_sets(HostedZoneId=f"/hostedzone/{msg['zone_id']}")
                # field names are not consistent with regard to capitalization, so lowercase the first letter
                # and don't include SOA records. NS1 zones already include SOA data
                msg['records'] = [transform_dict_key(r) for r in records['ResourceRecordSets'] if r['Type'] != 'SOA']

            msgs.append(msg)
        
        # send zones
        payload = {
            "event": "ZoneSnapshot",
            "length": len(msgs),
            "zones": msgs
        }
        json_payload = json.dumps(payload)
        headers = {
            'content-type' : 'application/json',
            'content-length' : str(len(json_payload))
        }

        put_response = requests.put(endpoint, data=json_payload, headers=headers)

        if put_response.status_code != 200:
            print(f"PUT to {endpoint} failed with {put_response.status_code}: {put_response.content}")
            break

        if not response['IsTruncated']:
            break

        marker = response['NextMarker']
