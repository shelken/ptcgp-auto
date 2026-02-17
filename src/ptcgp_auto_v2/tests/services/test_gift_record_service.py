# -*- coding: utf-8 -*-
import unittest
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from ptcgp_auto_v2.services.gift_record_service import GiftRecordService


class TestGiftRecordService(unittest.TestCase):
    @patch(
        "ptcgp_auto_v2.services.gift_record_service.get_game_biz_date_str",
        return_value="2026-02-15",
    )
    def test_today_local_date_should_use_game_biz_date(self, _mock_biz_date):
        self.assertEqual("2026-02-15", GiftRecordService.today_local_date())

    def test_parse_count_transition_success(self):
        before_count, after_count = GiftRecordService.parse_count_transition("12>11")
        self.assertEqual(before_count, 12)
        self.assertEqual(after_count, 11)

    def test_parse_count_transition_with_spaces(self):
        before_count, after_count = GiftRecordService.parse_count_transition(" 3 > 2 ")
        self.assertEqual(before_count, 3)
        self.assertEqual(after_count, 2)

    def test_parse_count_transition_invalid(self):
        before_count, after_count = GiftRecordService.parse_count_transition("abc")
        self.assertIsNone(before_count)
        self.assertIsNone(after_count)

    @patch("ptcgp_auto_v2.services.gift_record_service.TaskInstanceRepository")
    def test_ensure_send_card_daily_pending_create_when_missing(self, repo_cls):
        repo = repo_cls.return_value
        repo.get_by_account_and_type.return_value = None
        repo.get_or_create.return_value = SimpleNamespace(
            status="pending", save=lambda: None
        )

        result = GiftRecordService.ensure_send_card_daily_pending(account_id=6)

        self.assertTrue(result)
        repo.get_or_create.assert_called_once_with(
            account_id=6,
            task_type="send_card_daily",
            reset_type="interval",
        )

    @patch("ptcgp_auto_v2.services.gift_record_service.TaskInstanceRepository")
    def test_ensure_send_card_daily_pending_reset_to_pending(self, repo_cls):
        repo = repo_cls.return_value
        saved = {"called": False}

        def _save():
            saved["called"] = True

        instance = SimpleNamespace(status="completed", save=_save)
        repo.get_by_account_and_type.return_value = instance

        result = GiftRecordService.ensure_send_card_daily_pending(account_id=7)

        self.assertTrue(result)
        self.assertEqual("pending", instance.status)
        self.assertTrue(saved["called"])

    @patch("ptcgp_auto_v2.services.gift_record_service.TaskInstanceRepository")
    def test_ensure_send_card_daily_pending_clear_next_run_at_when_already_pending(
        self, repo_cls
    ):
        repo = repo_cls.return_value
        saved = {"called": False}

        def _save():
            saved["called"] = True

        instance = SimpleNamespace(status="pending", next_run_at=object(), save=_save)
        repo.get_by_account_and_type.return_value = instance

        result = GiftRecordService.ensure_send_card_daily_pending(account_id=8)

        self.assertTrue(result)
        self.assertEqual("pending", instance.status)
        self.assertIsNone(instance.next_run_at)
        self.assertTrue(saved["called"])

    @patch("ptcgp_auto_v2.services.gift_record_service.TaskInstanceRepository")
    def test_ensure_claim_gifts_pending_create_when_missing(self, repo_cls):
        repo = repo_cls.return_value
        repo.get_by_account_and_type.return_value = None
        repo.get_or_create.return_value = SimpleNamespace(
            status="pending", save=lambda: None
        )

        result = GiftRecordService.ensure_claim_gifts_pending(account_id=6)

        self.assertTrue(result)
        repo.get_or_create.assert_called_once_with(
            account_id=6,
            task_type="claim_gifts",
            reset_type="daily",
        )

    @patch("ptcgp_auto_v2.services.gift_record_service.TaskInstanceRepository")
    def test_ensure_claim_gifts_pending_reset_to_pending(self, repo_cls):
        repo = repo_cls.return_value
        saved = {"called": False}

        def _save():
            saved["called"] = True

        instance = SimpleNamespace(status="completed", save=_save)
        repo.get_by_account_and_type.return_value = instance

        result = GiftRecordService.ensure_claim_gifts_pending(account_id=7)

        self.assertTrue(result)
        self.assertEqual("pending", instance.status)
        self.assertTrue(saved["called"])

    @patch("ptcgp_auto_v2.services.gift_record_service.TaskInstanceRepository")
    def test_ensure_claim_gifts_pending_clear_next_run_at_when_already_pending(
        self, repo_cls
    ):
        repo = repo_cls.return_value
        saved = {"called": False}

        def _save():
            saved["called"] = True

        instance = SimpleNamespace(status="pending", next_run_at=object(), save=_save)
        repo.get_by_account_and_type.return_value = instance

        result = GiftRecordService.ensure_claim_gifts_pending(account_id=8)

        self.assertTrue(result)
        self.assertEqual("pending", instance.status)
        self.assertIsNone(instance.next_run_at)
        self.assertTrue(saved["called"])

    @patch("ptcgp_auto_v2.services.gift_record_service.AccountGiftRecordRepository")
    def test_has_daily_attempt_false_when_record_missing(self, record_repo_cls):
        record_repo = record_repo_cls.return_value
        record_repo.get_daily_record.return_value = None

        result = GiftRecordService.has_daily_attempt(account_id=1, target_friend_id="f")

        self.assertFalse(result)

    @patch("ptcgp_auto_v2.services.gift_record_service.AccountGiftRecordRepository")
    def test_has_daily_attempt_false_when_status_init(self, record_repo_cls):
        record_repo = record_repo_cls.return_value
        record_repo.get_daily_record.return_value = SimpleNamespace(status="init")

        result = GiftRecordService.has_daily_attempt(account_id=1, target_friend_id="f")

        self.assertFalse(result)

    @patch("ptcgp_auto_v2.services.gift_record_service.AccountGiftRecordRepository")
    def test_has_daily_attempt_true_when_status_not_init(self, record_repo_cls):
        record_repo = record_repo_cls.return_value
        record_repo.get_daily_record.return_value = SimpleNamespace(status="failed")

        result = GiftRecordService.has_daily_attempt(account_id=1, target_friend_id="f")

        self.assertTrue(result)

    @patch("ptcgp_auto_v2.services.gift_record_service.AccountGiftRecordRepository")
    @patch("ptcgp_auto_v2.services.gift_record_service.AccountCardRepository")
    def test_mark_success_should_sync_sender_and_target_count(
        self,
        card_repo_cls,
        gift_repo_cls,
    ):
        card_repo = card_repo_cls.return_value
        card_repo.get.side_effect = [
            SimpleNamespace(count=2, yolo_conf=0.9, hash_similarity=0.95),
            SimpleNamespace(count=5, yolo_conf=0.8, hash_similarity=0.9),
        ]
        gift_repo = gift_repo_cls.return_value
        gift_repo.update.side_effect = lambda record: record

        record = cast(
            Any,
            SimpleNamespace(
                account_id=1,
                target_account_id=6,
                card_id=None,
                before_count=None,
                after_count=None,
                count_source=None,
                status="init",
                error_code=None,
                error_message=None,
            ),
        )

        GiftRecordService.mark_success_and_sync_count(
            record=record,
            card_id=100,
            before_count=2,
            after_count=1,
        )

        self.assertEqual(2, card_repo.upsert.call_count)
        sender_call = card_repo.upsert.call_args_list[0].kwargs
        target_call = card_repo.upsert.call_args_list[1].kwargs
        self.assertEqual(1, sender_call["account_id"])
        self.assertEqual(1, sender_call["count"])
        self.assertEqual(6, target_call["account_id"])
        self.assertEqual(6, target_call["count"])

    @patch("ptcgp_auto_v2.services.gift_record_service.AccountGiftRecordRepository")
    @patch("ptcgp_auto_v2.services.gift_record_service.AccountCardRepository")
    def test_mark_success_should_only_sync_sender_when_target_missing(
        self,
        card_repo_cls,
        gift_repo_cls,
    ):
        card_repo = card_repo_cls.return_value
        card_repo.get.return_value = SimpleNamespace(
            count=2,
            yolo_conf=0.9,
            hash_similarity=0.95,
        )
        gift_repo = gift_repo_cls.return_value
        gift_repo.update.side_effect = lambda record: record

        record = cast(
            Any,
            SimpleNamespace(
                account_id=1,
                target_account_id=None,
                card_id=None,
                before_count=None,
                after_count=None,
                count_source=None,
                status="init",
                error_code=None,
                error_message=None,
            ),
        )

        GiftRecordService.mark_success_and_sync_count(
            record=record,
            card_id=100,
            before_count=2,
            after_count=1,
        )

        self.assertEqual(1, card_repo.upsert.call_count)


if __name__ == "__main__":
    unittest.main()
