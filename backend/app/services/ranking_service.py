"""排名服务"""
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date, datetime
from app.models.ranking import RankingSnapshot
from loguru import logger


class RankingService:
    def __init__(self, db: Session):
        self.db = db

    def get_top50(self, snapshot_date: Optional[date] = None) -> List[RankingSnapshot]:
        """获取指定日期的TOP50排名

        如果指定日期没有排名数据，自动降级到最新的有效排名
        """
        if snapshot_date is None:
            snapshot_date = date.today()

        # 尝试查询指定日期的排名
        rankings = (
            self.db.query(RankingSnapshot)
            .filter(RankingSnapshot.snapshot_date == snapshot_date)
            .order_by(RankingSnapshot.rank_position)
            .limit(50)
            .all()
        )

        # 如果指定日期没有数据，自动降级到最新排名
        if not rankings:
            logger.warning(f"排名: {snapshot_date} 无数据，降级到最近有效排名")
            return self.get_latest_top50()

        return rankings

    def get_latest_top50(self) -> List[RankingSnapshot]:
        """获取最新TOP50排名"""
        latest_date = (
            self.db.query(RankingSnapshot.snapshot_date)
            .order_by(RankingSnapshot.snapshot_date.desc())
            .first()
        )
        if latest_date:
            rankings = (
                self.db.query(RankingSnapshot)
                .filter(RankingSnapshot.snapshot_date == latest_date[0])
                .order_by(RankingSnapshot.rank_position)
                .limit(50)
                .all()
            )
            if rankings:
                logger.info(f"排名: 使用最近有效排名日期 {latest_date[0]}")
                return rankings
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