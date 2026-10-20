from datetime import datetime
from fastapi import Request
from app.modules.dependencies import GetHandler
from app.web.framework.renderer import Renderer
from app.core.clock import now_naive_ist

class PaymentsController:
    __slots__ = ()

    @staticmethod
    async def overview_page(request: Request):
        user = request.state.user
        service = GetHandler.payment_posting_service(request)
        
        balance = await service.get_user_balance(user.id)
        raw_outstanding = await service.get_user_outstanding(user.id)
        raw_recent = await service.transaction_history_by_user(user.id, limit=5)
        
        to_collect = []
        to_pay = []
        total_to_collect = 0.0
        total_to_pay = 0.0
        
        for item in raw_outstanding:
            val = float(item.balance)
            formatted_item = {
                "counterparty_name": item.counterparty_name or "System",
                "balance": abs(val),
                "updated_at": item.updated_at.strftime("%Y-%m-%d") if item.updated_at else "-",
            }
            if val > 0:
                to_collect.append(formatted_item)
                total_to_collect += val
            elif val < 0:
                to_pay.append(formatted_item)
                total_to_pay += abs(val)

        recent_entries = []
        for entry in raw_recent:
            recent_entries.append({
                "id": str(entry.id),
                "transfer_id": str(entry.transfer_id),
                "counterparty_name": entry.counterparty_name or "System",
                "entry_type": "Credit" if entry.entry_type == 2 else "Debit",
                "amount": entry.amount,
                "balance_before": entry.balance_before,
                "balance_after": entry.balance_after,
                "created_at": entry.created_at.strftime("%Y-%m-%d %H:%M") if entry.created_at else "-",
            })

        return Renderer.page(
            request=request,
            template="pages/payments/overview.html",
            model={
                "balance": balance,
                "to_collect": to_collect,
                "to_pay": to_pay,
                "total_to_collect": total_to_collect,
                "total_to_pay": total_to_pay,
                "recent_entries": recent_entries,
                "user": user,
            }
        )

    @staticmethod
    async def history_page(
        request: Request,
        start_date: str = "",
        end_date: str = "",
        user_id: str = "",
    ):
        user = request.state.user
        service = GetHandler.payment_posting_service(request)
        db_manager = request.app.state.application.container.database
        
        from datetime import datetime
        from app.modules.administration.infrastructure.models import UserModel
        from sqlalchemy import select
        from uuid import UUID

        start_dt = None
        end_dt = None
        if start_date.strip():
            try:
                start_dt = datetime.strptime(start_date.strip(), "%Y-%m-%d")
            except ValueError:
                pass
        if end_date.strip():
            try:
                end_dt = datetime.strptime(end_date.strip() + " 23:59:59", "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        from app.modules.administration.domain.enums import Role
        from app.modules.administration.infrastructure.hierarchy import Hierarchy
        from sqlalchemy import or_

        target_user = None
        selected_user_id = ""
        selected_user_name = ""
        # Farmers only ever see their own history
        is_farmer = user.role_type == Role.FARMER

        if user_id.strip() and not is_farmer:
            try:
                u_uuid = UUID(user_id.strip())
                stmt = select(UserModel.id, UserModel.name, UserModel.mobile).where(UserModel.id == u_uuid)
                # Another user's history only within the viewer's hierarchy
                if user.role_type != Role.SUPER_ADMIN:
                    allowed = [UserModel.id.in_(Hierarchy.controlled_users(user))]
                    farmers = Hierarchy.farmer_users(user)
                    if farmers is not None:
                        allowed.append(UserModel.id.in_(farmers))
                    stmt = stmt.where(or_(*allowed))
                res = await db_manager.session.execute(stmt)
                target_user = res.one_or_none()
                if target_user:
                    selected_user_id = str(target_user.id)
                    selected_user_name = f"{target_user.name} ({target_user.mobile})" if getattr(target_user, 'mobile', None) else target_user.name
            except Exception:
                pass

        # Default to loggedin user if no user selected or target_user not found
        active_user = target_user if target_user else user

        # Fetch ledger entries for the active user
        entries = await service.transaction_history_by_user(
            user_id=active_user.id,
            start_date=start_dt,
            end_date=end_dt,
            limit=100,
        )
        
        # A farmer's "My Payments" lists only money received (credits)
        if is_farmer:
            entries = [e for e in entries if e.entry_type == 2]

        # Format items for UI
        formatted_entries = []
        for entry in entries:
            source_type_val = getattr(entry, "source_type", None)
            method_val = getattr(entry, "payment_method", None)
            
            s_type = int(source_type_val) if source_type_val is not None else 0
            p_method = int(method_val) if method_val is not None else 0
            
            if s_type == 2:
                payment_type_label = "Milk Payment"
                badge_bg = "#dbeafe"
                badge_color = "#1e40af"
                icon_class = "fa-cow"
            elif p_method == 2:
                payment_type_label = "UPI"
                badge_bg = "#dcfce7"
                badge_color = "#15803d"
                icon_class = "fa-mobile-screen-button"
            elif p_method == 3:
                payment_type_label = "Bank Transfer"
                badge_bg = "#e0f2fe"
                badge_color = "#0369a1"
                icon_class = "fa-building-columns"
            elif p_method == 4:
                payment_type_label = "Online"
                badge_bg = "#f3e8ff"
                badge_color = "#7e22ce"
                icon_class = "fa-globe"
            elif p_method == 1:
                payment_type_label = "Offline (Cash)"
                badge_bg = "#fef9c3"
                badge_color = "#854d0e"
                icon_class = "fa-money-bill-wave"
            elif s_type == 4:
                payment_type_label = "Advance"
                badge_bg = "#ffedd5"
                badge_color = "#c2410c"
                icon_class = "fa-hand-holding-dollar"
            elif s_type == 3:
                payment_type_label = "Adjustment"
                badge_bg = "#f3f4f6"
                badge_color = "#374151"
                icon_class = "fa-sliders"
            else:
                payment_type_label = "Manual"
                badge_bg = "#f1f5f9"
                badge_color = "#475569"
                icon_class = "fa-receipt"

            formatted_entries.append({
                "id": str(entry.id),
                "transfer_id": str(entry.transfer_id),
                "counterparty_name": entry.counterparty_name or "System",
                "entry_type": "Credit" if entry.entry_type == 2 else "Debit",  # LedgerEntryType.CREDIT is 2, DEBIT is 1
                "amount": entry.amount,
                "balance_before": entry.balance_before,
                "balance_after": entry.balance_after,
                "payment_type_label": payment_type_label,
                "badge_bg": badge_bg,
                "badge_color": badge_color,
                "icon_class": icon_class,
                "created_at": entry.created_at.strftime("%Y-%m-%d %H:%M") if entry.created_at else "-",
            })
            
        return Renderer.page(
            request=request,
            template="pages/payments/history.html",
            model={
                "entries": formatted_entries,
                "user": user,
                "active_user": active_user,
                "selected_user_id": selected_user_id,
                "selected_user_name": selected_user_name,
                "start_date": start_date,
                "end_date": end_date,
                "is_filtered_user": target_user is not None and target_user.id != user.id,
                "is_farmer": is_farmer,
            }
        )

    @staticmethod
    async def give_receive_page(
        request: Request,
        target_user_id: str = None,
        amount: str = None,
    ):
        user = request.state.user
        prefilled_user = None
        
        if target_user_id:
            db_manager = request.app.state.application.container.database
            from app.modules.administration.infrastructure.models import UserModel
            from sqlalchemy import select
            from uuid import UUID
            try:
                stmt = select(UserModel.id, UserModel.name, UserModel.mobile).where(UserModel.id == UUID(target_user_id))
                res = await db_manager.session.execute(stmt)
                u = res.one_or_none()
                if u:
                    prefilled_user = {"id": str(u.id), "name": u.name, "mobile": u.mobile}
            except Exception:
                pass
        
        return Renderer.page(
            request=request,
            template="pages/payments/give_receive.html",
            model={
                "prefilled_user": prefilled_user,
                "prefilled_amount": amount,
                "error": None,
                "success": None,
            }
        )

    @staticmethod
    async def post_give_receive(request: Request):
        user = request.state.user
        db_manager = request.app.state.application.container.database
        service = GetHandler.payment_posting_service(request)
        
        form = await request.form()
        counterparty_id = form.get("counterparty_id")
        action_type = form.get("action_type")
        amount_str = form.get("amount", "0.0")
        method_str = form.get("payment_method", "1")
        reference = form.get("reference", "").strip()
        description = form.get("description", "").strip()
        
        from app.modules.administration.infrastructure.models import UserModel
        from sqlalchemy import select
        from decimal import Decimal
        import uuid
        from uuid import UUID
        from app.modules.payments.application.command import PostPaymentCommand
        from app.modules.payments.domain.enums import PaymentSourceType, PaymentMethod
        
        stmt = select(UserModel.id, UserModel.name, UserModel.mobile).where(UserModel.id != user.id).order_by(UserModel.name.asc())
        res = await db_manager.session.execute(stmt)
        users = [{"id": str(u.id), "name": u.name, "mobile": u.mobile} for u in res.all()]

        try:
            amount = Decimal(amount_str)
        except Exception:
            return Renderer.page(
                request=request,
                template="pages/payments/give_receive.html",
                model={
                    "users": users,
                    "error": "Invalid amount format.",
                    "success": None,
                }
            )

        if amount <= 0:
            return Renderer.page(
                request=request,
                template="pages/payments/give_receive.html",
                model={
                    "users": users,
                    "error": "Amount must be greater than zero.",
                    "success": None,
                }
            )

        if not counterparty_id:
            return Renderer.page(
                request=request,
                template="pages/payments/give_receive.html",
                model={
                    "users": users,
                    "error": "Please select a user.",
                    "success": None,
                }
            )

        try:
            cp_uuid = UUID(counterparty_id)
        except ValueError:
            return Renderer.page(
                request=request,
                template="pages/payments/give_receive.html",
                model={
                    "users": users,
                    "error": "Invalid user ID.",
                    "success": None,
                }
            )

        if action_type == "give":
            sender_id = cp_uuid
            receiver_id = user.id
        else:
            sender_id = user.id
            receiver_id = cp_uuid

        try:
            cmd = PostPaymentCommand(
                sender_id=sender_id,
                receiver_id=receiver_id,
                amount=amount,
                source_type=PaymentSourceType.MANUAL,
                payment_method=PaymentMethod(int(method_str)),
                idempotency_key=str(uuid.uuid4()),
                reference=reference if reference else None,
                description=description if description else None,
            )
            
            await service.post(cmd)
            
            return Renderer.page(
                request=request,
                template="pages/payments/give_receive.html",
                model={
                    "users": users,
                    "error": None,
                    "success": "Transaction successfully!",
                }
            )
        except Exception as e:
            return Renderer.page(
                request=request,
                template="pages/payments/give_receive.html",
                model={
                    "users": users,
                    "error": f"Failed to post transaction: {str(e)}",
                    "success": None,
                }
            )

    @staticmethod
    async def search_users_api(request: Request, q: str = ""):
        user = request.state.user
        db_manager = request.app.state.application.container.database
        
        from app.modules.administration.infrastructure.models import UserModel
        from sqlalchemy import select, or_
        from fastapi.responses import JSONResponse
        
        include_self_param = request.query_params.get("include_self", "true").lower()
        include_self = include_self_param in ("true", "1", "yes")

        stmt = select(UserModel.id, UserModel.name, UserModel.mobile)
        if not include_self:
            stmt = stmt.where(UserModel.id != user.id)

        if q.strip():
            keyword = f"%{q.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    UserModel.name.ilike(keyword),
                    UserModel.mobile.ilike(keyword)
                )
            )
            
        stmt = stmt.order_by(UserModel.name.asc()).limit(10)
        res = await db_manager.session.execute(stmt)
        users = [{"id": str(u.id), "name": u.name, "mobile": u.mobile or ""} for u in res.all()]
        
        return JSONResponse(content={"users": users})

    @staticmethod
    async def outstanding_page(request: Request):
        user = request.state.user
        service = GetHandler.payment_posting_service(request)
        
        outstanding_records = await service.get_user_outstanding(user_id=user.id)
        
        to_collect = sum(r.balance for r in outstanding_records if r.balance > 0)
        to_pay = sum(abs(r.balance) for r in outstanding_records if r.balance < 0)
        
        return Renderer.page(
            request=request,
            template="pages/payments/outstanding.html",
            model={
                "outstanding": outstanding_records,
                "to_collect": to_collect,
                "to_pay": to_pay,
            }
        )

    @staticmethod
    async def pair_statement_page(request: Request, counterparty_id: str = None):
        user = request.state.user
        db_manager = request.app.state.application.container.database
        
        from_user_id_param = request.query_params.get("from_user_id", "")
        counterparty_id_param = counterparty_id or request.query_params.get("counterparty_id", "")
        start_date = request.query_params.get("start_date", "")
        end_date = request.query_params.get("end_date", "")
        
        from datetime import timedelta
        
        start_dt = None
        end_dt = None
        
        if not start_date.strip() and not end_date.strip():
            now_dt = now_naive_ist()
            start_dt = now_dt - timedelta(days=7)
            # End date set to end of today
            end_dt = datetime.strptime(now_dt.strftime("%Y-%m-%d") + " 23:59:59", "%Y-%m-%d %H:%M:%S")
            start_date = start_dt.strftime("%Y-%m-%d")
            end_date = now_dt.strftime("%Y-%m-%d")
        else:
            if start_date.strip():
                try:
                    start_dt = datetime.strptime(start_date.strip(), "%Y-%m-%d")
                except ValueError:
                    pass
            if end_date.strip():
                try:
                    end_dt = datetime.strptime(end_date.strip() + " 23:59:59", "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
        
        from app.modules.administration.infrastructure.models import UserModel
        from sqlalchemy import select
        from uuid import UUID
        
        from_user = user
        if from_user_id_param.strip():
            try:
                f_uuid = UUID(from_user_id_param.strip())
                stmt = select(UserModel.id, UserModel.name, UserModel.mobile).where(UserModel.id == f_uuid)
                res = await db_manager.session.execute(stmt)
                fetched_from = res.one_or_none()
                if fetched_from:
                    from_user = fetched_from
            except Exception:
                pass

        selected_counterparty = None
        pair_history = []
        
        if counterparty_id_param.strip():
            try:
                c_uuid = UUID(counterparty_id_param.strip())
                stmt = select(UserModel.id, UserModel.name, UserModel.mobile).where(UserModel.id == c_uuid)
                res = await db_manager.session.execute(stmt)
                selected_counterparty = res.one_or_none()
                
                if selected_counterparty:
                    from app.modules.payments.infrastructure.repository import PaymentLedgerRepository
                    ledger_repo = PaymentLedgerRepository(db_manager.session)
                    
                    user_entries = await ledger_repo.get_pair_history(
                        user_id=from_user.id,
                        counterparty_id=c_uuid,
                        start_date=start_dt,
                        end_date=end_dt,
                        limit=100
                    )
                    counterparty_entries = await ledger_repo.get_pair_history(
                        user_id=c_uuid,
                        counterparty_id=from_user.id,
                        start_date=start_dt,
                        end_date=end_dt,
                        limit=100
                    )
                    
                    counterparty_map = {e.transfer_id: e for e in counterparty_entries}
                    
                    for ue in user_entries:
                        ce = counterparty_map.get(ue.transfer_id)
                        if ce:
                            pair_history.append({
                                "transfer_id": ue.transfer_id,
                                "amount": ue.amount,
                                "created_at": ue.created_at,
                                "user_entry_type": ue.entry_type,
                                "user_before": ue.balance_before,
                                "user_after": ue.balance_after,
                                "counterparty_before": ce.balance_before,
                                "counterparty_after": ce.balance_after,
                            })
            except Exception as e:
                print(f"Error loading pair statement: {e}")
                pass

        return Renderer.page(
            request=request,
            template="pages/payments/pair_statement.html",
            model={
                "from_user": from_user,
                "selected_counterparty": selected_counterparty,
                "pair_history": pair_history,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
