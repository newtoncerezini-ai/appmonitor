import base64
import json
from email.utils import parseaddr
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.utils import timezone


def _safe_pdf_text(value):
    text = str(value or "-").replace("\r", "")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap_text(text, limit=92):
    words = str(text or "-").replace("\r", "").split()
    if not words:
        return ["-"]
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > limit and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _pdf_text(x, y, text, size=10, color="0 0 0", font="F1"):
    return f"BT /{font} {size} Tf {color} rg {x} {y} Td ({_safe_pdf_text(text)}) Tj ET"


def _pdf_rect(x, y, width, height, color):
    return f"{color} rg {x} {y} {width} {height} re f"


def _pdf_line(x1, y1, x2, y2, color="0.25 0.38 0.55", width=1):
    return f"{color} RG {width} w {x1} {y1} m {x2} {y2} l S"


def _draw_wrapped_text(commands, x, y, text, limit=92, size=9, leading=12, color="0.13 0.18 0.28", max_lines=8):
    for line in _wrap_text(text, limit=limit)[:max_lines]:
        commands.append(_pdf_text(x, y, line, size=size, color=color))
        y -= leading
    return y


def gerar_pdf_ata_reuniao(reuniao):
    participantes_internos = [
        participante.get_full_name() or participante.username
        for participante in reuniao.participantes_usuarios.all()
    ]
    participantes_externos = [
        f"{participante.nome} <{participante.email}>"
        for participante in reuniao.participantes_externos_lista.all()
    ]
    participantes_legado = reuniao.participantes_externos or reuniao.participantes
    participantes = participantes_internos + participantes_externos
    if participantes_legado:
        participantes.extend([linha.strip() for linha in participantes_legado.splitlines() if linha.strip()])

    data_reuniao = timezone.localtime(reuniao.data_hora)
    commands = [
        _pdf_rect(0, 690, 595, 152, "0.02 0.18 0.34"),
        "0.00 0.57 0.82 rg 330 690 m 420 742 520 730 595 760 l 595 690 l h f",
        "0.08 0.31 0.55 rg 0 690 m 120 665 230 696 320 742 l 380 772 490 766 595 790 l 595 842 l 0 842 l h f",
        _pdf_text(52, 790, "ATA DE REUNIAO", size=9, color="0.61 0.91 0.75"),
        _pdf_text(52, 758, reuniao.titulo.upper()[:48], size=20, color="1 1 1"),
        _pdf_text(52, 730, f"Empresa: {reuniao.empresa.nome}", size=9, color="0.90 0.96 1"),
        _pdf_text(52, 714, f"Data: {data_reuniao.strftime('%d/%m/%Y %H:%M')}", size=9, color="0.90 0.96 1"),
        _pdf_text(315, 730, f"Local: {reuniao.local or '-'}", size=9, color="0.90 0.96 1"),
        _pdf_text(315, 714, f"Status: {reuniao.get_status_display()}", size=9, color="0.90 0.96 1"),
    ]

    y = 650
    commands.extend(
        [
            _pdf_text(52, y, "PARTICIPANTES", size=10, color="0.00 0.39 0.22"),
            _pdf_line(52, y - 8, 543, y - 8, color="0.00 0.39 0.22", width=0.8),
        ]
    )
    y -= 26
    y = _draw_wrapped_text(commands, 52, y, ", ".join(participantes) if participantes else "-", limit=105, max_lines=4)

    y -= 18
    commands.extend(
        [
            _pdf_text(52, y, "ITENS DA AGENDA", size=10, color="0.00 0.39 0.22"),
            _pdf_line(52, y - 8, 543, y - 8, color="0.00 0.39 0.22", width=0.8),
        ]
    )
    y -= 26
    agenda_items = []
    for bloco in [reuniao.pauta, reuniao.ata, reuniao.decisoes]:
        agenda_items.extend([linha.strip() for linha in str(bloco or "").splitlines() if linha.strip()])
    if not agenda_items:
        agenda_items = ["Nenhum item de agenda registrado."]
    for index, item in enumerate(agenda_items[:10], start=1):
        y = _draw_wrapped_text(commands, 68, y, f"{index}. {item}", limit=90, size=9, leading=12, max_lines=2)
        y -= 4

    y -= 10
    commands.extend(
        [
            _pdf_text(52, y, "ENCAMINHAMENTOS", size=10, color="0.00 0.39 0.22"),
            _pdf_line(52, y - 8, 543, y - 8, color="0.00 0.39 0.22", width=0.8),
            _pdf_rect(52, y - 34, 491, 20, "0.90 0.95 0.98"),
            _pdf_text(60, y - 28, "Item", size=8, color="0.02 0.18 0.34"),
            _pdf_text(240, y - 28, "Responsavel", size=8, color="0.02 0.18 0.34"),
            _pdf_text(348, y - 28, "Prazo", size=8, color="0.02 0.18 0.34"),
            _pdf_text(420, y - 28, "Status", size=8, color="0.02 0.18 0.34"),
        ]
    )
    y -= 52
    encaminhamentos = list(reuniao.encaminhamentos.select_related("responsavel"))
    if not encaminhamentos:
        commands.append(_pdf_text(60, y, "Nenhum encaminhamento registrado.", size=9, color="0.37 0.43 0.52"))
    for item in encaminhamentos[:12]:
        responsavel = item.responsavel.get_full_name() or item.responsavel.username if item.responsavel else "-"
        prazo = item.prazo.strftime("%d/%m/%Y") if item.prazo else "-"
        status = "Convertido" if item.ja_gerado else "Pendente"
        row_y = y
        commands.append(_pdf_line(52, row_y + 10, 543, row_y + 10, color="0.84 0.89 0.94", width=0.5))
        _draw_wrapped_text(commands, 60, row_y, item.descricao, limit=34, size=8, leading=10, max_lines=2)
        _draw_wrapped_text(commands, 240, row_y, responsavel, limit=20, size=8, leading=10, max_lines=2)
        commands.append(_pdf_text(348, row_y, prazo, size=8, color="0.13 0.18 0.28"))
        commands.append(_pdf_text(420, row_y, status, size=8, color="0.13 0.18 0.28"))
        y -= 28

    commands.extend(
        [
            _pdf_line(52, 46, 543, 46, color="0.84 0.89 0.94", width=0.5),
            _pdf_text(52, 28, "Gerado automaticamente pela Plataforma de Execucao Estrategica", size=8, color="0.37 0.43 0.52"),
        ]
    )

    stream = "\n".join(commands).encode("cp1252", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

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


def _coletar_destinatarios(reuniao):
    destinatarios = []
    for usuario in reuniao.participantes_usuarios.exclude(email=""):
        destinatarios.append(usuario.email)
    for participante in reuniao.participantes_externos_lista.exclude(email=""):
        destinatarios.append(participante.email)
    return sorted(set(destinatarios))


def _conteudo_email_ata(reuniao):
    subject = f"Ata consolidada - {reuniao.titulo}"
    body = (
        f"Ola,\n\n"
        f"Segue em anexo a ata consolidada da reuniao \"{reuniao.titulo}\".\n\n"
        "Este envio foi gerado automaticamente pelo sistema de monitoramento.\n"
    )
    filename = f"ata-reuniao-{reuniao.pk}.pdf"
    return subject, body, filename, gerar_pdf_ata_reuniao(reuniao)


def _enviar_por_brevo_api(reuniao, destinatarios):
    api_key = getattr(settings, "BREVO_API_KEY", "")
    remetente_nome, remetente_email = parseaddr(getattr(settings, "DEFAULT_FROM_EMAIL", ""))
    if not remetente_email:
        raise ValueError("DEFAULT_FROM_EMAIL precisa conter um e-mail valido.")

    subject, body, filename, pdf = _conteudo_email_ata(reuniao)
    payload = {
        "sender": {"name": remetente_nome or "Consultoria X", "email": remetente_email},
        "to": [{"email": email} for email in destinatarios],
        "subject": subject,
        "textContent": body,
        "attachment": [
            {
                "name": filename,
                "content": base64.b64encode(pdf).decode("ascii"),
            }
        ],
    }
    request = Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=getattr(settings, "EMAIL_TIMEOUT", 10)) as response:
            if response.status >= 400:
                raise RuntimeError(f"Brevo API retornou status {response.status}.")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Brevo API retornou erro {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Nao foi possivel conectar na API do Brevo: {exc.reason}") from exc


def enviar_ata_reuniao_por_email(reuniao):
    destinatarios = _coletar_destinatarios(reuniao)
    if not destinatarios:
        return 0

    if getattr(settings, "BREVO_API_KEY", ""):
        _enviar_por_brevo_api(reuniao, destinatarios)
        return len(destinatarios)

    subject, body, filename, pdf = _conteudo_email_ata(reuniao)
    connection = get_connection(timeout=getattr(settings, "EMAIL_TIMEOUT", 10))
    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=destinatarios,
        connection=connection,
    )
    message.attach(filename, pdf, "application/pdf")
    message.send(fail_silently=False)
    return len(destinatarios)
