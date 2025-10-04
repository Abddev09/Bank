from django.http import HttpResponse
from django.contrib import admin
from import_export.admin import ImportExportMixin
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
import csv
from collections import defaultdict

from card.models import Card
from .models import Transfer, Error
from utils import format_card_number, format_phone_number,  format_balance


# ---------- helper: write sheet ----------
def _write_sheet_from_rows(ws, headers, rows):
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    align = Alignment(horizontal="center", vertical="center")

    # headers
    for col_num, column_title in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=column_title)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = align

    # rows
    for r_idx, row in enumerate(rows, start=2):
        for c_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=r_idx, column=c_idx, value=value)
            cell.alignment = align

    ws.freeze_panes = "A2"

    for column_cells in ws.columns:
        length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = length + 3


# ========================
# TransferAdmin (Excel + Crosscheck)
# ========================
@admin.register(Transfer)
class TransferAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = (
        'ext_id', 'sender_id', 'receiver_id', 'display_sending_amount', 'confirmed_at', 'get_state_display'
    )
    search_fields = [
        'ext_id', 'sender_id', 'receiver_id', 'sending_amount', 'created_at', 'confirmed_at', 'cancelled_at', 'state'
    ]

    @admin.display(description="Sending amount")
    def display_sending_amount(self, obj):
        if obj.currency == "840":
            return f'{obj.sending_amount} USD'
        elif obj.currency == "860":
            return f'{obj.sending_amount} UZS'
        elif obj.currency == "643":
            return f'{obj.sending_amount} RUB'
        return obj.sending_amount

    actions = ["export_selected_xlsx", "export_filtered_xlsx", "export_selected_csv"]

    def export_selected_xlsx(self, request, queryset):
        return self._export_transfers_with_crosscheck(queryset, filename="selected_transfers.xlsx")

    export_selected_xlsx.short_description = "Export selected transfers to Excel (with crosscheck)"

    def export_filtered_xlsx(self, request, queryset):
        qs = self.get_queryset(request)
        return self._export_transfers_with_crosscheck(qs, filename="filtered_transfers.xlsx")

    export_filtered_xlsx.short_description = "Export filtered transfers to Excel (with crosscheck)"

    def _export_transfers_with_crosscheck(self, transfers_qs, filename="transfers.xlsx"):
        wb = Workbook()
        ws = wb.active
        ws.title = "transfers"
        headers = [
            "Ext ID", "Sender ID", "Receiver ID",
            "Amount", "Currency", "Receiving Amount",
            "State", "Created At", "Confirmed At", "Cancelled At"
        ]

        transfer_rows = []
        for t in transfers_qs:
            transfer_rows.append([
                t.ext_id,
                t.sender_id,
                t.receiver_id,
                t.sending_amount,
                t.currency,
                t.receiving_amount,
                t.get_state_display(),
                t.created_at,
                t.confirmed_at,
                t.cancelled_at,
            ])

        _write_sheet_from_rows(ws, headers, transfer_rows)

        # Crosscheck - Card modelining barcha ma'lumotlarini olish
        send_counts = defaultdict(int)
        recv_counts = defaultdict(int)
        last_transfer = {}

        for sender_id, receiver_id, created in transfers_qs.values_list('sender_id', 'receiver_id', 'created_at'):
            if sender_id:
                send_counts[sender_id] += 1
                last_transfer[sender_id] = max(last_transfer.get(sender_id, created), created)
            if receiver_id:
                recv_counts[receiver_id] += 1
                last_transfer[receiver_id] = max(last_transfer.get(receiver_id, created), created)

        cards = Card.objects.all().values('id', 'card_number', 'phone', 'status', 'balance')
        cross_headers = [
            "Card ID", "Card Number", "Phone", "Status", "Balance",
            "Used as Sender", "Used as Receiver", "Transfers Count", "Last Transfer Date"
        ]
        cross_rows = []
        for c in cards:
            card_id = str(c['id'])
            used_sender = send_counts.get(card_id, 0) > 0
            used_receiver = recv_counts.get(card_id, 0) > 0
            transfers_count = send_counts.get(card_id, 0) + recv_counts.get(card_id, 0)
            last_dt = last_transfer.get(card_id)
            last_dt_iso = last_dt.isoformat() if last_dt else ""
            cross_rows.append([
                card_id,
                format_card_number(c['card_number']),
                format_phone_number(c.get('phone') or ""),
                c.get('status') or "",
                format_balance(c.get('balance') or 0),
                "YES" if used_sender else "NO",
                "YES" if used_receiver else "NO",
                transfers_count,
                last_dt_iso,
            ])

        ws2 = wb.create_sheet(title="crosscheck")
        _write_sheet_from_rows(ws2, cross_headers, cross_rows)

        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response

    def export_selected_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response['Content-Disposition'] = 'attachment; filename="selected_transfers.csv"'
        writer = csv.writer(response)
        writer.writerow(["Ext ID", "Sender ID", "Receiver ID", "Amount", "Currency", "State", "Created At"])
        for obj in queryset:
            writer.writerow([
                obj.ext_id,
                obj.sender_id,
                obj.receiver_id,
                obj.sending_amount,
                obj.currency,
                obj.get_state_display(),
                obj.created_at,
            ])
        return response

    export_selected_csv.short_description = "Export to CSV (selected transfers)"


# ========================
# ErrorAdmin
# ========================
@admin.register(Error)
class ErrorAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ('code', 'uz', 'ru', 'en')
    search_fields = ['code', 'uz', 'ru', 'en']
    actions = ["export_selected_xlsx", "export_selected_csv"]

    def export_selected_xlsx(self, request, queryset):
        wb = Workbook()
        ws = wb.active
        ws.title = "errors"
        headers = ["Code", "UZ", "RU", "EN"]
        rows = [[e.code, e.uz, e.ru, e.en] for e in queryset]
        _write_sheet_from_rows(ws, headers, rows)

        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response['Content-Disposition'] = 'attachment; filename="selected_errors.xlsx"'
        wb.save(response)
        return response

    export_selected_xlsx.short_description = "Export to Excel (selected errors)"

    def export_selected_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response['Content-Disposition'] = 'attachment; filename="selected_errors.csv"'
        writer = csv.writer(response)
        writer.writerow(["Code", "UZ", "RU", "EN"])
        for obj in queryset:
            writer.writerow([obj.code, obj.uz, obj.ru, obj.en])
        return response

    export_selected_csv.short_description = "Export to CSV (selected errors)"