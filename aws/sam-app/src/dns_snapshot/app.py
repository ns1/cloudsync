import os
import boto3
import json
import requests
from contextlib import contextmanager

route53 = boto3.client('route53')

MAX_SNAPSHOT_SIZE = 100 # in terms of records

endpoint = os.environ.get('ENDPOINT')

def retrieve_secret(secret_id): 
    url = f'http://localhost:2773/secretsmanager/get?secretId={secret_id}'
    headers = { "X-Aws-Parameters-Secrets-Token": os.environ.get('AWS_SESSION_TOKEN') }
    response = requests.get(url, headers=headers)

    # will raise an exception if not 200
    response.raise_for_status()
    response = response.json()

    print(response)

    # this key will be there unless the request fails
    return response['SecretString']

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

def get_records(zone_id: str) -> dict:
    pass

class Snapshot:
    def __init__(self, zone_id):
        self.zone_id = zone_id

    def __enter__(self):
        print(f"snapshotting zone {self.zone_id}")

        json_msg = json.dumps({
            "zone_id": self.zone_id
        })
        headers = {
            'content-type' : 'application/json',
            'content-length' : str(len(json_msg))
        }

        response = requests.post(f'{endpoint}/snapshot_status', data=json_msg, headers=headers)
        if response.status_code != 202:
            raise Exception

    def __exit__(self, exc_type, exc_value, exc_traceback):
        requests.delete(f'{endpoint}/snapshot_status/{self.zone_id}') 


def lambda_handler(event, context):
    try:
        request_type = event['RequestType']

        # skip Delete and Update events
        if request_type in ["Delete", "Update"]:
            response_data = build_response(event, 'SUCCESS')
        
        else:

            msgs = list()
            aws_account_id = context.invoked_function_arn.split(":")[4]
            marker = None

            if endpoint is None:
                print("ENDPOINT env variable not set")
                raise Exception

            endpoint = f"{endpoint}/dns"

            while True:
                kwargs = dict()
                if marker is not None:
                    kwargs['marker'] = marker

                response = route53.list_hosted_zones(**kwargs)
                zones = response['HostedZones']

                for zone in zones:
                    if msg['num_records'] > 2:
                        # TODO: deal with a truncated list
                        records = route53.list_resource_record_sets(HostedZoneId=f"/hostedzone/{msg['zone_id']}")

                        # field names are not consistent with regard to capitalization, so lowercase the first letter
                        # and don't include SOA records. NS1 zones already include SOA data
                        msg['records'] = [transform_dict_key(r) for r in records['ResourceRecordSets'] if r['Type'] != 'SOA']

                    msgs.append()
                
                # send zones
                msg = {
                    'source': 'AWS-Route53',
                    'version': 1,
                    'account_id': os.environ.get('ACCOUNT_ID'),
                    'auth_key': retrieve_secret(os.environ['SECRET_NAME']),
                    'msg_type': 'snapshot',
                    'payload': body['detail']
                }

                json_payload = json.dumps(msg)
                headers = {
                    'content-type' : 'application/json',
                    'content-length' : str(len(json_payload))
                }

                put_response = requests.put(endpoint, data=json_payload, headers=headers)

                if put_response.status_code != 200:
                    print(f"PUT to {endpoint} failed with {put_response.status_code}: {put_response.content}")
                    raise Exception

                if not response['IsTruncated']:
                    break

                marker = response['NextMarker']

            response_data = build_response(event, 'SUCCESS')

    except Exception:
        # Catch any exceptions and ensure we always return a response
        response_data = build_response(event, 'FAILED')

    # Respond to Cloudformation to let it know we are done
    result = requests.post(msg['ResponseURL'], json=json.dumps(response_data))
    return result