from pathlib import Path
from django.db import transaction
from django.http import FileResponse
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from apps.registry.api import ScopedModelPermissions
from .access import scoped, require_departments
from .models import (
    Allocation,
    Amendment,
    Attachment,
    Budget,
    BudgetRevision,
    Document,
    Funding,
    State,
    Transfer,
    PeriodChange,
    ContractUsage,
)
from .services import (
    allocation_value,
    audit,
    budget_value,
    create_split,
    money,
    policy_lock,
    reverse,
    source_departments,
    transition,
    used,
    validate_allocation,
)


class SplitEntry(serializers.Serializer):
    allocation = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False)
    percent = serializers.DecimalField(max_digits=7, decimal_places=4, required=False)


class FinancialPermissions(ScopedModelPermissions):
    def has_permission(self, request, view):
        if getattr(view, "action", "") in ("approve", "reject"):
            return bool(
                request.user.is_authenticated
                and request.user.has_perm("finance.approve_finance")
                and request.user.has_perm(
                    f"finance.view_{view.queryset.model._meta.model_name}"
                )
            )
        return super().has_permission(request, view)


def operation_serializer(model):
    extra = {}
    if model in (Document, Funding):
        extra["split"] = serializers.ListField(
            child=SplitEntry(), write_only=True, required=False, default=list
        )
        extra["distribution"] = serializers.SerializerMethodField()
    if model is Document:
        extra["source_documents"] = serializers.ListField(
            child=serializers.IntegerField(min_value=1),
            write_only=True,
            required=False,
            default=list,
        )
        extra["idempotency_key"] = serializers.UUIDField(required=False)
        extra["reversed"] = serializers.SerializerMethodField()
    if model in (Budget, Allocation):
        extra["balance"] = serializers.SerializerMethodField()

    class OperationSerializer(serializers.ModelSerializer):
        class Meta:
            fields = "__all__"
            validators = []
            read_only_fields = [
                "status",
                "created_by",
                "approved_by",
                "created_at",
                "approved_at",
                "version",
                "request_fingerprint",
                "reversal_of",
                "sources",
            ]

        def get_balance(self, obj) -> str:
            if isinstance(obj, Budget):
                from .services import total

                return str(
                    budget_value(obj)
                    - total(obj.allocations.filter(status=State.APPROVED))
                )
            return str(allocation_value(obj) - used(obj))

        def get_reversed(self, obj) -> bool:
            return Document.objects.filter(
                reversal_of=obj, status=State.APPROVED
            ).exists()

        def get_distribution(self, obj) -> list[dict]:
            parts = obj.parcels.all() if isinstance(obj, Document) else obj.items.all()
            return [
                {
                    "allocation": p.allocation_id,
                    "amount": str(p.amount),
                    "percent": str(
                        (p.amount / obj.amount * 100).quantize(money("0.01"))
                    ),
                    "portfolio": p.allocation.budget.portfolio.name,
                    "project": p.allocation.project.name
                    if p.allocation.project_id
                    else None,
                    "category": p.allocation.budget.category,
                }
                for p in parts.select_related(
                    "allocation__budget__portfolio", "allocation__project"
                )
            ]

    OperationSerializer.Meta.model = model
    OperationSerializer.__name__ = f"{model.__name__}Serializer"
    for name, field in extra.items():
        OperationSerializer._declared_fields[name] = field
    return OperationSerializer


