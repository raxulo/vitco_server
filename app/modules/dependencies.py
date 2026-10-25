from app.modules.common.milk_quality.application.handler import MilkQualityConfigHandler
from app.modules.common.fixedrate_config.application.handler import FixedRateConfigHandler
from fastapi import Request
from app.modules.common.settings.application.handler import SettingsHandler
from app.modules.common.profile.application.services import ProfileService
from app.modules.mcc.application.handler import MccHandler
from app.modules.dashboard.application.handler import DashboardHandler
from app.modules.vlcc.application.handler import VlccHandler
from app.modules.media.application.services import MediaService
from app.modules.administration.application.handler import UserHandler
from app.modules.admin.application.handler import AdminHandler
from app.modules.auth.application.handler import LoginHandler
from app.modules.farmer.application.handler import FarmerHandler
from app.modules.collections.mcc_collection.application.handler import MccCollectionHandler
from app.modules.dataexchange.application.handler import ExcelJobHandler
from app.modules.dataexchange.application.uploads import ExcelUploadService
from app.modules.dataexchange.application.farmer_exchange import FarmerExchangeHandler
from app.modules.dataexchange.application.vlcc_exchange import VlccExchangeHandler
from app.modules.dataexchange.application.prodata_exchange import ProdataExchangeHandler
from app.modules.dataexchange.application.formula_exchange import FormulaExchangeHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.bootstrap.state import ApplicationState


class GetHandler:
    """
    Fast API access helpers.

    Zero allocation.
    Zero runtime overhead.
    """

    __slots__ = ()

    @staticmethod
    def state(request: Request) -> ApplicationState:
        return request.app.state.application


    @staticmethod
    def container(request: Request):
        return request.app.state.application.container

    @staticmethod
    def login_handler(request: Request)-> LoginHandler:
        return request.app.state.application.container.resolve(LoginHandler)

    @staticmethod
    def admin_handler(request: Request)-> AdminHandler:
        return request.app.state.application.container.resolve(AdminHandler)

    @staticmethod
    def user_handler(request: Request)-> UserHandler:
        return request.app.state.application.container.resolve(UserHandler)

    @staticmethod
    def media_service(request: Request)-> MediaService:
        return request.app.state.application.container.resolve(MediaService)

    @staticmethod
    def dashboard_handler(request: Request)-> DashboardHandler:
        return request.app.state.application.container.resolve(DashboardHandler)

    @staticmethod
    def mcc_handler(request: Request)-> MccHandler:
        return request.app.state.application.container.resolve(MccHandler)

    @staticmethod
    def vlcc_handler(request: Request)-> VlccHandler:
        return request.app.state.application.container.resolve(VlccHandler)

    @staticmethod
    def profile_service(request: Request)-> ProfileService:
        return request.app.state.application.container.resolve(ProfileService)

    @staticmethod
    def farmer_handler(request: Request)-> FarmerHandler:
        return request.app.state.application.container.resolve(FarmerHandler)

    @staticmethod
    def mcc_collection_handler(request: Request)-> MccCollectionHandler:
        return request.app.state.application.container.resolve(MccCollectionHandler)

    @staticmethod
    def excel_handler(request: Request) -> ExcelJobHandler:
        return request.app.state.application.container.resolve(ExcelJobHandler)

    @staticmethod
    def excel_upload_service(request: Request) -> ExcelUploadService:
        return request.app.state.application.container.resolve(ExcelUploadService)

    @staticmethod
    def farmer_exchange_handler(request: Request) -> FarmerExchangeHandler:
        return request.app.state.application.container.resolve(FarmerExchangeHandler)

    @staticmethod
    def vlcc_exchange_handler(request: Request) -> VlccExchangeHandler:
        return request.app.state.application.container.resolve(VlccExchangeHandler)

    @staticmethod
    def prodata_exchange_handler(request: Request) -> ProdataExchangeHandler:
        return request.app.state.application.container.resolve(ProdataExchangeHandler)

    @staticmethod
    def formula_exchange_handler(request: Request) -> FormulaExchangeHandler:
        return request.app.state.application.container.resolve(FormulaExchangeHandler)


    @staticmethod
    def settings_handler(request: Request)-> SettingsHandler:
        return request.app.state.application.container.resolve(SettingsHandler)

    @staticmethod
    def fixed_rate_config_handler(request: Request)-> FixedRateConfigHandler:
        return request.app.state.application.container.resolve(FixedRateConfigHandler)

    @staticmethod
    def milk_quality_config_handler(request: Request)-> MilkQualityConfigHandler:
        return request.app.state.application.container.resolve(MilkQualityConfigHandler)

    @staticmethod
    def vlcc_collection_handler(request: Request):
        from app.modules.collections.vlcc_collection.application.handler import VlccCollectionHandler
        return request.app.state.application.container.resolve(VlccCollectionHandler)

    @staticmethod
    def ratechart_handler(request: Request):
        from app.modules.ratechart.application.handler import RateChartHandler
        return request.app.state.application.container.resolve(RateChartHandler)

    @staticmethod
    def unit_master_handler(request: Request):
        from app.modules.masters.units.application.handler import UnitMasterHandler
        return request.app.state.application.container.resolve(UnitMasterHandler)

    @staticmethod
    def item_master_handler(request: Request):
        from app.modules.masters.items.application.handler import ItemMasterHandler
        return request.app.state.application.container.resolve(ItemMasterHandler)

    @staticmethod
    def route_master_handler(request: Request):
        from app.modules.masters.route.application.handler import RouteMasterHandler
        return request.app.state.application.container.resolve(RouteMasterHandler)

    @staticmethod
    def report_service(request: Request):
        from app.modules.reports.application.services import ReportService
        return request.app.state.application.container.resolve(ReportService)

    @staticmethod
    def dispatch_handler(request: Request):
        from app.modules.collections.vlcc_collection.application.dispatch_handler import DispatchHandler
        return request.app.state.application.container.resolve(DispatchHandler)

    @staticmethod
    def device_item_version_handler(request: Request):
        from app.modules.common.device_item_version.application.handler import DeviceItemVersionHandler
        return request.app.state.application.container.resolve(DeviceItemVersionHandler)

    @staticmethod
    def payment_posting_service(request: Request):
        from app.modules.payments.application.service import PaymentPostingService
        return request.app.state.application.container.resolve(PaymentPostingService)

    @staticmethod
    def advance_item_service(request: Request):
        from app.modules.advanceditem.application.handler import AdvanceService
        return request.app.state.application.container.resolve(AdvanceService)

    @staticmethod
    def marketplace_handler(request: Request):
        from app.modules.marketplace.application.handler import MarketplaceCommandHandler
        return request.app.state.application.container.resolve(MarketplaceCommandHandler)


    # @staticmethod
    # def user(request: Request):
    #     return request.app.state.application.container.user

    # @staticmethod
    # def file(request: Request):
    #     return request.app.state.application.container.file