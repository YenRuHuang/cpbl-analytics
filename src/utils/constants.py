"""CPBL constants — team codes, venues, base states."""

# 球隊代碼 → 中文名
TEAM_NAMES: dict[str, str] = {
    "ADD": "味全龍",
    "AAA": "中信兄弟",
    "AJL": "樂天桃猿",
    "ACN": "統一7-ELEVEn獅",
    "AEO": "富邦悍將",
    "AKP": "台鋼雄鷹",
}

# 中文名 → 代碼（反向查詢）
TEAM_CODES: dict[str, str] = {v: k for k, v in TEAM_NAMES.items()}

# 球場
VENUES: dict[str, str] = {
    "洲際": "台中洲際棒球場",
    "桃園": "桃園國際棒球場",
    "台南": "台南市立棒球場",
    "新莊": "新莊棒球場",
    "大巨蛋": "台北大巨蛋",
    "亞太": "屏東亞太棒球訓練中心",
    "澄清湖": "高雄澄清湖棒球場",
}

# 24 base-out states for RE24
BASE_STATES = [
    "000", "100", "010", "001",
    "110", "101", "011", "111",
]

# Leverage Index 分類
LI_LOW = 0.5
LI_MEDIUM = 1.0
LI_HIGH = 1.5
LI_VERY_HIGH = 2.5

# 球數分類
COUNT_AHEAD = {"1-0", "2-0", "2-1", "3-0", "3-1"}     # 打者有利
COUNT_BEHIND = {"0-1", "0-2", "1-2"}                     # 投手有利
COUNT_EVEN = {"0-0", "1-1", "2-2", "3-2"}               # 平均
COUNT_TWO_STRIKE = {"0-2", "1-2", "2-2", "3-2"}         # 兩好球
