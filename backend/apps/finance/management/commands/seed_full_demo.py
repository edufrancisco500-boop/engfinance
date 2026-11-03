from datetime import date, timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.core.files.base import ContentFile
from apps.registry.models import Contract, CostCenter, Coordination, Portfolio, Project
from apps.evaluations.models import ActionPlan, Criterion, Cycle, Evaluation, Invitation
from apps.evaluations.services import submit_evaluation
from apps.finance.models import (
    Allocation,
    Amendment,
    Budget,
    BudgetRevision,
    Document,
    Funding,
    Policy,
    Attachment,
)
from apps.finance.services import audit, create_split, transition


class Command(BaseCommand):
    help = "Preenche todos os módulos locais com cenários fictícios, sem duplicar a demonstração."

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demonstração disponível somente em desenvolvimento.")
        policy = Policy.objects.order_by("pk").first()
        if policy and not policy.demo:
            raise CommandError(
                "Não é permitido misturar demonstração com política real."
            )
        if not policy:
            policy = Policy.objects.create(
                name="Política demonstrativa v1 — validar com a liderança", demo=True
            )
        call_command("setup_roles", stdout=self.stdout)
        call_command("seed_demo", user=options["user"], stdout=self.stdout)
        actor = get_user_model().objects.get(username=options["user"])
        now = timezone.localdate()
        year = now.year

        def approve(obj):
            if obj.status == "DRAFT":
                transition(model=type(obj), pk=obj.pk, actor=actor, action="submit")
            obj.refresh_from_db()
            if obj.status == "SUBMITTED":
                transition(model=type(obj), pk=obj.pk, actor=actor, action="approve")
            obj.refresh_from_db()
            return obj

        allocations = []
        contracts = []
        for i in range(1, 11):
            suffix = f"{i:03d}"
            portfolio = Portfolio.objects.get(code=f"DEMO-CAR-{suffix}")
            project = Project.objects.get(code=f"DEMO-PRJ-{suffix}")
            coordination, _ = Coordination.objects.get_or_create(
                code=f"DEMO-COO-{suffix}",
                defaults={
                    "name": f"Coordenação de {portfolio.name}",
                    "department": portfolio.department,
                    "description": "DADOS FICTÍCIOS PARA TESTE.",
                },
            )
            if project.coordination_id is None:
                project.coordination = coordination
                project.internal_order = f"DEMO-OI-{suffix}"
                project.pep_element = f"DEMO.PEP.{suffix}"
                project.status = (
                    "COMPLETED" if i == 10 else "PAUSED" if i == 8 else "ACTIVE"
                )
                project.save()
            contract = Contract.objects.get(code=f"DEMO-CTR-{suffix}")
            if contract.original_value == 0:
                contract.original_value = Decimal(150000 + i * 25000)
                contract.manager = f"Gestor fictício {i:02d}"
                contract.inspector = f"Fiscal fictício {i:02d}"
                contract.start_date = date(year, 1, 1)
                contract.end_date = now + timedelta(
                    days=(-20 if i == 10 else 15 if i == 9 else 30 * i)
                )
                contract.save()
                audit(actor, "demo_enrich", contract)
            if (
                contract.status == "DRAFT"
                and contract.financial_documents.filter(
                    reference__startswith="DEMO-"
                ).exists()
            ):
                contract.status = "CLOSED" if i == 10 else "ACTIVE"
                contract.save(update_fields=["status"])
            if not project.responsible:
                project.responsible = f"Responsável fictício {i:02d}"
                project.start_date = date(year, 1, 1)
                project.end_date = date(year, 12, 31)
                project.physical_progress = Decimal(20 + i * 6)
                project.save()
                audit(actor, "demo_enrich", project)
            center, _ = CostCenter.objects.get_or_create(
                code=f"DEMO-CC-{suffix}",
                defaults={
                    "name": f"Centro de custo — {portfolio.name}",
                    "department": portfolio.department,
                    "description": "DADOS FICTÍCIOS PARA TESTE.",
                },
            )
            budget, _ = Budget.objects.get_or_create(
                portfolio=portfolio,
                year=year,
                category="CAPEX" if i % 2 else "OPEX",
                defaults={
                    "amount": Decimal(600000 + i * 50000),
                    "created_by": actor,
                    "reason": "DEMO: orçamento anual ilustrativo.",
                },
            )
            approve(budget)
            revision, _ = BudgetRevision.objects.get_or_create(
                budget=budget,
                reason="DEMO: revisão orçamentária inicial.",
                defaults={"amount": Decimal(10000), "created_by": actor},
            )
            approve(revision)
            allocation, _ = Allocation.objects.get_or_create(
                budget=budget,
                project=project,
                cost_center=center,
                reason="DEMO: alocação inicial ao projeto.",
                defaults={
                    "amount": budget.amount * Decimal(".80"),
                    "created_by": actor,
                },
            )
            approve(allocation)
            allocations.append(allocation)
            contracts.append(contract)
            amendment, _ = Amendment.objects.get_or_create(
                contract=contract,
                reason="DEMO: adequação de escopo aprovada.",
                defaults={"amount": Decimal(5000), "created_by": actor},
            )
            approve(amendment)

        for i, contract in enumerate(contracts, 1):
            own = allocations[i - 1]
            other = allocations[i % 10]
            base = contract.original_value
            funding = Funding.objects.filter(
                contract=contract, reason="DEMO: financiamento 60/40 entre carteiras."
            ).first()
            if not funding:
                funding = create_split(
                    model=Funding,
                    actor=actor,
                    data={
                        "contract": contract,
                        "amount": base,
                        "reason": "DEMO: financiamento 60/40 entre carteiras.",
                    },
                    items=[
                        {"allocation": own.pk, "percent": "60"},
                        {"allocation": other.pk, "percent": "40"},
                    ],
                )
            approve(funding)
            commitment = (
                base * (Decimal(".65") + Decimal(i) * Decimal(".03"))
            ).quantize(Decimal(".01"))
            previous = None
            for kind, factor in [
                ("COMMITMENT", Decimal(1)),
                ("MEASUREMENT", Decimal(".80")),
                ("INVOICE", Decimal(".72")),
                ("PAYMENT", Decimal(".60")),
            ]:
                reference = f"DEMO-{kind}-{i:03d}"
                document = Document.objects.filter(
                    contract=contract, kind=kind, reference=reference
                ).first()
                if not document:
                    document = create_split(
                        model=Document,
                        actor=actor,
                        data={
                            "contract": contract,
                            "kind": kind,
                            "reference": reference,
                            "date": date(year, min(i, now.month), min(5 + i, 28)),
                            "amount": (commitment * factor).quantize(Decimal(".01")),
                            "funding": funding,
                            "reason": "DEMO: execução financeira fictícia.",
                        },
                        items=[],
                        sources=[previous.pk] if previous else [],
                    )
                approve(document)
                previous = document

        quarter = (now.month - 1) // 3 + 1
        opens = date(year, 3 * (quarter - 1) + 1, 1)
        closes = (
            date(year + 1, 1, 1) - timedelta(days=1)
            if quarter == 4
            else date(year, quarter * 3 + 1, 1) - timedelta(days=1)
        )
        cycle, _ = Cycle.objects.get_or_create(
            year=year, quarter=quarter, defaults={"opens": opens, "closes": closes}
        )
        criteria = [
            Criterion.objects.get_or_create(name=name, version=1)[0]
            for name in [
                "Qualidade dos serviços",
                "Cumprimento de prazos",
                "Segurança",
                "Comunicação",
                "Atendimento",
                "Resolução de problemas",
                "Cumprimento do escopo",
                "Custo-benefício",
                "Satisfação geral",
            ]
        ]
        for i, contract in enumerate(contracts, 1):
            invitation, created = Invitation.objects.get_or_create(
                cycle=cycle, contract=contract, user=actor
            )
            if created:
                invitation.criteria.set(criteria)
            if i % 2 and not Evaluation.objects.filter(invitation=invitation).exists():
                score = max(1, 6 - (i + 1) // 2)
                submit_evaluation(
                    actor=actor,
                    invitation=invitation,
                    answers=[
                        {
                            "criterion": c.pk,
                            "score": None if j == 7 and i == 1 else score,
                        }
                        for j, c in enumerate(criteria)
                    ],
                    comments={
                        "positives": "DEMO: equipe disponível e documentação organizada.",
                        "negatives": "DEMO: houve necessidade de melhorar a comunicação."
                        if score < 3
                        else "",
                        "problems": "DEMO: atrasos na entrega de relatórios."
                        if score < 3
                        else "",
                        "suggestions": "DEMO: realizar reuniões quinzenais de acompanhamento.",
                        "continuity": "DEMO: avaliação humana necessária para qualquer decisão contratual.",
                    },
                )
            ActionPlan.objects.get_or_create(
                contract=contract,
                title=f"DEMO: acompanhamento do contrato {i:02d}",
                defaults={
                    "description": "Dados fictícios: revisar entregas, indicadores e comunicação com o fornecedor.",
                    "responsible": f"Gestor fictício {i:02d}",
                    "due_date": now + timedelta(days=7 * i),
                    "status": "DONE" if i <= 2 else "PROGRESS" if i <= 5 else "OPEN",
                    "created_by": actor,
                },
            )
            if not Attachment.objects.filter(
                contract=contract, name="DEMO: memória descritiva"
            ).exists():
                attachment = Attachment(
                    contract=contract,
                    name="DEMO: memória descritiva",
                    uploaded_by=actor,
                )
                content = f"ENGFINANCE — DOCUMENTO FICTÍCIO PARA TESTE\n\nContrato: {contract.code}\nObjeto: {contract.name}\n\nEste arquivo não possui validade contratual ou fiscal.\nEscopo ilustrativo: acompanhamento técnico e financeiro de engenharia.\nQualquer decisão contratual depende de análise humana autorizada.\n"
                attachment.file.save(
                    f"demo-contrato-{i:03d}.txt",
                    ContentFile(content.encode("utf-8")),
                    save=True,
                )
                audit(actor, "demo_upload", attachment)
        self.stdout.write(
            self.style.SUCCESS(
                "Demonstração financeira, rateios, avaliações e planos de ação preparados."
            )
        )
