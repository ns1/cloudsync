import boto3
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    try:
        route53 = boto3.client('route53')
    except ClientError as err:
        print(f"Error getting route53 client: {err}")

    if (src := event.get('source')) is None or src != 'aws.route53':
        print(f'received out-of-band message')
        return
    
    detail = event.get('detail')
    if detail is None:
        print('malformed message')
        return

    msg = {
        'name': detail['eventName'],
        'time': detail['eventTime'],
    }
    
    if msg['name'] in ('CreateHostedZone', 'DeleteHostedZone'):
        zone_info = detail['responseElements']['hostedZone']
        msg['zone_id'] = zone_info['id'].split('/')[-1]
        msg['zone_name'] = zone_info['name']
        msg['zone_config'] = zone_info['config']
        msg['num_records'] = zone_info['resourceRecordSetCount']
        msg['nameservers'] = detail['responseElements']['delegationSet']['nameServers']

        if msg['name'] == 'CreateHostedZone':
            # Get the SOA and NS records
            try:
                response = route53.list_resource_record_sets(HostedZoneId=msg['zone_id'])
            except route53.exceptions.NoSuchHostedZone:
                print(f"zone with id {msg['zone_id']} not found")
            
            msg['soa_ttl'] = None
            for record in response['ResourceRecordSets']:
                if record['Type'] == 'SOA':
                    msg['soa_ttl'] = record['TTL']
                    break
            
            if msg['soa_ttl'] is None:
                print(f"SOA record not found for zone with id {msg['zone_id']}")
                return
        
        return msg
