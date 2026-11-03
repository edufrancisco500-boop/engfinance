from django.contrib import admin
from .models import AuditEvent, DepartmentAccess

# Cadastros operacionais usam a API auditada. Admin gerencia somente acesso.
admin.site.register(DepartmentAccess)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor", "action", "resource", "object_id"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
