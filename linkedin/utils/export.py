"""
ExportUtils — save scraped data to JSON and/or Excel files.
"""
import json
import os


class ExportUtils:
    """Utility class for exporting data to JSON and Excel formats."""

    @staticmethod
    def _ensure_dir(filepath: str) -> None:
        """Create parent directories if they do not exist."""
        directory = os.path.dirname(filepath)
        if directory:
            os.makedirs(directory, exist_ok=True)

    @staticmethod
    def to_json(data: list[dict], filepath: str) -> None:
        """
        Save a list of dicts to a JSON file.

        Args:
            data:     List of dicts to export.
            filepath: Destination file path (created if missing).
        """
        ExportUtils._ensure_dir(filepath)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 JSON sauvegardé : {filepath} ({len(data)} entrées)")

    @staticmethod
    def to_excel(
        data: list[dict],
        filepath: str,
        sheet_name: str = "Data",
    ) -> None:
        """
        Save a list of dicts to an Excel (.xlsx) file.

        Features:
        - Auto-adjusted column widths
        - First row frozen and bold

        Args:
            data:       List of dicts to export.
            filepath:   Destination file path (created if missing).
            sheet_name: Name of the worksheet.
        """
        try:
            import openpyxl
            from openpyxl.styles import Font
        except ImportError as exc:
            raise ImportError(
                "openpyxl is required for Excel export. "
                "Install it with: pip install openpyxl"
            ) from exc

        ExportUtils._ensure_dir(filepath)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name

        if not data:
            wb.save(filepath)
            print(f"💾 Excel sauvegardé : {filepath} (vide)")
            return

        headers = list(data[0].keys())
        ws.append(headers)

        # Bold + freeze header row
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = "A2"

        for row in data:
            cells = []
            for h in headers:
                val = row.get(h)
                if isinstance(val, (list, dict)):
                    val = json.dumps(val, ensure_ascii=False)
                cells.append(val)
            ws.append(cells)

        # Auto-adjust column widths
        for col in ws.columns:
            max_len = max(
                (len(str(cell.value)) if cell.value is not None else 0)
                for cell in col
            )
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 80)

        wb.save(filepath)
        print(f"💾 Excel sauvegardé : {filepath} ({len(data)} entrées)")

    @staticmethod
    def to_json_and_excel(
        data: list[dict],
        base_name: str,
        sheet_name: str = "Data",
    ) -> None:
        """
        Save data to both JSON and Excel at the same time.

        Args:
            data:       List of dicts to export.
            base_name:  Base file path without extension
                        (e.g. "output/companies").
            sheet_name: Name of the Excel worksheet.
        """
        ExportUtils.to_json(data, f"{base_name}.json")
        ExportUtils.to_excel(data, f"{base_name}.xlsx", sheet_name)
