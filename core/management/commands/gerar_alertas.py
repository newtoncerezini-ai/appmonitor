from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from core.models import Alerta, PlanoAcao, StatusWorkflow, Tarefa


class Command(BaseCommand):
    help = "Gera alertas para tarefas e etapas proximas do vencimento."

    def handle(self, *args, **options):
        hoje = timezone.localdate()
        limite = hoje + timedelta(days=7)
        total_alertas = 0

        tarefas = Tarefa.objects.select_related("responsavel", "iniciativa__empresa").filter(
            responsavel__isnull=False,
            status__in=[StatusWorkflow.NAO_INICIADO, StatusWorkflow.EM_ANDAMENTO],
            data_vencimento__isnull=False,
            data_vencimento__range=(hoje, limite),
        )
        etapas = PlanoAcao.objects.select_related(
            "responsavel",
            "tarefa",
            "tarefa__iniciativa__empresa",
        ).filter(
            responsavel__isnull=False,
            status__in=[StatusWorkflow.NAO_INICIADO, StatusWorkflow.EM_ANDAMENTO],
            data_fim_prevista__isnull=False,
            data_fim_prevista__range=(hoje, limite),
        )

        for tarefa in tarefas:
            _, created = Alerta.objects.get_or_create(
                empresa=tarefa.empresa,
                usuario=tarefa.responsavel,
                titulo=f"Tarefa perto do vencimento: {tarefa.nome}",
                defaults={
                    "mensagem": (
                        f"A tarefa '{tarefa.nome}' vence em {tarefa.data_vencimento} "
                        f"na iniciativa '{tarefa.iniciativa.nome}'."
                    )
                },
            )
            total_alertas += int(created)

        for etapa in etapas:
            _, created = Alerta.objects.get_or_create(
                empresa=etapa.tarefa.empresa,
                usuario=etapa.responsavel,
                titulo=f"Etapa perto do vencimento: {etapa.etapa}",
                defaults={
                    "mensagem": (
                        f"A etapa '{etapa.etapa}' da tarefa '{etapa.tarefa.nome}' "
                        f"tem fim previsto em {etapa.data_fim_prevista}."
                    )
                },
            )
            total_alertas += int(created)

        atrasadas = Tarefa.objects.filter(
            Q(data_vencimento__lt=hoje) & ~Q(status=StatusWorkflow.CONCLUIDO)
        ).update(status=StatusWorkflow.ATRASADO)
        self.stdout.write(
            self.style.SUCCESS(
                f"{total_alertas} alertas criados e {atrasadas} tarefas marcadas como atrasadas."
            )
        )
