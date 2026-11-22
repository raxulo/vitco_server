from fastapi import APIRouter

from app.api.v1.routers.auth import router as auth_router
from app.api.v1.routers.collection import router as collection_router
from app.api.v1.routers.dashboard import router as dashboard_router
from app.api.v1.routers.farmer import router as farmer_router
from app.api.v1.routers.mcc import router as mcc_router
from app.api.v1.routers.media import router as media_router
from app.api.v1.routers.profile import router as profile_router
from app.api.v1.routers.ratechart import router as ratechart_router
from app.api.v1.routers.sync import router as sync_router
from app.api.v1.routers.vlcc import router as vlcc_router
from app.api.v1.routers.payment import router as payment_router
from app.api.v1.routers.item_master import router as item_master_router
from app.api.v1.routers.unit_master import router as unit_master_router
from app.api.v1.routers.advance_item import router as advance_item_router
from app.api.v1.routers.marketplace import router as marketplace_router
from app.api.v1.routers.reports import router as reports_router
from app.api.v1.routers.dispatch import router as dispatch_router
from app.api.v1.routers.excel import router as excel_router
from app.api.v1.routers.support import router as support_router
from app.api.v1.routers.notifications import router as notifications_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(media_router)
api_v1_router.include_router(mcc_router)
api_v1_router.include_router(vlcc_router)
api_v1_router.include_router(farmer_router, prefix="/farmers")
api_v1_router.include_router(farmer_router, prefix="/members")
api_v1_router.include_router(ratechart_router)
api_v1_router.include_router(sync_router)
api_v1_router.include_router(profile_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(collection_router)
api_v1_router.include_router(payment_router)
api_v1_router.include_router(item_master_router)
api_v1_router.include_router(unit_master_router)
api_v1_router.include_router(advance_item_router)
api_v1_router.include_router(marketplace_router)
api_v1_router.include_router(reports_router)
api_v1_router.include_router(dispatch_router)
api_v1_router.include_router(dispatch_router, prefix="/vlcc")
api_v1_router.include_router(excel_router)
api_v1_router.include_router(support_router)
api_v1_router.include_router(notifications_router)






