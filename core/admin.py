from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Alerta,
    Empresa,
    Iniciativa,
    ObjetivoEstrategico,
    PlanoAcao,
    Tarefa,
    Usuario,
)


class PlanoAcaoInline(admin.TabularInline):
    model = PlanoAcao
    extra = 0


class TarefaInline(admin.TabularInline):
    model = Tarefa
    extra = 0


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "ativa", "criada_em")
    search_fields = ("nome", "slug")
    prepopulated_fields = {"slug": ("nome",)}


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Dados da empresa", {"fields": ("empresa", "perfil", "cargo")}),
    )
    list_display = ("username", "email", "first_name", "last_name", "empresa", "perfil", "is_staff")
    list_filter = ("empresa", "perfil", "is_staff", "is_superuser", "is_active")


@admin.register(ObjetivoEstrategico)
class ObjetivoEstrategicoAdmin(admin.ModelAdmin):
    list_display = ("nome", "empresa", "criado_em")
    list_filter = ("empresa",)
    search_fields = ("nome", "descricao")


@admin.register(Iniciativa)
class IniciativaAdmin(admin.ModelAdmin):
    list_display = ("nome", "empresa", "objetivo", "status", "data_inicio", "data_fim", "responsavel")
    list_filter = ("empresa", "status")
    search_fields = ("nome", "descricao")
    inlines = [TarefaInline]


@admin.register(Tarefa)
class TarefaAdmin(admin.ModelAdmin):
    list_display = ("nome", "iniciativa", "status", "data_vencimento", "responsavel")
    list_filter = ("iniciativa__empresa", "status")
    search_fields = ("nome",)
    inlines = [PlanoAcaoInline]


@admin.register(PlanoAcao)
class PlanoAcaoAdmin(admin.ModelAdmin):
    list_display = ("etapa", "tarefa", "status", "responsavel", "data_inicio_prevista", "data_fim_prevista")
    list_filter = ("tarefa__iniciativa__empresa", "status")
    search_fields = ("etapa", "observacoes")


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "empresa", "usuario", "lido", "criado_em")
    list_filter = ("empresa", "lido")
    search_fields = ("titulo", "mensagem", "usuario__username")
