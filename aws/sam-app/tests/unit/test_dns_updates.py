"""Unit tests for the DNS-updates SQS handler.

Two layers are covered independently:
  * handler()        - the SQS partial-batch failure contract and per-record
                       isolation (record_handler is mocked).
  * record_handler() - the per-message outcome contract: a messageId on failure,
                       None on success or an intentional skip (dns_post is mocked).
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from src.dns_updates.app import handler, record_handler


# --- Builders for the SQS event/record shapes the handler expects ------------

def _event(*records):
    return {"Records": list(records)}


def _detail(event_name="CreateHealthCheck", arn="arn:aws:iam::111122223333:user/tester"):
    # CreateHealthCheck is the simplest path through record_handler: no route53
    # calls or tag checks, just a single dns_post to the gateway.
    return {"userIdentity": {"arn": arn}, "eventName": event_name}


def _record(message_id, detail):
    return {"messageId": message_id, "body": json.dumps({"detail": detail})}


class TestHandlerBatchBehavior(unittest.TestCase):
    """handler() owns the SQS partial-batch contract and per-record isolation.

    record_handler is mocked so these assertions cover how the batch loop reacts
    to per-record outcomes, independent of how any individual record parses.
    """

    @patch("src.dns_updates.app.record_handler")
    def test_all_records_succeed_reports_no_failures(self, mock_record_handler):
        """Every record succeeding yields an empty batchItemFailures list."""
        mock_record_handler.return_value = None

        result = handler(_event({"messageId": "m1"}, {"messageId": "m2"}), None)

        self.assertEqual(result, {"batchItemFailures": []})

    @patch("src.dns_updates.app.record_handler")
    def test_soft_failure_is_reported_by_message_id(self, mock_record_handler):
        """A soft failure (record_handler returns the messageId, e.g. a non-202)
        is reported so SQS retries that message.
        """
        mock_record_handler.side_effect = lambda record: record["messageId"]

        result = handler(_event({"messageId": "m1"}, {"messageId": "m2"}), None)

        self.assertEqual(
            result["batchItemFailures"],
            [{"itemIdentifier": "m1"}, {"itemIdentifier": "m2"}],
        )

    @patch("src.dns_updates.app.record_handler")
    def test_hard_failure_is_isolated_to_the_failing_record(self, mock_record_handler):
        """A hard failure (record_handler raises) is reported for retry but must
        not propagate out of handler(); otherwise SQS retries the whole batch and
        the already-synced records get re-POSTed to NS1.
        """
        def side_effect(record):
            if record["messageId"] == "bad":
                raise RuntimeError("e.g. route53 throttling or a network blip")
            return None

        mock_record_handler.side_effect = side_effect

        result = handler(
            _event({"messageId": "ok1"}, {"messageId": "bad"}, {"messageId": "ok2"}),
            None,
        )

        self.assertEqual(result["batchItemFailures"], [{"itemIdentifier": "bad"}])

    @patch("src.dns_updates.app.record_handler")
    def test_mixed_batch_reports_only_failures(self, mock_record_handler):
        """A batch of success + soft failure + hard failure reports exactly the
        two failures and leaves the success out.
        """
        def side_effect(record):
            message_id = record["messageId"]
            if message_id == "soft":
                return message_id  # soft failure: record_handler returns the id
            if message_id == "hard":
                raise ValueError("hard failure: record_handler raises")
            return None  # success or intentional skip

        mock_record_handler.side_effect = side_effect

        result = handler(
            _event({"messageId": "ok"}, {"messageId": "soft"}, {"messageId": "hard"}),
            None,
        )

        failed_ids = {f["itemIdentifier"] for f in result["batchItemFailures"]}
        self.assertEqual(failed_ids, {"soft", "hard"})


class TestRecordHandlerContract(unittest.TestCase):
    """record_handler() returns a messageId on failure and None on success/skip."""

    @patch("src.dns_updates.app.dns_post")
    def test_non_202_response_returns_message_id(self, mock_dns_post):
        """A non-202 gateway response is a soft failure: return the messageId."""
        mock_dns_post.return_value = MagicMock(status_code=500, content=b"upstream error")

        self.assertEqual(record_handler(_record("m1", _detail())), "m1")

    @patch("src.dns_updates.app.dns_post")
    def test_202_response_returns_none(self, mock_dns_post):
        """A 202 gateway response is a success: return None."""
        mock_dns_post.return_value = MagicMock(status_code=202, content=b"")

        self.assertIsNone(record_handler(_record("m1", _detail())))

    def test_malformed_body_returns_message_id(self):
        """An unparseable body is a permanent failure, but it is still reported
        so it lands in the DLQ rather than being silently dropped.
        """
        record = {"messageId": "m1", "body": "not valid json"}

        self.assertEqual(record_handler(record), "m1")

    def test_cloudsync_outbound_updates_are_skipped(self):
        """Updates authored by CloudSync-outbound are ignored (return None) to
        avoid an echo loop.
        """
        # account_id is unset under test, so build the role arn the handler
        # compares against from that same (None) value.
        account_id = os.environ.get("ACCOUNT_ID")
        arn = f"arn:aws:sts::{account_id}:assumed-role/NS1_CloudSync_Role/cloudsync-{account_id}"
        record = _record("m1", _detail(event_name="ChangeResourceRecordSets", arn=arn))

        self.assertIsNone(record_handler(record))


if __name__ == "__main__":
    unittest.main()
