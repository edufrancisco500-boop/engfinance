from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING
from django.db.models import Min
from .services import ZERO, net_parcels


def percentage(value, base):
    return float((value / base * 100).quantize(Decimal("0.01"))) if base > 0 else None


def contract_metrics(
    *, contract, value, expiry, position, period, today, usage, show_people
):
    # Os estoques são posições contratuais acumuladas; os rankings respeitam o período selecionado.
    position = position.filter(document__date__lte=today)
    committed = net_parcels(position.filter(document__kind="COMMITMENT"))
    realized = net_parcels(position.filter(document__kind="MEASUREMENT"))
    paid = net_parcels(position.filter(document__kind="PAYMENT"))
    balance = value - committed
    remaining = value - realized
    period_realized = net_parcels(period.filter(document__kind="MEASUREMENT"))
    period_paid = net_parcels(period.filter(document__kind="PAYMENT"))
    uses = list(usage)
    people = {}
    for record in uses:
        key = " ".join(record.person_name.casefold().split())
        entry = people.setdefault(
            key,
            {
                "name": record.person_name,
                "team": record.team,
                "uses": 0,
                "last_used": record.date.isoformat(),
            },
        )
        entry["uses"] += 1
        entry["last_used"] = max(entry["last_used"], record.date.isoformat())
    days = (expiry - today).days if expiry else None
    first_measurement = position.filter(
        document__kind="MEASUREMENT", document__reversal_of__isnull=True
    ).aggregate(v=Min("document__date"))["v"]
    start = contract.start_date or first_measurement
    forecast = {
        "method": "Média diária do realizado desde o início até hoje, incluindo dias sem execução; projeção linear, sem sazonalidade.",
        "confidence": "baixa",
        "monthly_rate": None,
        "exhaustion_date": None,
        "projected_end_spend": None,
        "projected_overrun": None,
        "scenario": "insufficient_data",
        "message": "Sem histórico suficiente para projetar o consumo.",
    }
    if days is not None and days < 0:
        forecast.update(
            scenario="expired",
            message=f"Contrato vencido há {abs(days)} dias. Verifique a situação e eventuais aditivos.",
        )
    elif contract.status in ("CLOSED", "CANCELLED", "SUSPENDED"):
        forecast.update(
            scenario="inactive",
            message="Contrato encerrado, cancelado ou suspenso: projeção de consumo não aplicada.",
        )
    elif start and start <= today and realized > ZERO:
        elapsed = max(1, (today - start).days + 1)
        rate = realized / Decimal(elapsed)
        forecast["monthly_rate"] = str((rate * 30).quantize(Decimal("0.01")))
        forecast["observed_days"] = elapsed
        if remaining <= 0:
            forecast.update(
                scenario="limit_reached",
                message="O realizado já atingiu ou ultrapassou o valor contratado.",
            )
        else:
            remaining_days = int(
                (remaining / rate).to_integral_value(rounding=ROUND_CEILING)
            )
            if remaining_days <= (date.max - today).days:
                forecast["exhaustion_date"] = (
                    today + timedelta(days=remaining_days)
                ).isoformat()
            if days is not None:
                projected = realized + rate * max(days, 0)
                forecast["projected_end_spend"] = str(
                    projected.quantize(Decimal("0.01"))
                )
                forecast["projected_overrun"] = str(
                    max(ZERO, projected - value).quantize(Decimal("0.01"))
                )
                before = remaining_days < days
                forecast.update(
                    scenario="exhaustion_before_expiry" if before else "within_limit",
                    message="Ao ritmo histórico, o valor contratado pode se esgotar antes do término."
                    if before
                    else "Ao ritmo histórico, o realizado projetado permanece dentro do valor contratado até o término.",
                )
            else:
                forecast.update(
                    scenario="no_expiry",
                    message="Consumo médio calculado; cadastre o término para comparar a projeção com a vigência.",
                )
    return {
        "code": contract.code,
        "supplier": contract.supplier.name,
        "status": contract.status,
        "start_date": contract.start_date.isoformat() if contract.start_date else None,
        "start_year": contract.start_date.year if contract.start_date else None,
        "end_date": expiry.isoformat() if expiry else None,
        "days_remaining": days,
        "period_realized": str(period_realized),
        "period_paid": str(period_paid),
        "period_committed": str(
            net_parcels(period.filter(document__kind="COMMITMENT"))
        ),
        "lifetime_committed": str(committed),
        "lifetime_realized": str(realized),
        "lifetime_paid": str(paid),
        "balance": str(balance),
        "balance_percent": percentage(balance, value),
        "remaining_to_realize": str(remaining),
        "remaining_to_realize_percent": percentage(remaining, value),
        "spent_percent": percentage(realized, value),
        "usage_count": len(uses),
        "people_count": len(people),
        "people": sorted(people.values(), key=lambda entry: entry["name"])
        if show_people
        else [],
        "people_visible": show_people,
        "position_date": today.isoformat(),
        "forecast": forecast,
    }


def rankings(rows):
    return {
        "most_spent": sorted(
            rows, key=lambda r: (-Decimal(r["period_realized"]), r["code"])
        )[:5],
        "most_paid": sorted(
            rows, key=lambda r: (-Decimal(r["period_paid"]), r["code"])
        )[:5],
        "most_committed": sorted(
            rows, key=lambda r: (-Decimal(r["period_committed"]), r["code"])
        )[:5],
        "least_used": sorted(
            rows,
            key=lambda r: (r["usage_count"], Decimal(r["period_realized"]), r["code"]),
        )[:5],
        "spending_basis": "Realizado por medições aprovadas, líquido de estornos, no período selecionado.",
        "usage_basis": "Quantidade de registros explícitos de utilização no período; lançamentos e avaliações não são contados como uso.",
    }
