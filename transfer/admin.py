from django.http import HttpResponse
from django.contrib import admin, messages as mes
from import_export.admin import ImportExportMixin
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
import csv
from collections import defaultdict

from card.models import Card
from .models import Transfer, Error
from utils import format_card_number, format_phone_number, format_expire, format_balance, card_mask


# ---------- helper: write sheet ----------
def _write_sheet_from_rows(ws, headers, rows):
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    align = Alignment(horizontal="center", vertical="center")

    # write headers
    for col_num, column_title in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=column_title)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = align

    # write rows
    for r_idx, row in enumerate(rows, start=2):
        for c_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=r_idx, column=c_idx, value=value)
            cell.alignment = align

    # auto-filter and freeze header
    last_col = get_column_letter(len(headers))
    ws.auto_filter.ref = f"A1:{last_col}{ws.max_row}"
    ws.freeze_panes = "A2"

    # auto column width
    for column_cells in ws.columns:
        length = max(len(str(cell.value)) if cell.value else 0 for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = length + 3


# ========================
# TransferAdmin (Excel + Crosscheck)
# ========================
@admin.register(Transfer)
class TransferAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = (
        'ext_id', 'display_sender_card_number', 'display_receiver_card_number',
        'sending_amount', 'created_at', 'confirmed_at', 'cancelled_at',
        'sender_phone', 'state'
    )
    search_fields = [
        'ext_id','sender_card_number','receiver_card_number',
        'sending_amount','created_at','confirmed_at','cancelled_at','sender_phone','state'
    ]


    @admin.display(description="Sender Card number")
    def display_sender_card_number(self, obj):
        print(obj)
        return card_mask(format_card_number(obj.sender_card_number))

    @admin.display(description="Receiver Card number")
    def display_receiver_card_number(self, obj):
        return card_mask(format_card_number(obj.receiver_card_number))


    actions = ["export_selected_xlsx", "export_filtered_xlsx", "export_selected_csv"]

    # Export selected transfers as Excel and include Crosscheck sheet
    def export_selected_xlsx(self, request, queryset):
        return self._export_transfers_with_crosscheck(queryset, filename="selected_transfers.xlsx")

    export_selected_xlsx.short_description = "Export selected transfers to Excel (with crosscheck)"

    # Export filtered (visible) transfers as Excel and include Crosscheck sheet
    def export_filtered_xlsx(self, request, queryset):
        qs = self.get_queryset(request)
        return self._export_transfers_with_crosscheck(qs, filename="filtered_transfers.xlsx")

    export_filtered_xlsx.short_description = "Export filtered transfers to Excel (with crosscheck)"

    def _export_transfers_with_crosscheck(self, transfers_qs, filename="transfers.xlsx"):
        wb = Workbook()
        # Transfers sheet
        ws = wb.active
        ws.title = "transfers"
        headers = [
            "Ext ID", "Sender Card", "Receiver Card", "Sender Expiry",
            "Sender Phone", "Receiver Phone", "Amount", "Currency", "Receiving Amount",
            "State", "Try Count", "Created At", "Confirmed At", "Cancelled At"
        ]

        # prepare transfer rows
        transfer_rows = []
        for t in transfers_qs:
            transfer_rows.append([
                t.ext_id,
                format_card_number(t.sender_card_number),
                format_card_number(t.receiver_card_number),
                format_expire(t.sender_card_expiry) if getattr(t, "sender_card_expiry", None) else "",
                format_phone_number(t.sender_phone),
                format_phone_number(t.receiver_phone),
                t.sending_amount,
                t.currency,
                t.receiving_amount,
                t.get_state_display() if hasattr(t, "get_state_display") else t.state,
                t.try_count,
                t.created_at,
                t.confirmed_at,
                t.cancelled_at,
            ])

        _write_sheet_from_rows(ws, headers, transfer_rows)

        # Crosscheck sheet (based on the transfers_qs passed)
        # Build counts from the provided transfers queryset (so filters apply)
        send_counts = defaultdict(int)
        recv_counts = defaultdict(int)
        last_transfer = {}

        # use .values_list to be slightly more efficient
        for sender, receiver, created in transfers_qs.values_list('sender_card_number', 'receiver_card_number', 'created_at'):
            if sender:
                sfn = format_card_number(sender)
                send_counts[sfn] += 1
                last_transfer[sfn] = max(last_transfer.get(sfn, created), created)
            if receiver:
                rfn = format_card_number(receiver)
                recv_counts[rfn] += 1
                last_transfer[rfn] = max(last_transfer.get(rfn, created), created)

        # build crosscheck rows from all cards (so you can see unused as well)
        cards = Card.objects.all().values('card_number', 'phone', 'status', 'balance')
        cross_headers = [
            "Card Number", "Phone", "Status", "Balance",
            "Used as Sender", "Used as Receiver", "Transfers Count", "Last Transfer Date"
        ]
        cross_rows = []
        for c in cards:
            cn = format_card_number(c['card_number'])
            used_sender = send_counts.get(cn, 0) > 0
            used_receiver = recv_counts.get(cn, 0) > 0
            transfers_count = send_counts.get(cn, 0) + recv_counts.get(cn, 0)
            last_dt = last_transfer.get(cn)
            last_dt_iso = last_dt.isoformat() if last_dt else ""
            cross_rows.append([
                cn,
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

        # prepare response
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response

    # CSV fallback (kept for convenience)
    def export_selected_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response['Content-Disposition'] = 'attachment; filename="selected_transfers.csv"'
        writer = csv.writer(response)
        writer.writerow(["Ext ID", "Sender Card", "Receiver Card", "Amount", "Currency", "State", "Sender Phone", "Created At"])
        for obj in queryset:
            writer.writerow([
                obj.ext_id,
                obj.sender_card_number,
                obj.receiver_card_number,
                obj.sending_amount,
                obj.currency,
                obj.get_state_display() if hasattr(obj, "get_state_display") else obj.state,
                obj.sender_phone,
                obj.created_at,
            ])
        return response

    export_selected_csv.short_description = "Export to CSV (selected transfers)"


# ========================
# ErrorAdmin (Excel export)
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
