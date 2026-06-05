"""排名服务"""
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date, datetime
from app.models.ranking import RankingSnapshot


class RankingService:
    def __init__(self, db: Session):
        self.db = db

    def get_top50(self, snapshot_date: Optional[date] = None) -> List[RankingSnapshot]:
        """获取指定日期的TOP50排名"""
        if snapshot_date is None:
            snapshot_date = date.today()

        return (
            self.db.query(RankingSnapshot)
            .filter(RankingSnapshot.snapshot_date == snapshot_date)
            .order_by(RankingSnapshot.rank_position)
            .limit(50)
            .all()
        )

    def get_latest_top50(self) -> List[RankingSnapshot]:
        """获取最新TOP50排名"""
        latest_date = (
            self.db.query(RankingSnapshot.snapshot_date)
            .order_by(RankingSnapshot.snapshot_date.desc())
            .first()
        )
        if latest_date:
            return self.get_top50(latest_date[0])
        return []

    def save_ranking_snapshot(self, snapshot_date: date, rankings: list):
        """保存排名快照"""
        # 先删除旧数据
        self.db.query(RankingSnapshot).filter(
            RankingSnapshot.snapshot_date == snapshot_date
        ).delete()

        # 批量插入
        for rank, item in enumerate(rankings, 1):
            snapshot = RankingSnapshot(
                snapshot_date=snapshot_date,
                rank_position=rank,
                stock_code=item["stock_code"],
                stock_name=item.get("stock_name", ""),
                predicted_return=item.get("predicted_return", 0),
                industry=item.get("industry", ""),
                market_cap=item.get("market_cap", 0),
                top_factors_json=item.get("top_factors", []),
            )
            self.db.add(snapshot)

        self.db.commit()