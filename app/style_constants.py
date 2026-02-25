"""analyzer.py와 merger.py가 공유하는 XLSX 스타일 상수 및 래퍼 함수."""

ROW_PAD = 1  # 빈 첫 행
COL_PAD = 1  # 빈 첫 열


def apply_sheet_style(ws, headers, rows, leader_col=None, title=None):
    """XLSX 시트에 스타일을 적용하는 public 래퍼."""
    from app.output_builder import apply_sheet_style as _impl

    _impl(ws, headers, rows, leader_col=leader_col, title=title)
