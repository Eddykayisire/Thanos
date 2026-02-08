# thanos_app/gui/account_table_model.py
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PySide6.QtGui import QColor
from typing import List, Dict, Any
from thanos_app.core.definitions import IMPORTANCE_LEVELS

class AccountTableModel(QAbstractTableModel):
    def __init__(self, data: List[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self._data = data or []
        self._headers = ["Importance", "Service", "Catégorie", "Identifiant", "Tags"]
        self._column_keys = ["importance", "name", "category", "username", "tags"]

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid(): return None
        row, col = index.row(), index.column()
        
        key = self._column_keys[col]
        val = self._data[row].get(key)
        
        if role == Qt.DisplayRole:
            if val is None: return ""
            if key == "importance":
                return IMPORTANCE_LEVELS.get(val, {}).get("label", str(val))
            return val

        if role == Qt.DecorationRole:
            if key == "importance":
                color_hex = IMPORTANCE_LEVELS.get(val, {}).get("color")
                if color_hex:
                    return QColor(color_hex)

        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft | Qt.AlignVCenter
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int: return len(self._data)
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int: return len(self._headers)
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if role == Qt.DisplayRole and orientation == Qt.Horizontal: return self._headers[section]
        return None
    def refresh_data(self, new_data: List[Dict[str, Any]]):
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()
    def get_account_id_for_row(self, row: int) -> int | None:
        if 0 <= row < self.rowCount(): return self._data[row].get('id')
        return None
