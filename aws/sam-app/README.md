# NS1-AWS CloudSync

This project is a template for an AWS Serverless Application that enables you to keep your AWS Route 53 DNS zones and records synchronized with NS1.  
It contains source code and supporting files for a serverless application that you can deploy with the SAM CLI. It includes the following directories and files:

* `template.yml` : The application uses several AWS resources, including Lambda functions, Eventbridge rules, and IAM roles. These resources are defined in this file.
* `src/configure` : This is the source for the Lambda function that runs when the CloudFormation stack is created and destroyed. It takes care of storing the API key needed to send events to NS1 Connect in a safe place, and cleaning up when the stack is no longer needed.
* `src/dns_updates` : This is the source for the Lambda function that is responsible for sending zone and record events to NS1 Connect.
* `src/dns_snapshot` : This is the source for the Lambda function that runs when the CloudFormation stack is created to get NS1 Connect up-to-date with the existing zones and records in your AWS account.

## Architecture
```
 +--------------+       +--------------+       +--------------+       +--------------+       +--------------+       +--------------+
 |   Route 53   |  -->  |  CloudTrail  |  -->  |  EventBridge |  -->  |      SQS     |  -->  |    Lambda    |  -->  |      NS1     |
 +--------------+       +--------------+       +--------------+       +--------------+       +--------------+       +--------------+
```

When zones and records are created, changed, and deleted, events are automatically recorded in CloudTrail. The installed EventBridge rule watches for these events and queues them up for the Lambda to take on the next leg. Processing of the messages for the events is minimal. The message is taken in its entirety, lightly wrapped, and sent off across the Internet to the NS1 CloudSync REST API endpoint. Events are then processed asynchronously in NS1 Connect.

## Parameters

- **`NS1APIKey`** *(required)* — Your NS1 Connect account API key.
- **`CreateCloudTrail`** (default: `false`) — Set to `true` only if your AWS account has no existing active multi-region CloudTrail trail. Most accounts already have a default trail (`management-events`); leave as `false` to avoid creating a duplicate trail and incurring unnecessary charges (~$3/month).
- **`CloudTrailName`** (default: `NS1CloudSyncTrail`) — **Only used when `CreateCloudTrail` is `true`.** Leave as default if `CreateCloudTrail` is `false`. Name for the new trail created by this stack. Do not set this to the name of an existing trail.
- **`DLQAlarmNotificationArn`** *(optional)* — ARN of an SNS topic to notify when CloudWatch alarms fire. Two alarms are created by this stack: one fires when a message lands in the dead-letter queue after repeated 5xx failures (`CloudSyncUpdatesDLQueueNotEmpty`); the other fires when a message is discarded due to an expired CloudSync entitlement or invalid API key (`CloudSyncSyncUnauthorized`). Leave blank to skip SNS notifications — both alarms remain visible in CloudWatch either way.

## Security and permissions

You will need to provide an NS1 API key when installing the stack. A secret in AWS Secrets Manager is created for this key. When the `dns_updates` Lambda initializes it will request the key from Secrets Manager and store it in memory for the lifetime of the Lambda execution environment.

This template creates several IAM roles. Most of them are scoped to resources that the stack creates, such as the SQS queues, Secrets Manager secrets, CloudTrail bucket, and Step Functions state machine.

One exception is `Route53NSUpdaterRole`, which grants `route53:ChangeResourceRecordSets` on hosted zones in the account, but only for `NS` record changes. That role is assumable only by the AWS principal identified by the `AccountId` and `LambdaRoleName` parameters, so the stack does create a write-capable role for existing Route 53 resources.

The `dns_updates` Lambda function role itself remains limited to reading Route 53 data, receiving and deleting messages from the SQS queue, reading the NS1 API key secret, and starting the snapshot state machine. The Lambda also fails closed for zone-change updates when the hosted zone does not carry the configured sync tag, and it will not forward `ChangeResourceRecordSets` batches that include non-`NS` record types.
