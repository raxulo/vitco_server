"""
RealTimeTransfer
================

Module Configurator

Registers module handlers and repositories in the Service Container.

Python 3.13+
"""

from app.modules.common.profile.application.services import ProfileService
from app.modules.dashboard.application.handler import DashboardHandler
from app.modules.dashboard.infrastructure.repository import DashboardRepository
from app.modules.common.device_item_version.infrastructure.repository import DeviceItemVersionRepository
from app.modules.common.device_item_version.application.handler import DeviceItemVersionHandler
from app.modules.common.address.application.handler import AddressHandler
from app.modules.common.address.infrastructure.repository import AddressRepository
from app.modules.common.bank.application.handler import BankAccountHandler
from app.modules.common.bank.infrastructure.repository import BankAccountRepository
from app.core.container.container import ServiceContainer
from app.modules.mcc.application.handler import MccHandler
from app.modules.mcc.infrastructure.repository import MccRepository
from app.modules.administration.application.handler import UserHandler
from app.modules.admin.infrastructure.repository import AdminRepository
from app.modules.admin.application.handler import AdminHandler

from app.modules.common.fixedrate_config.application.handler import FixedRateConfigHandler
from app.modules.common.fixedrate_config.infrastructure.repository import FixedRateConfigRepository
from app.modules.common.milk_quality.application.handler import MilkQualityConfigHandler
from app.modules.common.milk_quality.infrastructure.repository import MilkQualityConfigRepository
from app.modules.common.settings.application.handler import SettingsHandler
from app.modules.common.settings.infrastructure.repository import SettingsRepository
from app.modules.vlcc.application.handler import VlccHandler
from app.modules.vlcc.infrastructure.repository import VlccRepository
from app.modules.farmer.application.handler import FarmerHandler
from app.modules.farmer.infrastructure.repository import FarmerRepository
from app.modules.ratechart.application.handler import RateChartHandler
from app.modules.ratechart.infrastructure.repository import RateChartRepository
from app.modules.masters.route.application.handler import RouteMasterHandler
from app.modules.masters.route.infrastructure.repository import RouteMasterRepository
from app.modules.masters.items.application.handler import ItemMasterHandler
from app.modules.masters.items.infrastructure.repository import ItemMasterRepository
from app.modules.masters.units.application.handler import UnitMasterHandler
from app.modules.masters.units.infrastructure.repository import UnitMasterRepository
from app.modules.masters.advanced.application.handler import AdvanceHandler
from app.modules.masters.advanced.infrastructure.repository import AdvanceRepository
from app.modules.advanceditem.infrastructure.repository import AdvanceRecordRepository
from app.modules.advanceditem.application.handler import AdvanceService
from app.modules.collections.mcc_collection.application.handler import MccCollectionHandler
from app.modules.collections.mcc_collection.infrastructure.repository import MccCollectionRepository
from app.modules.collections.vlcc_collection.application.handler import VlccCollectionHandler
from app.modules.collections.vlcc_collection.infrastructure.repository import VlccCollectionRepository
from app.modules.collections.vlcc_collection.infrastructure.dispatch_repository import DispatchRepository
from app.modules.collections.vlcc_collection.application.dispatch_handler import DispatchHandler
from app.modules.media.infrastructure.media_repository import MediaRepository
from app.modules.media.application.services import MediaService
from app.config.filesystem import storage_config
from app.modules.media.domain.local_storage import LocalStorage
from app.modules.products.application.handler import ProductHandler
from app.modules.products.infrastructure.repository import ProductRepository
from app.modules.dataexchange.infrastructure.repository import ExcelJobRepository
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage
from app.modules.dataexchange.infrastructure.file_guard import FileGuard
from app.modules.dataexchange.application.handler import ExcelJobHandler
from app.modules.dataexchange.application.uploads import ExcelUploadService
from app.modules.dataexchange.application.farmer_exchange import FarmerExchangeHandler
from app.modules.dataexchange.application.vlcc_exchange import VlccExchangeHandler
from app.modules.dataexchange.application.prodata_exchange import ProdataExchangeHandler
from app.modules.dataexchange.infrastructure.vlcc_scope import VlccScope
from app.modules.dataexchange.infrastructure.owner_scope import OwnerScope
from app.modules.dataexchange.infrastructure.ratechart_scope import RateChartScope
from app.worker.supervisor import WorkerSupervisor

