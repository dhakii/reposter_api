from __future__ import annotations

import os
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.publishers.base import PublishMetadata, PublishResult

logger = logging.getLogger("cascade")

DEFAULT_CASCADE_FILE = Path(__file__).resolve().parent.parent / "data" / "cascade_state.json"


class CascadeCampaignManager:
    """
    Менеджер каскадной публикации (1 ролик на 3 дня по разным площадкам):
      - День 1 (18:00): Сборка нового видео -> Публикация в VK Клипы
      - День 2 (18:00): Публикация этого же видео в Instagram Reels
      - День 3 (18:00): Публикация этого же видео в YouTube Shorts
      - День 4 (18:00): Запуск нового цикла (новый ролик -> VK) и т.д.
    """

    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = Path(state_file or DEFAULT_CASCADE_FILE)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def get_configured_chain(self) -> List[str]:
        """Возвращает цепочку площадок из .env или по умолчанию (vk -> instagram -> youtube)."""
        chain_env = os.getenv("CASCADE_PLATFORMS", "vk,instagram,youtube")
        chain = [p.strip().lower() for p in chain_env.split(",") if p.strip()]
        return chain or ["vk", "instagram", "youtube"]

    def load_state(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Не удалось прочитать cascade_state.json: %s", e)
        return {}

    def save_state(self, state: Dict[str, Any]):
        try:
            self.state_file.write_text(
                json.dumps(state, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error("Ошибка сохранения cascade_state.json: %s", e)

    def start_new_campaign(
        self,
        video_path: Path,
        video_filename: str,
        lot_nums: List[int],
        lots: List[Dict[str, Any]],
        first_platform_result: PublishResult,
    ) -> Dict[str, Any]:
        chain = self.get_configured_chain()
        now_ts = time.strftime("%Y-%m-%d %H:%M:%S")

        steps = []
        for idx, platform in enumerate(chain, start=1):
            if idx == 1:
                steps.append({
                    "day": idx,
                    "platform": platform,
                    "status": "published" if first_platform_result.success else "failed",
                    "published_at": now_ts if first_platform_result.success else None,
                    "post_id": first_platform_result.post_id,
                    "error": first_platform_result.error,
                })
            else:
                steps.append({
                    "day": idx,
                    "platform": platform,
                    "status": "pending",
                    "published_at": None,
                    "post_id": None,
                    "error": None,
                })

        state = {
            "campaign_id": time.strftime("%Y%m%d_%H%M%S"),
            "video_path": str(video_path),
            "video_filename": video_filename,
            "lot_nums": lot_nums,
            "lots": [
                {
                    "lot_num": l.get("lot_num"),
                    "artist": l.get("artist"),
                    "title": l.get("title"),
                    "price": l.get("price"),
                    "size": l.get("size"),
                }
                for l in lots
            ],
            "created_at": now_ts,
            "current_step_index": 0,
            "total_steps": len(chain),
            "chain": chain,
            "steps": steps,
            "status": "active" if len(chain) > 1 else "completed",
        }
        self.save_state(state)
        logger.info(
            "Стартовала новая 3-дневная кампания %s! День 1 завершен (%s). Следующая площадка: День 2 (%s)",
            state["campaign_id"],
            chain[0],
            chain[1] if len(chain) > 1 else "нет",
        )
        return state

    def get_pending_action(self) -> Optional[Dict[str, Any]]:
        state = self.load_state()
        if not state or state.get("status") != "active":
            return None

        steps = state.get("steps", [])
        for idx, step in enumerate(steps):
            if step.get("status") == "pending":
                video_p = Path(state.get("video_path", ""))
                if not video_p.exists():
                    logger.warning("Видеофайл кампании %s не найден на диске. Кампания сбрасывается.", video_p)
                    return None
                return {
                    "campaign_id": state.get("campaign_id"),
                    "step_index": idx,
                    "day": step.get("day"),
                    "platform": step.get("platform"),
                    "video_path": video_p,
                    "lot_nums": state.get("lot_nums", []),
                    "lots": state.get("lots", []),
                }
        return None

    def record_step_result(self, step_index: int, result: PublishResult):
        state = self.load_state()
        if not state or "steps" not in state or step_index >= len(state["steps"]):
            return

        now_ts = time.strftime("%Y-%m-%d %H:%M:%S")
        step = state["steps"][step_index]
        step["status"] = "published" if result.success else "failed"
        step["published_at"] = now_ts
        step["post_id"] = result.post_id
        step["error"] = result.error
        state["current_step_index"] = step_index

        if step_index + 1 >= len(state["steps"]):
            state["status"] = "completed"
            logger.info("Кампания %s полностью завершена на всех площадках!", state.get("campaign_id"))
        else:
            next_platform = state["steps"][step_index + 1]["platform"]
            logger.info("Шаг %d (%s) выполнен. Следующий шаг: %s", step_index + 1, step["platform"], next_platform)

        self.save_state(state)
