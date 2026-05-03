"""DocumentFormatter - 数字工具（中文数字转换）Mixin"""
from __future__ import annotations


class NumberUtilsMixin:
    """数字工具（中文数字转换）"""

    CHINESE_NUMS = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
        '十': 10, '百': 100, '千': 1000, '万': 10000
    }

    NUM_TO_CHINESE = {
        1: '一', 2: '二', 3: '三', 4: '四', 5: '五',
        6: '六', 7: '七', 8: '八', 9: '九', 10: '十',
        11: '十一', 12: '十二', 13: '十三', 14: '十四', 15: '十五',
        16: '十六', 17: '十七', 18: '十八', 19: '十九', 20: '二十',
        21: '二十一', 22: '二十二', 23: '二十三', 24: '二十四', 25: '二十五',
        26: '二十六', 27: '二十七', 28: '二十八', 29: '二十九', 30: '三十',
        31: '三十一', 32: '三十二', 33: '三十三', 34: '三十四', 35: '三十五',
        36: '三十六', 37: '三十七', 38: '三十八', 39: '三十九', 40: '四十',
        41: '四十一', 42: '四十二', 43: '四十三', 44: '四十四', 45: '四十五',
        46: '四十六', 47: '四十七', 48: '四十八', 49: '四十九', 50: '五十',
        51: '五十一', 52: '五十二', 53: '五十三', 54: '五十四', 55: '五十五',
        56: '五十六', 57: '五十七', 58: '五十八', 59: '五十九', 60: '六十',
        61: '六十一', 62: '六十二', 63: '六十三', 64: '六十四', 65: '六十五',
        66: '六十六', 67: '六十七', 68: '六十八', 69: '六十九', 70: '七十',
        71: '七十一', 72: '七十二', 73: '七十三', 74: '七十四', 75: '七十五',
        76: '七十六', 77: '七十七', 78: '七十八', 79: '七十九', 80: '八十',
        81: '八十一', 82: '八十二', 83: '八十三', 84: '八十四', 85: '八十五',
        86: '八十六', 87: '八十七', 88: '八十八', 89: '八十九', 90: '九十',
        91: '九十一', 92: '九十二', 93: '九十三', 94: '九十四', 95: '九十五',
        96: '九十六', 97: '九十七', 98: '九十八', 99: '九十九', 100: '一百',
    }

    def _get_unit_name(self) -> str:
        """获取内容类型对应的单位名称"""
        if self.content_type == "novel":
            return "章"
        elif self.content_type == "series_script":
            return "集"
        elif self.content_type == "movie_script":
            return "场"
        return "章"


    def _number_to_chinese(self, num: int) -> str:
        """将数字转换为中文"""
        if num in self.NUM_TO_CHINESE:
            return self.NUM_TO_CHINESE[num]

        # 对于大于100的数字，动态生成
        if num <= 0:
            return "零"

        result = ""
        if num >= 10000:
            result += self.NUM_TO_CHINESE.get(num //
                                              10000, str(num // 10000)) + "万"
            num %= 10000
        if num >= 1000:
            result += self.NUM_TO_CHINESE.get(num //
                                              1000, str(num // 1000)) + "千"
            num %= 1000
        if num >= 100:
            result += self.NUM_TO_CHINESE.get(num //
                                              100, str(num // 100)) + "百"
            num %= 100
        if num >= 10:
            if num >= 20:
                result += self.NUM_TO_CHINESE.get(num // 10, str(num // 10))
            result += "十"
            num %= 10
        if num > 0:
            result += self.NUM_TO_CHINESE.get(num, str(num))

        return result


    def _chinese_to_number(self, chinese_str: str) -> int:
        """将中文数字转换为阿拉伯数字"""
        if not chinese_str:
            return 0

        if chinese_str.isdigit():
            return int(chinese_str)

        if len(chinese_str) == 1 and chinese_str in self.CHINESE_NUMS:
            return self.CHINESE_NUMS[chinese_str]

        result = 0
        temp = 0

        for char in chinese_str:
            if char in self.CHINESE_NUMS:
                num = self.CHINESE_NUMS[char]
                if num >= 10:
                    if temp == 0:
                        temp = 1
                    result += temp * num
                    temp = 0
                else:
                    temp = num

        result += temp
        return result if result > 0 else 0


