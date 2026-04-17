from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.http import Http404
from django.utils import timezone
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, TemplateView

from .forms import IniciativaForm, ObjetivoEstrategicoForm, PlanoAcaoForm, TarefaForm
from .models import Iniciativa, ObjetivoEstrategico, PlanoAcao, StatusWorkflow, Tarefa, Usuario


class EmpresaContextMixin(LoginRequiredMixin):
    active_section = ""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.empresa:
            raise Http404("Usuário sem empresa vinculada.")
        return super().dispatch(request, *args, **kwargs)

    def get_empresa(self):
        return self.request.user.empresa

    def get_base_context(self):
        usuario = self.request.user
        empresa = self.get_empresa()
        return {
            "empresa": empresa,
            "active_section": self.active_section,
            "pode_gerenciar_execucao": usuario.pode_gerenciar_execucao,
            "nav_counts": {
                "objetivos": empresa.objetivos_estrategicos.count(),
                "iniciativas": empresa.iniciativas.count(),
                "tarefas": Tarefa.objects.filter(iniciativa__empresa=empresa).count(),
                "planos": PlanoAcao.objects.filter(tarefa__iniciativa__empresa=empresa).count(),
            },
        }


class DashboardView(EmpresaContextMixin, TemplateView):
    template_name = "core/dashboard.html"
    active_section = "dashboard"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        usuario = self.request.user
        empresa = self.get_empresa()
        hoje = timezone.localdate()
        limite_alerta = hoje + timedelta(days=7)

        tarefas = (
            Tarefa.objects.select_related("iniciativa", "responsavel")
            .filter(iniciativa__empresa=empresa)
            .order_by("data_vencimento", "nome")
        )
        iniciativas = (
            Iniciativa.objects.select_related("objetivo", "responsavel")
            .filter(empresa=empresa)
            .order_by("data_fim", "nome")
        )
        objetivos = empresa.objetivos_estrategicos.order_by("nome")
        etapas = (
            PlanoAcao.objects.select_related("tarefa", "responsavel")
            .filter(tarefa__iniciativa__empresa=empresa)
            .order_by("data_fim_prevista", "etapa")
        )

        minhas_tarefas = tarefas.filter(
            Q(responsavel=usuario) | Q(planos_acao__responsavel=usuario)
        ).distinct()
        total_tarefas = tarefas.count()
        tarefas_concluidas = tarefas.filter(status=StatusWorkflow.CONCLUIDO).count()
        total_etapas = etapas.count()
        etapas_concluidas = etapas.filter(status=StatusWorkflow.CONCLUIDO).count()
        total_iniciativas = iniciativas.count()
        iniciativas_concluidas = iniciativas.filter(status=StatusWorkflow.CONCLUIDO).count()
        percentual_tarefas = int((tarefas_concluidas / total_tarefas) * 100) if total_tarefas else 0
        percentual_etapas = int((etapas_concluidas / total_etapas) * 100) if total_etapas else 0
        percentual_iniciativas = int((iniciativas_concluidas / total_iniciativas) * 100) if total_iniciativas else 0
        alertas_tarefas = tarefas.filter(
            status__in=[StatusWorkflow.NAO_INICIADO, StatusWorkflow.EM_ANDAMENTO],
            data_vencimento__isnull=False,
            data_vencimento__lte=limite_alerta,
        )
        alertas_etapas = etapas.filter(
            status__in=[StatusWorkflow.NAO_INICIADO, StatusWorkflow.EM_ANDAMENTO],
            data_fim_prevista__isnull=False,
            data_fim_prevista__lte=limite_alerta,
        )

        context.update(
            {
                **self.get_base_context(),
                "hoje": hoje,
                "objetivos": objetivos[:8],
                "minhas_tarefas": minhas_tarefas[:10],
                "minhas_etapas": etapas.filter(responsavel=usuario)[:10],
                "iniciativas_em_andamento": iniciativas.exclude(status=StatusWorkflow.CONCLUIDO)[:10],
                "alertas_tarefas": alertas_tarefas[:10],
                "alertas_etapas": alertas_etapas[:10],
                "total_alertas": alertas_tarefas.count() + alertas_etapas.count(),
                "saude_operacao": {
                    "tarefas": percentual_tarefas,
                    "etapas": percentual_etapas,
                    "iniciativas": percentual_iniciativas,
                    "responsaveis": Usuario.objects.filter(empresa=empresa).count(),
                },
                "kpis": {
                    "objetivos": objetivos.count(),
                    "iniciativas_ativas": iniciativas.exclude(status=StatusWorkflow.CONCLUIDO).count(),
                    "tarefas_abertas": tarefas.exclude(status=StatusWorkflow.CONCLUIDO).count(),
                    "etapas_abertas": etapas.exclude(status=StatusWorkflow.CONCLUIDO).count(),
                },
            }
        )
        return context


