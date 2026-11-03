import csv
import io
import json
import zipfile
from decimal import Decimal
from pathlib import Path
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiTypes
from apps.registry.api import RESOURCES, serializer_for
from apps.registry.models import AuditEvent
from apps.registry.services import save_record
from apps.evaluations.models import Criterion
from .access import department_ids
from .models import Policy
from .selectors import dashboard


@extend_schema(
    responses=OpenApiTypes.OBJECT,
    description="Indicadores financeiros calculados no backend, limitados ao escopo e aos filtros.",
)
@api_view(["GET"])
def dashboard_view(request):
    return Response(dashboard(request.user, request.query_params))


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
def metadata(request):
    user = request.user
    policy = Policy.objects.order_by("pk").first()
    eligible = []
    if user.has_perm("evaluations.add_invitation"):
        from django.contrib.auth import get_user_model

        users = get_user_model().objects.filter(is_active=True)
        if not user.is_superuser:
            users = users.filter(
                departmentaccess__department_id__in=department_ids(user)
            ).distinct()
        eligible = list(users.values("id", "username"))
    return Response(
        {
            "username": user.username,
            "groups": list(user.groups.values_list("name", flat=True)),
            "permissions": sorted(user.get_all_permissions()),
            "superuser": user.is_superuser,
            "policy": {
                "name": policy.name,
                "demo": policy.demo,
                "explanation": policy.explanation,
                "low_balance_percent": policy.low_balance_percent,
                "poor_rating": str(policy.poor_rating),
                "expiry_days": policy.expiry_days,
            }
            if policy
            else None,
            "eligible_users": eligible,
            "criteria": list(
                Criterion.objects.filter(active=True).values("id", "name", "version")
            ),
            "pending_decisions": [
                "Alçadas corporativas",
                "Definição oficial de realizado",
                "Retenções e adiantamentos",
                "Transferências entre carteiras/exercícios",
                "Confidencialidade e pesos das avaliações",
                "Entra ID e provedor de IA",
            ],
        }
    )


@extend_schema(
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    description="Ajusta low_balance_percent, poor_rating e expiry_days. Justificativa reason obrigatória.",
)
@api_view(["PATCH"])
@transaction.atomic
def configure_policy(request):
    from rest_framework import serializers
    from .services import policy_lock

    if not request.user.has_perm("finance.change_policy"):
        raise PermissionDenied(
            "Somente administradores autorizados podem ajustar os alertas."
        )

    class Parameters(serializers.Serializer):
        low_balance_percent = serializers.IntegerField(min_value=0, max_value=100)
        poor_rating = serializers.DecimalField(
            max_digits=3,
            decimal_places=2,
            min_value=Decimal("1"),
            max_value=Decimal("5"),
        )
        expiry_days = serializers.IntegerField(min_value=1, max_value=365)
        reason = serializers.CharField(max_length=2000)

    serializer = Parameters(data=request.data)
    serializer.is_valid(raise_exception=True)
    policy = policy_lock()
    data = serializer.validated_data
    before = {key: str(getattr(policy, key)) for key in data if key != "reason"}
    for key, value in data.items():
        if key != "reason":
            setattr(policy, key, value)
    policy.save()
    AuditEvent.objects.create(
        actor=request.user,
        action="configure_alerts",
        resource="finance.Policy",
        object_id=str(policy.pk),
        before=before,
        after={key: str(value) for key, value in data.items()},
    )
    return Response({"detail": "Parâmetros de alerta atualizados."})


