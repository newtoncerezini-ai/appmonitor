import csv
import io
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import formats
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import Iniciativa, ObjetivoEstrategico, StatusWorkflow, Tarefa, Usuario


OPEN_STATUSES = [
    StatusWorkflow.NAO_INICIADO,
    StatusWorkflow.EM_ANDAMENTO,
    StatusWorkflow.ATRASADO,
    StatusWorkflow.BLOQUEADO,
]


def _percent(part, total):
    return int((part / total) * 100) if total else 0


def _parse_date_filter(value):
    return parse_date(value) if value else None


def _date(value):
    return formats.date_format(value, "SHORT_DATE_FORMAT") if value else "-"


def _status_counts(queryset):
    counts = {key: 0 for key, _label in StatusWorkflow.choices}
    for item in queryset.values("status").annotate(total=Count("id")):
        counts[item["status"]] = item["total"]
    return [
        {"key": key, "label": label, "total": counts.get(key, 0)}
        for key, label in StatusWorkflow.choices
    ]


def _base_querysets(empresa, filters):
    tarefas = Tarefa.objects.select_related(
        "responsavel",
        "iniciativa",
        "iniciativa__objetivo",
    ).filter(iniciativa__empresa=empresa)
    iniciativas = Iniciativa.objects.select_related(
        "responsavel",
        "objetivo",
    ).filter(empresa=empresa)

    if filters["responsavel"]:
        tarefas = tarefas.filter(responsavel_id=filters["responsavel"])
        iniciativas = iniciativas.filter(responsavel_id=filters["responsavel"])
    if filters["iniciativa"]:
        tarefas = tarefas.filter(iniciativa_id=filters["iniciativa"])
        iniciativas = iniciativas.filter(pk=filters["iniciativa"])
    if filters["objetivo"]:
        tarefas = tarefas.filter(iniciativa__objetivo_id=filters["objetivo"])
        iniciativas = iniciativas.filter(objetivo_id=filters["objetivo"])
    if filters["status"]:
        tarefas = tarefas.filter(status=filters["status"])
        iniciativas = iniciativas.filter(status=filters["status"])

    data_inicio = filters["data_inicio"]
    data_fim = filters["data_fim"]
    if data_inicio:
        tarefas = tarefas.filter(data_vencimento__isnull=False, data_vencimento__gte=data_inicio)
        iniciativas = iniciativas.filter(data_fim__isnull=False, data_fim__gte=data_inicio)
    if data_fim:
        tarefas = tarefas.filter(data_vencimento__isnull=False, data_vencimento__lte=data_fim)
        iniciativas = iniciativas.filter(data_fim__isnull=False, data_fim__lte=data_fim)

    return tarefas.order_by("data_vencimento", "nome"), iniciativas.order_by("data_fim", "nome")


