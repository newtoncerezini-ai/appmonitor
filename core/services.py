from django.conf import settings
from django.core.mail import EmailMessage
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


def _append_section(lines, title, content):
    lines.append("")
    lines.append(title)
    for line in str(content or "-").splitlines() or ["-"]:
        lines.extend(_wrap_text(line))


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

    encaminhamentos = []
    for item in reuniao.encaminhamentos.select_related("responsavel"):
        responsavel = item.responsavel.get_full_name() or item.responsavel.username if item.responsavel else "-"
        prazo = item.prazo.strftime("%d/%m/%Y") if item.prazo else "-"
        encaminhamentos.append(f"- {item.descricao} | Responsavel: {responsavel} | Prazo: {prazo}")

    lines = [
        "Ata de Reuniao",
        reuniao.titulo,
        f"Empresa: {reuniao.empresa.nome}",
        f"Data: {timezone.localtime(reuniao.data_hora).strftime('%d/%m/%Y %H:%M')}",
        f"Local: {reuniao.local or '-'}",
        f"Status: {reuniao.get_status_display()}",
    ]
    _append_section(lines, "Participantes", "\n".join(participantes) if participantes else "-")
    _append_section(lines, "Pauta", reuniao.pauta)
    _append_section(lines, "Anotacoes da ata", reuniao.ata)
    _append_section(lines, "Decisoes", reuniao.decisoes)
    _append_section(lines, "Encaminhamentos", "\n".join(encaminhamentos) if encaminhamentos else "-")

    content_lines = []
    y = 800
    for index, line in enumerate(lines[:58]):
        font_size = 16 if index == 0 else 12
        leading = 22 if index == 0 else 16
        content_lines.append(f"BT /F1 {font_size} Tf 50 {y} Td ({_safe_pdf_text(line)}) Tj ET")
        y -= leading

    stream = "\n".join(content_lines).encode("cp1252", errors="replace")
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


def enviar_ata_reuniao_por_email(reuniao):
    destinatarios = []
    for usuario in reuniao.participantes_usuarios.exclude(email=""):
        destinatarios.append(usuario.email)
    for participante in reuniao.participantes_externos_lista.exclude(email=""):
        destinatarios.append(participante.email)

    destinatarios = sorted(set(destinatarios))
    if not destinatarios:
        return 0

    subject = f"Ata consolidada - {reuniao.titulo}"
    body = (
        f"Ola,\n\n"
        f"Segue em anexo a ata consolidada da reuniao \"{reuniao.titulo}\".\n\n"
        "Este envio foi gerado automaticamente pelo sistema de monitoramento.\n"
    )
    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=destinatarios,
    )
    filename = f"ata-reuniao-{reuniao.pk}.pdf"
    message.attach(filename, gerar_pdf_ata_reuniao(reuniao), "application/pdf")
    message.send(fail_silently=False)
    return len(destinatarios)
