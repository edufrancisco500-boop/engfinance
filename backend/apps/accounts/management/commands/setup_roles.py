from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cria perfis iniciais de cadastro, sem usuários ou alçadas financeiras."

    def handle(self, *args, **options):
        roles = {
            "Administrador": ["view", "add", "change"],
            "Gestor de engenharia": ["view"],
            "Analista financeiro": ["view", "add", "change"],
            "Gestor de contratos": ["view", "add", "change"],
            "Fiscal de contratos": ["view"],
            "Colaborador": [],
            "Auditor": ["view"],
        }
        for name, actions in roles.items():
            group, _ = Group.objects.get_or_create(name=name)
            # Somente adiciona permissões iniciais; não remove concessões já administradas.
            models = [
                "department",
                "portfolio",
                "project",
                "supplier",
                "contract",
                "coordination",
                "costcenter",
            ]
            if name == "Gestor de contratos":
                writable = ["supplier", "contract"]
            elif name == "Administrador":
                writable = models
            else:
                writable = ["portfolio", "project"]
            codes = [
                f"{action}_{model}"
                for action in actions
                for model in models
                if action == "view" or model in writable
            ]
            group.permissions.add(
                *Permission.objects.filter(
                    content_type__app_label="registry", codename__in=codes
                )
            )
            if name != "Colaborador":
                group.permissions.add(
                    *Permission.objects.filter(
                        content_type__app_label__in=["finance", "evaluations"],
                        codename__startswith="view_",
                    ).exclude(codename="view_individual")
                )
                group.permissions.add(
                    *Permission.objects.filter(
                        codename="view_auditevent", content_type__app_label="registry"
                    )
                )
            if name in (
                "Administrador",
                "Analista financeiro",
                "Gestor de contratos",
                "Fiscal de contratos",
            ):
                group.permissions.add(
                    *Permission.objects.filter(
                        content_type__app_label="finance", codename__startswith="add_"
                    ).exclude(codename="add_policy")
                )
            if name in ("Administrador", "Gestor de engenharia"):
                group.permissions.add(
                    *Permission.objects.filter(
                        content_type__app_label="finance", codename="approve_finance"
                    )
                )
            if name in ("Administrador", "Gestor de contratos", "Gestor de engenharia"):
                group.permissions.add(
                    *Permission.objects.filter(
                        content_type__app_label="evaluations",
                        codename__in=[
                            "add_cycle",
                            "add_invitation",
                            "add_actionplan",
                            "change_actionplan",
                        ],
                    )
                )
            if name == "Administrador":
                group.permissions.add(
                    *Permission.objects.filter(
                        content_type__app_label="registry",
                        codename__in=[
                            "view_costcenter",
                            "add_costcenter",
                            "change_costcenter",
                        ],
                    )
                )
                group.permissions.add(
                    *Permission.objects.filter(
                        content_type__app_label="finance",
                        codename__in=["change_policy", "change_contractusage"],
                    )
                )
        self.stdout.write(
            self.style.SUCCESS(
                "Perfis criados. Atribua grupos e escopos por gerência no admin."
            )
        )