def _responsavel_rows(empresa, tarefas, iniciativas):
    usuarios = list(Usuario.objects.filter(empresa=empresa).order_by("first_name", "username"))
    rows = []
    for usuario in usuarios:
        tarefas_usuario = tarefas.filter(responsavel=usuario)
        iniciativas_usuario = iniciativas.filter(responsavel=usuario)
        total_tarefas = tarefas_usuario.count()
        tarefas_concluidas = tarefas_usuario.filter(status=StatusWorkflow.CONCLUIDO).count()
        proximo_vencimento = (
            tarefas_usuario.filter(
                status__in=OPEN_STATUSES,
                data_vencimento__isnull=False,
            )
            .order_by("data_vencimento")
            .first()
        )
        if total_tarefas or iniciativas_usuario.exists():
            rows.append(
                {
                    "usuario": usuario,
                    "cargo": usuario.cargo or usuario.get_perfil_display(),
                    "tarefas_total": total_tarefas,
                    "tarefas_abertas": tarefas_usuario.filter(status__in=OPEN_STATUSES).count(),
                    "tarefas_concluidas": tarefas_concluidas,
                    "tarefas_atrasadas": tarefas_usuario.filter(status=StatusWorkflow.ATRASADO).count(),
                    "iniciativas_total": iniciativas_usuario.count(),
                    "iniciativas_abertas": iniciativas_usuario.filter(status__in=OPEN_STATUSES).count(),
                    "iniciativas_atrasadas": iniciativas_usuario.filter(status=StatusWorkflow.ATRASADO).count(),
                    "progresso": _percent(tarefas_concluidas, total_tarefas),
                    "proximo_vencimento": proximo_vencimento,
                }
            )

    tarefas_sem_responsavel = tarefas.filter(responsavel__isnull=True)
    iniciativas_sem_responsavel = iniciativas.filter(responsavel__isnull=True)
    if tarefas_sem_responsavel.exists() or iniciativas_sem_responsavel.exists():
        total_tarefas = tarefas_sem_responsavel.count()
        tarefas_concluidas = tarefas_sem_responsavel.filter(status=StatusWorkflow.CONCLUIDO).count()
        rows.append(
            {
                "usuario": None,
                "cargo": "Sem responsavel definido",
                "tarefas_total": total_tarefas,
                "tarefas_abertas": tarefas_sem_responsavel.filter(status__in=OPEN_STATUSES).count(),
                "tarefas_concluidas": tarefas_concluidas,
                "tarefas_atrasadas": tarefas_sem_responsavel.filter(status=StatusWorkflow.ATRASADO).count(),
                "iniciativas_total": iniciativas_sem_responsavel.count(),
                "iniciativas_abertas": iniciativas_sem_responsavel.filter(status__in=OPEN_STATUSES).count(),
                "iniciativas_atrasadas": iniciativas_sem_responsavel.filter(status=StatusWorkflow.ATRASADO).count(),
                "progresso": _percent(tarefas_concluidas, total_tarefas),
                "proximo_vencimento": tarefas_sem_responsavel.filter(
                    status__in=OPEN_STATUSES,
                    data_vencimento__isnull=False,
                ).order_by("data_vencimento").first(),
            }
        )
    return sorted(rows, key=lambda row: (row["tarefas_atrasadas"], row["tarefas_abertas"]), reverse=True)


def _iniciativa_rows(iniciativas, tarefas):
    rows = []
    for iniciativa in iniciativas.prefetch_related("dependencias"):
        tarefas_iniciativa = tarefas.filter(iniciativa=iniciativa)
        total_tarefas = tarefas_iniciativa.count()
        tarefas_concluidas = tarefas_iniciativa.filter(status=StatusWorkflow.CONCLUIDO).count()
        rows.append(
            {
                "iniciativa": iniciativa,
                "objetivo": iniciativa.objetivo,
                "responsavel": iniciativa.responsavel,
                "tarefas_total": total_tarefas,
                "tarefas_abertas": tarefas_iniciativa.filter(status__in=OPEN_STATUSES).count(),
                "tarefas_concluidas": tarefas_concluidas,
                "tarefas_atrasadas": tarefas_iniciativa.filter(status=StatusWorkflow.ATRASADO).count(),
                "progresso": _percent(tarefas_concluidas, total_tarefas),
                "dependencias_total": iniciativa.dependencias.count(),
                "proximo_vencimento": tarefas_iniciativa.filter(
                    status__in=OPEN_STATUSES,
                    data_vencimento__isnull=False,
                ).order_by("data_vencimento").first(),
            }
        )
    return rows


