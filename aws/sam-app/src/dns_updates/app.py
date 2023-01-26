import os
import json

import requests

endpoint = os.environ.get('ENDPOINT')
secret_name = 'CloudSync/APIKey'

# TODO: Handle the case when the secret doesn't exist in Secrets Manager.
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

def record_handler(record):
    try: 
        body = json.loads(record['body'])

    except json.JSONDecodeError:
        print(f"error decoding body as JSON")
        print(record['body'])
        return record['messageId']

    msg = {
        'source': 'AWS-Route53',
        'version': 1,
        'auth_key': retrieve_secret(secret_name),
        'payload': body
    }
    
    json_msg = json.dumps(msg)
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