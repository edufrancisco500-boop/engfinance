from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.forms.models import model_to_dict

from apps.registry.models import (
    AuditEvent,
    Contract,
    Department,
    DepartmentAccess,
    Portfolio,
    Project,
    Supplier,
)


SCENARIOS = [
    (
        "Infraestrutura",
        "Expansão de Infraestrutura",
        "Ampliação da unidade Norte",
        "Horizonte Engenharia Simulada",
        "Obras civis da unidade Norte",
        "Construção de fundações, drenagem e acessos internos.",
    ),
    (
        "Automação",
        "Modernização Industrial",
        "Automação da linha de montagem",
        "Vetor Automação Simulada",
        "Integração dos sistemas de automação",
        "Instalação de sensores e integração de controladores industriais.",
    ),
    (
        "Energia",
        "Eficiência Energética",
        "Modernização da subestação",
        "Lume Energia Simulada",
        "Adequação elétrica da subestação",
        "Revisão de painéis, proteção elétrica e comissionamento.",
    ),
    (
        "Manutenção",
        "Confiabilidade Operacional",
        "Revitalização das bombas industriais",
        "Atlas Manutenção Simulada",
        "Manutenção de equipamentos rotativos",
        "Inspeção, revisão e testes de bombas e conjuntos mecânicos.",
    ),
    (
        "Meio Ambiente",
        "Sustentabilidade e Meio Ambiente",
        "Reuso de água industrial",
        "VerdeFluxo Ambiental Simulada",
        "Implantação do sistema de reuso",
        "Instalação de filtros, tubulações e instrumentação de qualidade.",
    ),
    (
        "Logística",
        "Infraestrutura Logística",
        "Reforma do centro de distribuição",
        "Rota Engenharia Simulada",
        "Adequação do centro logístico",
        "Reforma das docas e reorganização das áreas de movimentação.",
    ),
    (
        "Segurança",
        "Segurança das Instalações",
        "Ampliação do sistema de combate a incêndio",
        "Protege Instalações Simulada",
        "Montagem da rede de proteção",
        "Instalação de hidrantes, alarmes e sinalização de emergência.",
    ),
    (
        "Tecnologia",
        "Transformação Digital",
        "Rede de comunicação industrial",
        "Nexo Tecnologia Simulada",
        "Implantação de conectividade industrial",
        "Lançamento de fibra óptica e configuração de redes industriais.",
    ),
    (
        "Utilidades",
        "Modernização de Utilidades",
        "Renovação da central de ar comprimido",
        "Prisma Utilidades Simulada",
        "Adequação da central de compressores",
        "Substituição de linhas, montagem e testes de estanqueidade.",
    ),
    (
        "Engenharia de Processos",
        "Melhoria de Processos",
        "Otimização da estação de tratamento",
        "Delta Processos Simulada",
        "Estudos e melhorias da estação",
        "Levantamento técnico, revisão do processo e documentação de engenharia.",
    ),
]


class Command(BaseCommand):
    help = "Cria 10 registros fictícios de cada cadastro e concede acesso ao usuário indicado."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            required=True,
            help="Usuário local existente que receberá os dados de teste.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Dados de demonstração permitidos somente no desenvolvimento (DEBUG=true)."
            )
        try:
            actor = get_user_model().objects.get(
                username=options["user"], is_active=True
            )
        except get_user_model().DoesNotExist as error:
            raise CommandError("Usuário ativo não encontrado.") from error

        created_count = 0

        def create(model, lookup, defaults):
            nonlocal created_count
            record, created = model.objects.get_or_create(**lookup, defaults=defaults)
            if created:
                AuditEvent.objects.create(
                    actor=actor,
                    action="demo_create",
                    resource=model._meta.label,
                    object_id=str(record.pk),
                    after=model_to_dict(record),
                )
                created_count += 1
            return record

        for index, (
            department_name,
            portfolio_name,
            project_name,
            supplier_name,
            contract_name,
            scope,
        ) in enumerate(SCENARIOS, 1):
            suffix = f"{index:03d}"
            description = f"DADOS FICTÍCIOS PARA TESTE. Cenário {suffix}. {scope}"
            active = index <= 8
            department = create(
                Department,
                {"code": f"DEMO-GER-{suffix}"},
                {
                    "name": f"Gerência de {department_name}",
                    "description": description,
                    "active": True,
                },
            )
            create(DepartmentAccess, {"user": actor, "department": department}, {})
            create(
                Portfolio,
                {"code": f"DEMO-CAR-{suffix}"},
                {
                    "name": portfolio_name,
                    "description": description,
                    "department": department,
                    "active": active,
                },
            )
            create(
                Project,
                {"code": f"DEMO-PRJ-{suffix}"},
                {
                    "name": project_name,
                    "description": description,
                    "department": department,
                    "active": active,
                },
            )
            supplier = create(
                Supplier,
                {"code": f"DEMO-FOR-{suffix}"},
                {
                    "name": supplier_name,
                    "description": description
                    + " Identificador fiscal sintético, sem validade fiscal.",
                    "tax_id": f"99000000{index:04d}00",
                    "active": active,
                },
            )
            create(
                Contract,
                {"code": f"DEMO-CTR-{suffix}"},
                {
                    "name": contract_name,
                    "description": description,
                    "department": department,
                    "supplier": supplier,
                    "active": active,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demonstração pronta: 10 gerências, 10 carteiras, 10 projetos, 10 fornecedores e 10 contratos. "
                f"{created_count} registros/concessões criados. Registros existentes foram preservados."
            )
        )