def build_reports_context(empresa, params):
    filters = {
        "responsavel": params.get("responsavel", ""),
        "iniciativa": params.get("iniciativa", ""),
        "objetivo": params.get("objetivo", ""),
        "status": params.get("status", ""),
        "data_inicio": _parse_date_filter(params.get("data_inicio", "")),
        "data_fim": _parse_date_filter(params.get("data_fim", "")),
    }
    tarefas, iniciativas = _base_querysets(empresa, filters)
    hoje = timezone.localdate()
    limite_alerta = hoje + timedelta(days=7)

    total_tarefas = tarefas.count()
    tarefas_concluidas = tarefas.filter(status=StatusWorkflow.CONCLUIDO).count()
    total_iniciativas = iniciativas.count()
    iniciativas_concluidas = iniciativas.filter(status=StatusWorkflow.CONCLUIDO).count()

    tarefas_risco = tarefas.filter(
        Q(status=StatusWorkflow.ATRASADO)
        | Q(status__in=OPEN_STATUSES, data_vencimento__isnull=False, data_vencimento__lt=hoje)
    ).distinct()
    proximos_vencimentos = tarefas.filter(
        status__in=OPEN_STATUSES,
        data_vencimento__isnull=False,
        data_vencimento__gte=hoje,
        data_vencimento__lte=limite_alerta,
    ).order_by("data_vencimento", "nome")

    return {
        "report_querystring": params.urlencode() if hasattr(params, "urlencode") else "",
        "filters": {
            **filters,
            "data_inicio": params.get("data_inicio", ""),
            "data_fim": params.get("data_fim", ""),
        },
        "filter_options": {
            "responsaveis": Usuario.objects.filter(empresa=empresa).order_by("first_name", "username"),
            "iniciativas": Iniciativa.objects.filter(empresa=empresa).order_by("nome"),
            "objetivos": ObjetivoEstrategico.objects.filter(empresa=empresa).order_by("nome"),
            "status_options": StatusWorkflow.choices,
        },
        "kpis": {
            "tarefas_total": total_tarefas,
            "tarefas_abertas": tarefas.filter(status__in=OPEN_STATUSES).count(),
            "tarefas_atrasadas": tarefas_risco.count(),
            "tarefas_progresso": _percent(tarefas_concluidas, total_tarefas),
            "iniciativas_total": total_iniciativas,
            "iniciativas_abertas": iniciativas.filter(status__in=OPEN_STATUSES).count(),
            "iniciativas_atrasadas": iniciativas.filter(status=StatusWorkflow.ATRASADO).count(),
            "iniciativas_progresso": _percent(iniciativas_concluidas, total_iniciativas),
        },
        "status_tarefas": _status_counts(tarefas),
        "status_iniciativas": _status_counts(iniciativas),
        "responsavel_rows": _responsavel_rows(empresa, tarefas, iniciativas),
        "iniciativa_rows": _iniciativa_rows(iniciativas, tarefas),
        "tarefas_risco": tarefas_risco.order_by("data_vencimento", "nome")[:12],
        "proximos_vencimentos": proximos_vencimentos[:12],
    }