class ObjectiveListView(EmpresaContextMixin, ListView):
    model = ObjetivoEstrategico
    template_name = "core/objective_list.html"
    context_object_name = "objetivos"
    active_section = "objetivos"

    def get_queryset(self):
        return (
            ObjetivoEstrategico.objects.filter(empresa=self.get_empresa())
            .annotate(total_iniciativas=Count("iniciativas"))
            .order_by("nome")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        iniciativas = Iniciativa.objects.filter(empresa=self.get_empresa())
        context.update(
            {
                **self.get_base_context(),
                "page_title": "Objetivos estratégicos",
                "page_intro": "Os pilares que organizam a consultoria e orientam a execução das iniciativas.",
                "hero_value": self.object_list.count(),
                "hero_label": "Objetivos ativos",
                "hero_secondary": iniciativas.count(),
                "hero_secondary_label": "Iniciativas ligadas",
            }
        )
        return context


class InitiativeListView(EmpresaContextMixin, ListView):
    model = Iniciativa
    template_name = "core/initiative_list.html"
    context_object_name = "iniciativas"
    active_section = "iniciativas"

    def get_queryset(self):
        queryset = (
            Iniciativa.objects.select_related("objetivo", "responsavel")
            .filter(empresa=self.get_empresa())
            .prefetch_related("tarefas", "dependencias")
            .order_by("data_fim", "nome")
        )
        status = self.request.GET.get("status")
        responsavel = self.request.GET.get("responsavel")
        janela = self.request.GET.get("janela")
        hoje = timezone.localdate()

        if status:
            queryset = queryset.filter(status=status)
        if responsavel:
            queryset = queryset.filter(responsavel_id=responsavel)
        if janela:
            dias_map = {"7": 7, "15": 15, "30": 30}
            dias = dias_map.get(janela)
            if dias:
                queryset = queryset.filter(
                    data_fim__isnull=False,
                    data_fim__gte=hoje,
                    data_fim__lte=hoje + timedelta(days=dias),
                )
        return queryset

    def _build_board_columns(self, iniciativas):
        colunas = [
            ("nao_iniciado", "Nao iniciado"),
            ("em_andamento", "Em andamento"),
            ("atrasado", "Em atraso"),
            ("concluido", "Concluido"),
        ]
        return [
            {
                "key": key,
                "title": title,
                "items": [iniciativa for iniciativa in iniciativas if iniciativa.status == key],
            }
            for key, title in colunas
        ]

    def _build_gantt_rows(self, iniciativas):
        iniciativas_com_datas = [i for i in iniciativas if i.data_inicio and i.data_fim]
        if not iniciativas_com_datas:
            return {"rows": [], "has_data": False}

        inicio_base = min(i.data_inicio for i in iniciativas_com_datas)
        fim_base = max(i.data_fim for i in iniciativas_com_datas)
        total_dias = max((fim_base - inicio_base).days + 1, 1)
        marcos = []
        cursor = inicio_base
        while cursor <= fim_base:
            marcos.append(cursor)
            cursor += timedelta(days=7)

        rows = []
        for iniciativa in iniciativas:
            if iniciativa.data_inicio and iniciativa.data_fim:
                offset = (iniciativa.data_inicio - inicio_base).days
                duration = max((iniciativa.data_fim - iniciativa.data_inicio).days + 1, 1)
                rows.append(
                    {
                        "item": iniciativa,
                        "offset_pct": round((offset / total_dias) * 100, 2),
                        "width_pct": round((duration / total_dias) * 100, 2),
                    }
                )
            else:
                rows.append({"item": iniciativa, "offset_pct": None, "width_pct": None})

        return {
            "rows": rows,
            "has_data": True,
            "timeline_start": inicio_base,
            "timeline_end": fim_base,
            "milestones": marcos,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        iniciativas = list(self.object_list)
        view_mode = self.request.GET.get("view", "lista")
        responsavel_qs = Usuario.objects.filter(empresa=self.get_empresa()).order_by("first_name", "username")
        context.update(
            {
                **self.get_base_context(),
                "page_title": "Iniciativas",
                "page_intro": "Cada iniciativa conecta um objetivo estratégico com entregas práticas, responsáveis claros e prazo.",
                "hero_value": self.object_list.exclude(status=StatusWorkflow.CONCLUIDO).count(),
                "hero_label": "Em andamento",
                "hero_secondary": self.object_list.count(),
                "hero_secondary_label": "Total mapeado",
                "total_com_dependencias": self.object_list.filter(dependencias__isnull=False).distinct().count(),
                "view_mode": view_mode,
                "status_options": StatusWorkflow.choices,
                "responsaveis_filtro": responsavel_qs,
                "selected_status": self.request.GET.get("status", ""),
                "selected_responsavel": self.request.GET.get("responsavel", ""),
                "selected_janela": self.request.GET.get("janela", ""),
                "board_columns": self._build_board_columns(iniciativas),
                "gantt": self._build_gantt_rows(iniciativas),
            }
        )
        return context


class TaskListView(EmpresaContextMixin, ListView):
    model = Tarefa
    template_name = "core/task_list.html"
    context_object_name = "tarefas"
    active_section = "tarefas"

    def get_queryset(self):
        queryset = (
            Tarefa.objects.select_related("iniciativa", "responsavel", "iniciativa__objetivo")
            .filter(iniciativa__empresa=self.get_empresa())
            .prefetch_related("planos_acao")
            .order_by("data_vencimento", "nome")
        )
        iniciativa_id = self.request.GET.get("iniciativa")
        if iniciativa_id:
            queryset = queryset.filter(iniciativa_id=iniciativa_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        empresa = self.get_empresa()
        tarefas = self.object_list
        context.update(
            {
                **self.get_base_context(),
                "page_title": "Tarefas",
                "page_intro": "Visão operacional da execução com foco em responsável, vencimento e acesso rápido ao plano de ação.",
                "hero_value": tarefas.exclude(status=StatusWorkflow.CONCLUIDO).count(),
                "hero_label": "Tarefas abertas",
                "hero_secondary": tarefas.filter(status=StatusWorkflow.ATRASADO).count(),
                "hero_secondary_label": "Em atraso",
                "iniciativas_filtro": Iniciativa.objects.filter(empresa=empresa).order_by("nome"),
                "iniciativa_selecionada": self.request.GET.get("iniciativa", ""),
            }
        )
        return context


class InitiativeDetailView(EmpresaContextMixin, DetailView):
    model = Iniciativa
    template_name = "core/initiative_detail.html"
    context_object_name = "iniciativa"
    active_section = "iniciativas"

    def get_queryset(self):
        return (
            Iniciativa.objects.select_related("objetivo", "responsavel")
            .filter(empresa=self.get_empresa())
            .prefetch_related("tarefas__planos_acao", "tarefas__responsavel", "dependencias", "desbloqueia_iniciativas")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tarefas = self.object.tarefas.select_related("responsavel").all()
        concluidas = tarefas.filter(status=StatusWorkflow.CONCLUIDO).count()
        total = tarefas.count()
        progresso = int((concluidas / total) * 100) if total else 0
        context.update(
            {
                **self.get_base_context(),
                "tarefas": tarefas,
                "progresso": progresso,
            }
        )
        return context


class GestaoExecucaoMixin(EmpresaContextMixin):
    permission_denied_message = "Seu perfil não tem permissão para criar itens."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.pode_gerenciar_execucao:
            return HttpResponseForbidden(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


class BaseCreateView(GestaoExecucaoMixin, CreateView):
    template_name = "core/form.html"
    title = ""
    submit_label = "Salvar"
    success_message = "Cadastro realizado com sucesso."
    back_url = reverse_lazy("core:dashboard")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, self.success_message)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                **self.get_base_context(),
                "title": self.title,
                "submit_label": self.submit_label,
                "back_url": self.get_back_url(),
            }
        )
        return context

    def get_back_url(self):
        return self.back_url


class ObjetivoCreateView(BaseCreateView):
    model = ObjetivoEstrategico
    form_class = ObjetivoEstrategicoForm
    title = "Novo objetivo estratégico"
    submit_label = "Criar objetivo"
    success_message = "Objetivo estratégico criado com sucesso."

    def form_valid(self, form):
        form.instance.empresa = self.request.user.empresa
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("core:dashboard")


class IniciativaCreateView(BaseCreateView):
    model = Iniciativa
    form_class = IniciativaForm
    title = "Nova iniciativa"
    submit_label = "Criar iniciativa"
    success_message = "Iniciativa criada com sucesso."

    def form_valid(self, form):
        form.instance.empresa = self.request.user.empresa
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("core:dashboard")


class TarefaCreateView(BaseCreateView):
    model = Tarefa
    form_class = TarefaForm
    title = "Nova tarefa"
    submit_label = "Criar tarefa"
    success_message = "Tarefa criada com sucesso."

    def get_initial(self):
        initial = super().get_initial()
        iniciativa_id = self.request.GET.get("iniciativa")
        if iniciativa_id:
            initial["iniciativa"] = iniciativa_id
        return initial

    def get_success_url(self):
        return reverse("core:tarefa_detail", kwargs={"pk": self.object.pk})


class PlanoAcaoCreateView(BaseCreateView):
    model = PlanoAcao
    form_class = PlanoAcaoForm
    title = "Novo plano de ação"
    submit_label = "Criar etapa"
    success_message = "Etapa do plano de ação criada com sucesso."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        tarefa_id = self.kwargs.get("tarefa_pk") or self.request.GET.get("tarefa")
        if tarefa_id:
            kwargs["tarefa"] = Tarefa.objects.get(pk=tarefa_id, iniciativa__empresa=self.request.user.empresa)
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        tarefa_id = self.kwargs.get("tarefa_pk") or self.request.GET.get("tarefa")
        if tarefa_id:
            initial["tarefa"] = tarefa_id
        return initial

    def get_success_url(self):
        return reverse("core:tarefa_detail", kwargs={"pk": self.object.tarefa_id})

    def get_back_url(self):
        tarefa_id = self.kwargs.get("tarefa_pk")
        if tarefa_id:
            return reverse("core:tarefa_detail", kwargs={"pk": tarefa_id})
        return reverse("core:dashboard")


class TarefaDetailView(EmpresaContextMixin, DetailView):
    model = Tarefa
    template_name = "core/tarefa_detail.html"
    context_object_name = "tarefa"

    def get_queryset(self):
        return Tarefa.objects.select_related(
            "iniciativa",
            "responsavel",
            "iniciativa__objetivo",
        ).prefetch_related("planos_acao").filter(iniciativa__empresa=self.request.user.empresa)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["planos_acao"] = self.object.planos_acao.select_related("responsavel")
        context.update(
            {
                **EmpresaContextMixin.get_base_context(self),
                "pode_gerenciar_execucao": self.request.user.pode_gerenciar_execucao,
                "progresso": int(
                    (
                        self.object.planos_acao.filter(status=StatusWorkflow.CONCLUIDO).count()
                        / self.object.planos_acao.count()
                    )
                    * 100
                )
                if self.object.planos_acao.count()
                else 0,
            }
        )
        return context
