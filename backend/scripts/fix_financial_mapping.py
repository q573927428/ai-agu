"""
修正 fetch_financial_full.py 和 fetch_real_data.py 中的字段映射
根据 Tushare Pro 实际返回列名重新映射

用法: python scripts/fix_financial_mapping.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ========== 正确的字段映射（基于 Tushare Pro 实际返回列名）==========

# income 表 — 对应 pro.income()
INCOME_FIELD_MAP = {
    # Tushare列名 → 模型字段名
    "revenue": "revenue",              # 营业总收入
    "total_revenue": "revenue",        # 营业总收入（备用）
    "oper_cost": "cost",               # 营业总成本
    "total_cogs": "cost",              # 营业总成本（备用）
    "sell_exp": "sell_expense",        # 销售费用
    "admin_exp": "admin_expense",      # 管理费用
    "fin_exp": "fin_expense",          # 财务费用
    "rd_exp": "rd_expense",            # 研发费用
    "operate_profit": "operating_profit",  # 营业利润
    "total_profit": "total_profit",    # 利润总额
    "n_income_attr_p": "net_profit",   # 归母净利润
    "non_oper_income": "non_op_income",    # 营业外收入
    "non_oper_exp": "non_op_expense",      # 营业外支出
    "income_tax": "income_tax",        # 所得税费用
    "minority_gain": "minority_pl",    # 少数股东损益
    "minority_pl": "minority_pl",      # (备用)
    "basic_eps": "eps",                # 基本每股收益
    "diluted_eps": "diluted_eps",      # 稀释每股收益
}

# balancesheet 表 — 对应 pro.balancesheet()
BALANCESHEET_FIELD_MAP = {
    "total_assets": "total_assets",                          # 总资产
    "total_cur_assets": "current_assets",                    # 流动资产
    "money_cap": "money_cap",                                # 货币资金
    "accounts_receiv": "accounts_rece",                      # 应收账款
    "inventories": "inventory",                              # 存货
    "fix_assets": "fixed_assets",                            # 固定资产
    "intan_assets": "intan_assets",                          # 无形资产
    "goodwill": "goodwill",                                  # 商誉
    "total_liab": "total_liab",                              # 总负债
    "total_cur_liab": "current_liab",                        # 流动负债
    "accounts_pay": "accounts_pay",                          # 应付账款
    "lt_borr": "longterm_loan",                              # 长期借款
    "bond_payable": "bonds_payable",                         # 应付债券
    "total_hldr_eqy_exc_min_int": "total_equity",            # 净资产(归属母公司)
    "minority_int": "minority_int",                          # 少数股东权益
    "total_share": "cap_stk",                                # 实收资本(股本)
    "cap_rese": "cap_reserve",                               # 资本公积金
    "surplus_rese": "surplus_reserve",                       # 盈余公积金
    "undistr_porfit": "retained_earn",                       # 未分配利润
    "retained_earnings": "retained_earn",                    # 未分配利润(备用)
}

# cashflow 表 — 对应 pro.cashflow()
CASHFLOW_FIELD_MAP = {
    "c_inf_fr_operate_a": "oper_cash_in",                    # 经营活动现金流入
    "st_cash_out_act": "oper_cash_out",                      # 经营活动现金流出
    "n_cashflow_act": "net_oper_cash",                       # 经营活动现金流量净额
    "stot_inflows_inv_act": "inv_cash_in",                   # 投资活动现金流入
    "stot_out_inv_act": "inv_cash_out",                      # 投资活动现金流出
    "n_cashflow_inv_act": "net_inv_cash",                    # 投资活动现金流量净额
    "stot_cash_in_fnc_act": "fin_cash_in",                   # 筹资活动现金流入
    "stot_cashout_fnc_act": "fin_cash_out",                  # 筹资活动现金流出
    "n_cash_flows_fnc_act": "net_fin_cash",                  # 筹资活动现金流量净额
    "n_incr_cash_cash_equ": "cash_equiv_net",                # 现金等价物净增加额
    "free_cashflow": "free_cashflow",                        # 自由现金流
}

# fina_indicator 表 — 对应 pro.fina_indicator()
FINA_INDICATOR_FIELD_MAP = {
    "roe": "roe",                                            # 净资产收益率
    "roa": "roa",                                            # 总资产收益率
    "gross_margin": "gross_margin",                          # 销售毛利率
    "grossprofit_margin": "gross_margin",                    # 销售毛利率(备用)
    "netprofit_margin": "net_margin",                        # 销售净利率
    "eps": "eps",                                            # 每股收益
    # 成长能力
    "or_yoy": "revenue_yoy",                                 # 营收同比增长率
    "tr_yoy": "revenue_yoy",                                 # 营收同比增长率(备用)
    "netprofit_yoy": "net_profit_yoy",                       # 净利润同比增长率
    "ocf_yoy": "oper_cf_yoy",                                # 经营活动现金流同比增长率
    "roe_yoy": "roe_yoy",                                    # ROE同比增长率
    # 运营能力
    "assets_turn": "asset_turnover",                         # 总资产周转率
    "ar_turn": "receiv_turn",                                # 应收账款周转率
    # 偿债能力
    "debt_to_assets": "debt_ratio",                          # 资产负债率
    "current_ratio": "current_ratio",                        # 流动比率
    "quick_ratio": "quick_ratio",                            # 速动比率
    # 每股指标
    "bps": "bps",                                            # 每股净资产
    "cfps": "cashflow_ps",                                   # 每股经营活动现金流
    "ocfps": "cashflow_ps",                                  # 每股经营活动现金流(备用)
}


def patch_file(filepath: str):
    """给文件打补丁，替换 field_map 定义"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 在 fetch_financial_full.py 中替换 fetch_table 函数的 field_map
    # 匹配 fetch_real_data.py 中的 field_map 块
    old_field_map_block = """                # 通用字段映射
                field_map = {
                    # 利润表
                    "revenue": "revenue", "revenue_yoy": "revenue_yoy", "cost": "cost",
                    "sell_expense": "sell_expense", "admin_expense": "admin_expense",
                    "fin_expense": "fin_expense", "rd_expense": "rd_expense",
                    "operate_profit": "operating_profit", "total_profit": "total_profit",
                    "total_profit_yoy": "total_profit_yoy",
                    "n_income_attr_p": "net_profit", "yoy_profit": "net_profit_yoy",
                    "non_op_income": "non_op_income", "non_op_expense": "non_op_expense",
                    "income_tax": "income_tax", "minority_pl": "minority_pl",
                    "basic_eps": "eps", "diluted_eps": "diluted_eps",
                    "eps_yoy": "eps_yoy",
                    # 资产负债表
                    "total_assets": "total_assets", "current_assets": "current_assets",
                    "money_cap": "money_cap", "accounts_rece": "accounts_rece",
                    "inventory": "inventory", "fixed_assets": "fixed_assets",
                    "intan_assets": "intan_assets", "goodwill": "goodwill",
                    "total_liab": "total_liab", "current_liab": "current_liab",
                    "accounts_pay": "accounts_pay", "longterm_loan": "longterm_loan",
                    "bonds_payable": "bonds_payable",
                    "total_hldr_eqy_exc_min_int": "total_equity",
                    "minority_int": "minority_int",
                    "cap_stk": "cap_stk", "cap_reserve": "cap_reserve",
                    "surplus_reserve": "surplus_reserve", "retained_earn": "retained_earn",
                    # 现金流量表
                    "c_inflow_act": "oper_cash_in", "c_outflow_act": "oper_cash_out",
                    "n_cashflow_act": "net_oper_cash",
                    "c_inflow_inv": "inv_cash_in", "c_outflow_inv": "inv_cash_out",
                    "n_cashflow_inv": "net_inv_cash",
                    "c_inflow_fnc": "fin_cash_in", "c_outflow_fnc": "fin_cash_out",
                    "n_cashflow_fnc": "net_fin_cash",
                    "n_cashflow_net": "cash_equiv_net", "free_cashflow": "free_cashflow",
                    # 财务指标
                    "roe": "roe", "roa": "roa", "gross_profit_margin": "gross_margin",
                    "net_profit_margin": "net_margin", "eps": "eps",
                    "rd_exp_ratio": "rd_exp_ratio",
                    "yoy_or": "revenue_yoy", "yoy_profit": "net_profit_yoy",
                    "yoy_cashflow_act": "oper_cf_yoy", "yoy_roe": "roe_yoy",
                    "asset_turn": "asset_turnover", "inventory_turn": "inventory_turn",
                    "receiv_turn": "receiv_turn",
                    "debt_ratio": "debt_ratio", "current_ratio": "current_ratio",
                    "quick_ratio": "quick_ratio", "interest_coverage": "interest_coverage",
                    "bps": "bps", "cf_ps": "cashflow_ps", "div_per_share": "dividend_ps",
                }"""

    new_field_map_block = """                # 通用字段映射（基于 Tushare Pro 实际返回列名）
                if api_name == "利润表":
                    from scripts.fix_financial_mapping import INCOME_FIELD_MAP as field_map
                elif api_name == "资产负债表":
                    from scripts.fix_financial_mapping import BALANCESHEET_FIELD_MAP as field_map
                elif api_name == "现金流量表":
                    from scripts.fix_financial_mapping import CASHFLOW_FIELD_MAP as field_map
                elif api_name == "财务指标":
                    from scripts.fix_financial_mapping import FINA_INDICATOR_FIELD_MAP as field_map
                else:
                    field_map = {}"""

    if old_field_map_block in content:
        content = content.replace(old_field_map_block, new_field_map_block)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 已修复: {filepath}")
        return True
    else:
        print(f"⚠️ 未找到匹配的field_map块: {filepath}")
        # 尝试找另一种格式
        return False


if __name__ == "__main__":
    # 打补丁到两个脚本文件
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    files_to_patch = [
        os.path.join(base_dir, "scripts", "fetch_financial_full.py"),
        os.path.join(base_dir, "scripts", "fetch_real_data.py"),
    ]
    
    for fpath in files_to_patch:
        patch_file(fpath)
    
    print("\n📋 建议：补丁打完后再运行测试")
    print("  python scripts/fetch_financial_full.py --top 5 --delay 1.0")