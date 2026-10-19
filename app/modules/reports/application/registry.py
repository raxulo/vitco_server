# application/registry.py

from app.modules.reports.executors.mcc.mcc_shift_summary import MccShiftSummaryExecutor
from app.modules.reports.domain.enums import ReportType
from app.modules.reports.executors.base import ReportExecutor


class ReportRegistry:

    def __init__(
        self,
        executors: dict[ReportType, ReportExecutor],
    ):
        self._executors = executors

    def get(
        self,
        report_type: ReportType,
    ) -> ReportExecutor:

        try:
            return self._executors[report_type]
        except KeyError:
            raise ValueError(
                f"Unsupported report: {report_type}")



# registry = ReportRegistry({
#     ReportType.MCC_SHIFT_SUMMARY:
#         MccShiftSummaryExecutor(session),

#     ReportType.MCC_LEDGER:
#         MccLedgerExecutor(session),

#     ReportType.MCC_SUMMARY:
#         MccSummaryExecutor(session),

#     ReportType.MCC_PAYMENT_SUMMARY:
#         MccPaymentSummaryExecutor(session),

#     ReportType.VLCC_SHIFT_SUMMARY:
#         VlccShiftSummaryExecutor(session),

#     ReportType.VLCC_MEMBER_LEDGER:
#         VlccMemberLedgerExecutor(session),

#     ReportType.DISPATCH_SUMMARY:
#         DispatchSummaryExecutor(session),
# })
#             )