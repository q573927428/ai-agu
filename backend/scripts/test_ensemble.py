"""测试多模型集成置信度算法"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from app.ml.model import EnsembleModel


class MockModel:
    """模拟 LightGBM 模型"""
    def __init__(self, name, base_offset=0.0, noise_scale=0.5):
        """name 用于可重复的随机种子，base_offset 用于模拟系统性偏差"""
        self.name = name
        self.base_offset = base_offset
        self.noise_scale = noise_scale

    def predict(self, X):
        n = len(X)
        base = np.array([5, 12, 8, 3, 25, -2, 15.5, 0.5, 10.2, 18.7])[:n]
        # 固定种子，确保每次调用predict结果一致
        rng = np.random.RandomState(hash(self.name) % 100000)
        noise = rng.randn(n) * self.noise_scale
        return base + self.base_offset + noise


def build_ensemble(models):
    ensemble = EnsembleModel()
    ensemble.models = [m for m in models]
    ensemble.model_versions = [f"model_{i}" for i in range(len(models))]
    ensemble.model_ids = list(range(len(models)))
    ensemble.loaded = True
    return ensemble


def test_high_consistency():
    """场景1: 模型间一致性好 -> 置信度应该高"""
    print("=" * 60)
    print("场景1: 模型间一致性好（低噪音）")
    print("=" * 60)

    m1 = MockModel("modelA", base_offset=0.0, noise_scale=0.2)
    m2 = MockModel("modelB", base_offset=0.2, noise_scale=0.2)
    m3 = MockModel("modelC", base_offset=-0.1, noise_scale=0.2)

    ensemble = build_ensemble([m1, m2, m3])
    X = pd.DataFrame({"f1": [1, 2, 3], "f2": [4, 5, 6]})
    preds, confs = ensemble.predict(X)

    for i, (p, c) in enumerate(zip(preds, confs)):
        print(f"  股票{i+1}: 预测={p:.2f}%, 置信度={c:.4f}")
    print(f"  >>> 平均置信度: {np.mean(confs):.4f}  (期望: > 0.6)\n")
    return np.mean(confs)


def test_low_consistency():
    """场景2: 模型间分歧大 -> 置信度应该低"""
    print("=" * 60)
    print("场景2: 模型间分歧大（高噪音）")
    print("=" * 60)

    m1 = MockModel("modelA", base_offset=5.0, noise_scale=3.0)
    m2 = MockModel("modelB", base_offset=-3.0, noise_scale=3.0)
    m3 = MockModel("modelC", base_offset=2.0, noise_scale=3.0)

    ensemble = build_ensemble([m1, m2, m3])
    X = pd.DataFrame({"f1": [1, 2, 3], "f2": [4, 5, 6]})
    preds, confs = ensemble.predict(X)

    for i, (p, c) in enumerate(zip(preds, confs)):
        print(f"  股票{i+1}: 预测={p:.2f}%, 置信度={c:.4f}")
    print(f"  >>> 平均置信度: {np.mean(confs):.4f}  (期望: < 场景1的结果)\n")
    return np.mean(confs)


def test_extreme_penalty():
    """场景3: 极端预测值应受惩罚"""
    print("=" * 60)
    print("场景3: 极端预测值（>20%）应受惩罚")
    print("=" * 60)

    class ExtremeMock:
        def predict(self, X):
            n = len(X)
            return np.array([35.0, 5.0, 40.0, 12.0])[:n]

    m_all = [ExtremeMock() for _ in range(3)]
    ensemble = build_ensemble(m_all)
    X = pd.DataFrame({"f1": [1, 2, 3, 4]})
    preds, confs = ensemble.predict(X)

    for i, (p, c) in enumerate(zip(preds, confs)):
        status = "[极端!]" if abs(p) > 20 else "[正常]"
        print(f"  股票{i+1}: 预测={p:.2f}%, 置信度={c:.4f}  {status}")
    print()


def test_model_count_impact():
    """场景4: 更多模型应提高置信度"""
    print("=" * 60)
    print("场景4: 更多模型数量对置信度的影响")
    print("=" * 60)

    X_single = pd.DataFrame({"f1": [1]})

    # 2个模型
    ensemble2 = build_ensemble([
        MockModel("mA", noise_scale=1.0),
        MockModel("mB", noise_scale=1.0)
    ])
    _, conf2 = ensemble2.predict(X_single)
    print(f"  2个模型: 置信度={conf2[0]:.4f}")

    # 3个模型
    ensemble3 = build_ensemble([
        MockModel("mA", noise_scale=1.0),
        MockModel("mB", noise_scale=1.0),
        MockModel("mC", noise_scale=1.0)
    ])
    _, conf3 = ensemble3.predict(X_single)
    print(f"  3个模型: 置信度={conf3[0]:.4f}")

    # 4个模型
    ensemble4 = build_ensemble([
        MockModel("mA", noise_scale=1.0),
        MockModel("mB", noise_scale=1.0),
        MockModel("mC", noise_scale=1.0),
        MockModel("mD", noise_scale=1.0)
    ])
    _, conf4 = ensemble4.predict(X_single)
    print(f"  4个模型: 置信度={conf4[0]:.4f}  (期望: >= 2个模型的结果)")
    print()


if __name__ == "__main__":
    c1 = test_high_consistency()
    c2 = test_low_consistency()
    test_extreme_penalty()
    test_model_count_impact()

    # 核心验证
    print("=" * 60)
    print("验证结论")
    print("=" * 60)
    if c1 > c2:
        print("✅ PASS: 一致性高 > 一致性低 (置信度合理区分)")
    else:
        print("❌ FAIL: 置信度区分不符合预期")
    print()