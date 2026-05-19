# ========== position_manager.py 完整代码 ==========

import json
from pathlib import Path
from typing import Dict, List, Any

class PositionManager:
    def __init__(self, positions_dir="positions"):
        # 使用相对于本文件的绝对路径
        self.base_dir = Path(__file__).parent.resolve()  # 这行必须在最前面！
        self.positions_dir = self.base_dir / positions_dir
        self.positions: Dict[str, Any] = {}
        self.load_all_positions()

    def load_all_positions(self):
        for file in self.positions_dir.glob("*.json"):
            with open(file, "r", encoding="utf-8") as f:
                pos = json.load(f)
                self.positions[pos["name"]] = pos

    def get_position(self, name: str) -> Dict:
        return self.positions.get(name)

    def get_question_bank(self, position_name: str) -> List[Dict]:
        pos = self.get_position(position_name)
        return pos.get("question_bank", []) if pos else []

    def get_knowledge_base_paths(self, position_name: str) -> List[Path]:
        pos = self.get_position(position_name)
        if not pos:
            return []

        # Allow both explicit file list and directory/glob patterns in positions/*.json.
        entries = pos.get("knowledge_base", []) or []
        out: List[Path] = []

        for entry in entries:
            p = Path(entry)
            if not p.is_absolute():
                p = self.base_dir / p

            # If it's a directory, include all md files under it.
            if p.exists() and p.is_dir():
                out.extend([x for x in p.rglob("*.md") if x.is_file()])
                continue

            # If it looks like a glob (contains wildcard), expand it.
            if any(ch in str(p) for ch in ("*", "?", "[")):
                out.extend([x for x in self.base_dir.glob(str(entry)) if x.is_file()])
                continue

            out.append(p)

        # Deduplicate and avoid the accidental nested "knowledge_base/knowledge_base" mirror.
        seen = set()
        deduped: List[Path] = []
        for p in out:
            try:
                rp = p.resolve()
            except Exception:
                rp = p
            s = str(rp)
            if "\\knowledge_base\\knowledge_base\\" in s or "/knowledge_base/knowledge_base/" in s:
                continue
            if s in seen:
                continue
            seen.add(s)
            deduped.append(rp)

        return deduped
 
