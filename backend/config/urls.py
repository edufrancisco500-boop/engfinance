from django.contrib import admin
from django.contrib.auth import login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from django.urls import include, path
from apps.registry.api import RESOURCES, viewset_for
from apps.finance.api import (
    FINANCE_RESOURCES,
    operation_viewset,
    AttachmentViewSet,
    ContractUsageViewSet,
)
from apps.finance.views import (
    dashboard_view,
    metadata,
    report,
    import_registry,
    ai_summary,
    audit_log,
    configure_policy,
)
from apps.evaluations.api import (
    CycleViewSet,
    InvitationViewSet,
    EvaluationViewSet,
    PlanViewSet,
)


@require_GET
@ensure_csrf_cookie
def session_view(request):
    user = request.user
    return JsonResponse(
        {
            "authenticated": user.is_authenticated,
            "username": user.username if user.is_authenticated else None,
        }
    )


@require_POST
@csrf_protect
def login_view(request):
    # Login local apenas no desenvolvimento; produção depende do provedor aprovado.
    from django.conf import settings

    if not settings.DEBUG:
        return JsonResponse(
            {"detail": "Login local indisponível neste ambiente."}, status=403
        )
    from apps.accounts.services import local_authenticate

    user, throttled = local_authenticate(
        request,
        username=request.POST.get("username", ""),
        password=request.POST.get("password", ""),
    )
    if throttled:
        response = JsonResponse(
            {"detail": "Muitas tentativas. Aguarde 15 minutos para tentar novamente."},
            status=429,
        )
        response["Retry-After"] = "900"
        return response
    if user is None:
        return JsonResponse({"detail": "Credenciais inválidas."}, status=400)
    login(request, user)
    return JsonResponse({"username": user.username})


@require_POST
@csrf_protect
def logout_view(request):
    logout(request)
    return JsonResponse({"authenticated": False})


router = DefaultRouter()
for resource, model in RESOURCES.items():
    router.register(resource, viewset_for(model), basename=resource)
for resource, model in FINANCE_RESOURCES.items():
    router.register(resource, operation_viewset(model), basename=resource)
router.register("attachments", AttachmentViewSet, basename="attachments")
router.register("contract-usage", ContractUsageViewSet, basename="contract-usage")
router.register("cycles", CycleViewSet, basename="cycles")
router.register("invitations", InvitationViewSet, basename="invitations")
router.register("evaluations", EvaluationViewSet, basename="evaluations")
router.register("action-plans", PlanViewSet, basename="action-plans")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(router.urls)),
    path("api/dashboard/", dashboard_view),
    path("api/metadata/", metadata),
    path("api/reports/", report),
    path("api/import/", import_registry),
    path("api/ai-summary/", ai_summary),
    path("api/audit/", audit_log),
    path("api/policy/", configure_policy),
    path("api/session/", session_view),
    path("api/login/", login_view),
    path("api/logout/", logout_view),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
]
