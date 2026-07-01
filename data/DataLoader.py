import pandas as pd


class DataLoader:
    def __init__(self, filepath):
        """存文件路径，不做任何读取"""
        self.filepath = filepath    # ← 加这行
    
    def load(self, in_sep='\t', in_encoding='gbk', in_skiprows=2):
        """
        核心方法：执行完整的 读取→清洗→映射 流程
        返回: 标准 DataFrame (列名: 日期, 开盘, 最高, 最低, 收盘, 成交量)
        """
        # 1. read_csv (gbk, tab, skiprows)
        df = pd.read_csv(
            self.filepath,
            sep=in_sep,          # 分隔符是什么？
            encoding=in_encoding,     # 中文券商软件导出 → gbk
            skiprows=in_skiprows,     # 跳过前几行标题
        )
        # 2. strip 列名
        df.columns = df.columns.str.strip()
        # 3. 只保留 6 列
        keep_cols = ["时间", "开盘", "最高", "最低", "收盘", "成交量"]
        df = df[keep_cols]
        # 4. strip 时间列 + 过滤非日期行
        df["时间"] = df["时间"].str.strip()
        df = df[df["时间"].str.match(r"^\d{4}/\d{2}/\d{2}")].copy()
        # 5. to_datetime
        df["时间"] = pd.to_datetime(df["时间"])
        # 6. sort + reset_index
        df = df.sort_values("时间", ascending=True).reset_index(drop=True)
        # 7. rename 时间→日期
        df = df.rename(columns={"时间": "日期"})
        return df