"""vulture 精确白名单。

只保留 ORM 字段、SQLite 动态属性和 E2E 通过反射/探针使用的入口。
"""

from ptcgp_auto_v2.db.connection import Database
from ptcgp_auto_v2.db.models.account_battle_progress import AccountBattleProgress
from ptcgp_auto_v2.db.models.pack_card import PackCard
from ptcgp_auto_v2.tests.e2e.harness import SchedulerHarness, configure_runtime_from_env
from ptcgp_auto_v2.tests.e2e.probe_workers import (
    mark_task_completed_by_id,
    probe_complete_after_pending,
    probe_complete_run,
    probe_hang_run,
    probe_mark_running,
)
from ptcgp_auto_v2.tests.e2e.test_e2e_harness_snapshot import (
    _FakeRepositoryFactory,
    _FakeRunLeaseRepo,
)

Database.connection
Database.connection.row_factory
AccountBattleProgress.Config.unique_together
PackCard.pack_record_id
PackCard.pack_record

configure_runtime_from_env
SchedulerHarness.start_scheduler
SchedulerHarness.override_scheduler_lease_timeout
SchedulerHarness.signal_worker
SchedulerHarness.collect_runtime_process_metrics

probe_complete_run
probe_hang_run
probe_mark_running
probe_complete_after_pending
mark_task_completed_by_id

_FakeRunLeaseRepo.get_active_by_account_id
_FakeRunLeaseRepo.get_latest_by_account_id
_FakeRepositoryFactory.run_leases


class _RuntimeSupervisorProbe:
    lease_timeout_seconds = 0


_RuntimeSupervisorProbe.lease_timeout_seconds
