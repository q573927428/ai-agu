# A股量化选股平台 - 开发文档

> 版本：v1.0  
> 日期：2026-06-05  
> 技术栈：Nuxt4 + Vue3 + TypeScript / Python FastAPI / MySQL8 / AkShare / LightGBM

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [项目目录结构](#3-项目目录结构)
4. [数据库设计](#4-数据库设计)
5. [后端模块设计](#5-后端模块设计)
6. [前端模块设计](#6-前端模块设计)
7. [因子体系设计（50个因子）](#7-因子体系设计50个因子)
8. [机器学习流程](#8-机器学习流程)
9. [REST API 设计](#9-rest-api-设计)
10. [定时任务设计](#10-定时任务设计)
11. [部署方案](#11-部署方案)
12. [开发路线图](#12-开发路线图)

---

## 1. 项目概述

### 1.1 项目目标

构建一个全自动化的A股量化选股平台，实现从数据采集、因子计算、模型训练到股票排名预测的完整流水线，并通过Web前端展示TOP50股票排名及详情。

### 1.2 核心功能

| 编号 | 功能 | 描述 |
|------|------|------|
| F1 | 数据采集 | 每日自动获取A股全市场股票数据（不含K线）及财务数据 |
| F2 | 因子工程 | 计算50个宏观/市场/行业/个股因子 |
| F3 | 标签生成 | 基于次日收益率生成训练标签 |
| F4 | 模型训练 | 使用LightGBM训练排序模型 |
| F5 | 每日预测 | 预测全市场股票次日收益率 |
| F6 | TOP50排名 | 输出收益率预测最高的50只股票 |
| F7 | REST API | 提供标准RESTful接口供前端调用 |
| F8 | 前端展示 | Nuxt4页面展示排名列表与股票详情 |

### 1.3 技术选型理由

| 技术 | 理由 |
|------|------|
| **Python FastAPI** | 高性能异步框架，原生支持异步数据采集；自动生成Swagger文档 |
| **Nuxt4 + Vue3 + TypeScript** | SSR/SSG支持，SEO友好；类型安全；Vue3 Composition API |
| **MySQL8** | 成熟的关系型数据库，支持窗口函数、CTE，适合结构化因子数据存储 |
| **AkShare** | 国产开源金融数据接口，覆盖A股全市场数据，免费使用 |
| **LightGBM** | 基于直方图的梯度提升框架，训练速度快，支持排序学习（LTR），适合金融数据 |

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Nuxt4)                       │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐ │
│  │ 首页仪表盘 │  │ TOP50排名 │  │ 股票详情页 │  │ 因子分析  │ │
│  └───────────┘  └───────────┘  └───────────┘  └──────────┘ │
│                         │ HTTP/REST                         │
└─────────────────────────┼───────────────────────────────────┘
                          │
┌─────────────────────────┼───────────────────────────────────┐
│                    Backend (FastAPI)                        │
│  ┌──────────────────────┴──────────────────────────────┐   │
│  │                   API Layer                          │   │
│  │  /api/v1/stocks  /api/v1/rankings  /api/v1/factors  │   │
│  └──────────┬──────────────────────────────┬───────────┘   │
│             │                              │                │
│  ┌──────────┴──────────┐  ┌────────────────┴───────────┐   │
│  │   Service Layer     │  │   ML Pipeline              │   │
│  │  - StockService     │  │  - FactorEngine            │   │
│  │  - RankingService   │  │  - LabelGenerator          │   │
│  │  - FactorService    │  │  - LightGBMTrainer         │   │
│  └──────────┬──────────┘  │  - Predictor               │   │
│             │              └────────────────┬───────────┘   │
│  ┌──────────┴──────────────────────────────┴───────────┐   │
│  │                  Data Layer / DAO                    │   │
│  └──────────┬──────────────────────────────┬───────────┘   │
│             │                              │                │
│  ┌──────────┴──────────┐  ┌────────────────┴───────────┐   │
│  │   MySQL8 Database   │  │   AkShare Data Fetcher     │   │
│  └─────────────────────┘  └────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Task Scheduler (APScheduler)            │   │
│  │  - 每日数据更新  - 因子计算  - 模型训练  - 预测     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 数据流图

```
AkShare ──→ DataFetcher ──→ MySQL (原始数据)
                                │
                    ┌───────────┴───────────┐
                    │   FactorEngine        │
                    │   (计算50个因子)        │
                    └───────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │   LabelGenerator      │
                    │   (次日收益率标签)       │
                    └───────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │   训练数据集 (features) │
                    └───────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │   LightGBMTrainer     │
                    │   (模型训练/更新)      │
                    └───────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │   Predictor           │
                    │   (每日预测)           │
                    └───────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │   RankingEngine       │
                    │   (TOP50排序输出)      │
                    └───────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │   REST API / Nuxt4    │
                    │   (前端展示)           │
                    └───────────────────────┘
```

---

## 3. 项目目录结构

### 3.1 后端 (backend/)

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI 应用入口
│   ├── config.py                   # 配置管理 (DB, AkShare, 模型路径等)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                 # 依赖注入 (DB Session, 服务实例)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py           # v1 路由聚合
│   │       ├── stocks.py           # 股票相关接口
│   │       ├── rankings.py         # 排名相关接口
│   │       └── factors.py          # 因子相关接口
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                 # SQLAlchemy Base
│   │   ├── stock.py                # 股票基础信息表
│   │   ├── stock_daily.py          # 股票每日行情/因子数据
│   │   ├── financial.py            # 财务报表数据
│   │   ├── macro.py                # 宏观经济数据
│   │   ├── factor.py               # 因子存储表
│   │   ├── prediction.py           # 预测结果表
│   │   └── ranking.py              # 排名快照表
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── stock.py                # Pydantic 请求/响应模型
│   │   ├── ranking.py
│   │   └── factor.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── data_fetcher.py         # AkShare 数据采集服务
│   │   ├── factor_engine.py        # 因子计算引擎
│   │   ├── label_generator.py      # 标签生成器
│   │   ├── trainer.py              # LightGBM 训练器
│   │   ├── predictor.py            # 预测器
│   │   ├── ranking_service.py      # 排名服务
│   │   └── stock_service.py        # 股票信息服务
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── features.py             # 特征工程工具
│   │   ├── model.py                # LightGBM 模型封装
│   │   └── evaluation.py           # 模型评估工具 (IC/RankIC/回测)
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── jobs.py                 # APScheduler 定时任务定义
│   └── utils/
│       ├── __init__.py
│       ├── date_utils.py           # 交易日历工具
│       └── db_utils.py             # 数据库工具函数
├── alembic/                         # 数据库迁移
│   ├── env.py
│   └── versions/
├── tests/
│   ├── __init__.py
│   ├── test_data_fetcher.py
│   ├── test_factor_engine.py
│   └── test_trainer.py
├── scripts/
│   ├── init_db.py                   # 数据库初始化脚本
│   ├── backfill_data.py            # 历史数据回填脚本
│   └── run_pipeline.py             # 一键运行完整流水线
├── requirements.txt
├── .env                             # 环境变量配置
└── Dockerfile
```

### 3.2 前端 (frontend/)

```
frontend/
├── nuxt.config.ts                   # Nuxt4 配置
├── tsconfig.json
├── package.json
├── app/
│   ├── app.vue                      # 根组件
│   ├── layouts/
│   │   └── default.vue             # 默认布局
│   ├── pages/
│   │   ├── index.vue               # 首页仪表盘
│   │   ├── rankings.vue            # TOP50排名页
│   │   └── stock/
│   │       └── [code].vue          # 股票详情页 (动态路由)
│   ├── components/
│   │   ├── common/
│   │   │   ├── AppHeader.vue       # 顶部导航
│   │   │   ├── AppFooter.vue       # 底部
│   │   │   └── LoadingSpinner.vue  # 加载组件
│   │   ├── dashboard/
│   │   │   ├── MarketOverview.vue  # 市场概览卡片
│   │   │   ├── FactorHeatmap.vue   # 因子热力图
│   │   │   └── ModelMetrics.vue    # 模型指标展示
│   │   ├── ranking/
│   │   │   ├── RankingTable.vue    # 排名表格
│   │   │   ├── RankingFilters.vue  # 排名筛选器
│   │   │   └── StockCard.vue       # 股票卡片
│   │   └── stock/
│   │       ├── StockHeader.vue     # 股票头部信息
│   │       ├── FactorRadar.vue     # 因子雷达图
│   │       ├── FinancialTable.vue  # 财务数据表
│   │       └── PredictionChart.vue # 预测趋势图
│   ├── composables/
│   │   ├── useApi.ts               # API 请求封装
│   │   ├── useRankings.ts          # 排名数据逻辑
│   │   └── useStockDetail.ts       # 股票详情逻辑
│   ├── types/
│   │   ├── stock.ts                # TypeScript 类型定义
│   │   ├── ranking.ts
│   │   └── api.ts                  # API 响应类型
│   ├── assets/
│   │   ├── css/
│   │   │   └── main.css            # 全局样式
│   │   └── images/
│   └── utils/
│       ├── format.ts               # 数字/日期格式化
│       └── constants.ts            # 常量定义
├── server/
│   ├── api/
│   │   └── proxy.ts                # 服务端API代理 (可选SSR数据获取)
│   └── middleware/
├── public/
│   └── favicon.ico
└── Dockerfile
```

---

## 4. 数据库设计

### 4.1 ER图

```
┌──────────────────┐       ┌──────────────────────────┐
│   stock_basic     │       │   stock_daily            │
├──────────────────┤       ├──────────────────────────┤
│ PK stock_code     │──1:N──│ PK id                    │
│    stock_name     │       │ FK stock_code            │
│    industry       │       │    trade_date            │
│    list_date      │       │    open, high, low, close│
│    area           │       │    volume, amount        │
│    market         │       │    turnover_rate         │
│    is_active      │       │    total_mv, float_mv    │
└──────────────────┘       │    pe, pb, ps            │
                            │    ... (因子字段)        │
                            └──────────────────────────┘

┌──────────────────┐       ┌──────────────────────────┐
│   financial       │       │   macro_data             │
├──────────────────┤       ├──────────────────────────┤
│ PK id            │       │ PK id                     │
│ FK stock_code    │       │    data_date              │
│    report_date   │       │    gdp_yoy                │
│    revenue       │       │    cpi_yoy                │
│    net_profit    │       │    pmi                     │
│    total_assets  │       │    m2_yoy                  │
│    roe, roa      │       │    shibor_1m              │
│    debt_ratio    │       │    bond_10y_yield          │
│    ...            │       │    market_sentiment        │
└──────────────────┘       │    ...                     │
                            └──────────────────────────┘

┌──────────────────┐       ┌──────────────────────────┐
│   factor_store    │       │   prediction              │
├──────────────────┤       ├──────────────────────────┤
│ PK id            │       │ PK id                     │
│ FK stock_code    │       │ FK stock_code             │
│    trade_date    │       │    predict_date           │
│    factor_name   │       │    predicted_return       │
│    factor_value  │       │    confidence              │
│    factor_type   │       │    model_version           │
└──────────────────┘       │    rank_score             │
                            └──────────────────────────┘

┌──────────────────────────┐
│   ranking_snapshot        │
├──────────────────────────┤
│ PK id                     │
│    snapshot_date          │
│    rank_position          │
│ FK stock_code             │
│    predicted_return       │
│    top_factors_json       │
└──────────────────────────┘
```

### 4.2 建表SQL（核心表）

```sql
-- 股票基础信息表
CREATE TABLE stock_basic (
    stock_code VARCHAR(10) PRIMARY KEY COMMENT '股票代码',
    stock_name VARCHAR(50) NOT NULL COMMENT '股票名称',
    industry VARCHAR(50) COMMENT '申万一级行业',
    sub_industry VARCHAR(50) COMMENT '申万二级行业',
    area VARCHAR(20) COMMENT '所属地区',
    market ENUM('SH', 'SZ', 'BJ') COMMENT '交易所',
    list_date DATE COMMENT '上市日期',
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否活跃',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_industry (industry),
    INDEX idx_market (market)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票基础信息表';

-- 股票每日数据表（含因子）
CREATE TABLE stock_daily (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
    trade_date DATE NOT NULL COMMENT '交易日期',
    open DECIMAL(12,3) COMMENT '开盘价',
    high DECIMAL(12,3) COMMENT '最高价',
    low DECIMAL(12,3) COMMENT '最低价',
    close DECIMAL(12,3) COMMENT '收盘价',
    pre_close DECIMAL(12,3) COMMENT '前收盘价',
    volume BIGINT COMMENT '成交量(股)',
    amount DECIMAL(16,2) COMMENT '成交额(元)',
    turnover_rate DECIMAL(10,4) COMMENT '换手率(%)',
    pe DECIMAL(12,4) COMMENT '市盈率',
    pe_ttm DECIMAL(12,4) COMMENT '市盈率TTM',
    pb DECIMAL(12,4) COMMENT '市净率',
    ps DECIMAL(12,4) COMMENT '市销率',
    pcf DECIMAL(12,4) COMMENT '市现率',
    total_mv DECIMAL(16,2) COMMENT '总市值(元)',
    float_mv DECIMAL(16,2) COMMENT '流通市值(元)',
    UNIQUE KEY uk_code_date (stock_code, trade_date),
    INDEX idx_date (trade_date),
    INDEX idx_code (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票每日数据表';

-- 财务数据表
CREATE TABLE financial (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    report_date DATE NOT NULL COMMENT '报告期',
    report_type ENUM('Q1','Q2','Q3','Q4','FY') COMMENT '报告类型',
    revenue DECIMAL(20,2) COMMENT '营业收入',
    revenue_yoy DECIMAL(10,4) COMMENT '营收同比增长率(%)',
    net_profit DECIMAL(20,2) COMMENT '归母净利润',
    net_profit_yoy DECIMAL(10,4) COMMENT '净利润同比增长率(%)',
    gross_margin DECIMAL(10,4) COMMENT '毛利率(%)',
    net_margin DECIMAL(10,4) COMMENT '净利率(%)',
    roe DECIMAL(10,4) COMMENT '净资产收益率(%)',
    roa DECIMAL(10,4) COMMENT '总资产收益率(%)',
    debt_ratio DECIMAL(10,4) COMMENT '资产负债率(%)',
    current_ratio DECIMAL(10,4) COMMENT '流动比率',
    quick_ratio DECIMAL(10,4) COMMENT '速动比率',
    total_assets DECIMAL(20,2) COMMENT '总资产',
    total_equity DECIMAL(20,2) COMMENT '净资产',
    operating_cashflow DECIMAL(20,2) COMMENT '经营活动现金流净额',
    free_cashflow DECIMAL(20,2) COMMENT '自由现金流',
    UNIQUE KEY uk_code_report (stock_code, report_date),
    INDEX idx_report_date (report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='财务数据表';

-- 宏观数据表
CREATE TABLE macro_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    data_date DATE NOT NULL COMMENT '数据日期',
    gdp_yoy DECIMAL(10,4) COMMENT 'GDP同比(%)',
    gdp_qoq DECIMAL(10,4) COMMENT 'GDP环比(%)',
    cpi_yoy DECIMAL(10,4) COMMENT 'CPI同比(%)',
    ppi_yoy DECIMAL(10,4) COMMENT 'PPI同比(%)',
    pmi DECIMAL(10,4) COMMENT '制造业PMI',
    pmi_service DECIMAL(10,4) COMMENT '服务业PMI',
    m2_yoy DECIMAL(10,4) COMMENT 'M2同比(%)',
    m1_yoy DECIMAL(10,4) COMMENT 'M1同比(%)',
    social_finance DECIMAL(20,2) COMMENT '社会融资规模(亿元)',
    shibor_1m DECIMAL(10,4) COMMENT 'SHIBOR 1个月(%)',
    bond_10y_yield DECIMAL(10,4) COMMENT '10年期国债收益率(%)',
    credit_spread DECIMAL(10,4) COMMENT '信用利差(%)',
    usdcny DECIMAL(10,4) COMMENT '美元兑人民币汇率',
    market_sentiment DECIMAL(10,4) COMMENT '市场情绪指数',
    margin_balance DECIMAL(20,2) COMMENT '融资余额(亿元)',
    north_flow DECIMAL(20,2) COMMENT '北向资金净流入(亿元)',
    UNIQUE KEY uk_date (data_date),
    INDEX idx_date (data_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='宏观经济数据表';

-- 因子存储表（宽表设计）
CREATE TABLE factor_store (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    -- 宏观因子
    macro_gdp_yoy DECIMAL(12,6),
    macro_cpi_yoy DECIMAL(12,6),
    macro_pmi DECIMAL(12,6),
    macro_m2_yoy DECIMAL(12,6),
    macro_shibor_1m DECIMAL(12,6),
    macro_bond_10y_yield DECIMAL(12,6),
    macro_credit_spread DECIMAL(12,6),
    macro_usdcny DECIMAL(12,6),
    macro_market_sentiment DECIMAL(12,6),
    macro_margin_trend DECIMAL(12,6),
    macro_north_flow_5d DECIMAL(12,6),
    -- 市场因子
    market_idx_return_5d DECIMAL(12,6),
    market_idx_return_20d DECIMAL(12,6),
    market_idx_volatility_20d DECIMAL(12,6),
    market_turnover_ma5 DECIMAL(12,6),
    market_advance_decline_ratio DECIMAL(12,6),
    market_volume_ratio DECIMAL(12,6),
    market_breadth_20d DECIMAL(12,6),
    market_vix_proxy DECIMAL(12,6),
    market_style_momentum DECIMAL(12,6),
    market_style_value DECIMAL(12,6),
    -- 行业因子
    industry_return_5d DECIMAL(12,6),
    industry_return_20d DECIMAL(12,6),
    industry_return_volatility DECIMAL(12,6),
    industry_pe_percentile DECIMAL(12,6),
    industry_pb_percentile DECIMAL(12,6),
    industry_roe_median DECIMAL(12,6),
    industry_momentum_rank DECIMAL(12,6),
    industry_reversal_signal DECIMAL(12,6),
    industry_fund_flow DECIMAL(12,6),
    industry_dispersion DECIMAL(12,6),
    -- 个股因子
    stock_return_1d DECIMAL(12,6),
    stock_return_5d DECIMAL(12,6),
    stock_return_20d DECIMAL(12,6),
    stock_volatility_20d DECIMAL(12,6),
    stock_volatility_60d DECIMAL(12,6),
    stock_volume_ratio_5d DECIMAL(12,6),
    stock_turnover_rate_5d DECIMAL(12,6),
    stock_pe_ttm DECIMAL(12,6),
    stock_pb DECIMAL(12,6),
    stock_ps_ttm DECIMAL(12,6),
    stock_roe_ttm DECIMAL(12,6),
    stock_roa_ttm DECIMAL(12,6),
    stock_revenue_yoy DECIMAL(12,6),
    stock_profit_yoy DECIMAL(12,6),
    stock_gross_margin DECIMAL(12,6),
    stock_debt_ratio DECIMAL(12,6),
    stock_momentum_20d DECIMAL(12,6),
    stock_reversal_5d DECIMAL(12,6),
    stock_size_factor DECIMAL(12,6),
    stock_illiquidity DECIMAL(12,6),
    -- 元数据
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_code_date (stock_code, trade_date),
    INDEX idx_date (trade_date),
    INDEX idx_stock_date (stock_code, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='因子存储表（宽表）';

-- 预测结果表
CREATE TABLE prediction (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    predict_date DATE NOT NULL COMMENT '预测生成日期',
    target_date DATE NOT NULL COMMENT '目标日期(T+1)',
    predicted_return DECIMAL(12,6) COMMENT '预测次日收益率',
    confidence DECIMAL(6,4) COMMENT '预测置信度',
    model_version VARCHAR(50) COMMENT '模型版本号',
    rank_score DECIMAL(12,6) COMMENT '排名分数',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_predict_date (predict_date),
    INDEX idx_stock_predict_date (stock_code, predict_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='预测结果表';

-- 排名快照表
CREATE TABLE ranking_snapshot (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_date DATE NOT NULL COMMENT '快照日期',
    rank_position INT NOT NULL COMMENT '排名位置(1-50)',
    stock_code VARCHAR(10) NOT NULL,
    stock_name VARCHAR(50) COMMENT '股票名称(冗余)',
    predicted_return DECIMAL(12,6) COMMENT '预测收益率',
    industry VARCHAR(50) COMMENT '行业',
    market_cap DECIMAL(16,2) COMMENT '总市值',
    top_factors_json JSON COMMENT 'TOP贡献因子JSON',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_snapshot_date (snapshot_date),
    INDEX idx_rank (snapshot_date, rank_position),
    UNIQUE KEY uk_snapshot_rank (snapshot_date, rank_position)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='排名快照表';

-- 模型训练记录表
CREATE TABLE model_record (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    model_version VARCHAR(50) NOT NULL COMMENT '模型版本',
    train_date DATE NOT NULL COMMENT '训练日期',
    data_start_date DATE COMMENT '训练数据起始日期',
    data_end_date DATE COMMENT '训练数据截止日期',
    num_samples INT COMMENT '训练样本数',
    num_features INT COMMENT '特征数量',
    params_json JSON COMMENT '超参数JSON',
    train_ic DECIMAL(10,6) COMMENT '训练集IC',
    valid_ic DECIMAL(10,6) COMMENT '验证集IC',
    train_rank_ic DECIMAL(10,6) COMMENT '训练集RankIC',
    valid_rank_ic DECIMAL(10,6) COMMENT '验证集RankIC',
    feature_importance_json JSON COMMENT '特征重要性JSON',
    model_path VARCHAR(255) COMMENT '模型文件路径',
    is_active TINYINT(1) DEFAULT 0 COMMENT '是否为当前使用模型',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_train_date (train_date),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型训练记录表';
```

---

## 5. 后端模块设计

### 5.1 模块依赖关系

```
main.py (FastAPI入口)
  ├── api/v1/router.py (路由注册)
  │     ├── stocks.py      ──→ StockService      ──→ DAO
  │     ├── rankings.py    ──→ RankingService    ──→ DAO
  │     └── factors.py     ──→ FactorService     ──→ DAO
  │
  ├── services/
  │     ├── data_fetcher.py     ──→ AkShare API
  │     ├── factor_engine.py    ──→ MySQL (读原始数据) → factor_store (写)
  │     ├── label_generator.py  ──→ MySQL (计算标签)
  │     ├── trainer.py          ──→ ml/model.py (LightGBM)
  │     ├── predictor.py        ──→ ml/model.py + MySQL
  │     └── ranking_service.py  ──→ prediction表 → ranking_snapshot表
  │
  └── scheduler/jobs.py         ──→ 调用各Service
```

### 5.2 核心服务说明

#### 5.2.1 DataFetcher (data_fetcher.py)

```python
class DataFetcher:
    """AkShare数据采集服务"""

    async def fetch_all_stock_basic(self) -> pd.DataFrame:
        """获取全市场A股基础信息"""
        # ak.stock_info_a_code_name()

    async def fetch_stock_daily_batch(self, date: str) -> pd.DataFrame:
        """获取指定日期全市场股票日数据（不含K线序列）"""
        # ak.stock_zh_a_spot()

    async def fetch_financial_data(self, stock_code: str, report_date: str) -> dict:
        """获取财务数据"""
        # ak.stock_financial_abstract()

    async def fetch_macro_data(self) -> dict:
        """获取宏观经济数据"""
        # ak.macro_china_gdp_yearly()
        # ak.macro_china_cpi_yearly()
        # ak.macro_china_pmi()
        # ak.macro_china_money_supply()
        # ak.bond_china_yield()
        # ...

    async def fetch_market_index(self) -> pd.DataFrame:
        """获取市场指数数据"""
        # ak.stock_zh_index_daily(symbol="sh000001")  # 上证指数
```

#### 5.2.2 FactorEngine (factor_engine.py)

```python
class FactorEngine:
    """因子计算引擎 - 计算全部50个因子"""

    def compute_macro_factors(self, macro_data: pd.DataFrame, trade_date: str) -> pd.Series:
        """计算11个宏观因子"""

    def compute_market_factors(self, index_data: pd.DataFrame, trade_date: str) -> pd.Series:
        """计算10个市场因子"""

    def compute_industry_factors(self, stock_data: pd.DataFrame, trade_date: str) -> pd.DataFrame:
        """计算10个行业因子"""

    def compute_stock_factors(self, stock_data: pd.DataFrame, financial_data: pd.DataFrame, trade_date: str) -> pd.DataFrame:
        """计算19个个股因子"""

    def compute_all(self, trade_date: str) -> pd.DataFrame:
        """计算全市场全部因子，输出因子宽表"""
        # 1. 获取宏观数据 → 计算宏观因子
        # 2. 获取指数数据 → 计算市场因子
        # 3. 获取个股数据 → 分组计算行业因子
        # 4. 获取财务数据 → 计算个股因子
        # 5. 合并所有因子 → 写入factor_store表

    def preprocess_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """因子预处理：去极值(MAD)、标准化(Z-Score)、中性化(行业+市值)"""
        # - 缺失值填充（行业中位数）
        # - MAD法去极值（5倍中位数绝对偏差）
        # - Z-Score标准化（截面标准化）
        # - 行业市值中性化（可选）
```

#### 5.2.3 LabelGenerator (label_generator.py)

```python
class LabelGenerator:
    """标签生成器 - 计算次日收益率"""

    def generate_labels(self, stock_data: pd.DataFrame, trade_date: str) -> pd.DataFrame:
        """
        次日收益率 = T+1日的pct_chg（涨跌幅百分比）
        直接使用stock_daily表中的pct_chg字段
        """
        # 遍历每只股票，取T+1日的涨跌幅
        # 输出：stock_code, trade_date, future_return_1d

    def generate_classification_labels(self, returns: pd.Series, threshold: float = 0.0) -> pd.Series:
        """将收益率转换为分类标签（可选，用于分类模型）"""
        # 0: 下跌, 1: 上涨
```

#### 5.2.4 Trainer (trainer.py)

```python
class LightGBMTrainer:
    """LightGBM训练器"""

    def __init__(self):
        self.model = None
        self.model_version = None

    def prepare_training_data(self, start_date: str, end_date: str) -> tuple:
        """准备训练数据：从factor_store和标签表合并"""
        # X: factor_store中的所有因子列
        # y: future_return_1d

    def train(self, X_train, y_train, X_valid, y_valid, params: dict = None) -> dict:
        """训练LightGBM回归模型"""
        # 默认参数：
        # objective='regression'
        # metric='rmse'
        # boosting_type='gbdt'
        # num_leaves=31
        # learning_rate=0.05
        # feature_fraction=0.8
        # bagging_fraction=0.8
        # bagging_freq=5
        # verbose=-1
        # early_stopping_rounds=50

    def evaluate(self, X_test, y_test) -> dict:
        """模型评估：计算IC, RankIC, MSE等指标"""

    def save_model(self, path: str):
        """保存模型文件 + 记录到model_record表"""

    def load_model(self, path: str):
        """加载已训练模型"""

    def get_feature_importance(self) -> pd.DataFrame:
        """获取特征重要性排序"""
```

#### 5.2.5 Predictor (predictor.py)

```python
class Predictor:
    """预测器 - 每日预测全市场股票"""

    def predict_daily(self, trade_date: str) -> pd.DataFrame:
        """
        1. 获取当日所有股票的最新因子数据
        2. 加载最新活跃模型
        3. 对因子进行与训练时相同的预处理
        4. 批量预测
        5. 结果写入prediction表
        """

    def get_top_n(self, predict_date: str, n: int = 50) -> list:
        """获取当日预测收益率最高的N只股票"""
```

---

## 6. 前端模块设计

### 6.1 页面路由

| 路由 | 页面 | 描述 |
|------|------|------|
| `/` | 首页仪表盘 | 市场概览、最新排名摘要、模型状态 |
| `/rankings` | TOP50排名页 | 完整排名表格，支持按行业/市值筛选 |
| `/rankings?date=2026-06-01` | 历史排名 | 查看历史某日排名 |
| `/stock/[code]` | 股票详情页 | 详细因子分析、财务数据、预测趋势 |

### 6.2 组件树

```
app.vue
└── layouts/default.vue
    ├── AppHeader.vue (导航栏)
    ├── <NuxtPage />
    │   ├── pages/index.vue
    │   │   ├── MarketOverview.vue
    │   │   ├── RankingTable.vue (TOP10预览)
    │   │   └── ModelMetrics.vue
    │   ├── pages/rankings.vue
    │   │   ├── RankingFilters.vue
    │   │   └── RankingTable.vue (完整)
    │   └── pages/stock/[code].vue
    │       ├── StockHeader.vue
    │       ├── FactorRadar.vue
    │       ├── FinancialTable.vue
    │       └── PredictionChart.vue
    └── AppFooter.vue
```

### 6.3 数据流 (Composables)

```typescript
// composables/useApi.ts
export function useApi() {
  const config = useRuntimeConfig()
  const baseURL = config.public.apiBase

  async function fetchRankings(date?: string): Promise<RankingItem[]> { ... }
  async function fetchStockDetail(code: string): Promise<StockDetail> { ... }
  async function fetchFactorAnalysis(code: string): Promise<FactorData> { ... }
  async function fetchMarketOverview(): Promise<MarketOverview> { ... }

  return { fetchRankings, fetchStockDetail, fetchFactorAnalysis, fetchMarketOverview }
}
```

---

## 7. 因子体系设计（50个因子）

### 7.1 宏观因子（11个）

| 序号 | 因子编码 | 因子名称 | 计算方式 | 数据源 |
|------|----------|----------|----------|--------|
| M01 | `macro_gdp_yoy` | GDP同比增速 | 最新公布GDP同比值 | AkShare宏观 |
| M02 | `macro_cpi_yoy` | CPI同比 | 最新CPI同比 | AkShare宏观 |
| M03 | `macro_pmi` | 制造业PMI | 最新PMI值 | AkShare宏观 |
| M04 | `macro_m2_yoy` | M2同比增速 | 最新M2同比 | AkShare宏观 |
| M05 | `macro_shibor_1m` | SHIBOR 1月利率 | 最新1月Shibor | AkShare利率 |
| M06 | `macro_bond_10y_yield` | 10年期国债收益率 | 最新10年国债收益率 | AkShare债券 |
| M07 | `macro_credit_spread` | 信用利差 | AA企业债收益率 - 国债收益率 | 计算 |
| M08 | `macro_usdcny` | 美元人民币汇率 | 最新即期汇率 | AkShare汇率 |
| M09 | `macro_market_sentiment` | 市场情绪 | 融资买入额/总成交额 (5日均值) | 计算 |
| M10 | `macro_margin_trend` | 融资趋势 | 融资余额5日变化率 | 计算 |
| M11 | `macro_north_flow_5d` | 北向资金5日净流入 | 近5日北向资金累计净流入 | AkShare |

### 7.2 市场因子（10个）

| 序号 | 因子编码 | 因子名称 | 计算方式 |
|------|----------|----------|----------|
| T01 | `market_idx_return_5d` | 市场指数5日收益 | 上证指数近5日收益率 |
| T02 | `market_idx_return_20d` | 市场指数20日收益 | 上证指数近20日收益率 |
| T03 | `market_idx_volatility_20d` | 市场波动率 | 上证指数20日波动率(年化) |
| T04 | `market_turnover_ma5` | 市场换手率均线 | 全市场5日平均换手率 |
| T05 | `market_advance_decline_ratio` | 涨跌比 | 上涨家数/下跌家数 |
| T06 | `market_volume_ratio` | 量比 | 全市场成交额/5日均成交额 |
| T07 | `market_breadth_20d` | 市场宽度 | 站上20日均线股票占比 |
| T08 | `market_vix_proxy` | 波动率代理指标 | ATR/收盘价 全市场中位数 |
| T09 | `market_style_momentum` | 动量风格 | 高动量组收益 - 低动量组收益 |
| T10 | `market_style_value` | 价值风格 | 低PE组收益 - 高PE组收益 |

### 7.3 行业因子（10个）

| 序号 | 因子编码 | 因子名称 | 计算方式 |
|------|----------|----------|----------|
| I01 | `industry_return_5d` | 行业5日收益 | 申万一级行业指数5日收益率 |
| I02 | `industry_return_20d` | 行业20日收益 | 行业指数20日收益率 |
| I03 | `industry_return_volatility` | 行业波动率 | 行业指数20日波动率 |
| I04 | `industry_pe_percentile` | 行业PE分位数 | 个股PE在行业内的分位数 |
| I05 | `industry_pb_percentile` | 行业PB分位数 | 个股PB在行业内的分位数 |
| I06 | `industry_roe_median` | 行业中位数ROE | 行业内ROE中位数 |
| I07 | `industry_momentum_rank` | 行业动量排名 | 行业指数60日动量在全行业的排名 |
| I08 | `industry_reversal_signal` | 行业反转信号 | 行业5日收益率的反转指标 |
| I09 | `industry_fund_flow` | 行业资金流向 | 行业主力资金净流入/流通市值 |
| I10 | `industry_dispersion` | 行业离散度 | 行业内个股收益率的截面标准差 |

### 7.4 个股因子（19个）

| 序号 | 因子编码 | 因子名称 | 计算方式 | 类型 |
|------|----------|----------|----------|------|
| S01 | `stock_return_1d` | 1日收益率 | (C_t / C_{t-1} - 1) | 动量 |
| S02 | `stock_return_5d` | 5日收益率 | (C_t / C_{t-5} - 1) | 动量 |
| S03 | `stock_return_20d` | 20日收益率 | (C_t / C_{t-20} - 1) | 动量 |
| S04 | `stock_volatility_20d` | 20日波动率 | 近20日收益率标准差(年化) | 风险 |
| S05 | `stock_volatility_60d` | 60日波动率 | 近60日收益率标准差(年化) | 风险 |
| S06 | `stock_volume_ratio_5d` | 5日量比 | 5日均量/20日均量 | 量价 |
| S07 | `stock_turnover_rate_5d` | 5日换手率 | 近5日平均换手率 | 流动性 |
| S08 | `stock_pe_ttm` | 市盈率TTM | 总市值/归母净利润TTM | 估值 |
| S09 | `stock_pb` | 市净率 | 总市值/净资产 | 估值 |
| S10 | `stock_ps_ttm` | 市销率TTM | 总市值/营业收入TTM | 估值 |
| S11 | `stock_roe_ttm` | ROE TTM | 归母净利润TTM/净资产 | 盈利 |
| S12 | `stock_roa_ttm` | ROA TTM | 净利润TTM/总资产 | 盈利 |
| S13 | `stock_revenue_yoy` | 营收同比增长 | (本期营收/去年同期营收 - 1) | 成长 |
| S14 | `stock_profit_yoy` | 利润同比增长 | (本期净利润/去年同期净利润 - 1) | 成长 |
| S15 | `stock_gross_margin` | 毛利率 | (营收-成本)/营收 | 质量 |
| S16 | `stock_debt_ratio` | 资产负债率 | 总负债/总资产 | 杠杆 |
| S17 | `stock_momentum_20d` | 20日动量 | 20日收益率(剔除最近1日) | 动量 |
| S18 | `stock_reversal_5d` | 5日反转 | -5日收益率 | 反转 |
| S19 | `stock_size_factor` | 规模因子 | ln(总市值) | 规模 |
| S20 | `stock_illiquidity` | 非流动性 | 日收益率/成交额 的20日均值 | 流动性 |

> **因子预处理流程**：
> 1. 缺失值处理：行业中位数填充（个股因子），前值填充（宏观因子）
> 2. 去极值：MAD法，阈值5.0
> 3. 标准化：Z-Score截面标准化（均值0，标准差1）
> 4. 中性化：对行业和ln(市值)做正交化处理（可选，保留原始+中性化两套）

---

## 8. 机器学习流程

### 8.1 训练流程图

```
┌──────────────────────┐
│   数据准备阶段         │
├──────────────────────┤
│ 1. 从factor_store    │
│    获取全量因子数据    │
│ 2. 从stock_daily获取  │
│    future_return_1d   │
│    作为训练标签        │
│ 3. 合并因子+标签       │
│ 4. 按时间切分：        │
│    训练集(70%)         │
│    验证集(15%)         │
│    测试集(15%)         │
└──────────┬───────────┘
           │
┌──────────┴───────────┐
│   特征工程             │
├──────────────────────┤
│ 1. 缺失值处理          │
│ 2. 去极值(MAD 5σ)     │
│ 3. Z-Score标准化       │
│ 4. 相关性过滤(>0.95)   │
│ 5. 特征重要性初筛       │
└──────────┬───────────┘
           │
┌──────────┴───────────┐
│   模型训练             │
├──────────────────────┤
│ 使用LightGBM回归：     │
│ • objective=regression│
│ • metric=rmse         │
│ • 早停轮数=50          │
│ • 5折交叉验证          │
│ • 网格搜索调参         │
└──────────┬───────────┘
           │
┌──────────┴───────────┐
│   模型评估             │
├──────────────────────┤
│ • IC (Information     │
│   Coefficient)        │
│ • RankIC (Spearman)   │
│ • MSE / RMSE          │
│ • 分组收益单调性        │
│ • 特征重要性分析        │
└──────────┬───────────┘
           │
┌──────────┴───────────┐
│   模型保存与版本管理    │
├──────────────────────┤
│ • 保存.pkl模型文件     │
│ • 写入model_record表  │
│ • 设置is_active=1     │
│   (旧模型设为0)       │
└──────────────────────┘
```

### 8.2 LightGBM超参数

```python
DEFAULT_PARAMS = {
    'objective': 'regression',
    'metric': 'rmse',
    'boosting_type': 'gbdt',
    'num_leaves': 31,
    'max_depth': 7,
    'learning_rate': 0.05,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'min_child_samples': 20,
    'min_child_weight': 0.001,
    'reg_alpha': 0.1,
    'reg_lambda': 0.1,
    'num_iterations': 1000,
    'early_stopping_rounds': 50,
    'verbose': -1,
    'random_state': 42
}

# 网格搜索调参范围
PARAM_GRID = {
    'num_leaves': [15, 31, 63],
    'max_depth': [5, 7, 9],
    'learning_rate': [0.01, 0.05, 0.1],
    'feature_fraction': [0.6, 0.8, 1.0]
}
```

### 8.3 评估指标公式

- **IC (Pearson)**: `corr(predicted_return, actual_return)`
- **RankIC (Spearman)**: `corr(rank(predicted_return), rank(actual_return))`
- **IR (Information Ratio)**: `mean(IC) / std(IC)`
- **分组收益**: 按预测值等分10组，计算各组实际平均收益，检验单调性

### 8.4 模型更新策略

| 场景 | 策略 | 频率 |
|------|------|------|
| 每日预测 | 加载最新活跃模型，预测当日全市场股票 | 每日(交易日) |
| 模型重训 | 每月重新训练，使用截止到上月的数据 | 每月1次 |
| 增量更新 | 每周用新产生的因子数据做增量训练 | 每周1次(可选) |
| 紧急回撤 | 若连续5日IC < 0，触发紧急重训 | 按需 |

---

## 9. REST API 设计

### 9.1 API 概览

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/rankings` | 获取TOP50排名 |
| GET | `/api/v1/rankings/{date}` | 获取历史某日排名 |
| GET | `/api/v1/stocks/{code}` | 获取股票详情 |
| GET | `/api/v1/stocks/{code}/factors` | 获取股票因子数据 |
| GET | `/api/v1/stocks/{code}/financial` | 获取股票财务数据 |
| GET | `/api/v1/stocks/{code}/prediction` | 获取股票预测历史 |
| GET | `/api/v1/market/overview` | 市场概览数据 |
| GET | `/api/v1/factors/importance` | 因子重要性排名 |
| GET | `/api/v1/model/status` | 模型状态信息 |

### 9.2 API 详细定义

#### 9.2.1 获取TOP50排名

```
GET /api/v1/rankings?date=2026-06-05&industry=电子

Response:
{
  "code": 0,
  "data": {
    "date": "2026-06-05",
    "rankings": [
      {
        "rank": 1,
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "predicted_return": 0.0852,
        "industry": "食品饮料",
        "market_cap": 2800000000000,
        "top_factors": [
          {"name": "stock_roe_ttm", "contribution": 0.15},
          {"name": "industry_momentum_rank", "contribution": 0.12}
        ]
      }
      // ... 共50条
    ],
    "total": 50
  },
  "message": "success"
}
```

#### 9.2.2 获取股票详情

```
GET /api/v1/stocks/600519

Response:
{
  "code": 0,
  "data": {
    "basic": {
      "stock_code": "600519",
      "stock_name": "贵州茅台",
      "industry": "食品饮料",
      "market": "SH",
      "list_date": "2001-08-27",
      "total_mv": 2800000000000,
      "float_mv": 2800000000000
    },
    "latest_daily": {
      "close": 1850.00,
      "pe_ttm": 32.5,
      "pb": 12.3,
      "turnover_rate": 0.35
    },
    "latest_prediction": {
      "predict_date": "2026-06-05",
      "predicted_return": 0.0852,
      "confidence": 0.78
    }
  },
  "message": "success"
}
```

#### 9.2.3 市场概览

```
GET /api/v1/market/overview

Response:
{
  "code": 0,
  "data": {
    "market_index": {
      "sh_index": 3350.25,
      "sh_change": 0.52,
      "sz_index": 10850.30,
      "sz_change": 0.38
    },
    "market_stats": {
      "up_count": 2850,
      "down_count": 1520,
      "flat_count": 130,
      "advance_decline_ratio": 1.875
    },
    "top_industries": [
      {"industry": "电子", "return_5d": 3.25},
      {"industry": "计算机", "return_5d": 2.85}
    ],
    "model_status": {
      "model_version": "v20260601",
      "last_train_date": "2026-06-01",
      "latest_ic": 0.0452,
      "is_active": true
    }
  }
}
```

---

## 10. 定时任务设计

### 10.1 任务调度表

使用 **APScheduler** 进行定时任务管理。

| 任务ID | 任务名称 | 执行时间 | 频率 | 描述 |
|--------|----------|----------|------|------|
| J01 | `fetch_stock_data` | 15:30 | 每个交易日 | 采集当日全市场股票日数据 |
| J02 | `fetch_financial_data` | 16:00 | 每周一 | 更新最新财报数据 |
| J03 | `fetch_macro_data` | 09:00 | 每个交易日 | 采集最新宏观经济数据 |
| J04 | `compute_factors` | 16:00 | 每个交易日 | 计算全市场50个因子 |
| J05 | `generate_labels` | 16:30 | 每个交易日 | 为最新数据生成次日标签 |
| J06 | `daily_predict` | 17:00 | 每个交易日 | 预测全市场股票次日收益率 |
| J07 | `generate_ranking` | 17:30 | 每个交易日 | 生成TOP50排名快照 |
| J08 | `train_model` | 每月1日 02:00 | 每月 | 使用全量历史数据重训模型 |
| J09 | `backfill_history` | 手动触发 | 按需 | 历史数据回填(初始化用) |

### 10.2 调度配置代码

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

# 交易日检测辅助函数
def is_trade_day(date):
    """判断是否为A股交易日"""
    # 使用 chinese_calendar 库或自维护交易日历

# 添加定时任务
scheduler.add_job(
    fetch_stock_data_job,
    CronTrigger(hour=15, minute=30, day_of_week='mon-fri'),
    id='fetch_stock_data'
)

scheduler.add_job(
    compute_factors_job,
    CronTrigger(hour=16, minute=0, day_of_week='mon-fri'),
    id='compute_factors'
)

scheduler.add_job(
    daily_predict_job,
    CronTrigger(hour=17, minute=0, day_of_week='mon-fri'),
    id='daily_predict'
)

# 每月1号凌晨2点重训模型
scheduler.add_job(
    train_model_job,
    CronTrigger(day=1, hour=2, minute=0),
    id='train_model'
)
```

### 10.3 每日流水线

```
15:30 ──→ J01 数据采集
            │
            ├── 全市场当日行情
            ├── 个股估值数据
            └── 更新 stock_daily 表
16:00 ──→ J04 因子计算
            │
            ├── 读取最新宏观/市场/行业/个股数据
            ├── 计算50个因子
            └── 写入 factor_store 表
16:30 ──→ J05 标签生成
            │
            ├── 根据T+1日pct_chg计算次日收益率
            └── (使用stock_daily.pct_chg字段作为标签)
17:00 ──→ J06 每日预测
            │
            ├── 加载最新模型
            ├── 获取当日因子数据
            ├── 批量预测次日收益率
            └── 写入 prediction 表
17:30 ──→ J07 生成排名
            │
            ├── 按predicted_return降序排列
            ├── 取前50名
            └── 写入 ranking_snapshot 表
```

---

## 11. 部署方案

### 11.1 Docker Compose 部署

```yaml
# docker-compose.yml
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    container_name: agu-mysql
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: agu_quant
      MYSQL_USER: agu_user
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql
    command: --default-authentication-plugin=mysql_native_password

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: agu-backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=mysql+pymysql://agu_user:${MYSQL_PASSWORD}@mysql:3306/agu_quant
      - REDIS_URL=redis://redis:6379
    depends_on:
      - mysql
    volumes:
      - ./backend/models:/app/models  # 模型文件持久化

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: agu-frontend
    ports:
      - "3000:3000"
    environment:
      - API_BASE_URL=http://backend:8000
    depends_on:
      - backend

volumes:
  mysql_data:
```

### 11.2 环境变量 (.env)

```bash
# MySQL
MYSQL_ROOT_PASSWORD=your_root_password
MYSQL_PASSWORD=your_user_password
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=agu_quant

# Backend
DATABASE_URL=mysql+pymysql://agu_user:password@localhost:3306/agu_quant
APP_ENV=production
LOG_LEVEL=INFO

# Model
MODEL_DIR=./models
MODEL_VERSION=v1.0

# AkShare (无需额外配置，但可设置代理)
HTTP_PROXY=
HTTPS_PROXY=

# Frontend
NUXT_PUBLIC_API_BASE=http://localhost:8000
```

---

## 12. 开发路线图

### 阶段一：基础设施搭建（第1-2周）

- [ ] 项目初始化：创建前后端项目骨架
- [ ] 数据库设计：编写完整建表SQL，完成索引优化
- [ ] 数据库连接：SQLAlchemy ORM 模型定义
- [ ] Alembic 数据库迁移配置
- [ ] FastAPI 基础框架搭建（路由、中间件、异常处理）
- [ ] Nuxt4 基础框架搭建（布局、路由、API封装）
- [ ] Docker 开发环境配置

### 阶段二：数据采集模块（第3周）

- [ ] AkShare 接口调研与封装（DataFetcher）
- [ ] 全市场A股基础信息采集
- [ ] 股票每日行情数据采集
- [ ] 财务数据采集（资产负债表、利润表、现金流量表）
- [ ] 宏观数据采集（GDP/CPI/PMI/M2/Shibor/国债收益率等）
- [ ] 数据质量检查与异常处理
- [ ] 历史数据回填脚本

### 阶段三：因子计算模块（第4-5周）

- [ ] FactorEngine 核心计算逻辑
- [ ] 宏观因子计算（11个）
- [ ] 市场因子计算（10个）
- [ ] 行业因子计算（10个）
- [ ] 个股因子计算（19个）
- [ ] 因子预处理流程（去极值、标准化、中性化）
- [ ] 因子数据写入因子存储表
- [ ] 因子覆盖率监控

### 阶段四：机器学习模块（第6-7周）

- [ ] LabelGenerator：次日收益率标签计算
- [ ] 训练数据集构建（因子+标签合并）
- [ ] LightGBM 模型封装（训练、保存、加载）
- [ ] 模型训练脚本（包含5折交叉验证）
- [ ] 超参数网格搜索
- [ ] 模型评估：IC、RankIC、分组收益
- [ ] 特征重要性分析与输出
- [ ] Predictor：每日预测流程

### 阶段五：排名与API（第8周）

- [ ] RankingService：TOP50排名生成
- [ ] REST API 完整开发（排名、股票详情、市场概览、因子查询）
- [ ] API 文档（Swagger / OpenAPI）
- [ ] 请求参数校验、错误处理、日志记录
- [ ] API 限流与缓存

### 阶段六：前端开发（第9-10周）

- [ ] 首页仪表盘（市场概览、TOP10预览、模型指标）
- [ ] TOP50排名页面（表格、筛选、分页、历史查询）
- [ ] 股票详情页（因子雷达图、财务数据、预测趋势图）
- [ ] ECharts 图表集成
- [ ] 响应式设计适配
- [ ] SSR/SSG 优化
- [ ] 加载状态与错误处理

### 阶段七：定时任务与自动化（第11周）

- [ ] APScheduler 集成
- [ ] 交易日历工具
- [ ] 每日数据采集定时任务
- [ ] 每日因子计算定时任务
- [ ] 每日预测与排名定时任务
- [ ] 每月模型重训定时任务
- [ ] 任务执行日志与告警

### 阶段八：测试与优化（第12周）

- [ ] 单元测试：各Service模块
- [ ] 集成测试：API接口
- [ ] 因子IC表现回溯测试
- [ ] 模型稳定性测试
- [ ] 性能优化：数据库查询、批量计算
- [ ] 前端性能优化
- [ ] 部署文档与运维手册
- [ ] 上线部署

---

## 附录

### A. 关键第三方库

#### 后端 (requirements.txt)

```
fastapi==0.115.*
uvicorn[standard]==0.34.*
sqlalchemy==2.0.*
pymysql==1.1.*
alembic==1.14.*
pydantic==2.10.*
pydantic-settings==2.7.*
akshare==1.16.*
pandas==2.2.*
numpy==2.2.*
lightgbm==4.5.*
scikit-learn==1.6.*
scipy==1.15.*
apscheduler==3.10.*
httpx==0.28.*
python-dotenv==1.0.*
redis==5.2.*
loguru==0.7.*
```

#### 前端 (package.json 关键依赖)

```json
{
  "dependencies": {
    "nuxt": "^4.0.0",
    "vue": "^3.5.0",
    "vue-router": "^4.5.0",
    "pinia": "^2.3.0",
    "echarts": "^5.5.0",
    "vue-echarts": "^7.0.0",
    "element-plus": "^2.9.0",
    "@element-plus/icons-vue": "^2.3.0",
    "dayjs": "^1.11.0",
    "ofetch": "^1.4.0"
  },
  "devDependencies": {
    "typescript": "^5.7.0",
    "@nuxtjs/eslint-config-typescript": "^12.0.0",
    "sass": "^1.83.0"
  }
}
```

### B. AkShare 核心API参考

```python
import akshare as ak

# 股票基础信息
df = ak.stock_info_a_code_name()  # 全市场股票代码名称

# 实时行情（非K线）
df = ak.stock_zh_a_spot()  # A股实时/当日行情

# 个股历史日数据
df = ak.stock_zh_a_hist(symbol="600519", period="daily", start_date="20250101", end_date="20250601")

# 财务数据
df = ak.stock_financial_abstract(symbol="600519")  # 财务摘要

# 指数数据
df = ak.stock_zh_index_daily(symbol="sh000001")  # 上证指数

# 宏观经济
df = ak.macro_china_gdp_yearly()        # GDP
df = ak.macro_china_cpi_yearly()        # CPI
df = ak.macro_china_pmi()               # PMI
df = ak.macro_china_money_supply()      # 货币供应量(M0/M1/M2)
df = ak.macro_china_shibor_all()        # Shibor利率
df = ak.bond_china_yield()              # 国债收益率曲线

# 北向资金
df = ak.stock_hsgt_north_net_flow_in_em()  # 北向资金净流入

# 融资融券
df = ak.stock_margin_detail_sse()       # 融资融券明细
```

### C. 性能优化建议

1. **批量数据采集**：使用异步HTTP批量获取数据，减少IO等待
2. **数据库批量写入**：使用 `INSERT ... ON DUPLICATE KEY UPDATE` 批量upsert
3. **因子计算向量化**：使用pandas/numpy向量化运算替代循环
4. **模型推理加速**：将LightGBM模型转为ONNX格式以加速推理
5. **缓存机制**：Redis缓存热门API响应（排名、市场概览），TTL可设为5分钟
6. **数据库分区**：对 `stock_daily` 和 `factor_store` 按 `trade_date` 分区

### D. 风险提示

- 本系统仅供研究学习使用，不构成任何投资建议
- 量化选股模型存在过拟合风险，历史表现不代表未来收益
- 数据来源AkShare依赖第三方维护，需关注数据质量与稳定性
- 需遵守相关法律法规，不用于非法荐股或操纵市场

---

> **文档维护**：本文档随项目开发持续更新，最新版本以Git仓库为准。


### 🚀 启动方式

__方式1: Docker Compose (推荐)__

```bash
# 在项目根目录执行
docker-compose up -d
```

__方式2: 本地开发__

后端:

```bash
cd backend
pip install -r requirements.txt
python scripts/init_db.py
python -m uvicorn app.main:app --reload --port 8000
```

前端:

```bash
cd frontend
pnpm install  # 已完成
pnpm dev
```

前端依赖已安装成功(802个包)，TypeScript 错误均为未安装依赖导致的正常现象，安装后已解决。

net start MySQL97
net stop MySQL97