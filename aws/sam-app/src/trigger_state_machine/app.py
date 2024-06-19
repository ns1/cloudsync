import os
import boto3
from crhelper import CfnResource

helper = CfnResource(json_logging=False, log_level='DEBUG',
                     boto_level='CRITICAL', sleep_on_delete=120, ssl_verify=None)


@helper.create
def create(event, context):
    step_functions_client = boto3.client('stepfunctions')
    state_machine_arn = os.environ.get('STATE_MACHINE_ARN')
    if not bool(state_machine_arn):
        print("STATE_MACHINE_ARN env variable not set")
        raise Exception("STATE_MACHINE_ARN env variable not set")

    response = step_functions_client.start_execution(
        stateMachineArn=state_machine_arn,
    )

    if response['ResponseMetadata']['HTTPStatusCode'] != 200:
        print(
            f"State machine trigger failed with status code: {response['ResponseMetadata']['HTTPStatusCode']}. {response}")
        raise Exception("Failed to start execution")


def lambda_handler(event, context):
    try:
        helper(event, context)
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        helper.init_failure(e)
