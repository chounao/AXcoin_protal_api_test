
from datetime import datetime, timedelta
import calendar
import urllib.parse
import common.logger
logger = common.logger.logger
class GetTime:
    def get_current_month_range(self):
        """
        获取当月的起始和结束时间，并转换为URL编码格式
        :return: (起始时间, 结束时间) URL编码格式
        """
        # 获取当前日期
        now = datetime.now()

        # 当月第一天零点零分零秒
        start_of_month = datetime(now.year, now.month, 1, 0, 0, 0)

        # 当月最后一天23点59分59秒
        last_day = calendar.monthrange(now.year, now.month)[1]
        end_of_month = datetime(now.year, now.month, last_day, 23, 59, 59)

        # 转换为指定格式
        start_str = start_of_month.strftime("%Y/%m/%d %H:%M")
        end_str = end_of_month.strftime("%Y/%m/%d %H:%M")

        # URL编码
        start_encoded = urllib.parse.quote(start_str).replace('%2F', '%2F')
        end_encoded = urllib.parse.quote(end_str).replace('%2F', '%2F')
        # print("起始时间：", start_encoded)
        # print("结束时间：", end_encoded)
        logger.info(f"当前月的时间范围: {start_encoded} - {end_encoded}")
        return start_encoded, end_encoded

    def get_now_time(self):
        """
        获取当前时间，并转换为URL编码格式
        :return: 当前时间 URL编码格式
        """
        now = datetime.now()
        now_str = now.strftime("%Y/%m/%d %H:%M")
        # logger.info(f"当前时间: {now_str}")
        now_encoded = urllib.parse.quote(now_str).replace('%2F', '%2F')
        # print("当前时间：", now_encoded)
        logger.info(f"当前时间: {now_encoded}")
        return now_encoded

    # 输入一个月份获取当前月份的时间范围并以url编码格式输出
    def get_month_range(self,date):
        """
        获取指定年月的起始和结束时间，并转换为URL编码格式
        :param year: 年份（如2025）
        :param month: 月份（1-12）
        :return: (起始时间, 结束时间) URL编码格式
        """

        year, month = int(date[:4]), int(date[4:])
        # 参数验证
        if not isinstance(year, int) or not isinstance(month, int):
            raise ValueError("年份和月份必须是整数")

        if month < 1 or month > 12:
            raise ValueError("月份必须在1-12之间")

        if year < 1900 or year > 2100:
            raise ValueError("年份必须在1900-2100之间")

        try:
            start_of_month = datetime(year, month, 1, 0, 0, 0)
            last_day = calendar.monthrange(year, month)[1]
            end_of_month = datetime(year, month, last_day, 23, 59, 59)
            print("起始时间：", start_of_month, " 结束时间：", end_of_month)


            #转成东八区时间

            start_str = (start_of_month - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            end_str = (end_of_month - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            start_encoded = start_str
            end_encoded = end_str


            #专程url编码格式
            # start_str = start_of_month.strftime("%Y/%m/%d %H:%M")
            # end_str = end_of_month.strftime("%Y/%m/%d %H:%M")
            # print("起始时间：", start_str, " 结束时间：", end_str)
            # start_encoded = urllib.parse.quote(start_str).replace('%2F', '%2F')
            # end_encoded = urllib.parse.quote(end_str).replace('%2F', '%2F')

            logger.info(f"指定年月的时间范围: {start_encoded} - {end_encoded}")
            return start_encoded, end_encoded
        except Exception as e:
            logger.error(f"获取月份时间范围失败: {e}")
            raise
    #输入一个人日期，获取当天开始时间和结束时间并以url编码返回
    def get_day_range(self,date):
        """
        获取指定日期的起始和结束时间，并转换为URL编码格式
        :param date: 日期（如20250901）
        :return: (起始时间, 结束时间) URL编码格式
        """
        year, month, day = int(date[:4]), int(date[4:6]), int(date[6:])
        # 参数验证
        if not isinstance(year, int) or not isinstance(month, int) or not isinstance(day, int):
            raise ValueError("日期必须是整数")

        if month < 1 or month > 12:
            raise ValueError("月份必须在1-12之间")

        if day < 1 or day > 31:
            raise ValueError("日期必须在1-31之间")

        try:
            start_of_day = datetime(year, month, day, 0, 0, 0)
            end_of_day = datetime(year, month, day, 23, 59, 59)
            print("起始时间：", start_of_day, " 结束时间：", end_of_day)

            #专东八区用的时间
            start_str =  (start_of_day - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            end_str = (end_of_day - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            start_encoded = start_str
            end_encoded = end_str
            # print("起始时间：", start_encoded, " 结束时间：",end_encoded)


            #转url编码格式
            # start_str = start_of_day.strftime("%Y/%m/%d %H:%M")
            # end_str = end_of_day.strftime("%Y/%m/%d %H:%M")
            # print("起始时间：", start_str, " 结束时间：", end_str)
            # start_encoded = urllib.parse.quote(start_str).replace('%2F', '%2F')
            # end_encoded = urllib.parse.quote(end_str).replace('%2F', '%2F')
            logger.info(f"指定日期的时间范围: {start_encoded} - {end_encoded}")
            return start_encoded, end_encoded
        except Exception as e:
            logger.error(f"获取日期时间范围失败: {e}")
            raise

    def get_time_range(self, date):
        """
        获取指定日期的起始和结束时间，并转换为URL编码格式
        :param date: 日期（如20250901）
        :return: (起始时间, 结束时间) URL编码格式
        """
        # 参数有效性检查
        if not date or not isinstance(date, str):
            raise ValueError(f"无效的日期格式: {date}。期望格式: YYYYMMDD 或 YYYYMM")

        # 验证日期格式 - 只能是8位数字(YYYYMMDD)或6位数字(YYYYMM)
        if len(date) == 8:
            # 验证是否全为数字
            if not date.isdigit():
                raise ValueError(f"无效的日期格式: {date}。期望格式: YYYYMMDD")
            start_encoded, end_encoded = self.get_day_range(date)
            return start_encoded, end_encoded
        elif len(date) == 6:
            # 验证是否全为数字
            if not date.isdigit():
                raise ValueError(f"无效的日期格式: {date}。期望格式: YYYYMM")
            start_encoded, end_encoded = self.get_month_range(date)
            return start_encoded, end_encoded
        else:
            raise ValueError(f"无效的日期长度: {date}。期望格式: YYYYMMDD(8位) 或 YYYYMM(6位)")



    def get_month_for_year(self, year):
        # 根据输入的年份返回该年份的月份列表返回的为2025-01这种
        if not isinstance(year, int) or year < 1 or year > 9999:
            raise ValueError("年份必须是1到9999之间的整数")

        month_list = [f"{year}{month:02d}" for month in range(1, 13)]
        logger.info(f"该年份的月份列表: {month_list}")
        return month_list





    def get_day_for_month(self, year, month):
        # 根据输入的年份和月份返回该月份的日期列表返回的为2025-01-01这种
        if not isinstance(year, int) or year < 1 or year > 9999:
            raise ValueError("年份必须是1到9999之间的整数")
        if not isinstance(month, int) or month < 1 or month > 12:
            raise ValueError("月份必须是1到12之间的整数")
        day_list = [f"{year}{month:02d}{day:02d}" for day in range(1, calendar.monthrange(year, month)[1] + 1)]

        logger.info(f"生成了{year}年{month}月的{len(day_list)}个日期")
        return day_list




if __name__ == '__main__':
    get_time = GetTime()
    get_time.get_time_range('20251222')
