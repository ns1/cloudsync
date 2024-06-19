import unittest
from unittest.mock import patch, MagicMock
import os
from src.trigger_state_machine.app import create


class TestLambdaHandler(unittest.TestCase):

    @patch('boto3.client')
    @patch.dict(os.environ, {'STATE_MACHINE_ARN': 'test_arn'})
    def test_create_success(self, mock_boto_client):
        mock_step_functions_client = MagicMock()
        mock_boto_client.return_value = mock_step_functions_client

        mock_step_functions_client.start_execution.return_value = {
            'ResponseMetadata': {
                'HTTPStatusCode': 200
            }
        }

        event = {}
        context = {}

        create(event, context)

        mock_step_functions_client.start_execution.assert_called_once_with(
            stateMachineArn='test_arn'
        )

    @patch('boto3.client')
    def test_create_no_state_machine_arn(self, mock_boto_client):
        event = {}
        context = {}

        with self.assertRaises(Exception) as ex:
            create(event, context)

        self.assertIn("STATE_MACHINE_ARN env variable not set",
                      str(ex.exception))

    @patch('boto3.client')
    def test_create_init_failure(self, mock_boto_client):
        mock_boto_client.side_effect = Exception("Failed to initialize boto3 client")

        event = {}
        context = {}

        with self.assertRaises(Exception) as ex:
            create(event, context)

        self.assertIn("Failed to initialize boto3 client", str(ex.exception))


if __name__ == '__main__':
    unittest.main()
