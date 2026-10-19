from app.core.exceptions.base import ForbiddenException
from uuid import UUID
from fastapi import Request
from fastapi.responses import HTMLResponse
from app.modules.dependencies import GetHandler
from app.web.framework.renderer import Renderer
from app.core.exceptions.base import ValidateError
from fastapi.responses import Response, RedirectResponse
from app.modules.administration.domain.enums import Role

from app.modules.common.address.application.command import CreateAddressCommand, UpdateAddressCommand
from app.modules.common.bank.application.command import CreateBankAccountCommand, UpdateBankAccountCommand
from app.modules.administration.application.command import CreateUserCommand, ListUsersQuery, GetUserQuery, UpdateUserCommand

class SubAdminController:

    @staticmethod
    async def list_page(
        request: Request,
        page: int = 1,
        limit: int = 10,
        search: str = "",
    ):
        user = request.state.user
        if user.role_type not in {Role.SUPER_ADMIN, Role.ADMIN}:
            raise ForbiddenException("You are not authorized to access this page")

        handler = GetHandler.user_handler(request)

        users = []
        if user.role_type == Role.SUPER_ADMIN:
            admins = await handler.list(ListUsersQuery(page=1, size=1000, role=Role.ADMIN, owner=user))
            subadmins = await handler.list(ListUsersQuery(page=1, size=1000, role=Role.SUB_ADMIN, owner=user))
            users = admins + subadmins
        else:
            users = await handler.list(ListUsersQuery(page=1, size=1000, role=Role.SUB_ADMIN, owner=user))

        if search.strip():
            pat = search.strip().lower()
            users = [u for u in users if pat in u.name.lower() or pat in u.email.lower()]

        total_items = len(users)
        total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1
        paginated_users = users[(page - 1) * limit : page * limit]

        return Renderer.page(
            request=request,
            template="pages/sub_admin/list.html",
            model={
                "items": paginated_users,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "search": search,
                "role_type": user.role_type,
            },
        )

    @staticmethod
    async def create_page(request: Request):
        user = request.state.user
        if user.role_type not in {Role.SUPER_ADMIN, Role.ADMIN}:
            raise ForbiddenException("You are not authorized to access this page")

        allowed_roles = []
        if user.role_type == Role.SUPER_ADMIN:
            allowed_roles = [
                {"value": Role.ADMIN.value, "label": "Admin"},
                {"value": Role.SUB_ADMIN.value, "label": "Sub Admin"},
            ]
        elif user.role_type == Role.ADMIN:
            allowed_roles = [
                {"value": Role.SUB_ADMIN.value, "label": "Sub Admin"},
            ]

        return Renderer.page(
            request=request,
            template="pages/sub_admin/create_edit.html",
            model={
                "allowed_roles": allowed_roles,
            },
        )

    @staticmethod
    async def create_post(request: Request):
        user = request.state.user
        if user.role_type not in {Role.SUPER_ADMIN, Role.ADMIN}:
            raise ForbiddenException("You are not authorized to access this page")

        form_data = await request.form()
        name = form_data.get("name")
        email = form_data.get("email")
        password = form_data.get("password")
        role_val = int(form_data.get("role"))
        mobile = form_data.get("mobile")

        if user.role_type == Role.ADMIN and role_val != Role.SUB_ADMIN.value:
            raise ValidateError("You are only allowed to create Sub Admin")

        profile_image = form_data.get("profile_image")
        if profile_image and not profile_image.filename:
            profile_image = None

        command = CreateUserCommand(
            name=name,
            email=email,
            password_hash=password,
            role=Role(role_val),
            mobile=mobile,
            is_active=True,
            created_by=user.id,
            profile_image=profile_image,
        )

        address_line = form_data.get("address_line")
        city = form_data.get("city")
        state_val = form_data.get("state")
        pincode = form_data.get("pincode")

        address_command = None
        if address_line or city or state_val or pincode:
            address_command = CreateAddressCommand(
                line=address_line or "",
                city=city or "",
                state=state_val or "",
                pincode=pincode or "",
            )

        bank_name = form_data.get("bank_name")
        account_holder = form_data.get("account_holder")
        account_number = form_data.get("account_number")
        ifsc_code = form_data.get("ifsc_code")
        upi_id = form_data.get("upi_id")

        bank_command = None
        if bank_name or account_holder or account_number or ifsc_code or upi_id:
            bank_command = CreateBankAccountCommand(
                bank_name=bank_name or "",
                account_holder=account_holder or "",
                account_number=account_number or "",
                ifsc_code=ifsc_code or "",
                upi_id=upi_id or None,
            )

        profile_service = GetHandler.profile_service(request)
        async with profile_service._database.transaction():
            result = await profile_service.create(
                user_data=command,
                address_data=address_command,
                bank_data=bank_command,
                role=Role(role_val),
            )

        if result and result.user:
            return Renderer.redirect("/sub-admins")

        return Renderer.empty().error("Unable to create user").build()

    @staticmethod
    async def delete_post(request: Request, user_id: UUID):
        user = request.state.user
        if user.role_type not in {Role.SUPER_ADMIN, Role.ADMIN}:
            return HTMLResponse("Unauthorized", status_code=403)

        handler = GetHandler.user_handler(request)
        target_user = await handler.get(GetUserQuery(id=user_id))
        if user.role_type == Role.ADMIN:
            if int(target_user.role) != Role.SUB_ADMIN.value:
                return HTMLResponse("Unauthorized", status_code=403)

        from app.modules.administration.application.command import DeleteUserCommand
        await handler.delete(DeleteUserCommand(id=user_id))
        
        redirect_url = request.query_params.get("redirect")
        if request.headers.get("HX-Request"):
            if redirect_url:
                return Response(headers={"HX-Redirect": redirect_url})
            return Renderer.empty().success("Successfully deleted").build()

        return RedirectResponse("/sub-admins", status_code=303)

    @staticmethod
    async def validate_email(request: Request, email: str):
        handler = GetHandler.user_handler(request)
        is_available = not await handler._repository.exists_email(email.strip().lower())
        if is_available:
            return HTMLResponse('<h6 style="color:green">Email available</h6>')
        return HTMLResponse('<h6 style="color:red">Email already in use</h6>')

    @staticmethod
    async def view_page(request: Request, user_id: UUID):
        user = request.state.user
        if user.role_type not in {Role.SUPER_ADMIN, Role.ADMIN}:
            raise ForbiddenException("You are not authorized to access this page")

        profile_service = GetHandler.profile_service(request)
        profile = await profile_service.get_profile(user_id)

        if user.role_type == Role.ADMIN and int(profile.user.role) != Role.SUB_ADMIN.value:
            raise ValidateError("You are not authorized to view this profile")

        return Renderer.page(
            request=request,
            template="pages/sub_admin/view.html",
            model={
                "user": profile.user,
                "address": profile.address,
                "bank_account": profile.bank_account,
            },
        )

    @staticmethod
    async def edit_page(request: Request, user_id: UUID):
        user = request.state.user
        if user.role_type not in {Role.SUPER_ADMIN, Role.ADMIN}:
            raise ForbiddenException("You are not authorized to access this page")

        profile_service = GetHandler.profile_service(request)
        profile = await profile_service.get_profile(user_id)

        allowed_roles = []
        if user.role_type == Role.SUPER_ADMIN:
            allowed_roles = [
                {"value": Role.ADMIN.value, "label": "Admin"},
                {"value": Role.SUB_ADMIN.value, "label": "Sub Admin"},
            ]
        elif user.role_type == Role.ADMIN:
            allowed_roles = [
                {"value": Role.SUB_ADMIN.value, "label": "Sub Admin"},
            ]

        return Renderer.page(
            request=request,
            template="pages/sub_admin/create_edit.html",
            model={
                "user": profile.user,
                "address": profile.address,
                "bank": profile.bank_account,
                "allowed_roles": allowed_roles,
                "is_edit": True,
            },
        )

    @staticmethod
    async def edit_post(request: Request, user_id: UUID):
        user = request.state.user
        if user.role_type not in {Role.SUPER_ADMIN, Role.ADMIN}:
            raise ForbiddenException("You are not authorized to access this page")

        form_data = await request.form()
        name = form_data.get("name")
        email = form_data.get("email")
        password = form_data.get("password")
        role_val = int(form_data.get("role"))
        mobile = form_data.get("mobile")

        if user.role_type == Role.ADMIN and role_val != Role.SUB_ADMIN.value:
            raise ValidateError("You are only allowed to update Sub Admin")

        # Handle image upload if a new file is uploaded
        profile_image = form_data.get("profile_image")
        

        command = UpdateUserCommand(
            id=user_id,
            name=name,
            email=email,
            password_hash=password if password else None,
            role=Role(role_val),
            mobile=mobile,
            is_active=True,
            profile_image=profile_image,
        )

        address_line = form_data.get("address_line")
        city = form_data.get("city")
        state_val = form_data.get("state")
        pincode = form_data.get("pincode")

        address_command = None
        if address_line or city or state_val or pincode:
            address_command = UpdateAddressCommand(
                id=user_id, # Placeholder, will be replaced inside services
                line=address_line or "",
                city=city or "",
                state=state_val or "",
                pincode=pincode or "",
            )

        bank_name = form_data.get("bank_name")
        account_holder = form_data.get("account_holder")
        account_number = form_data.get("account_number")
        ifsc_code = form_data.get("ifsc_code")
        upi_id = form_data.get("upi_id")

        bank_command = None
        if bank_name or account_holder or account_number or ifsc_code or upi_id:
            bank_command = UpdateBankAccountCommand(
                id=user_id, # Placeholder, will be replaced inside services
                bank_name=bank_name or "",
                account_holder=account_holder or "",
                account_number=account_number or "",
                ifsc_code=ifsc_code or "",
                upi_id=upi_id or None,
            )

        profile_service = GetHandler.profile_service(request)
        async with profile_service._database.transaction():
            await profile_service.update(
                user_data=command,
                address_data=address_command,
                bank_data=bank_command,
            )

        return Renderer.redirect("/sub-admins")