from app.modules.payments.application.service import PaymentPostingService
from app.bootstrap.state import ApplicationState
from app.config.settings import settings
from app.modules.auth.application.handler import LoginHandler
from app.modules.administration.infrastructure.repository import UserRepository
from app.modules.auth.infrastructure.password import PasswordService
from app.modules.auth.infrastructure.jwt import JWTService


class ModuleConfigurator:
    """
    Registers all application Handlers.
    """

    __slots__ = ()

    @classmethod
    def configure(cls, state: ApplicationState) -> None:
        _container = state.container
        cls._repo_config(_container)
        cls._media_register(_container)
        cls._dataexchange_register(_container)
        cls._service_register(_container)
        cls._handler_config(_container)


    @classmethod
    def _service_register(cls, container: ServiceContainer):
        get_user_repo = container.resolve(UserRepository)
        get_address_repo = container.resolve(AddressRepository)
        get_bank_repo = container.resolve(BankAccountRepository)
        get_password_ser= container.resolve(PasswordService)
        media_serv = container.resolve(MediaService)
        
        profile_service = ProfileService(
            database=container.database,
            user_repository=get_user_repo,
            address_repository=get_address_repo,
            bank_repository=get_bank_repo,
            media_service=media_serv,
            password=get_password_ser,
        )
        container.register(ProfileService, profile_service)

        payment_service = PaymentPostingService(database=container.database)
        container.register(PaymentPostingService, payment_service)

    @classmethod
    def _repo_config(cls, container: ServiceContainer):
        cls._password_register(container)
        cls._jwt_register(container)

        _database = container.database
        
        repository = UserRepository(_database)
        container.register(UserRepository, repository)

        repository = AdminRepository(_database)
        container.register(AdminRepository, repository)

        repository = BankAccountRepository(_database)
        container.register(BankAccountRepository, repository)

        repository = AddressRepository(_database)
        container.register(AddressRepository, repository)



        repository = MccRepository(_database)
        container.register(MccRepository, repository)

        repository = FixedRateConfigRepository(_database)
        container.register(FixedRateConfigRepository, repository)

        repository = MilkQualityConfigRepository(_database)
        container.register(MilkQualityConfigRepository, repository)

        repository = SettingsRepository(_database)
        container.register(SettingsRepository, repository)

        repository = VlccRepository(_database)
        container.register(VlccRepository, repository)

        repository = FarmerRepository(_database)
        container.register(FarmerRepository, repository)

        repository = RateChartRepository(_database)
        container.register(RateChartRepository, repository)

        repository = RouteMasterRepository(_database)
        container.register(RouteMasterRepository, repository)

        repository = ItemMasterRepository(_database)
        container.register(ItemMasterRepository, repository)

        repository = UnitMasterRepository(_database)
        container.register(UnitMasterRepository, repository)

        repository = AdvanceRepository(_database)
        container.register(AdvanceRepository, repository)

        repository = AdvanceRecordRepository(_database)
        container.register(AdvanceRecordRepository, repository)

        repository = MccCollectionRepository(_database)
        container.register(MccCollectionRepository, repository)

        repository = VlccCollectionRepository(_database)
        container.register(VlccCollectionRepository, repository)

        dispatch_repository = DispatchRepository(_database)
        container.register(DispatchRepository, dispatch_repository)

        if not container.storage:
            container.storage = LocalStorage(
                root_path=str(storage_config.media),
            )

        media_repo = MediaRepository(_database)
        container.register(MediaRepository, media_repo)

        repository = ProductRepository(_database)
        container.register(ProductRepository, repository)

        repository = DashboardRepository(_database)
        container.register(DashboardRepository, repository)

        repository = DeviceItemVersionRepository(_database)
        container.register(DeviceItemVersionRepository, repository)

        from app.modules.marketplace.infrastructure.repository import MarketplaceRepository
        repository = MarketplaceRepository(_database)
        container.register(MarketplaceRepository, repository)

        repository = ExcelJobRepository(_database)
        container.register(ExcelJobRepository, repository)

    @classmethod
    def _dataexchange_register(cls, container: ServiceContainer):
        """Excel import / export infrastructure, shared by the API and the exchange worker."""
        mb = 1024 * 1024
        storage = ExchangeStorage(
            settings.EXCHANGE_PATH,
            max_upload_bytes=settings.EXCHANGE_MAX_UPLOAD_MB * mb,
            min_free_bytes=settings.EXCHANGE_MIN_FREE_DISK_MB * mb,
        )
        container.register(ExchangeStorage, storage)
        container.register(FileGuard, FileGuard(max_uncompressed_bytes=settings.EXCHANGE_MAX_UNCOMPRESSED_MB * mb))

    @classmethod
    def _handler_config(cls, container: ServiceContainer):
        cls._administration(container)
        cls._login(container)
        cls._admin(container)
        cls._bank_account(container)
        cls._address(container)
        cls._mcc(container)
        cls._fixed_rate_config(container)
        cls._milk_quality_config(container)
        cls._settings(container)
        cls._vlcc(container)
        cls._farmer(container)
        cls._rate_chart(container)
        cls._route_master(container)
        cls._item_master(container)
        cls._unit_master(container)
        cls._advance(container)
        cls._advance_item(container)
        cls._mcc_collection(container)
        cls._vlcc_collection(container)
        cls._product(container)
        cls._dashboard(container)
        cls._device_item_version(container)
        cls._reports(container)
        cls._marketplace(container)
        cls._dataexchange(container)

    @classmethod
    def _dataexchange(cls, container: ServiceContainer):
        handler = ExcelJobHandler(
            database=container.database,
            repository=container.resolve(ExcelJobRepository),
            storage=container.resolve(ExchangeStorage),
            guard=container.resolve(FileGuard),
            max_queued=settings.EXCHANGE_MAX_QUEUED_JOBS,
        )
        container.register(ExcelJobHandler, handler)

        uploads = ExcelUploadService(
            storage=container.resolve(ExchangeStorage),
            guard=container.resolve(FileGuard),
            chunk_size=settings.EXCHANGE_UPLOAD_CHUNK_MB * 1024 * 1024,
        )
        container.register(ExcelUploadService, uploads)

        scope = VlccScope(container.database, container.resolve(FarmerRepository))
        container.register(VlccScope, scope)
        container.register(FarmerExchangeHandler, FarmerExchangeHandler(
            database=container.database,
            jobs=handler,
            scope=scope,
            uploads=uploads,
            storage=container.resolve(ExchangeStorage),
        ))

        owner_scope = OwnerScope(container.database)
        container.register(OwnerScope, owner_scope)
        container.register(VlccExchangeHandler, VlccExchangeHandler(
            database=container.database,
            jobs=handler,
            scope=owner_scope,
            uploads=uploads,
            storage=container.resolve(ExchangeStorage),
        ))

        ratechart_scope = RateChartScope(container.database)
        container.register(RateChartScope, ratechart_scope)
        container.register(ProdataExchangeHandler, ProdataExchangeHandler(
            database=container.database,
            jobs=handler,
            scope=ratechart_scope,
            uploads=uploads,
            storage=container.resolve(ExchangeStorage),
        ))


        supervisor = WorkerSupervisor(
            database=container.database,
            repository=container.resolve(ExcelJobRepository),
            storage=container.resolve(ExchangeStorage),
            enabled=settings.EXCHANGE_WORKER_ENABLED,
            log_dir=settings.LOG_PATH,
            heartbeat_timeout_s=settings.EXCHANGE_HEARTBEAT_TIMEOUT_S,
            file_ttl_hours=settings.EXCHANGE_FILE_TTL_HOURS,
        )
        container.register(WorkerSupervisor, supervisor)

    @classmethod
    def _marketplace(cls, container: ServiceContainer):
        from app.modules.marketplace.infrastructure.repository import MarketplaceRepository
        from app.modules.marketplace.application.handler import MarketplaceCommandHandler
        handler = MarketplaceCommandHandler(
            database=container.database,
            repository=container.resolve(MarketplaceRepository),
            media_service=container.resolve(MediaService),
        )
        container.register(MarketplaceCommandHandler, handler)



    @classmethod
    def _password_register(cls, container: ServiceContainer):
        password_service = PasswordService()
        container.register(PasswordService, password_service)

    @classmethod
    def _jwt_register(cls, container: ServiceContainer):
        jwt_service = JWTService(secret_key=settings.SECRET_KEY)
        container.register(JWTService, jwt_service)

    @classmethod
    def _get_password_service(cls,container: ServiceContainer) -> PasswordService:
        return container.resolve(PasswordService)

    @classmethod
    def _get_jwt_service(cls,container: ServiceContainer) -> JWTService:
        return container.resolve(JWTService)

    @classmethod
    def _administration(cls, container: ServiceContainer):
        password_service = cls._get_password_service(container)

        user_handler = UserHandler(
            database=container.database,
            repository=container.resolve(UserRepository),
            password=password_service,
            media_service=container.resolve(MediaService),
        )
        container.register(UserHandler, user_handler)

    @classmethod
    def _login(cls, container: ServiceContainer):
        password_service = cls._get_password_service(container)
        jwt_service = cls._get_jwt_service(container)

        login_handler = LoginHandler(
            repository=container.resolve(UserRepository),
            password_service=password_service,
            jwt_service=jwt_service,
        )
        container.register(LoginHandler, login_handler)

    @classmethod
    def _admin(cls, container: ServiceContainer):
        password_service = cls._get_password_service(container)
        jwt_service = cls._get_jwt_service(container)

        admin_handler = AdminHandler(
            repository=container.resolve(AdminRepository),
            password_service=password_service,
            jwt_service=jwt_service,
            profile_service=container.resolve(ProfileService),
        )
        container.register(AdminHandler, admin_handler)

    @classmethod
    def _mcc(cls, container: ServiceContainer):
        mcc_handler = MccHandler(
            database=container.database,
            user_repository=container.resolve(UserRepository),
            mcc_repository=container.resolve(MccRepository),
            address_repository=container.resolve(AddressRepository),
            bank_account_repository=container.resolve(BankAccountRepository),
            settings_repository=container.resolve(SettingsRepository),
            milk_quality_config_repository=container.resolve(MilkQualityConfigRepository),
            fixed_rate_config_repository=container.resolve(FixedRateConfigRepository),
            password=cls._get_password_service(container),
            profile_service=container.resolve(ProfileService),
        )
        container.register(MccHandler, mcc_handler)

    @classmethod
    def _bank_account(cls, container: ServiceContainer):
        bank_account_handler = BankAccountHandler(
            database=container.database,
            repository=container.resolve(BankAccountRepository),
        )
        container.register(BankAccountHandler, bank_account_handler)

    @classmethod
    def _address(cls, container: ServiceContainer):
        address_handler = AddressHandler(
            database=container.database,
            repository=container.resolve(AddressRepository),
        )
        container.register(AddressHandler, address_handler)

    @classmethod
    def _fixed_rate_config(cls, container: ServiceContainer):
        handler = FixedRateConfigHandler(
            database=container.database,
            repository=container.resolve(FixedRateConfigRepository),
        )
        container.register(FixedRateConfigHandler, handler)

    @classmethod
    def _milk_quality_config(cls, container: ServiceContainer):
        handler = MilkQualityConfigHandler(
            database=container.database,
            repository=container.resolve(MilkQualityConfigRepository),
        )
        container.register(MilkQualityConfigHandler, handler)

    @classmethod
    def _settings(cls, container: ServiceContainer):
        handler = SettingsHandler(
            repository=container.resolve(SettingsRepository),
        )
        container.register(SettingsHandler, handler)

    @classmethod
    def _vlcc(cls, container: ServiceContainer):
        handler = VlccHandler(
            database=container.database,
            user_repository=container.resolve(UserRepository),
            vlcc_repository=container.resolve(VlccRepository),
            settings_repository=container.resolve(SettingsRepository),
            milk_quality_config_repository=container.resolve(MilkQualityConfigRepository),
            password=cls._get_password_service(container),
            profile_service=container.resolve(ProfileService)
        )
        container.register(VlccHandler, handler)

    @classmethod
    def _farmer(cls, container: ServiceContainer):
        handler = FarmerHandler(
            database=container.database,
            user_repository=container.resolve(UserRepository),
            farmer_repository=container.resolve(FarmerRepository),
            profile_service=container.resolve(ProfileService)
        )
        container.register(FarmerHandler, handler)

    @classmethod
    def _rate_chart(cls, container: ServiceContainer):
        handler = RateChartHandler(
            database=container.database,
            repository=container.resolve(RateChartRepository),
        )
        container.register(RateChartHandler, handler)

    @classmethod
    def _route_master(cls, container: ServiceContainer):
        handler = RouteMasterHandler(
            database=container.database,
            repository=container.resolve(RouteMasterRepository),
        )
        container.register(RouteMasterHandler, handler)

    @classmethod
    def _item_master(cls, container: ServiceContainer):
        handler = ItemMasterHandler(
            database=container.database,
            repository=container.resolve(ItemMasterRepository),
        )
        container.register(ItemMasterHandler, handler)

    @classmethod
    def _unit_master(cls, container: ServiceContainer):
        handler = UnitMasterHandler(
            database=container.database,
            repository=container.resolve(UnitMasterRepository),
        )
        container.register(UnitMasterHandler, handler)

    @classmethod
    def _advance(cls, container: ServiceContainer):
        handler = AdvanceHandler(
            database=container.database,
            repository=container.resolve(AdvanceRepository),
        )
        container.register(AdvanceHandler, handler)

    @classmethod
    def _advance_item(cls, container: ServiceContainer):
        service = AdvanceService(
            advance_record_repository=container.resolve(AdvanceRecordRepository),
            payment_posting_service=container.resolve(PaymentPostingService),
            item_master_repository=container.resolve(ItemMasterRepository),
        )
        container.register(AdvanceService, service)

    @classmethod
    def _mcc_collection(cls, container: ServiceContainer):
        handler = MccCollectionHandler(
            database=container.database,
            repository=container.resolve(MccCollectionRepository),
            payment_service=container.resolve(PaymentPostingService),
        )
        container.register(MccCollectionHandler, handler)

    @classmethod
    def _vlcc_collection(cls, container: ServiceContainer):
        handler = VlccCollectionHandler(
            database=container.database,
            repository=container.resolve(VlccCollectionRepository),
            payment_service=container.resolve(PaymentPostingService),
        )
        container.register(VlccCollectionHandler, handler)

        dispatch_handler = DispatchHandler(
            database=container.database,
            repository=container.resolve(DispatchRepository),
        )
        container.register(DispatchHandler, dispatch_handler)

    @classmethod
    def _media_register(cls, container: ServiceContainer):
        service = MediaService(
            repository=container.resolve(MediaRepository),
            storage=container.storage,
        )
        container.register(MediaService, service)

    @classmethod
    def _product(cls, container: ServiceContainer):
        handler = ProductHandler(
            database=container.database,
            repository=container.resolve(ProductRepository),
        )
        container.register(ProductHandler, handler)

    @classmethod
    def _dashboard(cls, container: ServiceContainer):
        handler = DashboardHandler(
            repository=container.resolve(DashboardRepository),
        )
        container.register(DashboardHandler, handler)

    @classmethod
    def _device_item_version(cls, container: ServiceContainer):
        handler = DeviceItemVersionHandler(
            repository=container.resolve(DeviceItemVersionRepository),
        )
        container.register(DeviceItemVersionHandler, handler)

    @classmethod
    def _reports(cls, container: ServiceContainer):
        from app.modules.reports.application.registry import ReportRegistry
        from app.modules.reports.application.services import ReportService
        from app.modules.reports.domain.enums import ReportType
        from app.modules.reports.executors.mcc.mcc_shift_summary import MccShiftSummaryExecutor
        from app.modules.reports.executors.mcc.mcc_weight_shift_summary import MccWeightShiftSummaryExecutor
        from app.modules.reports.executors.mcc.mcc_weight_date_wise import MccWeightDateWiseExecutor
        from app.modules.reports.executors.mcc.mcc_weight_route_wise import MccWeightRouteWiseExecutor
        from app.modules.reports.executors.mcc.mcc_weight_vlcc_wise import MccWeightVlccWiseExecutor
        from app.modules.reports.executors.mcc.mcc_vlcc_bill import MccVlccBillExecutor
        from app.modules.reports.executors.mcc.mcc_bill_comparison import MccBillComparisonExecutor
        from app.modules.reports.executors.mcc.mcc_payment_summary import MccPaymentSummaryExecutor
        from app.modules.reports.executors.mcc.mcc_milk_bill_summary import MccMilkBillSummaryExecutor
        from app.modules.reports.executors.mcc.mcc_duplicate_receipt import MccDuplicateReceiptExecutor
        from app.modules.reports.executors.mcc.mcc_weight_duplicate_receipt import MccWeightDuplicateReceiptExecutor
        from app.modules.reports.executors.mcc.mcc_fixed_rate_summary import (
            MccFixedRatePaymentSummaryExecutor,
            MccFixedRateSummaryExecutor,
        )
        from app.modules.reports.executors.vlcc.vlcc_shift_summary import VlccShiftSummaryExecutor
        from app.modules.reports.executors.vlcc.vlcc_member_ledger import VlccMemberLedgerExecutor
        from app.modules.reports.executors.vlcc.vlcc_milk_bill_summary import VlccMilkBillSummaryExecutor
        from app.modules.reports.executors.vlcc.vlcc_duplicate_receipt import VlccDuplicateReceiptExecutor
        from app.modules.reports.executors.vlcc.dispatch_summary import DispatchSummaryExecutor

        executors = {
            ReportType.MCC_SHIFT_SUMMARY: MccShiftSummaryExecutor(container.database),
            ReportType.MCC_WEIGHT_SHIFT_SUMMARY: MccWeightShiftSummaryExecutor(container.database),
            ReportType.MCC_WEIGHT_DATE_WISE: MccWeightDateWiseExecutor(container.database),
            ReportType.MCC_WEIGHT_ROUTE_WISE: MccWeightRouteWiseExecutor(container.database),
            ReportType.MCC_WEIGHT_VLCC_WISE: MccWeightVlccWiseExecutor(container.database),
            ReportType.MCC_VLCC_BILL: MccVlccBillExecutor(container.database),
            ReportType.MCC_PAYMENT_SUMMARY: MccPaymentSummaryExecutor(container.database),
            ReportType.MCC_MILK_BILL_SUMMARY: MccMilkBillSummaryExecutor(container.database),
            ReportType.MCC_DUPLICATE_RECEIPT: MccDuplicateReceiptExecutor(container.database),
            ReportType.MCC_WEIGHT_DUPLICATE_RECEIPT: MccWeightDuplicateReceiptExecutor(container.database),
            ReportType.MCC_FIXED_RATE_SUMMARY: MccFixedRateSummaryExecutor(container.database),
            ReportType.MCC_FIXED_RATE_PAYMENT_SUMMARY: MccFixedRatePaymentSummaryExecutor(container.database),
            # Fixed-rate MCC's "Member Ledger" behaves exactly like the MCC member ledger
            ReportType.MCC_LEDGER: MccVlccBillExecutor(container.database),
            ReportType.MCC_BILL_COMPARISON: MccBillComparisonExecutor(
                container.database,
                container.resolve(RateChartHandler),
            ),
            ReportType.VLCC_SHIFT_SUMMARY: VlccShiftSummaryExecutor(container.database),
            ReportType.VLCC_MEMBER_LEDGER: VlccMemberLedgerExecutor(container.database),
            ReportType.VLCC_MILK_BILL_SUMMARY: VlccMilkBillSummaryExecutor(container.database),
            ReportType.VLCC_DUPLICATE_RECEIPT: VlccDuplicateReceiptExecutor(container.database),
            ReportType.DISPATCH_SUMMARY: DispatchSummaryExecutor(container.database),
        }
        registry = ReportRegistry(executors)
        service = ReportService(registry)
        container.register(ReportService, service)