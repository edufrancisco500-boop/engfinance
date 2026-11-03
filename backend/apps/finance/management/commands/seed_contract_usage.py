from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from apps.registry.models import Contract, Project
from apps.finance.models import ContractUsage
from apps.finance.services import audit


class Command(BaseCommand):
    help = "Acrescenta registros fictícios de utilização, sem criar contas de acesso."

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demonstração disponível somente em desenvolvimento.")
        actor = get_user_model().objects.get(username=options["user"])
        names = [
            "Marina Costa",
            "Rafael Lima",
            "Beatriz Alves",
            "Lucas Rocha",
            "Camila Santos",
            "Pedro Nunes",
            "Juliana Melo",
            "Bruno Teixeira",
            "Ana Ribeiro",
            "Diego Martins",
        ]
        created = 0
        for i, contract in enumerate(
            Contract.objects.filter(code__startswith="DEMO-CTR-").order_by("code"), 1
        ):
            project = Project.objects.filter(
                code=contract.code.replace("CTR", "PRJ")
            ).first()
            for event in range((i % 5 + 1) * 2):
                person = names[(i + event) % len(names)] + " (fictício)"
                row, is_new = ContractUsage.objects.get_or_create(
                    contract=contract,
                    purpose=f"DEMO: utilização {event + 1:02d} — acompanhamento de engenharia.",
                    defaults={
                        "project": project,
                        "person_name": person,
                        "team": "Equipe fictícia de engenharia",
                        "date": timezone.localdate()
                        - timedelta(days=(i * 7 + event * 3) % 60),
                        "created_by": actor,
                    },
                )
                if is_new:
                    audit(actor, "demo_contract_use", row)
                    created += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"{created} utilizações fictícias adicionadas. Contas e valores financeiros preservados."
            )
        )
