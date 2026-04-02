"""RE24（Run Expectancy）矩陣計算工具。

CPBL 尚無足夠歷史資料建立本土 RE24，暫用 MLB 2023 數據作為 proxy。
待 CPBL 資料累積後，可透過 scripts/build_re_matrix.py 建立本土矩陣並存入 DB。

base_state 格式：三位字串，各代表一、二、三壘是否有人
  - "000" = 空壘
  - "100" = 一壘有人
  - "111" = 滿壘
"""

from __future__ import annotations

from dataclasses import dataclass

# MLB 2023 RE24 矩陣（近似值）
# 資料來源：FanGraphs / Baseball Savant 公開數據
# 格式：(base_state, outs) -> 預期得分
MLB_RE24_2023: dict[tuple[str, int], float] = {
    ("000", 0): 0.481,
    ("000", 1): 0.254,
    ("000", 2): 0.098,
    ("100", 0): 0.859,
    ("100", 1): 0.509,
    ("100", 2): 0.224,
    ("010", 0): 1.100,
    ("010", 1): 0.664,
    ("010", 2): 0.319,
    ("001", 0): 1.353,
    ("001", 1): 0.950,
    ("001", 2): 0.353,
    ("110", 0): 1.437,
    ("110", 1): 0.884,
    ("110", 2): 0.429,
    ("101", 0): 1.798,
    ("101", 1): 1.140,
    ("101", 2): 0.494,
    ("011", 0): 1.940,
    ("011", 1): 1.352,
    ("011", 2): 0.570,
    ("111", 0): 2.282,
    ("111", 1): 1.520,
    ("111", 2): 0.736,
}

# 所有 24 個 base-out state 的平均預期得分（用於 LI 基準）
_AVG_RE24 = sum(MLB_RE24_2023.values()) / len(MLB_RE24_2023)


@dataclass(frozen=True)
class ReMatrix:
    """RE24 矩陣的封裝，攜帶來源資訊。"""

    matrix: dict[tuple[str, int], float]
    source: str  # "mlb_2023_proxy" 或 "cpbl_{year}"
    year: int | None


def get_re24(year: int | None = None) -> dict[tuple[str, int], float]:
    """取得 RE24 矩陣。

    Args:
        year: CPBL 年份。若 None 或該年度尚無本土資料，使用 MLB 2023 proxy。

    Returns:
        (base_state, outs) -> 預期得分 的 dict。
    """
    # 未來擴充點：若 year 在 DB 中有 CPBL 本土矩陣，從 DB 讀取後回傳
    # 目前一律使用 MLB 2023 proxy
    return MLB_RE24_2023


def get_run_expectancy(
    base_state: str,
    outs: int,
    year: int | None = None,
) -> float:
    """查詢特定情境的預期得分。

    Args:
        base_state: 三位字串，如 "100"、"011"、"000"。
        outs: 出局數（0、1、2）。
        year: 年份，用於選擇矩陣版本。

    Returns:
        預期得分（浮點數）。

    Raises:
        KeyError: base_state 或 outs 不合法時。
    """
    matrix = get_re24(year)
    key = (base_state, outs)
    if key not in matrix:
        raise KeyError(
            f"無效的 base_state/outs 組合：{key}。"
            f"base_state 需為 3 位字串（'000'~'111'），outs 需為 0~2。"
        )
    return matrix[key]


def compute_leverage_index(
    base_state: str,
    outs: int,
    inning: int,
    score_diff: int,
) -> float:
    """計算 Leverage Index（壓力指數）。

    使用簡化公式，以 RE24 的 spread 為基礎，再乘以局數因子與分差因子。

    Args:
        base_state: 三位字串，如 "100"。
        outs: 出局數（0、1、2）。
        inning: 局數（1 開始，延長賽 > 9）。
        score_diff: 分差（進攻方分數 - 防守方分數，可為負）。

    Returns:
        Leverage Index（浮點數，1.0 為平均壓力）。
    """
    re = get_run_expectancy(base_state, outs)

    # 基礎 LI：當前情境的預期得分佔平均的比例
    base_li = re / _AVG_RE24 if _AVG_RE24 > 0 else 1.0

    # 局數因子
    inning_factor = _inning_factor(inning)

    # 分差因子
    close_game_factor = _close_game_factor(score_diff)

    return base_li * inning_factor * close_game_factor


def _inning_factor(inning: int) -> float:
    """局數因子：後段局數壓力較高。"""
    if inning > 9:
        return 1.5
    if inning >= 7:
        return 1.2
    return 1.0


def _close_game_factor(score_diff: int) -> float:
    """分差因子：比賽愈接近壓力愈高。"""
    abs_diff = abs(score_diff)
    if abs_diff <= 2:
        return 1.3
    if abs_diff <= 4:
        return 1.0
    return 0.5
