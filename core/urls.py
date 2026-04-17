from django.urls import path

from .views import (
    DashboardView,
    IniciativaCreateView,
    InitiativeDetailView,
    InitiativeListView,
    ObjetivoCreateView,
    ObjectiveListView,
    PlanoAcaoCreateView,
    TaskListView,
    TarefaCreateView,
    TarefaDetailView,
)

app_name = "core"

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("objetivos/", ObjectiveListView.as_view(), name="objective_list"),
    path("objetivos/novo/", ObjetivoCreateView.as_view(), name="objetivo_create"),
    path("iniciativas/", InitiativeListView.as_view(), name="initiative_list"),
    path("iniciativas/nova/", IniciativaCreateView.as_view(), name="iniciativa_create"),
    path("iniciativas/<int:pk>/", InitiativeDetailView.as_view(), name="initiative_detail"),
    path("tarefas/", TaskListView.as_view(), name="task_list"),
    path("tarefas/nova/", TarefaCreateView.as_view(), name="tarefa_create"),
    path("planos-acao/novo/", PlanoAcaoCreateView.as_view(), name="plano_acao_create"),
    path("tarefas/<int:tarefa_pk>/planos-acao/novo/", PlanoAcaoCreateView.as_view(), name="plano_acao_create_for_task"),
    path("tarefas/<int:pk>/", TarefaDetailView.as_view(), name="tarefa_detail"),
]