def operation_viewset(model):
    class OperationViewSet(viewsets.ReadOnlyModelViewSet, viewsets.GenericViewSet):
        queryset = model.objects.all()
        serializer_class = operation_serializer(model)
        permission_classes = [FinancialPermissions]
        http_method_names = ["get", "post", "head", "options"]

        def get_queryset(self):
            query = scoped(super().get_queryset(), self.request.user)
            for field in (
                "status",
                "contract",
                "kind",
                "year",
                "category",
                "portfolio",
                "budget",
            ):
                if field in self.request.query_params and field in {
                    f.name for f in model._meta.fields
                }:
                    query = query.filter(**{field: self.request.query_params[field]})
            return query

        @transaction.atomic
        def create(self, request):
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = dict(serializer.validated_data)
            if model in (Document, Funding):
                items = data.pop("split", [])
                sources = data.pop("source_documents", [])
                obj = create_split(
                    model=model,
                    actor=request.user,
                    data=data,
                    items=items,
                    sources=sources,
                )
            else:
                policy_lock()
                obj = model(**data, created_by=request.user)
                if isinstance(obj, PeriodChange) and not request.user.has_perm(
                    "finance.change_policy"
                ):
                    from rest_framework.exceptions import PermissionDenied

                    raise PermissionDenied(
                        "Competências globais são administradas por perfil autorizado."
                    )
                require_departments(request.user, source_departments(obj))
                if isinstance(obj, Allocation):
                    validate_allocation(obj)
                obj.full_clean(exclude=["created_at", "approved_at"])
                obj.save()
                audit(request.user, "create", obj)
            return Response(self.get_serializer(obj).data, status=201)

        def change_state(self, request, pk, name):
            obj = self.get_object()
            result = transition(
                model=model,
                pk=obj.pk,
                actor=request.user,
                action=name,
                reason=str(request.data.get("reason", "")),
            )
            return Response(self.get_serializer(result).data)

        @action(detail=True, methods=["post"])
        def submit(self, request, pk=None):
            return self.change_state(request, pk, "submit")

        @action(detail=True, methods=["post"])
        def approve(self, request, pk=None):
            return self.change_state(request, pk, "approve")

        @action(detail=True, methods=["post"])
        def reject(self, request, pk=None):
            return self.change_state(request, pk, "reject")

    if model is Document:

        @action(detail=True, methods=["post"], url_path="reverse")
        def reverse_action(self, request, pk=None):
            obj = reverse(
                document=self.get_object(),
                actor=request.user,
                reason=str(request.data.get("reason", "")),
            )
            return Response(self.get_serializer(obj).data, status=201)

        OperationViewSet.reverse_action = reverse_action
    OperationViewSet.__name__ = f"{model.__name__}ViewSet"
    return OperationViewSet


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ["id", "contract", "name", "file", "uploaded_by", "created_at"]
        read_only_fields = ["uploaded_by", "created_at"]
        extra_kwargs = {"file": {"write_only": True}}

    def validate_file(self, file):
        suffix = Path(file.name).suffix.lower()
        if file.size > 5 * 1024 * 1024 or suffix not in (
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".txt",
        ):
            raise ValidationError("Envie PDF, PNG, JPG ou TXT com até 5 MB.")
        header = file.read(16)
        file.seek(0)
        valid = (
            suffix == ".pdf"
            and header.startswith(b"%PDF-")
            or suffix == ".png"
            and header.startswith(b"\x89PNG\r\n\x1a\n")
            or suffix in (".jpg", ".jpeg")
            and header.startswith(b"\xff\xd8\xff")
            or suffix == ".txt"
            and b"\0" not in header
        )
        if not valid:
            raise ValidationError(
                "Conteúdo do arquivo não corresponde ao tipo permitido."
            )
        return file


class AttachmentViewSet(viewsets.ModelViewSet):
    queryset = Attachment.objects.all().order_by("-created_at", "-pk")
    serializer_class = AttachmentSerializer
    permission_classes = [ScopedModelPermissions]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        query = scoped(super().get_queryset(), self.request.user)
        if self.request.query_params.get("contract"):
            query = query.filter(contract_id=self.request.query_params["contract"])
        return query

    def perform_create(self, serializer):
        require_departments(
            self.request.user, {serializer.validated_data["contract"].department_id}
        )
        obj = serializer.save(uploaded_by=self.request.user)
        audit(self.request.user, "upload", obj)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        obj = self.get_object()
        audit(request.user, "download", obj)
        response = FileResponse(
            obj.file.open("rb"), as_attachment=True, filename=Path(obj.file.name).name
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response


FINANCE_RESOURCES = {
    "budgets": Budget,
    "budget-revisions": BudgetRevision,
    "allocations": Allocation,
    "amendments": Amendment,
    "fundings": Funding,
    "documents": Document,
    "transfers": Transfer,
    "periods": PeriodChange,
}


class ContractUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractUsage
        fields = "__all__"
        read_only_fields = ["created_by", "created_at"]

    def validate(self, data):
        from django.utils import timezone

        contract = data.get("contract", getattr(self.instance, "contract", None))
        project = data.get("project", getattr(self.instance, "project", None))
        ids = {contract.department_id}
        if project:
            ids.add(project.department_id)
        require_departments(self.context["request"].user, ids)
        if (
            data.get("date", getattr(self.instance, "date", timezone.localdate()))
            > timezone.localdate()
        ):
            raise ValidationError(
                "Registros de utilização devem ter data de hoje ou anterior."
            )
        if "person_name" in data:
            data["person_name"] = " ".join(data["person_name"].split())
            if not data["person_name"]:
                raise ValidationError("Informe a pessoa que utilizou o contrato.")
        return data


class ContractUsageViewSet(viewsets.ModelViewSet):
    queryset = ContractUsage.objects.all()
    serializer_class = ContractUsageSerializer
    permission_classes = [ScopedModelPermissions]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        query = scoped(super().get_queryset(), self.request.user)
        if self.request.query_params.get("contract"):
            query = query.filter(contract_id=self.request.query_params["contract"])
        return query

    @transaction.atomic
    def perform_create(self, serializer):
        obj = serializer.save(created_by=self.request.user)
        event = audit(self.request.user, "record_contract_use", obj)
        self.record_details(obj, event)

    @transaction.atomic
    def perform_update(self, serializer):
        from django.forms.models import model_to_dict

        before = model_to_dict(self.get_object())
        before["date"] = str(before["date"])
        obj = serializer.save()
        event = audit(self.request.user, "update_contract_use", obj, before)
        self.record_details(obj, event)

    def record_details(self, obj, event):
        event.after = {
            "contract": obj.contract_id,
            "project": obj.project_id,
            "person_name": obj.person_name,
            "team": obj.team,
            "date": str(obj.date),
            "purpose": obj.purpose,
        }
        event.save(update_fields=["after"])