def generate_reports_csv(empresa, report):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

    writer.writerow(["Relatorio de execucao", empresa.nome])
    writer.writerow(["Gerado em", timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")])
    writer.writerow([])

    writer.writerow(["Resumo"])
    writer.writerow(["Indicador", "Valor"])
    for label, value in [
        ("Tarefas filtradas", report["kpis"]["tarefas_total"]),
        ("Tarefas abertas", report["kpis"]["tarefas_abertas"]),
        ("Tarefas em risco", report["kpis"]["tarefas_atrasadas"]),
        ("Progresso das tarefas", f"{report['kpis']['tarefas_progresso']}%"),
        ("Iniciativas filtradas", report["kpis"]["iniciativas_total"]),
        ("Iniciativas abertas", report["kpis"]["iniciativas_abertas"]),
        ("Iniciativas atrasadas", report["kpis"]["iniciativas_atrasadas"]),
        ("Progresso das iniciativas", f"{report['kpis']['iniciativas_progresso']}%"),
    ]:
        writer.writerow([label, value])
    writer.writerow([])

    writer.writerow(["Tarefas por status"])
    writer.writerow(["Status", "Total"])
    for item in report["status_tarefas"]:
        writer.writerow([item["label"], item["total"]])
    writer.writerow([])

    writer.writerow(["Iniciativas por status"])
    writer.writerow(["Status", "Total"])
    for item in report["status_iniciativas"]:
        writer.writerow([item["label"], item["total"]])
    writer.writerow([])

    writer.writerow(["Relatorio por responsavel"])
    writer.writerow([
        "Responsavel",
        "Cargo",
        "Tarefas",
        "Abertas",
        "Concluidas",
        "Atrasadas",
        "Iniciativas",
        "Iniciativas abertas",
        "Iniciativas atrasadas",
        "Progresso",
        "Proximo vencimento",
    ])
    for row in report["responsavel_rows"]:
        writer.writerow([
            row["usuario"] or "Sem responsavel",
            row["cargo"],
            row["tarefas_total"],
            row["tarefas_abertas"],
            row["tarefas_concluidas"],
            row["tarefas_atrasadas"],
            row["iniciativas_total"],
            row["iniciativas_abertas"],
            row["iniciativas_atrasadas"],
            f"{row['progresso']}%",
            _date(row["proximo_vencimento"].data_vencimento) if row["proximo_vencimento"] else "-",
        ])
    writer.writerow([])

    writer.writerow(["Relatorio por iniciativa"])
    writer.writerow([
        "Iniciativa",
        "Objetivo",
        "Responsavel",
        "Status",
        "Tarefas",
        "Abertas",
        "Concluidas",
        "Atrasadas",
        "Dependencias",
        "Progresso",
        "Data fim",
        "Proximo vencimento",
    ])
    for row in report["iniciativa_rows"]:
        writer.writerow([
            row["iniciativa"].nome,
            row["objetivo"].nome,
            row["responsavel"] or "Nao definido",
            row["iniciativa"].get_status_display(),
            row["tarefas_total"],
            row["tarefas_abertas"],
            row["tarefas_concluidas"],
            row["tarefas_atrasadas"],
            row["dependencias_total"],
            f"{row['progresso']}%",
            _date(row["iniciativa"].data_fim),
            _date(row["proximo_vencimento"].data_vencimento) if row["proximo_vencimento"] else "-",
        ])
    writer.writerow([])

    writer.writerow(["Tarefas com atencao"])
    writer.writerow(["Tarefa", "Iniciativa", "Responsavel", "Status", "Vencimento"])
    for tarefa in report["tarefas_risco"]:
        writer.writerow([
            tarefa.nome,
            tarefa.iniciativa.nome,
            tarefa.responsavel or "Sem responsavel",
            tarefa.get_status_display(),
            _date(tarefa.data_vencimento),
        ])

    return ("\ufeff" + output.getvalue()).encode("utf-8")


def _pdf_safe(value):
    return str(value or "-").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_text(x, y, text, size=9, color="0.10 0.13 0.20", font="F1"):
    return f"BT /{font} {size} Tf {color} rg {x} {y} Td ({_pdf_safe(text)}) Tj ET"


def _pdf_rect(x, y, width, height, color):
    return f"{color} rg {x} {y} {width} {height} re f"


def _pdf_line(x1, y1, x2, y2, color="0.78 0.83 0.91", width=0.6):
    return f"{color} RG {width} w {x1} {y1} m {x2} {y2} l S"


def _truncate(value, limit):
    text = str(value or "-")
    return text if len(text) <= limit else f"{text[:limit - 3]}..."


def _draw_row(commands, y, columns, widths, color="0.10 0.13 0.20"):
    x = 52
    for value, width in zip(columns, widths):
        commands.append(_pdf_text(x, y, _truncate(value, max(int(width / 4.6), 8)), size=8, color=color))
        x += width
    commands.append(_pdf_line(52, y - 7, 543, y - 7))
    return y - 18


def _new_page(pages, title, subtitle):
    commands = [
        _pdf_rect(0, 760, 595, 82, "0.14 0.34 0.90"),
        _pdf_text(52, 804, title, size=18, color="1 1 1"),
        _pdf_text(52, 782, subtitle, size=9, color="0.90 0.94 1"),
    ]
    pages.append(commands)
    return commands, 724


def generate_reports_pdf(empresa, report):
    pages = []
    generated_at = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")
    commands, y = _new_page(
        pages,
        "Relatorio de execucao",
        f"{empresa.nome} - gerado em {generated_at}",
    )

    kpis = report["kpis"]
    cards = [
        ("Tarefas", kpis["tarefas_total"], f"{kpis['tarefas_progresso']}% concluidas"),
        ("Abertas", kpis["tarefas_abertas"], "tarefas em execucao"),
        ("Riscos", kpis["tarefas_atrasadas"], "tarefas atrasadas/vencidas"),
        ("Iniciativas", kpis["iniciativas_total"], f"{kpis['iniciativas_progresso']}% concluidas"),
    ]
    x = 52
    for label, value, note in cards:
        commands.append(_pdf_rect(x, y - 54, 112, 54, "0.92 0.95 1"))
        commands.append(_pdf_text(x + 10, y - 18, label, size=8, color="0.36 0.40 0.48"))
        commands.append(_pdf_text(x + 10, y - 37, value, size=16, color="0.14 0.34 0.90"))
        commands.append(_pdf_text(x + 10, y - 49, note, size=7, color="0.36 0.40 0.48"))
        x += 126
    y -= 92

    commands.append(_pdf_text(52, y, "Distribuicao por status", size=12, color="0.14 0.34 0.90"))
    y -= 24
    commands.append(_pdf_text(52, y, "Tarefas", size=9, color="0.10 0.13 0.20"))
    commands.append(_pdf_text(300, y, "Iniciativas", size=9, color="0.10 0.13 0.20"))
    y -= 18
    for tarefa_status, iniciativa_status in zip(report["status_tarefas"], report["status_iniciativas"]):
        commands.append(_pdf_text(52, y, f"{tarefa_status['label']}: {tarefa_status['total']}", size=8))
        commands.append(_pdf_text(300, y, f"{iniciativa_status['label']}: {iniciativa_status['total']}", size=8))
        y -= 14

    y -= 18
    commands.append(_pdf_text(52, y, "Relatorio por responsavel", size=12, color="0.14 0.34 0.90"))
    y -= 22
    widths = [150, 55, 55, 65, 65, 70]
    y = _draw_row(commands, y, ["Responsavel", "Tarefas", "Abertas", "Atrasadas", "Iniciativas", "Progresso"], widths, color="0.36 0.40 0.48")
    for row in report["responsavel_rows"][:14]:
        if y < 82:
            commands, y = _new_page(pages, "Relatorio de execucao", "Responsaveis")
            y = _draw_row(commands, y, ["Responsavel", "Tarefas", "Abertas", "Atrasadas", "Iniciativas", "Progresso"], widths, color="0.36 0.40 0.48")
        y = _draw_row(
            commands,
            y,
            [
                row["usuario"] or "Sem responsavel",
                row["tarefas_total"],
                row["tarefas_abertas"],
                row["tarefas_atrasadas"],
                row["iniciativas_total"],
                f"{row['progresso']}%",
            ],
            widths,
        )

    commands, y = _new_page(pages, "Relatorio de execucao", "Iniciativas e riscos")
    commands.append(_pdf_text(52, y, "Relatorio por iniciativa", size=12, color="0.14 0.34 0.90"))
    y -= 22
    widths = [178, 98, 72, 52, 58, 58]
    y = _draw_row(commands, y, ["Iniciativa", "Responsavel", "Status", "Tarefas", "Atrasadas", "Progresso"], widths, color="0.36 0.40 0.48")
    for row in report["iniciativa_rows"][:18]:
        if y < 82:
            commands, y = _new_page(pages, "Relatorio de execucao", "Iniciativas")
            y = _draw_row(commands, y, ["Iniciativa", "Responsavel", "Status", "Tarefas", "Atrasadas", "Progresso"], widths, color="0.36 0.40 0.48")
        y = _draw_row(
            commands,
            y,
            [
                row["iniciativa"].nome,
                row["responsavel"] or "Nao definido",
                row["iniciativa"].get_status_display(),
                row["tarefas_total"],
                row["tarefas_atrasadas"],
                f"{row['progresso']}%",
            ],
            widths,
        )

    y -= 20
    if y < 130:
        commands, y = _new_page(pages, "Relatorio de execucao", "Tarefas com atencao")
    commands.append(_pdf_text(52, y, "Tarefas com atencao", size=12, color="0.14 0.34 0.90"))
    y -= 22
    widths = [202, 120, 88, 76]
    y = _draw_row(commands, y, ["Tarefa", "Iniciativa", "Responsavel", "Vencimento"], widths, color="0.36 0.40 0.48")
    for tarefa in report["tarefas_risco"][:12]:
        if y < 82:
            commands, y = _new_page(pages, "Relatorio de execucao", "Tarefas com atencao")
            y = _draw_row(commands, y, ["Tarefa", "Iniciativa", "Responsavel", "Vencimento"], widths, color="0.36 0.40 0.48")
        y = _draw_row(
            commands,
            y,
            [
                tarefa.nome,
                tarefa.iniciativa.nome,
                tarefa.responsavel or "Sem responsavel",
                _date(tarefa.data_vencimento),
            ],
            widths,
        )

    return _build_pdf(pages)


def _build_pdf(pages):
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        None,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    page_refs = []
    next_object = 4
    for commands in pages:
        page_obj = next_object
        content_obj = next_object + 1
        page_refs.append(f"{page_obj} 0 R")
        stream = "\n".join(commands).encode("cp1252", errors="replace")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj} 0 R >>".encode("ascii")
        )
        objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
        next_object += 2
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(page_refs)} >>".encode("ascii")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii")
    )
    return bytes(pdf)
