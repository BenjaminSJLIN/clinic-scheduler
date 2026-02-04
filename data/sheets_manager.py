"""
Google Sheets 資料管理
"""
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import List, Dict, Optional
from datetime import datetime, date
from data.models import Employee, ShiftRequirement, TimeOffRequest, PreAssignedShift, Schedule, Shift


class SheetsManager:
    """Google Sheets 資料管理器"""
    
    # 工作表名稱對應（支援中英文）
    SHEET_NAMES = {
        'config': ['設定檔', 'Configuration'],
        'employees': ['員工名單', 'Employee Roster'],
        'admin': ['管理員', 'Admin'],
        'timeoff': ['請假', 'Time Off Requests'],
        'preassigned': ['已排班', 'Pre-Assigned Shifts'],
        'schedules': ['排班表', 'Schedules']
    }
    
    def __init__(self, credentials_path: str = None, spreadsheet_id: str = None, credentials_dict: dict = None):
        """
        初始化 Google Sheets 連線
        
        Args:
            credentials_path: 服務帳戶憑證檔案路徑 (本地開發使用)
            spreadsheet_id: Google 試算表 ID
            credentials_dict: 憑證字典 (線上部署使用,從 Streamlit Secrets 讀取)
        """
        self.credentials_path = credentials_path
        self.credentials_dict = credentials_dict
        self.spreadsheet_id = spreadsheet_id
        self.client = None
        self.spreadsheet = None
        self._sheet_name_cache = {}  # 快取實際的工作表名稱
        
    def connect(self) -> bool:
        """建立連線"""
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # 優先使用憑證字典(從 Streamlit Secrets),否則使用憑證檔案
            if self.credentials_dict:
                # 從字典建立憑證 (Streamlit Secrets)
                creds = ServiceAccountCredentials.from_json_keyfile_dict(
                    self.credentials_dict, scope
                )
            elif self.credentials_path:
                # 從檔案建立憑證 (本地開發)
                creds = ServiceAccountCredentials.from_json_keyfile_name(
                    self.credentials_path, scope
                )
            else:
                raise Exception("必須提供 credentials_dict 或 credentials_path")
            
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            return True
        except Exception as e:
            print(f"連線失敗: {e}")
            return False
    
    def get_worksheet(self, sheet_key: str):
        """
        取得工作表（支援中英文名稱）
        
        Args:
            sheet_key: 工作表類型 ('config', 'employees', 'admin', 'timeoff', 'preassigned')
            
        Returns:
            工作表物件，找不到則拋出例外
        """
        # 檢查快取
        if sheet_key in self._sheet_name_cache:
            return self.spreadsheet.worksheet(self._sheet_name_cache[sheet_key])
        
        # 嘗試所有可能的名稱
        possible_names = self.SHEET_NAMES.get(sheet_key, [])
        for name in possible_names:
            try:
                sheet = self.spreadsheet.worksheet(name)
                # 找到了，加入快取
                self._sheet_name_cache[sheet_key] = name
                return sheet
            except:
                continue
        
        # 都找不到，顯示錯誤
        raise Exception(f"找不到工作表，嘗試過的名稱: {', '.join(possible_names)}")
    
    def get_config(self) -> List[ShiftRequirement]:
        """讀取班次設定"""
        try:
            sheet = self.get_worksheet('config')
            records = sheet.get_all_records()
            
            requirements = []
            for record in records:
                req = ShiftRequirement(
                    day_of_week=int(record['星期']),
                    shift_time=record['班次'],
                    num_people=int(record['人數']),
                    num_leaders=int(record['Leader數']),
                    num_injectors=int(record['打針數']),
                    num_leader_or_injector=int(record['Leader或打針數'])
                )
                requirements.append(req)
            
            return requirements
        except Exception as e:
            # 顯示可用的工作表名稱以幫助診斷
            try:
                worksheets = self.spreadsheet.worksheets()
                available = [ws.title for ws in worksheets]
                print(f"讀取設定檔失敗: {e}")
                print(f"可用的工作表: {', '.join(available)}")
                print(f"請確認工作表名稱為「設定檔」（注意：全形字元）")
            except:
                print(f"讀取設定檔失敗: {e}")
            return []
    
    def update_config(self, requirements: List[ShiftRequirement]) -> bool:
        """更新班次設定（管理員功能）"""
        try:
            sheet = self.get_worksheet('config')
            
            # 準備資料
            data = [['星期', '班次', '人數', 'Leader數', '打針數', 'Leader或打針數']]
            for req in requirements:
                data.append([
                    req.day_of_week,
                    req.shift_time,
                    req.num_people,
                    req.num_leaders,
                    req.num_injectors,
                    req.num_leader_or_injector
                ])
            
            # 清空並寫入
            sheet.clear()
            sheet.update('A1', data)
            return True
        except Exception as e:
            print(f"更新設定檔失敗: {e}")
            return False
    
    def get_employees(self) -> List[Employee]:
        """讀取員工名單"""
        try:
            sheet = self.get_worksheet('employees')
            records = sheet.get_all_records()
            
            employees = []
            for record in records:
                # 解析可上班時間
                # 格式：「1:早,中,晚;2:早,中;5:早,晚」或舊格式「早,中,晚」
                availability_str = str(record['可上班時間']).strip()
                available_shifts = {}
                
                if ':' in availability_str:
                    # 新格式：有指定星期幾
                    # 例如：「1:早,中,晚;2:早,中;5:早,晚」
                    day_entries = availability_str.split(';')
                    for entry in day_entries:
                        if ':' not in entry:
                            continue
                        day_str, shifts_str = entry.split(':', 1)
                        try:
                            day_num = int(day_str.strip())
                            shifts = [s.strip() for s in shifts_str.split(',')]
                            available_shifts[day_num] = shifts
                        except ValueError:
                            continue
                else:
                    # 舊格式：沒有指定星期幾，全週都可
                    # 例如：「早,中,晚」
                    shifts = [s.strip() for s in availability_str.split(',')]
                    # 套用到所有星期
                    for day in range(1, 8):
                        available_shifts[day] = shifts
                
                emp = Employee(
                    name=record['姓名'],
                    is_leader=str(record['Leader']).upper() == 'TRUE',
                    can_inject=str(record['打針']).upper() == 'TRUE',
                    available_shifts=available_shifts,
                    is_fulltime=str(record['正職']).upper() == 'TRUE'
                )
                employees.append(emp)
            
            return employees
        except Exception as e:
            # 顯示可用的工作表名稱以幫助診斷
            try:
                worksheets = self.spreadsheet.worksheets()
                available = [ws.title for ws in worksheets]
                print(f"讀取員工名單失敗: {e}")
                print(f"可用的工作表: {', '.join(available)}")
                print(f"請確認工作表名稱為「員工名單」（注意：全形字元）")
            except:
                print(f"讀取員工名單失敗: {e}")
            return []
    
    def update_employees(self, employees: List[Employee]) -> bool:
        """更新員工名單（管理員功能）"""
        try:
            sheet = self.get_worksheet('employees')
            
            # 準備資料
            data = [['姓名', 'Leader', '打針', '可上班時間', '正職']]
            for emp in employees:
                # 格式化可上班時間
                # 如果所有星期都一樣，用簡化格式；否則用完整格式
                if emp.available_shifts:
                    # 檢查是否所有星期都相同
                    all_days = list(emp.available_shifts.values())
                    if all_days and all(day_shifts == all_days[0] for day_shifts in all_days):
                        # 簡化格式
                        availability_str = ','.join(all_days[0])
                    else:
                        # 完整格式
                        parts = []
                        for day in sorted(emp.available_shifts.keys()):
                            shifts = emp.available_shifts[day]
                            if shifts:
                                parts.append(f"{day}:{','.join(shifts)}")
                        availability_str = ';'.join(parts)
                else:
                    availability_str = ""
                
                data.append([
                    emp.name,
                    emp.is_leader,
                    emp.can_inject,
                    availability_str,
                    emp.is_fulltime
                ])
            
            # 清空並寫入
            sheet.clear()
            sheet.update('A1', data)
            return True
        except Exception as e:
            print(f"更新員工名單失敗: {e}")
            return False
    
    def get_admin_credentials(self) -> Dict[str, str]:
        """讀取管理員帳密"""
        try:
            sheet = self.get_worksheet('admin')
            records = sheet.get_all_records()
            
            credentials = {}
            for record in records:
                # 確保帳號密碼都是字串比對
                username = str(record['帳號']).strip()
                password = str(record['密碼']).strip()
                credentials[username] = password
            
            return credentials
        except Exception as e:
            # 顯示可用的工作表名稱以幫助診斷
            try:
                worksheets = self.spreadsheet.worksheets()
                available = [ws.title for ws in worksheets]
                print(f"讀取管理員帳密失敗: {e}")
                print(f"可用的工作表: {', '.join(available)}")
                print(f"請確認工作表名稱為「管理員」（注意：全形字元）")
            except:
                print(f"讀取管理員帳密失敗: {e}")
            return {}
    
    def get_time_off_requests(self) -> List[TimeOffRequest]:
        """讀取請假申請"""
        try:
            sheet = self.get_worksheet('timeoff')
            records = sheet.get_all_records()
            
            requests = []
            for record in records:
                if not record.get('員工') or not record.get('日期'):
                    continue
                    
                # 解析日期
                date_str = str(record['日期'])
                try:
                    request_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except:
                    continue
                
                req = TimeOffRequest(
                    employee_name=record['員工'],
                    date=request_date,
                    shift_time=record['班次']
                )
                requests.append(req)
            
            return requests
        except Exception as e:
            print(f"讀取請假申請失敗: {e}")
            return []
    
    def add_time_off_request(self, request: TimeOffRequest) -> bool:
        """新增請假申請"""
        try:
            sheet = self.get_worksheet('timeoff')
            
            # 新增一列
            row = [
                request.employee_name,
                request.date.strftime('%Y-%m-%d'),
                request.shift_time
            ]
            sheet.append_row(row)
            return True
        except Exception as e:
            print(f"新增請假申請失敗: {e}")
            return False
    
    def remove_time_off_request(self, employee_name: str, request_date: str, shift_time: str) -> bool:
        """移除請假申請"""
        try:
            sheet = self.get_worksheet('timeoff')
            records = sheet.get_all_values()
            
            # 找到要刪除的列（跳過標題）
            for i, row in enumerate(records[1:], start=2):
                if (row[0] == employee_name and 
                    row[1] == request_date and 
                    row[2] == shift_time):
                    sheet.delete_rows(i)
                    return True
            
            return False
        except Exception as e:
            print(f"移除請假申請失敗: {e}")
            return False
    
    def get_pre_assigned_shifts(self) -> List[PreAssignedShift]:
        """讀取預先排班"""
        try:
            sheet = self.get_worksheet('preassigned')
            records = sheet.get_all_records()
            
            pre_assigned = []
            for record in records:
                if not record.get('員工') or not record.get('日期'):
                    continue
                    
                # 解析日期
                date_str = str(record['日期'])
                try:
                    shift_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except:
                    continue
                
                pre = PreAssignedShift(
                    employee_name=record['員工'],
                    date=shift_date,
                    shift_time=record['班次']
                )
                pre_assigned.append(pre)
            
            return pre_assigned
        except Exception as e:
            print(f"讀取預先排班失敗: {e}")
            return []
    
    def add_pre_assigned_shift(self, pre_assigned: PreAssignedShift) -> bool:
        """新增預先排班"""
        try:
            sheet = self.get_worksheet('preassigned')
            
            # 新增一列
            row = [
                pre_assigned.employee_name,
                pre_assigned.date.strftime('%Y-%m-%d'),
                pre_assigned.shift_time
            ]
            sheet.append_row(row)
            return True
        except Exception as e:
            print(f"新增預先排班失敗: {e}")
            return False
    
    def remove_pre_assigned_shift(self, employee_name: str, shift_date: str, shift_time: str) -> bool:
        """移除預先排班"""
        try:
            sheet = self.get_worksheet('preassigned')
            records = sheet.get_all_values()
            
            # 找到要刪除的列（跳過標題）
            for i, row in enumerate(records[1:], start=2):
                if (row[0] == employee_name and 
                    row[1] == shift_date and 
                    row[2] == shift_time):
                    sheet.delete_rows(i)
                    return True
            
            return False
        except Exception as e:
            print(f"移除預先排班失敗: {e}")
            return False
    
    def save_schedule(self, schedule: Schedule, start_date: date) -> bool:
        """
        儲存排班表到 Google Sheets
        
        Args:
            schedule: 排班表物件
            start_date: 排班開始日期（週一）
        
        Returns:
            成功回傳 True，失敗回傳 False
        """
        try:
            # 取得或建立「排班表」工作表
            try:
                sheet = self.get_worksheet('schedules')
            except:
                # 如果工作表不存在，建立一個新的
                sheet = self.spreadsheet.add_worksheet(title='排班表', rows=1000, cols=20)
                # 加入標題列
                headers = ['排班名稱', '儲存時間', '日期', '星期', '班次', '員工1', '員工2', '員工3', '員工4', '員工5']
                sheet.update('A1', [headers])
            
            # 準備資料
            schedule_name = start_date.strftime('%Y-%m-%d')  # 使用日期作為名稱
            saved_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            data_rows = []
            for shift in schedule.shifts:
                # 計算星期幾（1=週一, 7=週日）
                day_of_week = shift.date.weekday() + 1
                weekday_names = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
                weekday_str = weekday_names[day_of_week - 1]
                
                # 員工名單
                employee_names = [emp.name for emp in shift.assigned_employees]
                
                # 建立一列資料
                row = [
                    schedule_name,
                    saved_at,
                    shift.date.strftime('%Y-%m-%d'),
                    weekday_str,
                    shift.shift_time
                ]
                # 加入員工名單（最多 5 個欄位，不足的留空）
                row.extend(employee_names[:5])
                while len(row) < 10:  # 確保有 10 個欄位
                    row.append('')
                
                data_rows.append(row)
            
            # 附加資料到工作表
            if data_rows:
                sheet.append_rows(data_rows)
            
            return True
        except Exception as e:
            print(f"儲存排班表失敗: {e}")
            return False
    
    def get_saved_schedule_list(self) -> List[Dict]:
        """
        取得所有已儲存的排班列表
        
        Returns:
            排班列表，格式: [{'name': '2026-02-03', 'start_date': '2026-02-03', 'saved_at': '2026-02-03 12:00:00'}]
        """
        try:
            sheet = self.get_worksheet('schedules')
            records = sheet.get_all_values()
            
            if len(records) <= 1:  # 只有標題列或空的
                return []
            
            # 提取唯一的排班（根據排班名稱和儲存時間）
            schedules = {}
            for row in records[1:]:
                if len(row) >= 2 and row[0] and row[1]:
                    name = row[0]
                    saved_at = row[1]
                    start_date = row[2] if len(row) > 2 else name
                    
                    key = f"{name}_{saved_at}"
                    if key not in schedules:
                        schedules[key] = {
                            'name': name,
                            'start_date': start_date,
                            'saved_at': saved_at
                        }
            
            # 轉換為列表並按儲存時間排序（最新的在前）
            schedule_list = list(schedules.values())
            schedule_list.sort(key=lambda x: x['saved_at'], reverse=True)
            
            return schedule_list
        except Exception as e:
            print(f"讀取排班列表失敗: {e}")
            return []
    
    def load_schedule(self, schedule_name: str, saved_at: str) -> Optional[Schedule]:
        """
        從 Google Sheets 載入指定的排班表
        
        Args:
            schedule_name: 排班名稱（開始日期，例如 '2026-02-03'）
            saved_at: 儲存時間
        
        Returns:
            Schedule 物件，失敗則回傳 None
        """
        try:
            sheet = self.get_worksheet('schedules')
            records = sheet.get_all_values()
            
            if len(records) <= 1:
                return None
            
            # 先載入員工資料（用於建立 Employee 物件）
            employees = self.get_employees()
            employee_dict = {emp.name: emp for emp in employees}
            
            # 篩選出符合的排班資料
            shifts = []
            for row in records[1:]:
                if len(row) >= 5 and row[0] == schedule_name and row[1] == saved_at:
                    # 解析日期
                    try:
                        shift_date = datetime.strptime(row[2], '%Y-%m-%d').date()
                    except:
                        continue
                    
                    shift_time = row[4]
                    
                    # 解析員工名單（從第 6 欄開始）
                    assigned_employees = []
                    for i in range(5, len(row)):
                        if row[i] and row[i] in employee_dict:
                            assigned_employees.append(employee_dict[row[i]])
                    
                    # 建立 Shift 物件
                    shift = Shift(
                        date=shift_date,
                        shift_time=shift_time,
                        assigned_employees=assigned_employees
                    )
                    shifts.append(shift)
            
            if not shifts:
                return None
            
            # 建立 Schedule 物件
            schedule = Schedule(shifts=shifts)
            return schedule
        except Exception as e:
            print(f"載入排班表失敗: {e}")
            return None
    
    def delete_schedule(self, schedule_name: str, saved_at: str) -> bool:
        """
        刪除指定的排班表
        
        Args:
            schedule_name: 排班名稱（開始日期，例如 '2026-02-03'）
            saved_at: 儲存時間
        
        Returns:
            成功回傳 True，失敗回傳 False
        """
        try:
            sheet = self.get_worksheet('schedules')
            all_values = sheet.get_all_values()
            
            if len(all_values) <= 1:  # 只有標題列或空的
                return False
            
            # 找出要刪除的列（由下往上刪除以避免索引問題）
            rows_to_delete = []
            for i, row in enumerate(all_values[1:], start=2):  # 從第 2 列開始（跳過標題）
                if len(row) >= 2 and row[0] == schedule_name and row[1] == saved_at:
                    rows_to_delete.append(i)
            
            # 由下往上刪除，避免索引變動問題
            rows_to_delete.sort(reverse=True)
            for row_index in rows_to_delete:
                sheet.delete_rows(row_index)
            
            return len(rows_to_delete) > 0
        except Exception as e:
            print(f"刪除排班表失敗: {e}")
            return False
