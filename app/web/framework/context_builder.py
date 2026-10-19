from app.modules.dashboard.presentation.navigation import build_navigation

from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import Request


class ContextBuilder:

    @staticmethod
    def build(
        request: Request,
        model: Any = None,
    ) -> dict[str, Any]:


        context = {
            "request": request,
        }
        
        user = getattr(request.state, "user", None)
        if user and getattr(user, "role", None) is not None:
            try:
                role_val = int(user.role)
                navigation = build_navigation(role_val)
            except (ValueError, TypeError):
                navigation = ()
            context.update({"current_user": user, "navigation": navigation})
        else:
            context.update({"current_user": None, "navigation": ()})

        if model is None:
            return context

        if is_dataclass(model):
            context.update(asdict(model))

        elif isinstance(model, dict):
            context.update(model)

        else:
            context["model"] = model
        
        
        return context