def safe_cell(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@extend_schema(
    responses=OpenApiTypes.BINARY,
    description="Exporta o recorte autorizado em XLSX ou CSV. Parâmetros section e format_file.",
)
@api_view(["GET"])
def report(request):
    data = dashboard(request.user, request.query_params)
    section = request.query_params.get("section", "portfolios")
    if section not in ("portfolios", "contracts", "projects", "categories", "monthly"):
        raise ValidationError("Relatório inválido.")
    rows = data[section]
    headers = list(rows[0]) if rows else ["Sem registros"]
    fmt = request.query_params.get("format_file", "xlsx")
    if fmt == "csv":
        stream = io.StringIO()
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(headers)
        for row in rows:
            writer.writerow([safe_cell(row.get(k, "")) for k in headers])
        response = HttpResponse(
            "\ufeff" + stream.getvalue(), content_type="text/csv; charset=utf-8"
        )
    elif fmt == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill

        book = Workbook()
        sheet = book.active
        sheet.title = "EngFinance"
        sheet.append(
            ["EngFinance — dados fictícios" if data["policy"]["demo"] else "EngFinance"]
        )
        sheet.append(["Filtros", json.dumps(data["filters"], ensure_ascii=False)])
        sheet.append(headers)
        for cell in sheet[3]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="173D51")
        for row in rows:
            sheet.append([safe_cell(row.get(k, "")) for k in headers])
        sheet.freeze_panes = "A4"
        sheet.auto_filter.ref = (
            f"A3:{sheet.cell(max(3, sheet.max_row), len(headers)).coordinate}"
        )
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(
                65, max(16, max(len(str(c.value or "")) for c in column) + 2)
            )
        stream = io.BytesIO()
        book.save(stream)
        response = HttpResponse(
            stream.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        raise ValidationError("Formato inválido.")
    response["Content-Disposition"] = (
        f'attachment; filename="engfinance-{section}.{fmt}"'
    )
    AuditEvent.objects.create(
        actor=request.user,
        action="export",
        resource=f"analytics.{section}",
        object_id="report",
        after={"filters": data["filters"], "rows": len(rows)},
    )
    return response


@extend_schema(
    request={
        "multipart/form-data": {
            "type": "object",
            "properties": {
                "resource": {"type": "string"},
                "file": {"type": "string", "format": "binary"},
                "commit": {"type": "boolean"},
            },
        }
    },
    responses=OpenApiTypes.OBJECT,
)
@api_view(["POST"])
def import_registry(request):
    resource = request.data.get("resource", "")
    model = RESOURCES.get(resource)
    if model is None:
        raise ValidationError("Importação disponível somente para cadastros básicos.")
    if not request.user.has_perm(
        f"{model._meta.app_label}.add_{model._meta.model_name}"
    ):
        raise PermissionDenied("Sem permissão para importar este cadastro.")
    file = request.FILES.get("file")
    if not file or file.size > 2 * 1024 * 1024:
        raise ValidationError("Envie CSV ou XLSX com até 2 MB e 500 registros.")
    suffix = Path(file.name).suffix.lower()
    try:
        if suffix == ".csv":
            content = file.read().decode("utf-8-sig")
            reader = csv.DictReader(
                io.StringIO(content),
                delimiter=";" if ";" in content.splitlines()[0] else ",",
            )
            rows = list(reader)
        elif suffix == ".xlsx":
            from openpyxl import load_workbook

            with zipfile.ZipFile(file) as archive:
                if (
                    sum(item.file_size for item in archive.infolist())
                    > 20 * 1024 * 1024
                ):
                    raise ValidationError("Planilha descompactada excede o limite.")
            file.seek(0)
            book = load_workbook(file, read_only=True, data_only=False)
            sheet = book.active
            iterator = sheet.iter_rows()
            headers = [str(c.value or "").strip() for c in next(iterator)]
            rows = []
            for cells in iterator:
                if any(c.data_type == "f" for c in cells):
                    raise ValidationError("Importação não aceita fórmulas.")
                if any(c.value is not None for c in cells):
                    rows.append(dict(zip(headers, [c.value for c in cells])))
                if len(rows) > 500:
                    break
            book.close()
        else:
            raise ValidationError("Use CSV ou XLSX.")
    except (UnicodeError, zipfile.BadZipFile, ValueError, StopIteration, IndexError):
        raise ValidationError(
            "Arquivo inválido. Use cabeçalhos dos campos da API: code, name, department etc."
        )
    if not rows or len(rows) > 500:
        raise ValidationError("Importe entre 1 e 500 registros por operação.")
    serializers = []
    errors = []
    seen = set()
    cls = serializer_for(model)
    for index, row in enumerate(rows, 2):
        row = {k: v for k, v in row.items() if k and v is not None and v != ""}
        serializer = cls(data=row, context={"request": request})
        if row.get("code") in seen:
            errors.append({"line": index, "errors": "Código duplicado no arquivo."})
        elif not serializer.is_valid():
            errors.append({"line": index, "errors": serializer.errors})
        else:
            serializers.append(serializer)
        seen.add(row.get("code"))
    if errors:
        return Response({"valid": False, "errors": errors}, status=400)
    commit = str(request.data.get("commit", "false")).lower() == "true"
    if commit:
        with transaction.atomic():
            for serializer in serializers:
                save_record(serializer=serializer, actor=request.user, action="import")
    return Response(
        {
            "valid": True,
            "committed": commit,
            "count": len(serializers),
            "preview": rows[:10],
        }
    )


@extend_schema(
    responses=OpenApiTypes.OBJECT,
    description="Resumo local por regras, sem consulta externa e sem capacidade de alteração de dados.",
)
@api_view(["GET"])
def ai_summary(request):
    # Provedor local determinístico. Não chama APIs, não interpreta instruções de comentários e não escreve dados.
    data = dashboard(request.user, request.query_params)
    question = request.query_params.get("question", "Resumo executivo")[:500]
    total_risk = sum(1 for row in data["contracts"] if row["risk"] == "Alto")
    texts = [
        f"No recorte selecionado há {data['projects_count']} projetos e {data['contracts_count']} contratos.",
        f"Orçamento/base: R$ {data['budget']}; comprometido: R$ {data['committed']}; realizado: R$ {data['realized']}; pago: R$ {data['paid']}.",
        f"Foram identificados {total_risk} contratos com saldo reduzido e avaliação abaixo do limite configurado.",
    ]
    q = question.casefold()
    if any(word in q for word in ("pior", "avalia", "desempenho")):
        selected = sorted(
            (r for r in data["contracts"] if r["rating"] is not None),
            key=lambda r: r["rating"],
        )[:5]
        texts += [f"{r['name']}: avaliação {r['rating']:.2f}/5." for r in selected]
    elif any(word in q for word in ("saldo", "carteira")):
        selected = sorted(
            data["portfolios"], key=lambda r: Decimal(r["available"]), reverse=True
        )[:5]
        texts += [
            f"{r['name']}: saldo para comprometer no exercício R$ {r['available']}."
            for r in selected
        ]
    else:
        texts += [
            f"Investigar {alert['name']}: {', '.join(alert['reasons'])}."
            for alert in data["alerts"][:5]
        ]
    from apps.ai.providers import approved_provider

    insight = approved_provider().generate(paragraphs=texts)
    from apps.evaluations.models import Evaluation

    evaluations = Evaluation.objects.filter(
        invitation__contract_id__in=[row["id"] for row in data["contracts"]]
    )
    if data["filters"].get("year"):
        evaluations = evaluations.filter(
            invitation__cycle__year=data["filters"]["year"]
        )
    if data["filters"].get("quarter"):
        evaluations = evaluations.filter(
            invitation__cycle__quarter=data["filters"]["quarter"]
        )
    themes = []
    if request.user.has_perm("evaluations.view_results") and evaluations.count() >= (
        1 if data["policy"]["demo"] else 3
    ):
        texts_for_topics = [
            f"{e.negatives} {e.problems} {e.suggestions}".casefold()
            for e in evaluations
        ]
        for name, words in {
            "Prazo e entrega": ["atras", "prazo", "entrega"],
            "Comunicação": ["comunica", "reuni"],
            "Qualidade": ["qualidade", "retrabalho"],
            "Segurança": ["seguran", "acidente"],
        }.items():
            count = sum(
                any(word in text for word in words) for text in texts_for_topics
            )
            if count:
                themes.append({"name": name, "count": count})
    return Response(
        {
            "provider": insight.provider,
            "uses_language_model": insight.uses_language_model,
            "question": question,
            "paragraphs": insight.paragraphs,
            "themes": themes,
            "limitations": "Resumo automático por regras. Integração com modelo de IA externo ainda não configurada. Nenhuma decisão contratual é tomada.",
            "source": {
                "filters": data["filters"],
                "generated_at": timezone.now().isoformat(),
                "policy": data["policy"],
            },
        }
    )


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
def audit_log(request):
    if not request.user.has_perm("registry.view_auditevent"):
        raise PermissionDenied("Sem permissão para consultar auditoria.")
    query = AuditEvent.objects.all()
    if not request.user.is_superuser:
        # Exibe ações próprias. Auditoria transversal fica reservada à conta técnica nesta versão.
        query = query.filter(actor=request.user)
    return Response(
        list(
            query.values(
                "id", "created_at", "action", "resource", "object_id", "before", "after"
            )[:200]
        )
    )
